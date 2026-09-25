from __future__ import annotations
import logging
from typing import Optional
import httpx
from .utils import HTMLTruncateHandler
from .api import Auth, User, Diary, Mail

class nslib(Auth, User, Diary, Mail):
    def __init__(
        self,
        url: str,
        log_name: Optional[str] = None,
        log_level: Optional[int] = None,
        client: Optional[httpx.AsyncClient] = None,
        proxy: Optional[str] = None
    ):
        self.proxy = proxy
        self._client_args = {
            "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            "timeout": httpx.Timeout(30.0),
            "follow_redirects": True
        }
        if proxy:
            self._client_args["proxy"] = proxy

        if client:
            self.session = client
        else:
            self.session = httpx.AsyncClient(**self._client_args)

        url = url.rstrip("/")
        if "/api/mobile" in url:
            self.api = f"{url}/"
            url = url.replace("api/mobile", "")
        else:
            self.api = f"{url}/api/mobile/"
        
        self.url = f"{url}/"
        self.url1 = 'https://mobile.ir-tech.ru/'
        self.url2 = 'https://esia.gosuslugi.ru/'
        self.url3 = 'https://identity.ir-tech.ru/'
        self.client_secret = '04064338-13df-4747-8dea-69849f9ecdf0'
        self.app_ver = '1.3.9'
        self.lng = "ru"

        logger = logging.getLogger("mobnslib")
        logger.setLevel(logging.DEBUG)
        self.log = logger

        level = {
            1: logging.ERROR,
            2: logging.WARNING,
            3: logging.INFO,
            4: logging.DEBUG
        }
        
        if log_name:
            file_handler = HTMLTruncateHandler(log_name, encoding="utf-8", mode='w')
            target_level = level.get(log_level, logging.CRITICAL)
            file_handler.setLevel(target_level)
            file_format = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s')
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
            self.log.info(f"Log_level {log_level}")

    def _get_headers(self, access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}
