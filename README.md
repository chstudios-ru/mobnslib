# MobNsLib

Библиотека для асинхронного взаимодействия с API мобильного приложения сетевого дневника (NetSchool).

## Установка

```bash
pip install mobnslib
```

## Использование

```python
import asyncio
from MobNsLib import nsLib

async def main():
    ns = nsLib("https://your-school-url.ru")
    
    result = await ns.EsiaLogin(login="номер_телефона", password="пароль")
    if result['status'] == "ENTER_MFA":
        code = input()
        result = await ns.EsiaMfa(code, result)
    
    tokens = await ns.EsiaLogin(result)

    
if __name__ == "__main__":
    asyncio.run(main())
```

## Классы и их методы

Всего 8 классов, 1 для обрезки логов, 1 основной и 6 исключений

Классы исключения:

    NoDataInResponse - в ответе от нетскул/госуслуг нет ожидаемых данных, обычно это проблемы в либе, сообщите мне

    NotJSONResponse - в ответе вместо данных в формате json пришел, например, html код

    NoLoginOrPassword - только в методе esiaLogin, если не написали логин и пароль(надо будет убрать, наверно)

    UnexpectedResponse - неожиданный для библиотеки ответ сервера (только в esiaLogin, если встретили, свяжитесь со мной)

    WrongLoginOrPassword - неправильный логин/пароль (только в esiaLogin)

Класс обрезки логов:

    HTMLTruncateHandler (название сменить и написать про функционал)

Основной класс(nsLib):

    Перед использованием методов необходимо создать класс и передать в него url вашего дневника, а также название файла с логами и их уровень(по умолчанию - critical, от 1 до 4, где 4 - debug). Для получения списка доступных серверов есть getServerList, для которого не обязательно создавать класс (сомнительная формулировка)

    checkResponse() - принимает обьект response и проверяет на 4хх/5хх и json ли в ответе. Возвращает словарь.

    esiaLogin() - принимает логин(номер телефона) и пароль от госуслуг. Возвращает словарь, который потребуется для последующих 2 методов. Словарь содержит status(ENTER_MFA или DONE), loginState(из нетскула), cookies(для госуслуг). Если статус ENTER_MFA, то содержитdesc(тип мфа) и details(данные про мфа, по типу длины кода, количества попыток и  т.п.). Если статус DONE, то содержит redirect_url

    esiaMfa() - принимает строку mfa_code и LoginData из предыдущего метода. Возвращает словарь для следующего метода. Словарь содержит status, redirect_url, loginState(из нетскула) и cookies(для госуслуг)

    esiaLoginEnd - принимает LoginOrMfaData(status обязательно должен быть DONE). Возвращает словарь с токенами(access_token и refresh_token) и информацией о них(expires-in и created_at)
    
    
    Все следующие методы принимают словарь headers, нужный для авторизации. Должен выглядеть так: {"Authorization":"Bearer ваш_access_token"}

    


