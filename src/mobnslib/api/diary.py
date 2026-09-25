from __future__ import annotations
import asyncio
from datetime import date, datetime
from typing import Any, Optional
from ..utils import check_response, get_week_range
from ..exceptions import NoExpectedData, NoDataInResponse

class Diary:
    async def get_diary(
        self,
        access_token: str,
        student_id: int | str,
        start_date: Optional[str | datetime | date] = None,
        end_date: Optional[str | datetime | date] = None,
        day: Optional[str | datetime | date] = None,
        pattern: str = '%Y-%m-%d'
    ) -> list[dict[str, Any]]:
        headers = self._get_headers(access_token)
        if not (start_date and end_date):
            start_date, end_date = get_week_range(pattern, day)
        else:
            if hasattr(start_date, 'strftime'):
                start_date = start_date.strftime(pattern)
            if hasattr(end_date, 'strftime'):
                end_date = end_date.strftime(pattern)

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

    async def get_assignments(
        self,
        access_token: str,
        student_id: int | str,
        classmeeting_ids: Optional[list[int | str]] = None,
        diary: Optional[list[dict[str, Any]]] = None,
        limit: int = 20,
        delay: float = 0.1
    ) -> list[dict[str, Any]]:
        """Получение домашних заданий по урокам.
        
        Именно таким образом (порциями по limit элементов с задержкой delay) запрашивает
        данные официальное мобильное приложение NetSchool. Следование этой схеме
        предотвращает перегрузку сервера Сетевого Города и исключает ошибки 429 Too Many Requests.
        """
        headers = self._get_headers(access_token)
        if diary is not None and not classmeeting_ids:
            classmeeting_ids = []
            for day in diary:
                cm_id = day.get("classmeetingId")
                if cm_id:
                    classmeeting_ids.append(cm_id)

        elif diary is None and not classmeeting_ids:
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

    async def get_attachment_info(
        self,
        access_token: str,
        assignment_ids: Optional[list[int | str]] = None,
        diary: Optional[list[dict[str, Any]]] = None,
        limit: int = 20,
        delay: float = 0.1
    ) -> list[dict[str, Any]]:
        """Получение информации о вложениях к домашним заданиям.
        
        Повторяет проверенный паттерн официального мобильного приложения NetSchool
        (порционная загрузка с паузой) для защиты сервера от перегрузки.
        """
        headers = self._get_headers(access_token)
        if diary is not None and not assignment_ids:
            assignment_ids = []
            for day in diary:
                if day.get("attachmentExists"):
                    assignment_ids.extend(day.get("assignments", []))

        elif diary is None and not assignment_ids:
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

    async def load_attachment(self, access_token: str, attachment_id: int | str) -> str:
        headers = self._get_headers(access_token)
        response = await self.session.get(
            f"{self.api}attachments/{attachment_id}",
            headers=headers
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return response.text

    async def upload_attachment(self, access_token: str, student_id: int | str, file_path: str) -> str:
        headers = self._get_headers(access_token)
        with open(file_path, 'rb') as f:
            response = await self.session.post(
                f"{self.api}attachments",
                headers=headers,
                params={'userId': student_id},
                files={'file': f}
            )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return response.text

    async def _get_events(
        self,
        event_type: str | list[str],
        access_token: str,
        student_id: int | str,
        period_days: int,
        subject_group_ids: Optional[int | str | list[int | str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        headers = self._get_headers(access_token)
        if not limit: limit = 100
        if not offset: offset = 0

        params = {
             'studentId': student_id,
             'limit': limit,
             'offset': offset,
             'Types': event_type,
             'periodDays': period_days,
             'appVersion': self.app_ver,
             'lng': self.lng
        }
        if subject_group_ids is not None:
            params['subjectGroupId'] = subject_group_ids

        response = await self.session.get(
            f"{self.api}period-events",
             headers=headers,
             params=params
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def get_homework_info_events(
        self,
        access_token: str,
        student_id: int | str,
        period_days: int,
        subject_group_ids: Optional[int | str | list[int | str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Получить события домашних заданий и итогов за последние 'period_days' (дней)."""
        return await self._get_events('HomeworkInfo', access_token, student_id, period_days, subject_group_ids, limit, offset)

    async def get_result_info_events(
        self,
        access_token: str,
        student_id: int | str,
        period_days: int,
        subject_group_ids: Optional[int | str | list[int | str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Получить события новых оценок и итогов за последние 'period_days' (дней)."""
        return await self._get_events('ResultInfo', access_token, student_id, period_days, subject_group_ids, limit, offset)

    async def get_term_total_info_events(
        self,
        access_token: str,
        student_id: int | str,
        period_days: int,
        subject_group_ids: Optional[int | str | list[int | str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Получить события итоговых оценок за учебный период и итогов за последние 'period_days' (дней)."""
        return await self._get_events('TermTotalInfo', access_token, student_id, period_days, subject_group_ids, limit, offset)

    async def get_year_total_info_events(
        self,
        access_token: str,
        student_id: int | str,
        period_days: int,
        subject_group_ids: Optional[int | str | list[int | str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Получить события итоговых оценок за учебный год и итогов за последние 'period_days' (дней)."""
        return await self._get_events('YearTotalInfo', access_token, student_id, period_days, subject_group_ids, limit, offset)

    async def get_all_events(
        self,
        access_token: str,
        student_id: int | str,
        period_days: int,
        subject_group_ids: Optional[int | str | list[int | str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Получить все типы событий и итогов за последние 'period_days' (дней) разом."""
        return await self._get_events(['HomeworkInfo', 'ResultInfo', 'TermTotalInfo', 'YearTotalInfo'], access_token, student_id, period_days, subject_group_ids, limit, offset)
