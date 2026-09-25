from __future__ import annotations
from typing import Any, Optional
from ..utils import check_response

class Mail:
    async def get_mail_unread_count(self, access_token: str, student_id: int | str) -> int | str:
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
        text = response.text.strip().replace('"', '')
        return int(text) if text.isdigit() else text

    async def get_mails(
        self,
        access_token: str,
        student_id: int | str,
        box_type: str,
        expand: Optional[list[str]] = None,
        sort_by: str = 'Sent',
        invert_sort: bool = False,
        page_size: int = 20,
        page: int = 1
    ) -> dict[str, Any]:
        """Получить список писем из указанного ящика с постраничной загрузкой (пагинацией).

        Args:
            box_type: Тип ящика ('inbox', 'sent', 'draft', 'deleted').
            page_size: Количество писем на странице (по умолчанию 20).
            page: Номер запрашиваемой страницы (начиная с 1).
            sort_by: Поле для сортировки (по умолчанию 'Sent' - дата отправки).
            invert_sort: Порядок сортировки (False - сначала новые, True - сначала старые).
            expand: Дополнительные поля для загрузки (текст, тема, автор).
        """
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

    async def get_inbox_mails(
        self,
        access_token: str,
        student_id: int | str,
        expand: Optional[list[str]] = None,
        sort_by: str = 'Sent',
        invert_sort: bool = False,
        page_size: int = 20,
        page: int = 1
    ) -> dict[str, Any]:
        return await self.get_mails(access_token, student_id, 'inbox', expand, sort_by, invert_sort, page_size, page)
    
    async def get_sent_mails(
        self,
        access_token: str,
        student_id: int | str,
        expand: Optional[list[str]] = None,
        sort_by: str = 'Sent',
        invert_sort: bool = False,
        page_size: int = 20,
        page: int = 1
    ) -> dict[str, Any]:
        return await self.get_mails(access_token, student_id, 'sent', expand, sort_by, invert_sort, page_size, page)

    async def get_draft_mails(
        self,
        access_token: str,
        student_id: int | str,
        expand: Optional[list[str]] = None,
        sort_by: str = 'Sent',
        invert_sort: bool = False,
        page_size: int = 20,
        page: int = 1
    ) -> dict[str, Any]:
        return await self.get_mails(access_token, student_id, 'draft', expand, sort_by, invert_sort, page_size, page)

    async def get_deleted_mails(
        self,
        access_token: str,
        student_id: int | str,
        expand: Optional[list[str]] = None,
        sort_by: str = 'Sent',
        invert_sort: bool = False,
        page_size: int = 20,
        page: int = 1
    ) -> dict[str, Any]:
        return await self.get_mails(access_token, student_id, 'deleted', expand, sort_by, invert_sort, page_size, page)

    async def send_mail(
        self,
        access_token: str,
        student_id: int | str,
        subject: str,
        text: str,
        to_ids: list[int | str],
        copy: Optional[list[int | str]] = None,
        hidden_copy: Optional[list[int | str]] = None,
        attachment_ids: Optional[list[int | str]] = None,
        message_id: Optional[int | str] = None,
        notify: bool = False,
        draft: bool = False
    ) -> dict[str, Any]:
        """Отправка нового письма или сохранение черновика.

        Args:
            access_token: Токен доступа.
            student_id: ID отправителя (пользователя).
            subject: Тема письма.
            text: Тело / текст письма.
            to_ids: Список ID основных получателей (поле "Кому").
            copy: Список ID получателей открытой копии (поле "Копия").
            hidden_copy: Список ID получателей скрытой копии (поле "Скрытая копия").
            attachment_ids: Список ID файлов-вложений (полученных через upload_attachment).
            message_id: ID существующего письма (для редактирования черновика).
            notify: Уведомление о прочтении (True - отправителю придет системное уведомление после прочтения письма получателем).
            draft: Режим черновика (True - сохранить в черновиках, False - отправить адресатам).
        """
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

    async def delete_mail(self, access_token: str, student_id: int | str, message_id: int | str) -> dict[str, Any]:
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

    async def read_mail(self, access_token: str, student_id: int | str, message_id: int | str, page_size: int = 150) -> dict[str, Any]:
        """Пометить письмо как прочитанное и получить его полное содержимое.
        
        Возвращает полный объект письма: текст, тему, автора, списки получателей,
        вложения и метаданные.
        """
        headers = self._get_headers(access_token)
        response = await self.session.post(
            f"{self.api}mail/messages/{message_id}/read",
            headers=headers,
            params={"userId": student_id, "pageSize": page_size}
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return check_response(response, self.log)

    async def get_sample_mail(self, access_token: str, student_id: int | str, message_id: int | str, action: str) -> dict[str, Any]:
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

    async def get_sample_reply_mail(self, access_token: str, student_id: int | str, message_id: int | str) -> dict[str, Any]:
        return await self.get_sample_mail(access_token, student_id, message_id, 'reply')
    
    async def get_sample_forward_mail(self, access_token: str, student_id: int | str, message_id: int | str) -> dict[str, Any]:
        return await self.get_sample_mail(access_token, student_id, message_id, 'forward')

    async def get_sample_reply_all_mail(self, access_token: str, student_id: int | str, message_id: int | str) -> dict[str, Any]:
        return await self.get_sample_mail(access_token, student_id, message_id, 'replyall')

    async def block_user(self, access_token: str, student_id: int | str, user_id: int | str) -> dict[str, Any]:
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

    async def unblock_user(self, access_token: str, student_id: int | str, user_id: int | str) -> dict[str, Any]:
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

    async def get_blocked_users(self, access_token: str, student_id: int | str) -> list[dict[str, Any]]:
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

    async def get_recipients(self, access_token: str, student_id: int | str, org_id: int | str) -> list[dict[str, Any]]:
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

    async def get_recipient_by_id(self, access_token: str, user_id: int | str) -> dict[str, Any]:
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
