# mobnslib

Асинхронная библиотека для взаимодействия с сетевым дневником (NetSchool).

## Установка

Библиотека использует `httpx` для асинхронных HTTP запросов.
Для установки склонируйте репозиторий и установите через pip:

```bash
git clone https://github.com/chstudios-ru/mobnslib.git
cd mobnslib
pip install .
```

## Минимальное использование

Пример авторизации и получения данных о пользователе:

```python
import asyncio
from mobnslib import nslib

async def main():
    # Инициализация клиента. Вы можете передать свой httpx.AsyncClient и proxy
    client = nslib(url="https://example.com/")

    # 1. Авторизация
    login_data = await client.esia_login("ВАШ_ТЕЛЕФОН", "ВАШ_ПАРОЛЬ")
    
    # Если требуется MFA, используйте метод esia_mfa
    # login_data = await client.esia_mfa("123456", login_data)

    # Завершение авторизации и получение токенов
    tokens = await client.esia_login_end(login_data)
    access_token = tokens["access_token"]
    
    # 2. Получение информации об аккаунте
    info = await client.get_info(access_token)
    student_id = info[0]['id']
    print(f"ID студента: {student_id}")

    # 3. Получение дневника на текущую неделю
    diary = await client.get_diary(access_token, student_id)
    print(diary)

if __name__ == "__main__":
    asyncio.run(main())
```

## Документация по методам

Класс `nslib` предоставляет методы для работы с API. Все основные методы принимают `access_token`.

### Инициализация

```python
nslib(url: str, log_name: str = None, log_level: int = None, client: httpx.AsyncClient = None, proxy: str = None)
```
- `url`: Базовый URL сетевого города.
- `log_name`: Имя файла для записи логов.
- `log_level`: Уровень логирования (1 - ERROR, 4 - DEBUG).
- `client`: Пользовательский клиент `httpx.AsyncClient`.
- `proxy`: Прокси-сервер в формате строки.

### Авторизация
- `esia_login(login, password)`: Начало процесса авторизации через ЕСИА.
- `esia_mfa(mfa_code, login_data)`: Ввод кода двухфакторной аутентификации.
- `esia_login_end(login_or_mfa_data)`: Завершение авторизации, возвращает словарь с `access_token` и `refresh_token`.
- `token_refresh(refresh_token)`: Обновление токена доступа.

### Основные данные
- `get_info(access_token)`: Возвращает основную информацию о пользователе (ID студента, роль, школу).
- `get_school_year(access_token, student_id)`: Возвращает текущий учебный год и список всех годов.
- `get_diary(access_token, student_id, start_date=None, end_date=None, day=None)`: Получение дневника за неделю или указанный период.
- `get_totals(access_token, student_id, school_year_id)`: Итоговые оценки.
- `get_terms(access_token, student_id, school_year_id)`: Учебные периоды (четверти/триместры).
- `get_subjects(access_token, student_id, school_year_id, diary=None)`: Предметы.

### Задания и вложения
- `get_assignments(access_token, student_id, classmeeting_ids, diary, limit, delay)`: Домашние задания для списка уроков.
- `get_attachment_info(access_token, assignment_ids, diary, limit, delay)`: Информация о прикрепленных файлах.
- `load_attachment(access_token, attachment_id)`: Скачивание вложения.
- `upload_attachment(access_token, student_id, file_path)`: Загрузка вложения.

### Почта
- `get_inbox_mails(access_token, student_id)`: Входящие сообщения.
- `get_sent_mails(access_token, student_id)`: Отправленные сообщения.
- `send_mail(access_token, student_id, subject, text, to_ids, ...)`: Отправка письма.
- `read_mail(access_token, student_id, message_id)`: Чтение сообщения (пометка прочитанным).

### Исключения
Все исключения находятся в `mobnslib.exceptions`:
- `NoDataInResponse`: В ответе отсутствуют ожидаемые ключи/данные.
- `NotJSONResponse`: API вернул не JSON.
- `WrongLoginOrPassword`: Ошибка авторизации ЕСИА.
- `UnexpectedResponse`: Неожиданный ответ сервера во время авторизации.

### Утилиты
Доступны функции в модуле `mobnslib.utils`:
- `get_week_range(pattern, day)`: Получение начала и конца недели для переданной даты.
- `check_response(response, log)`: Проверка ответа и парсинг JSON с обработкой ошибок.
