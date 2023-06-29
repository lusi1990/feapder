# -*- coding: utf-8 -*-
"""
Created on 2022/9/7 4:11 PM
---------
@summary:
---------
@author: Boris
@email: boris_liu@foxmail.com
"""

import json
import os
import re
from collections import defaultdict
from typing import Union, List

try:
    from typing import Literal  # python >= 3.8
except ImportError:  # python <3.8
    from typing_extensions import Literal

from playwright.sync_api import Page, BrowserContext, ViewportSize, ProxySettings
from playwright.sync_api import Playwright, Browser
from playwright.sync_api import Response
from playwright.sync_api import sync_playwright

from feapder.utils import tools
from feapder.utils.log import log
from feapder.utils.webdriver.webdirver import *


class PlaywrightDriver(WebDriver):
    def __init__(
            self,
            *,
            page_on_event_callback: dict = None,
            storage_state_path: str = None,
            driver_type: Literal["chromium", "firefox", "webkit"] = "chromium",
            url_regexes: list = None,
            save_all: bool = False,
            **kwargs
    ):
        """

        Args:
            page_on_event_callback: page.on() 事件的回调 如 page_on_event_callback={"dialog": lambda dialog: dialog.accept()}
            storage_state_path: 保存浏览器状态的路径
            driver_type: 浏览器类型 chromium, firefox, webkit
            url_regexes: 拦截接口，支持正则，数组类型
            save_all: 是否保存所有拦截的接口, 默认只保存最后一个
            **kwargs:
        """
        super(PlaywrightDriver, self).__init__(**kwargs)
        self.driver: Playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.url = None
        self.storage_state_path = storage_state_path

        self._driver_type = driver_type
        self._page_on_event_callback = page_on_event_callback
        self._url_regexes = url_regexes
        self._save_all = save_all

        if self._save_all and self._url_regexes:
            log.warning(
                "获取完拦截的数据后, 请主动调用PlaywrightDriver的clear_cache()方法清空拦截的数据，否则数据会一直累加，导致内存溢出"
            )
            self._cache_data = defaultdict(list)
        else:
            self._cache_data = {}

        self._setup()

    def _setup(self):
        # 处理参数
        if self._proxy:
            proxy = self._proxy() if callable(self._proxy) else self._proxy
            proxy = self.format_context_proxy(proxy)
        else:
            proxy = None

        # 初始化浏览器对象
        self.driver = sync_playwright().start()
        # Browser needs to be launched with the global proxy.
        # If all contexts override the proxy, global proxy will be never used and can be any string
        self.browser = getattr(self.driver, self._driver_type).launch(
            headless=self._headless,
            args=["--no-sandbox"],
            proxy=proxy,
            executable_path=self._executable_path,
            downloads_path=self._download_path,
        )
        self.context = self._new_context(proxy)
        self.page = self._new_page()

    def _new_context(self, proxy):
        """

        :param proxy: context proxy 优先级高于 browser
        :return:
        """
        user_agent = (
            self._user_agent() if callable(self._user_agent) else self._user_agent
        )

        view_size = ViewportSize(
            width=self._window_size[0], height=self._window_size[1]
        )
        if self.storage_state_path and os.path.exists(self.storage_state_path):
            context = self.browser.new_context(
                user_agent=user_agent,
                screen=view_size,
                viewport=view_size,
                proxy=proxy,
                ignore_https_errors=True,
                storage_state=self.storage_state_path,
            )
        else:
            context = self.browser.new_context(
                user_agent=user_agent,
                screen=view_size,
                proxy=proxy,
                viewport=view_size,
                ignore_https_errors=True,
            )

        if self._use_stealth_js:
            path = os.path.join(os.path.dirname(__file__), "../js/stealth.min.js")
            context.add_init_script(path=path)
        return context

    def _new_page(self):
        """
        初始化页面
        """
        page = self.context.new_page()
        page.set_default_timeout(self._timeout * 1000)
        if not self._load_images:
            page.route(
                re.compile(r"(\.png$)|(\.png?)|(\.jpg$)|(\.jpg?)|(\.jpeg$)|(\.jpeg?)|(\.svg$)|(\.gif$)|(\.gif?)"),
                lambda route: route.abort())
        if self._page_on_event_callback:
            for event, callback in self._page_on_event_callback.items():
                page.on(event, callback)
        if self._url_regexes:
            page.on("response", self.on_response)
        return page

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            log.error(exc_val)

        self.quit()
        return True

    def format_context_proxy(self, proxy) -> ProxySettings:
        """
        Args:
            proxy: username:password@ip:port / ip:port
        Returns:
            {
                "server": "ip:port"
                "username": username,
                "password": password,
            }
            server: http://ip:port or socks5://ip:port. Short form ip:port is considered an HTTP proxy.
        """

        if "@" in proxy:
            certification, _proxy = proxy.split("@")
            username, password = certification.split(":")

            context_proxy = ProxySettings(
                server=_proxy,
                username=username,
                password=password,
            )
        else:
            context_proxy = ProxySettings(server=proxy)

        return context_proxy

    def save_storage_stage(self):
        if self.storage_state_path:
            os.makedirs(os.path.dirname(self.storage_state_path), exist_ok=True)
            self.context.storage_state(path=self.storage_state_path)

    def quit(self):
        self.page.close()
        self.context.close()
        self.browser.close()
        self.driver.stop()

    @property
    def domain(self):
        return tools.get_domain(self.url or self.page.url)

    @property
    def cookies(self):
        cookies_json = {}
        for cookie in self.page.context.cookies():
            cookies_json[cookie["name"]] = cookie["value"]

        return cookies_json

    @cookies.setter
    def cookies(self, val: Union[dict, List[dict]]):
        """
        设置cookie
        Args:
            val: List[{name: str, value: str, url: Union[str, NoneType], domain: Union[str, NoneType], path: Union[str, NoneType], expires: Union[float, NoneType], httpOnly: Union[bool, NoneType], secure: Union[bool, NoneType], sameSite: Union["Lax", "None", "Strict", NoneType]}]

        Returns:

        """
        if isinstance(val, list):
            self.page.context.add_cookies(val)
        else:
            cookies = []
            for key, value in val.items():
                cookies.append(
                    {"name": key, "value": value, "url": self.url or self.page.url}
                )
            self.page.context.add_cookies(cookies)

    @property
    def user_agent(self):
        return self.page.evaluate("() => navigator.userAgent")

    def on_response(self, response: Response):
        for regex in self._url_regexes:
            if re.search(regex, response.request.url):
                intercept_request = InterceptRequest(
                    url=response.request.url,
                    headers=response.request.headers,
                    data=response.request.post_data,
                )

                intercept_response = InterceptResponse(
                    request=intercept_request,
                    url=response.url,
                    headers=response.headers,
                    content=response.body(),
                    status_code=response.status,
                )
                if self._save_all:
                    self._cache_data[regex].append(intercept_response)
                else:
                    self._cache_data[regex] = intercept_response

    def get_response(self, url_regex) -> InterceptResponse:
        if self._save_all:
            response_list = self._cache_data.get(url_regex)
            if response_list:
                return response_list[-1]
        return self._cache_data.get(url_regex)

    def get_all_response(self, url_regex) -> List[InterceptResponse]:
        """
        获取所有匹配的响应, 仅在save_all=True时有效
        Args:
            url_regex:

        Returns:

        """
        response_list = self._cache_data.get(url_regex, [])
        if not isinstance(response_list, list):
            return [response_list]
        return response_list

    def get_text(self, url_regex):
        return (
            self.get_response(url_regex).content.decode()
            if self.get_response(url_regex)
            else None
        )

    def get_all_text(self, url_regex):
        """
        获取所有匹配的响应文本, 仅在save_all=True时有效
        Args:
            url_regex:

        Returns:

        """
        return [
            response.content.decode() for response in self.get_all_response(url_regex)
        ]

    def get_json(self, url_regex):
        return (
            json.loads(self.get_text(url_regex))
            if self.get_response(url_regex)
            else None
        )

    def get_all_json(self, url_regex):
        """
        获取所有匹配的响应json, 仅在save_all=True时有效
        Args:
            url_regex:

        Returns:

        """
        return [json.loads(text) for text in self.get_all_text(url_regex)]

    def clear_cache(self):
        self._cache_data = defaultdict(list)
