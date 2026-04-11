import getpass, requests, json, os, logging
from datetime import datetime, timedelta

class HTMLTruncateHandler(logging.FileHandler):
    """Специальный обработчик для файла, который режет HTML"""
    def emit(self, record):
        msg_lower = record.msg.lower()
        # Если в сообщении есть признаки HTML — режем его
        if "<!doctype html>" in msg_lower:
            record.msg = "<!DOCTYPE html>..."

        sensitive_keys = ["classmeetingid", "access", "code=ey"]
        if any(key in msg_lower for key in sensitive_keys):
            # Проверяем, не обрезали ли мы её уже (на случай длинных цепочек)
            if len(record.msg) > 50:
                record.msg = record.msg[:50] + "..."
        super().emit(record)

class nsLib:
    def __init__(self, url, logName=None, log_level=None):
        self.session = requests.Session()

        self.url = url
        self.url1 = 'https://mobile.ir-tech.ru'
        self.url2 = 'https://esia.gosuslugi.ru'
        self.url3 = 'https://identity.ir-tech.ru'
        self.appVer = '1.3.9'
        self.lng = "ru"
        self.client_secret = '04064338-13df-4747-8dea-69849f9ecdf0'

        logger = logging.getLogger("MyBigScript")
        logger.setLevel(logging.DEBUG)
        self.log = logger

        level = {
            1: logging.ERROR,
            2: logging.WARNING,
            3: logging.INFO,
            4: logging.DEBUG
        }
        
        if logName:
            file_handler = HTMLTruncateHandler("debug.log", encoding="utf-8", mode='w')
            target_level = level.get(log_level, logging.CRITICAL)
            file_handler.setLevel(target_level)
            file_format = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s')
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
            self.log.info(f"Log_level {log_level}")

    def esiaLogin(self, login_esia=None):
        log = self.log

        data = {'mobile':'1'}
        response = self.session.post(
            f"{self.url}/webapi/auth/login-state",
            data=data
        )
        self.loginState = response.text
        self.loginState = self.loginState.replace('"','')
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        response = self.session.get(
            f"{self.url}/webapi/sso/esia/crosslogin",
            params={
                'loginState':self.loginState,
                'esia_permissions':'1',
                'esia_role':'1'
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        pattern = '%d-%m-%Y_%H-%M-%S'
        ondate = datetime.now().strftime(pattern)
        response = self.session.get(
            f"{self.url2}/rs/dscl",
            params={
            'ondate':ondate
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")
        
        if login_esia == None:
            login_esia = {
            'login': input("Ваш логин:"),
            'password': getpass.getpass("Ваш пароль:")
            }
        response = self.session.post(
            f"{self.url2}/aas/oauth2/api/login/", 
            json=login_esia
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")
        print(response.text)
        if str(response.status_code) == '201':
            log.info(f"{response} {response.url}")
            log.error(f"Неправильный логин или пароль {response.text}")
            raise ValueError("Неправильные данные")
        if response.json().get('action') == 'ENTER_MFA':
            self.mfa_type_asked = response.json().get('mfa_details').get('type')

            return {'status':response.json().get('action'), 'desc':response.json().get('mfa_details').get('type'), 'details':response.json().get('mfa_details')}
        
        if response.get('action') == 'DONE':
            self.redir_url = response.json().get('redirect_url')

            return {'status':response.json().get('action')}
        
    def esiaMFA(self, mfa_code):
        log = self.log

        url = {
            'TTP':'totp',
            'SMS':'otp',
            'MAX':'otp-max'
        }

        response = self.session.post(
            f"{self.url2}/aas/oauth2/api/login/{url[self.mfa_type_asked]}/verify",
            params={
                'code':mfa_code
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        if response.json().get("action") == "MAX_QUIZ":
            print(response.text)
            response = self.session.post(
                f"{self.url2}/aas/oauth2/api/login/quiz-max/skip"
            )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        self.redir_url = response.json().get('redirect_url')

        return {'status':response.json().get('action')}
            
    def esiaLoginEnd(self, filename=None):
        log = self.log

        response = self.session.get(self.redir_url)
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        response = self.session.get(
            f"{self.url}/webapi/sso/esia/account-info", 
            params={'loginState':self.loginState}
        )
        tmp = response.json()
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        id = tmp['users'][0]['id']
        data = {
            'idp':'esia',
            'loginState':self.loginState,
            'LoginType':'8',
            'lscope':id
        }
        response = self.session.post(
            f"{self.url}/webapi/auth/login",
            data=data)
        at = response.json()['at']
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        headers = {
            'at':at
        }
        response = self.session.get(
            f"{self.url}/webapi/mysettings/mobile/pincode",
            headers=headers
        )
        device_code = response.json()['userCode']
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        data = {
            'grant_type':'urn:ietf:params:oauth:grant-type:device_code',
            'device_code':device_code,
            'client_id':'parent-mobile',
            'client_secret':self.client_secret
        }
        response = self.session.post(
            f"{self.url3}/connect/token",
            data=data
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        tokens = {
            'access_token':response.json()['access_token'],
            'refresh_token':response.json()['refresh_token'],
            'expires_in':response.json()['expires_in']
        }

        response = self.session.get(
            f"{self.url}/logout",
            headers=headers
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        if filename:
            with open(filename, 'w', encoding='utf_8') as n:
                json.dump(tokens, n)

        return {'authorization':f"Bearer {tokens.get('access_token')}"}

    def getInfo(self, headers):
        log = self.log

        response = self.session.get(
            f"{self.url3}/users/endpoints", 
            headers=headers,
            params={
                'appVersion':self.appVer,
                'lng':self.lng
            }
        )
        serverId = response.json()[0]['serverId']
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        response = self.session.get(
            f"{self.url}/api/mobile/users",
            headers=headers,
            params={
                'v':'2',
                'appVersion':self.appVer,
                'lng':self.lng
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        info = {
            'serverId':serverId,
            'firstName':response.json()[0]['firstName'],
            'schoolId':response.json()[0]['organizations'][0]['organization']['id'],
            'studentId':response.json()[0]['id'],
            'classId':response.json()[0]['organizations'][0]['classes'][0]['classId']
        }

        return info

    def get_week_range(self, pattern, date=None):
        if date is None:
            date = datetime.now()

        start_of_week = date - timedelta(days=date.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        start_of_week = start_of_week.strftime(pattern)
        end_of_week = end_of_week.strftime(pattern)

        return start_of_week, end_of_week

    def diary(self, headers, diaryName, startDate=None, studentId=None, endDate=None, day=None):
        log = self.log

        if studentId == None:
            studentId = self.getInfo(headers=headers).get('studentId')
        if startDate == None and endDate == None:
            startDate, endDate = self.get_week_range('%Y-%m-%d', day)

        response = self.session.get(
            f"{self.url}/api/mobile/classmeetings",
            params={
                'studentIds':studentId,
                'startDate':startDate,
                'endDate':endDate,
                'extraActivity':'null',
                'appVersion':self.appVer,
                'lng':self.lng 
            },
            headers=headers
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        with open(diaryName, 'w', encoding='utf_8') as diary:
            diary.write(response.text)
        
        return response.json()

    def tokenRefresh(self, filename):
        log = self.log

        if not os.path.exists(filename):
            print('Файл не найден')
            return False
        with open(filename, 'r', encoding='utf-8') as ddf:
            refresh_token = json.load(ddf)['refresh_token']

        data = {
            'grant_type':'refresh_token',
            'refresh_token':refresh_token,
            'client_id':'parent-mobile',
            'client_secret':self.client_secret
        }
        response = requests.post(
            f"{self.url3}/connect/token",
            data=data
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        tokens = {
                'access_token':response.json()['access_token'],
                'refresh_token':response.json()['refresh_token'],
                'expires_in':response.json()['expires_in']
            }
        with open(filename, 'w', encoding='utf_8') as n:
            json.dump(tokens, n)

        return {'authorization':f"Bearer {tokens.get('access_token')}"}

    def getToken(self, filename):
        if not os.path.exists(filename):
            print('Файл не найден')
            return False
        with open(filename, 'r', encoding='utf-8') as df:
            access_token = json.load(df)['access_token']

        return {'authorization':f"Bearer {access_token}"}
    
    def getVer(self):
        response = self.session.get(
            f"{self.url1}/api/v1/mobile/parent/app-versions/published",
            params={
                'appVersion':self.appVer,
                'lng':self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return response.text.replace('"','')
    