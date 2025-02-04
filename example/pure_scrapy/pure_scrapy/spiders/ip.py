import requests
import scrapy
from scrapy import Request, cmdline
from scrapy.http import HtmlResponse


class IpSpider(scrapy.Spider):
    name = "ip"
    allowed_domains = ["httpbin.org"]
    start_urls = ["https://httpbin.org/ip"]
    REDIS_KEY = name  # 指明Redis作为 IP代理池 的键

    def start_requests(self):
        yield scrapy.Request("https://httpbin.org/ip", callback=self.parse, dont_filter=True)

    def parse(self, response: HtmlResponse, **kwargs):
        print(response.json()['origin'])

    def get_proxy_ip(self):
        api_url = "https://dps.kdlapi.com/api/getdps/?secret_id=o5b3w54kddfiskjsu5ta&signature=tr45ga5grnvp1943h0paert5qwquy7cb&num=1&pt=1&sep=1"
        proxy_ip = requests.get(api_url).text
        username = "d4472377283"
        password = "rudm2ozb"
        return f"http://{username}:{password}@{proxy_ip}/"


if __name__ == '__main__':
    cmdline.execute("scrapy crawl ip".split())
