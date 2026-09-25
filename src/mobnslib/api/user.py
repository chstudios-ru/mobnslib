from __future__ import annotations
from typing import Any, Optional
import httpx
from ..utils import check_response
from ..exceptions import NoDataInResponse

class User:
    async def get_info(self, access_token: str) -> list[dict[str, Any]]:
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

    async def get_server_id(self, access_token: str) -> str:
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

    async def get_ver(self) -> str:
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

    async def get_school_year(self, access_token: str, student_id: int | str) -> dict[str, Any]:
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

    async def get_subjects(
        self,
        access_token: str,
        student_id: int | str,
        school_year_id: int | str,
        diary: Optional[list[dict[str, Any]]] = None
    ) -> list[dict[str, Any]]:
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

    async def get_totals(
        self,
        access_token: str,
        student_id: int | str,
        school_year_id: int | str
    ) -> list[dict[str, Any]]:
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

    async def get_terms(
        self,
        access_token: str,
        student_id: int | str,
        school_year_id: int | str
    ) -> list[dict[str, Any]]:
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

    async def get_announcements(self, access_token: str, student_id: int | str) -> list[dict[str, Any]]:
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

    @staticmethod
    async def get_server_list() -> dict[str, Any]:
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
                from ..exceptions import NotJSONResponse
                raise NotJSONResponse() from e
