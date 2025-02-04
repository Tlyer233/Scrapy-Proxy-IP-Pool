import redis
import random

from scrapy import signals
from scrapy.http import Request, Response
from loguru import logger
from scrapy.crawler import Crawler
from scrapy.settings import BaseSettings

from scrapy.utils.misc import load_object

# 如下列举了常见的被封禁ip(或ip不可用)时的异常或状态码, 用户可以根据目标网站的情况在settings.py中自行配置
NEED_UPDATE_PROXY_EXCEPTIONS = [
    'twisted.internet.defer.TimeoutError',  # 请求超时未响应，可能目标服务器检测到代理IP异常导致故意延迟不响应
    'twisted.internet.error.TimeoutError',  # 底层网络连接超时，可能代理服务器IP被目标网站封锁导致无法建立连接
    'twisted.internet.error.ConnectError',  # 与代理服务器建立连接失败，可能代理IP已被防火墙封禁或服务器已下线
    'scrapy.core.downloader.handlers.http11.TunnelError',  # 代理服务器要求身份验证或目标网站封禁该代理IP，导致无法建立HTTPS隧道连接
]

NEED_UPDATE_PROXY_CODES = [
    503,  # 服务不可用，服务器可能正在主动拒绝来自该代理IP的请求（反爬机制触发）
    407,  # 代理身份验证失败，或代理服务提供商已封禁当前IP的访问权限
    403,  # 服务器明确拒绝访问，通常表示当前代理IP已被加入黑名单
    429,  # 请求频率超限，目标网站针对该代理IP实施了速率限制
]


class ProxyPoolDownloaderMiddleware:
    def __init__(self, settings: BaseSettings, spider):
        # 该中间件的权值必须大于RetryMiddleware中间件
        proxy_pool_middleware_path = f"{self.__module__}.{self.__class__.__name__}"
        retry_middleware_path = "scrapy.downloadermiddlewares.retry.RetryMiddleware"
        priority_retry = settings.getint(f"DOWNLOADER_MIDDLEWARES.{proxy_pool_middleware_path}", None)
        priority_cur = settings.getint(f"DOWNLOADER_MIDDLEWARES.{retry_middleware_path}", None)
        if priority_retry is not None and priority_cur is not None and priority_cur <= priority_retry:
            raise ValueError(f"IP代理池中间件 {proxy_pool_middleware_path} 的权值 ({priority_cur}) 必须大于 RetryMiddleware ({retry_middleware_path}) 的权值 ({priority_retry})")
        # 必须重写"获取代理IP"的方法
        if not hasattr(spider, "get_proxy_ip"):
            raise NotImplementedError("spider中必须实现'get_proxy_ip' ")
        # 池的基本参数
        self.proxy_pool_size = settings.getint("PROXY_POOL_SIZE", 1)
        self.proxy_pool = list()
        self.spider = spider
        # Redis相关配置
        self.proxy_pool_enabled = settings.getbool("PROXY_POOL_ENABLED", False)  # 是否使用redis作为连接池
        if self.proxy_pool_enabled:
            self.redis_url = settings.get("REDIS_URL", "redis://127.0.0.1:6379/0")  # redis的连接地址
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            self.redis_key = spider.REDIS_KEY + ":proxy_pool"  # 获取redis_key
            self.clear_pool_on_start = settings.getbool("CLEAR_POOL_ON_START", True)  # 是在开始时清空ip池
        # 遇到哪些'异常'或'状态码'需要换ip
        self.need_update_proxy_exceptions = tuple(load_object(x) for x in settings.getlist("NEED_UPDATE_PROXY_EXCEPTIONS", NEED_UPDATE_PROXY_EXCEPTIONS))
        self.need_update_proxy_codes = settings.getlist("NEED_UPDATE_PROXY_CODES", NEED_UPDATE_PROXY_CODES)
        # 日志
        self.ip_used_count = 0

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        s = cls(crawler.settings, crawler.spider)
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(s.spider_closed, signal=signals.spider_closed)
        return s

    def process_request(self, request: Request, spider):
        request.meta['proxy'] = self.get_proxy_from_pool()  # 使用当前代理IP
        logger.info(f"请求URL{request.url}使用代理IP为:{request.meta['proxy']}")
        return None

    def process_response(self, request: Request, response: Response, spider):
        if response.status in self.need_update_proxy_codes:
            logger.debug(f"已更新代理, 异常状态码为:{response.status}")
            return self.update_proxy(request)
        return response

    def process_exception(self, request, exception, spider):
        if isinstance(exception, self.need_update_proxy_exceptions):
            logger.debug(f"已更新代理, 异常为type:{type(exception)}: {exception}")
            return self.update_proxy(request)
        return None

    def update_proxy(self, request: Request) -> Request:
        """
        使用"乐观锁"思想,更新过时IP,并返回携带新IP的request
        :param request: 未成功的网络请求
        :return: 返回携带新IP的request
        """
        # 解决request.meta['proxy']鉴权丢失问题
        last_proxy = request.meta['proxy'].split("//")[1]
        temp_proxy_list = self.client.smembers(self.redis_key) if self.proxy_pool_enabled else self.proxy_pool
        need_update = any(last_proxy in ip for ip in temp_proxy_list)  # 存在=>需要替换
        # 当前需要获取新的ip
        if need_update:
            # 替换"代理池"中的IP
            if self.proxy_pool_enabled:  # Redis
                self.client.srem(self.redis_key, last_proxy)
                self.client.sadd(self.redis_key, self.get_proxy_with_logging())
            else:  # 本地
                self.proxy_pool.remove(last_proxy)
                self.proxy_pool.append(self.get_proxy_with_logging())
        # 更换代理IP进行请求
        request.meta['proxy'] = self.get_proxy_from_pool()
        request.dont_filter = True  # 防止被过滤!!!
        return request

    def get_proxy_from_pool(self) -> str:
        """从代理池中获取一个代理ip"""
        if self.proxy_pool_enabled is True:
            return self.client.srandmember(self.redis_key, 1)[0]
        else:
            return random.choice(self.proxy_pool)

    def spider_opened(self):
        if self.proxy_pool_enabled:
            # 删除之前的键
            if self.clear_pool_on_start and self.client.exists(self.redis_key):
                self.client.delete(self.redis_key)
                logger.debug(f"{self.redis_key}已删除")
            # 初始化ip池
            for _ in range(self.proxy_pool_size):
                self.client.sadd(self.redis_key, self.get_proxy_with_logging())
        else:
            self.proxy_pool = [self.get_proxy_with_logging() for _ in range(self.proxy_pool_size)]

    def spider_closed(self):
        if self.proxy_pool_enabled:
            self.client.close()
        logger.info(f"本次程序运行共消耗{self.ip_used_count}个ip")

    def get_proxy_with_logging(self):
        """调用spider中的get_proxy_ip方法，并记录IP使用计数"""
        proxy_ip = self.spider.get_proxy_ip()  # 调用spider中的方法
        self.ip_used_count += 1
        logger.info(f"当前获取第{self.ip_used_count}个代理IP:{proxy_ip}")
        return proxy_ip
