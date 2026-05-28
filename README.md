# MobNsLib

Библиотека для асинхронного взаимодействия с API мобильного приложения сетевого дневника (NetSchool).

## Установка

```bash
pip install MobNsLib
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
    
    tokens = await ns.EsiaLogin()

    
if __name__ == "__main__":
    asyncio.run(main())
```
