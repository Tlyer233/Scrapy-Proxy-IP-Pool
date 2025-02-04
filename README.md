# Scrapy Proxy IP Pool

> 这是一个Scrapy中间件，用于管理代理IP池。

* 🥳支持Redis:支持使用Redis的IP代理池(也可本地List作为代理池)
* 🥵最大限度榨干每个IP: 只有请求为指定异常or状态码(被封)时才会更换IP
* 🤌简单配置: ez三步即可使用

> 如果你不知道如何写"代理IP池"可以花几分钟看下(<10min)然后可以自己写,当然也可以用我写的现成代理池

## 安装

使用以下命令安装：

```bash
pip install scrapy_proxy_ip_pool
```

## 基本使用

### STEP1:在`setting.py`中添加该中间件

* 要求❗: 这里的权值一定要大于`RetryMiddleware`(重试中间件默认550)

```python
PROXY_POOL_SIZE = 1  # 代理池的大小(有封ip的网站建议开大一点)
DOWNLOADER_MIDDLEWARES = {
    'scrapy_proxy_ip_pool.proxy_pool_downloader_middleware.ProxyPoolDownloaderMiddleware': 551,
}
```

### STEP2:在你的spider中必须要编写`def get_proxy_ip(self):->str`方法

* 要求❗:名字只能是这个,返回值是一个代理IP.
* 说明: 代理池中间件会读取这个方法,从而获取代理IP地址.

```python
import requests
import scrapy


class IpSpider(scrapy.Spider):
    name = "ip"
    REDIS_KEY = name

    def parse(self, response, **kwargs):
        pass

    # 示例
    def get_proxy_ip(self):
        api_url = "你请求付费代理的地址"
        proxy_ip = requests.get(api_url).text
        username = "你的代理用户名"
        password = "你的代理密码"
        return f"http://{username}:{password}@{proxy_ip}/"  # 一次只需要返回一个ip
```

## 其他配置

### 一. 使用Redis作为 代理池

* `settings.py`中配置如下内容:

```python
PROXY_POOL_ENABLED = 'True'  # 使用Redis进行代理池的构建(默认为False)
REDIS_URL = "redis://127.0.0.1:6379/0"
```

* `spider`中添加`REDIS_KEY`变量指明存储在Redis中使用的键

```python
import scrapy


class IpSpider(scrapy.Spider):
    name = "ip"
    REDIS_KEY = name  # 最终为 REDIS_KEY+":proxy_pool"
    ...
```

### 二. 指定异常和状态码

* `settings.py`中配置如下内容
* 说明: 如果遇到了这些异常, 就会更新IP; 如下默认配置的是常见可能被封异常和状态码
* 注意❗:这里依据网址而定, 如果不确定, 两个可以设置为空列表,后续根据报错改

```python
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
```

## 关键代码

#### 一. 更新IP

* ⏱什么时候会被调用:只有出现 `NEED_UPDATE_PROXY_EXCEPTIONS` 或 `NEED_UPDATE_PROXY_CODES` 中的异常或状态码,该方法才会被调用

```python
# 伪代码
def update_proxy(self, request: Request) -> Request:
    last_ip = 本次(有问题)
    请求的代理ip
    if last_ip in 代理池:
        在代理池中更换该(有问题)
        的ip
    request.meta['proxy'] = 新ip
    return request
```

```python
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
```

## Version

* `1.0.1`:【2025年2月4日】
  1. 修改`1.0.0`中的Bug(①修改包名,②完善README.md文档)
  2. 推送项目到Pypi,用户可以使用pip进行下载
  3. 首次推送项目到[Gitee](https://gitee.com/twilight-and-morning-mist/scrapy-proxy-ip-pool): 
***
* `1.0.0`:【2025年2月3日】
  1. 首次推送至[GitHub](https://github.com/Tlyer233/Scrapy-Proxy-IP-Pool),能够实现代理池功能