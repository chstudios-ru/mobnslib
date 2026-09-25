'''
Тест всех методов, вывод каждого сохраняется в отдельный файл в папке test_outputs.
Перед запуском номер телефона и пароль обязательно должны быть в .env, totp ключ опционально.
'''


import asyncio
import os
import json
from dotenv import load_dotenv
from mobnslib import nslib

# Load credentials from .env
load_dotenv()

LOGIN = os.getenv("LOGIN")
PASSWORD = os.getenv("PASSWORD")
TTP_KEY = os.getenv("TTP_KEY")  # Used for TOTP if needed
API_URL = os.getenv("API_URL", "https://school.region.ru/")

async def main():
    if not LOGIN or not PASSWORD:
        print("Please set ESIA_LOGIN and ESIA_PASSWORD in your .env file.")
        return

    client = nslib(url=API_URL, log_name="test_debug.log", log_level=4)
    output_dir = "test_outputs"
    os.makedirs(output_dir, exist_ok=True)

    def save_output(name, data):
        with open(os.path.join(output_dir, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Saved {name}.json")

    print("Logging in...")
    try:
        login_res = await client.esia_login(LOGIN, PASSWORD)
        
        # If MFA is required
        if login_res.get('status') == 'ENTER_MFA':
            if TTP_KEY and login_res.get('desc'):
                # Here you would generate the TOTP code using the TTP_KEY
                # For demonstration, we assume we have a valid mfa_code
                import pyotp
                totp = pyotp.TOTP(TTP_KEY)
                mfa_code = totp.now()
                
                print(f"MFA type: {login_res['desc']}. Code generated.")
            else:
                mfa_types = {
                    "TTP": "из приложения с кодами",
                    "MAX": "из макса",
                    "SMS": "из смс"
                }
                desc = login_res.get('desc', '')
                source = mfa_types.get(desc, desc)
                mfa_code = input(f"Введите код {source}: ")
            login_res = await client.esia_mfa(mfa_code, login_res)
            
        tokens = await client.esia_login_end(login_res)
        access_token = tokens['access_token']
        save_output("tokens", tokens)

        # 1. get_info
        print("Getting info...")
        info = await client.get_info(access_token)
        save_output("info", info)

        if not info:
            print("No info returned, cannot proceed.")
            return

        student_id = info[0]['id']

        # 2. get_server_id
        server_id = await client.get_server_id(access_token)
        save_output("server_id", {"server_id": server_id})

        # 3. get_diary
        print("Getting diary...")
        diary = await client.get_diary(access_token, student_id)
        save_output("diary", diary)

        # 4. get_school_year
        print("Getting school year...")
        school_year = await client.get_school_year(access_token, student_id)
        save_output("school_year", school_year)
        now_year = school_year.get("nowYear")

        if now_year:
            # 5. get_totals
            totals = await client.get_totals(access_token, student_id, now_year)
            save_output("totals", totals)

            # 6. get_terms
            terms = await client.get_terms(access_token, student_id, now_year)
            save_output("terms", terms)
            
            # 7. get_subjects
            subjects = await client.get_subjects(access_token, student_id, now_year, diary=diary)
            save_output("subjects", subjects)

        # 8. get_announcements
        announcements = await client.get_announcements(access_token, student_id)
        save_output("announcements", announcements)

        # 9. get_inbox_mails
        inbox = await client.get_inbox_mails(access_token, student_id)
        save_output("inbox_mails", inbox)

        print("Testing completed successfully.")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
