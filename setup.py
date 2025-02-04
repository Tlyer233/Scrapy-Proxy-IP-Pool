from setuptools import setup, find_packages

setup(
    name='scrapy_proxy_ip_pool',
    version='0.1.0',
    packages=find_packages("src"),
    package_dir={"": "src"},
    install_requires=[
        'scrapy>=2.8.0',
        'redis>=4.0.0',
        'loguru>=0.6.0',
    ],
    author='明廷盛',
    author_email='1594365335@qq.com',
    description='A Scrapy middleware for managing a pool of proxy IPs.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='你的项目网址',  # 如果有的话
    classifiers=[
        'Programming Language :: Python :: 3',
        'Framework :: Scrapy',
    ],
    entry_points={
        'scrapy.middleware': [
            'proxy_pool = scrapy_proxy_pool.proxy_pool_downloader_middleware.ProxyPoolDownloaderMiddleware',
        ],
    },
) 