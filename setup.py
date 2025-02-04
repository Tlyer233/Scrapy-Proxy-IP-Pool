from setuptools import setup, find_packages

setup(
    name='scrapy_proxy_ip_pool',
    version='1.0.0',
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        'Twisted>=20.3.0',
        'zope.interface>=5',
        'scrapy>=2.12.0',
        'redis>=5.2.1',
        'loguru>=0.7.2'
    ],
    setup_requires=["setuptools>=42", "wheel"],
    author='明廷盛',
    author_email='1594365335@qq.com',
    description='这是一个Scrapy中间件，用于管理代理IP池(支持使用Redis作为代理池)。',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/Tlyer233/Scrapy-Proxy-IP-Pool',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Framework :: Scrapy',
    ],
    entry_points={
        'scrapy.middleware': [
            'proxy_pool = scrapy_proxy_ip_pool.proxy_pool_downloader_middleware.ProxyPoolDownloaderMiddleware',
        ],
    },
)
