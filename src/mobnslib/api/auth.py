from __future__ import annotations
from typing import Any
import httpx
from datetime import datetime
from ..utils import check_response
from ..exceptions import (
    NoDataInResponse,
    UnexpectedResponse,
    WrongLoginOrPassword,
)

class Auth:
    def _get_temp_client_args(self) -> dict[str, Any]:
        args = self._client_args.copy()
        args["cookies"] = httpx.Cookies()
        return args

    async def esia_login(self, login: str, password: str) -> dict[str, Any]:
        session = httpx.AsyncClient(**self._get_temp_client_args())
        log = self.log

        data = {'mobile': '1'}
        response = await session.post(
            f"{self.url}webapi/auth/login-state",
            data=data
        )
        login_state = response.text.replace('"', '')
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        response = await session.get(
            f"{self.url}webapi/sso/esia/crosslogin",
            params={
                'loginState': login_state,
                'esia_permissions': '1',
                'esia_role': '1'
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        pattern = '%d-%m-%Y_%H-%M-%S'
        ondate = datetime.now().strftime(pattern)
        response = await session.get(
            f"{self.url2}rs/dscl",
            params={'ondate': ondate}
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        response = await session.post(
            f"{self.url2}aas/oauth2/api/login/", 
            json={
                'login': login,
                'password': password
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")
        
        cookies = [
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
            }
            for cookie in session.cookies.jar
        ]
        await session.aclose()

        tmp = check_response(response, log)
        if response.status_code == 201:
            log.error("Wrong login or password")
            raise WrongLoginOrPassword()
            
        if tmp.get('action') == 'ENTER_MFA':
            try:
                self.mfa_type_asked = tmp['mfa_details']['type']
                return {
                    'status': tmp['action'],
                    'desc': tmp['mfa_details']['type'],
                    'details': tmp['mfa_details'],
                    'loginState': login_state,
                    'cookies': cookies
                }
            except (KeyError, IndexError, TypeError) as e:
                log.error("No expected data in response", exc_info=True)
                raise NoDataInResponse() from e
        
        if tmp.get('action') == 'DONE':
            try:
                return {
                    'status': tmp['action'],
                    'redirect_url': tmp['redirect_url'],
                    'loginState': login_state,
                    'cookies': cookies
                }
            except (KeyError, IndexError, TypeError) as e:
                log.error("No expected data in response", exc_info=True)
                raise NoDataInResponse() from e

        log.error("Unexpected response", exc_info=True)
        raise UnexpectedResponse()

    async def esia_mfa(self, mfa_code: str, login_data: dict[str, Any]) -> dict[str, Any]:
        session = httpx.AsyncClient(**self._get_temp_client_args())
        log = self.log
        for c in login_data['cookies']:
            session.cookies.set(c['name'], c['value'], domain=c['domain'], path=c['path'])

        url_map = {
            'TTP': 'totp',
            'SMS': 'otp',
            'MAX': 'otp-max'
        }

        response = await session.post(
            f"{self.url2}aas/oauth2/api/login/{url_map.get(login_data['desc'])}/verify",
            params={'code': mfa_code}
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        if check_response(response, log).get("action") == "MAX_QUIZ":
            response = await session.post(
                f"{self.url2}aas/oauth2/api/login/quiz-max/skip"
            )
            log.info(f"{response} {response.url}")
            log.debug(f"{response.text}")

        cookies = [
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
            }
            for cookie in session.cookies.jar
        ]
        await session.aclose()
        
        try:
            temp = check_response(response, log)
            return {
                'status': temp['action'],
                'redirect_url': temp['redirect_url'],
                'loginState': login_data['loginState'],
                'cookies': cookies
            }
        except (KeyError, IndexError, TypeError) as e:
            log.error("No expected data in response", exc_info=True)
            raise NoDataInResponse() from e

    async def esia_login_end(self, login_or_mfa_data: dict[str, Any]) -> dict[str, Any]:
        session = httpx.AsyncClient(**self._get_temp_client_args())
        log = self.log
        for c in login_or_mfa_data['cookies']:
            session.cookies.set(c['name'], c['value'], domain=c['domain'], path=c['path'])

        response = await session.get(login_or_mfa_data['redirect_url'])
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        response = await session.get(
            f"{self.url}webapi/sso/esia/account-info", 
            params={'loginState': login_or_mfa_data['loginState']}
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        try:
            tmp = check_response(response, log)
            data = {
                'idp': 'esia',
                'loginState': login_or_mfa_data['loginState'],
                'LoginType': '8',
                'lscope': tmp['users'][0]['id']
            }
        except (KeyError, IndexError, TypeError) as e:
            log.error("No expected data in response", exc_info=True)
            raise NoDataInResponse() from e
            
        response = await session.post(
            f"{self.url}webapi/auth/login",
            data=data
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        try:
            temp_headers = {'at': check_response(response, log)['at']}
        except (KeyError, IndexError, TypeError) as e:
            log.error("No expected data in response", exc_info=True)
            raise NoDataInResponse() from e
            
        response = await session.get(
            f"{self.url}webapi/mysettings/mobile/pincode",
            headers=temp_headers
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        try:
            data = {
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                'device_code': check_response(response, log)['userCode'],
                'client_id': 'parent-mobile',
                'client_secret': self.client_secret
            }
        except (KeyError, IndexError, TypeError) as e:
            log.error("No expected data in response", exc_info=True)
            raise NoDataInResponse() from e
            
        response = await session.post(
            f"{self.url3}connect/token",
            data=data
        )
        tmp = check_response(response, log)
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        created_at_resp = await session.get(f'{self.url1}api/v1/mobile/parent/time')
        created_at = created_at_resp.text.replace('"', '')

        try:
            tokens = {
                'access_token': tmp['access_token'],
                'refresh_token': tmp['refresh_token'],
                'expires_in': int(tmp['expires_in']),
                'created_at': int(created_at)
            }
        except (KeyError, IndexError, TypeError) as e:
            log.error("No expected data in response", exc_info=True)
            raise NoDataInResponse() from e

        response = await session.get(
            f"{self.url}logout",
            headers=temp_headers
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")
        await session.aclose()

        return tokens

    async def token_refresh(self, refresh_token: str) -> dict[str, Any]:
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': 'parent-mobile',
            'client_secret': self.client_secret
        }
        response = await self.session.post(
            f"{self.url3}connect/token",
            data=data
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")

        try:
            tmp = check_response(response, self.log)
            tokens = {
                'access_token': tmp['access_token'],
                'refresh_token': tmp['refresh_token'],
                'expires_in': tmp['expires_in']
            }
        except (KeyError, IndexError, TypeError) as e:
            self.log.error("No expected data in response", exc_info=True)
            raise NoDataInResponse() from e

        return tokens
