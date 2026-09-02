import logging
import httpx
import asyncio
from datetime import datetime
from typing import Optional

from .utils import check_response, get_week_range, HTMLTruncateHandler
from .exceptions import (
    NoDataInResponse,
    UnexpectedResponse,
    WrongLoginOrPassword,
    NoExpectedData,
)

class nslib:
    def __init__(
        self,
        url: str,
        log_name: str = None,
        log_level: int = None,
        client: httpx.AsyncClient = None,
        proxy: str = None
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

    def _get_headers(self, access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    def _get_temp_client_args(self) -> dict:
        args = self._client_args.copy()
        args["cookies"] = httpx.Cookies()
        return args

    async def esia_login(self, login: str, password: str):
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

    async def esia_mfa(self, mfa_code: str, login_data: dict):
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

    async def esia_login_end(self, login_or_mfa_data: dict):
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

    async def get_info(self, access_token: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}users",
            headers=headers,
            params={
                'v': '2',
                'appVersion': self.app_ver,
                'lng': self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def get_server_id(self, access_token: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.url3}users/endpoints", 
            headers=headers,
            params={
                'appVersion': self.app_ver,
                'lng': self.lng
            }
        )
        try:
            server_id = check_response(response, self.log)[0].get('serverId')
        except (KeyError, IndexError, TypeError) as e:
            self.log.error("No expected data in response", exc_info=True)
            raise NoDataInResponse() from e
        
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return server_id

    async def get_diary(
        self,
        access_token: str,
        student_id: str,
        start_date: str = None,
        end_date: str = None,
        day: str = None,
        pattern: str = '%Y-%m-%d'
    ):
        headers = self._get_headers(access_token)
        if not (start_date and end_date):
            start_date, end_date = get_week_range(pattern, day)

        response = await self.session.get(
            f"{self.api}classmeetings",
            params={
                'studentIds': student_id,
                'startDate': start_date,
                'endDate': end_date,
                'extraActivity': 'null',
                'appVersion': self.app_ver,
                'lng': self.lng 
            },
            headers=headers
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def token_refresh(self, refresh_token: str):
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

    async def get_ver(self):
        response = await self.session.get(
            f"{self.url1}api/v1/mobile/parent/app-versions/published",
            params={
                'appVersion': self.app_ver,
                'lng': self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")

        if response.is_error:
            sent_payload = response.request.content.decode('utf-8') if hasattr(response.request, 'content') else ""
            self.log.error(f"HTTP error: {response.status_code} - {response.text}")
            self.log.debug(f"Sent payload: {sent_payload}")
            response.raise_for_status()

        return response.text.replace('"', '')

    async def get_assignments(self, access_token: str, student_id: str, classmeeting_ids=None, diary=None, limit: int = 20, delay: float = 0.1):
        headers = self._get_headers(access_token)
        if diary and not classmeeting_ids:
            classmeeting_ids = []
            for day in diary:
                cm_id = day.get("classmeetingId")
                if cm_id:
                    classmeeting_ids.append(cm_id)

        elif not diary:
            self.log.error("No expected data")
            raise NoExpectedData()

        assigns = []
        for i in range(0, len(classmeeting_ids), limit):
            chunk = classmeeting_ids[i : i + limit]
            response = await self.session.get(
                f"{self.api}assignments",
                headers=headers,
                params={
                    "studentId": student_id,
                    "classmeetingId": chunk,
                    "appVersion": self.app_ver,
                    "lng": self.lng
                }
            )
            self.log.info(f"{response} {response.url}")
            self.log.debug(f"{response.text}")
            try:
                assigns.extend(check_response(response, self.log))
            except (KeyError, IndexError, TypeError) as e:
                self.log.error("No expected data in response", exc_info=True)
                raise NoDataInResponse() from e
            
            if i + limit < len(classmeeting_ids):
                self.log.debug(f"Waiting {delay}s before next request...")
                await asyncio.sleep(delay)

        return assigns

    async def get_attachment_info(self, access_token: str, assignment_ids=None, diary=None, limit: int = 20, delay: float = 0.1):
        headers = self._get_headers(access_token)
        if diary and not assignment_ids:
            assignment_ids = []
            for day in diary:
                if day.get("attachmentExists"):
                    assignment_ids.extend(day.get("assignments", []))

        elif not diary:
            self.log.error("No expected data")
            raise NoExpectedData()

        attachments = []
        for i in range(0, len(assignment_ids), limit):
            chunk = assignment_ids[i : i + limit]
            response = await self.session.get(
                f"{self.api}attachments",
                headers=headers,
                params={
                    "assignmentId": chunk,
                    "appVersion": self.app_ver,
                    "lng": self.lng
                }
            )
            self.log.info(f"{response} {response.url}")
            self.log.debug(f"{response.text}")
            
            attachments.extend(check_response(response, self.log))
            if i + limit < len(assignment_ids):
                self.log.debug(f"Waiting {delay}s before next request...")
                await asyncio.sleep(delay)

        return attachments

    async def load_attachment(self, access_token: str, attachment_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}attachments/{attachment_id}",
            headers=headers
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return response.text

    async def upload_attachment(self, access_token: str, student_id: str, file_path: str):
        headers = self._get_headers(access_token)
        # Using open here requires careful handling in async, but keeping original logic
        with open(file_path, 'rb') as f:
            response = await self.session.post(
                f"{self.api}attachments",
                headers=headers,
                params={'userId': student_id},
                files={'file': f} # Adjusted for standard httpx files
            )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return response.text

    async def get_school_year(self, access_token: str, student_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}education",
             headers=headers,
             params={
                 'studentId': student_id,
                 'appVersion': self.app_ver,
                 'lng': self.lng
             }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")

        try:
            json_data = check_response(response, self.log)
            return {
                'nowYear': json_data[0]['schoolyear']['id'],
                'allYears': json_data
            }
        except (KeyError, IndexError, TypeError) as e:
            self.log.error("No expected data in response", exc_info=True)
            raise NoDataInResponse() from e

    async def get_subjects(self, access_token: str, student_id: str, school_year_id: str, diary=None):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}subjects",
            headers=headers,
            params={
                'studentId': student_id,
                'schoolYearId': school_year_id,
                'appVersion': self.app_ver,
                'lng': self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        subjects = check_response(response, self.log)

        if diary:
            group_mapping = {
                item['subjectId']: item['subjectGroupId'] 
                for item in diary if item.get('subjectGroupId')
            }
            for subject in subjects:
                subject['subjectGroupId'] = group_mapping.get(subject['id'])

        return subjects

    async def get_totals(self, access_token: str, student_id: str, school_year_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}totals",
             headers=headers,
             params={
                 'studentId': student_id,
                 'schoolYearId': school_year_id,
                 'appVersion': self.app_ver,
                 'lng': self.lng
             }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def get_terms(self, access_token: str, student_id: str, school_year_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}terms",
             headers=headers,
             params={
                 'studentId': student_id,
                 'schoolYearId': school_year_id,
                 'appVersion': self.app_ver,
                 'lng': self.lng
             }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def get_announcements(self, access_token: str, student_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}announcements",
             headers=headers,
             params={
                 'studentId': student_id,
                 'appVersion': self.app_ver,
                 'lng': self.lng
             }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def _get_events(self, event_type, access_token: str, student_id: str, period_days: int, subject_group_ids, limit: int = None, offset: int = None):
        headers = self._get_headers(access_token)
        if not limit: limit = 100
        if not offset: offset = 0

        response = await self.session.get(
            f"{self.api}period-events",
             headers=headers,
             params={
                 'studentId': student_id,
                 'limit': limit,
                 'offset': offset,
                 'subjectGroupId': subject_group_ids,
                 'Types': event_type,
                 'periodDays': period_days,
                 'appVersion': self.app_ver,
                 'lng': self.lng
             }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def get_homework_info_events(self, access_token: str, student_id: str, period_days: int, subject_group_ids=None, limit: int = None, offset: int = None):
        return await self._get_events('HomeworkInfo', access_token, student_id, period_days, subject_group_ids, limit, offset)

    async def get_result_info_events(self, access_token: str, student_id: str, period_days: int, subject_group_ids=None, limit: int = None, offset: int = None):
        return await self._get_events('ResultInfo', access_token, student_id, period_days, subject_group_ids, limit, offset)

    async def get_term_total_info_events(self, access_token: str, student_id: str, period_days: int, subject_group_ids=None, limit: int = None, offset: int = None):
        return await self._get_events('TermTotalInfo', access_token, student_id, period_days, subject_group_ids, limit, offset)

    async def get_year_total_info_events(self, access_token: str, student_id: str, period_days: int, subject_group_ids=None, limit: int = None, offset: int = None):
        return await self._get_events('YearTotalInfo', access_token, student_id, period_days, subject_group_ids, limit, offset)

    async def get_all_events(self, access_token: str, student_id: str, period_days: int, subject_group_ids=None, limit: int = None, offset: int = None):
        return await self._get_events(['HomeworkInfo', 'ResultInfo', 'TermTotalInfo', 'YearTotalInfo'], access_token, student_id, period_days, subject_group_ids, limit, offset)

    async def get_mail_unread_count(self, access_token: str, student_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}mail/messages/unread-count",
            headers=headers,
            params={
                'userId': student_id,
                'appVersion': self.app_ver,
                'lng': self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return response.text

    async def get_mails(
        self,
        access_token: str,
        student_id: str,
        box_type: str,
        expand: list = None,
        sort_by: str = 'Sent',
        invert_sort: bool = False,
        page_size: int = 20,
        page: int = 1
    ):
        if expand_is_none := expand is None:
            expand = ['text', 'subject', 'author']
            
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}mail/messages",
            headers=headers,
            params={
                'userId': student_id,
                'boxType': box_type,
                'pageSize': page_size,
                'OrderInfo.Field': sort_by,
                'OrderInfo.Ascending': invert_sort,
                'page': page,
                'expand': expand,
                'appVersion': self.app_ver,
                'lng': self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def get_inbox_mails(self, access_token: str, student_id: str, expand=None, sort_by='Sent', invert_sort=False, page_size=20, page=1):
        return await self.get_mails(access_token, student_id, 'inbox', expand, sort_by, invert_sort, page_size, page)
    
    async def get_sent_mails(self, access_token: str, student_id: str, expand=None, sort_by='Sent', invert_sort=False, page_size=20, page=1):
        return await self.get_mails(access_token, student_id, 'sent', expand, sort_by, invert_sort, page_size, page)

    async def get_draft_mails(self, access_token: str, student_id: str, expand=None, sort_by='Sent', invert_sort=False, page_size=20, page=1):
        return await self.get_mails(access_token, student_id, 'draft', expand, sort_by, invert_sort, page_size, page)

    async def get_deleted_mails(self, access_token: str, student_id: str, expand=None, sort_by='Sent', invert_sort=False, page_size=20, page=1):
        return await self.get_mails(access_token, student_id, 'deleted', expand, sort_by, invert_sort, page_size, page)

    async def send_mail(
        self,
        access_token: str,
        student_id: str,
        subject: str,
        text: str,
        to_ids: list,
        copy: list = None,
        hidden_copy: list = None,
        attachment_ids: list = None,
        message_id: str = None,
        notify: bool = False,
        draft: bool = False
    ):
        headers = self._get_headers(access_token)
        data = {
            'to': to_ids,
            'cc': copy or [],
            'bcc': hidden_copy or [],
            'subject': subject,
            'text': text,
            'attachmentIds': attachment_ids or [],
            'notify': notify,
            'draft': draft,
            'authorId': student_id,
            'messageId': message_id
        }
        response = await self.session.post(
            f"{self.api}mail/messages",
            headers=headers,
            json=data
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def delete_mail(self, access_token: str, student_id: str, message_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.post(
            f"{self.api}mail/messages/moving",
            headers=headers,
            params={'userId': student_id},
            files=[('messageIds', (None, str(message_id)))]
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")

        if response.is_error:
            sent_payload = response.request.content.decode('utf-8') if hasattr(response.request, 'content') else ""
            self.log.error(f"HTTP error: {response.status_code} - {response.text}")
            self.log.debug(f"Sent payload: {sent_payload}")
            response.raise_for_status()
        
        return {"status": "success", "message": f"Messages {message_id} moved to deleted.", "details": "No specific JSON response provided."}

    async def read_mail(self, access_token: str, student_id: str, message_id: str, page_size: int = 150):
        headers = self._get_headers(access_token)
        response = await self.session.post(
            f"{self.api}mail/messages/{message_id}/read",
            headers=headers,
            params={"userId": student_id, "pageSize": page_size}
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def get_sample_mail(self, access_token: str, student_id: str, message_id: str, action: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}mail/messages/{message_id}/edit",
            headers=headers,
            params={
                'userId': student_id,
                'action': action,
                'appVersion': self.app_ver,
                'lng': self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def get_sample_reply_mail(self, access_token: str, student_id: str, message_id: str):
        return await self.get_sample_mail(access_token, student_id, message_id, 'reply')
    
    async def get_sample_forward_mail(self, access_token: str, student_id: str, message_id: str):
        return await self.get_sample_mail(access_token, student_id, message_id, 'forward')

    async def get_sample_reply_all_mail(self, access_token: str, student_id: str, message_id: str):
        return await self.get_sample_mail(access_token, student_id, message_id, 'replyall')

    async def block_user(self, access_token: str, student_id: str, user_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.post(
            f"{self.api}mail/blocked-users",
            headers=headers,
            params={
                'userId': student_id,
                'authorId': user_id
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        
        if response.is_error:
            sent_payload = response.request.content.decode('utf-8') if hasattr(response.request, 'content') else ""
            self.log.error(f"HTTP error: {response.status_code} - {response.text}")
            self.log.debug(f"Sent payload: {sent_payload}")
            response.raise_for_status()

        return {"status": "success", "message": f"User {user_id} blocked."}

    async def unblock_user(self, access_token: str, student_id: str, user_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.delete(
            f"{self.api}mail/blocked-users",
            headers=headers,
            params={
                'userId': student_id,
                'authorId': user_id
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")

        if response.is_error:
            sent_payload = response.request.content.decode('utf-8') if hasattr(response.request, 'content') else ""
            self.log.error(f"HTTP error: {response.status_code} - {response.text}")
            self.log.debug(f"Sent payload: {sent_payload}")
            response.raise_for_status()

        return {"status": "success", "message": f"User {user_id} unblocked."}

    async def get_blocked_users(self, access_token: str, student_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}mail/blocked-users",
            headers=headers,
            params={
                'userId': student_id,
                'appVersion': self.app_ver,
                'lng': self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def get_recipients(self, access_token: str, student_id: str, org_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}address-book",
            headers=headers,
            params={
                'userId': student_id,
                'orgId': org_id,
                'appVersion': self.app_ver,
                'lng': self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def get_recipient_by_id(self, access_token: str, user_id: str):
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}address-book/recipients/get-by-userid",
            headers=headers,
            params={
                'userId': user_id,
                'appVersion': self.app_ver,
                'lng': self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    @staticmethod
    async def get_server_list():
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.get(
                "https://mobile.ir-tech.ru/api/v1/mobile/parent/end-points",
                params={
                    'appVersion': '1.3.9',
                    'lng': 'ru'
                }
            )
            
            if response.is_error:
                response.raise_for_status()

            try:
                import json
                return response.json()
            except (json.JSONDecodeError, ValueError) as e:
                from .exceptions import NotJSONResponse
                raise NotJSONResponse() from e

