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

class NoDataInResponse(Exception):
    def __init__(self, message="no expected data in response"):
        # 1. Сначала вызываем логгер
        nsLib.self.log.error(message, exc_info=True)
        
        # 2. Обязательно вызываем конструктор базового класса Exception
        super().__init__(message)

class NoLoginOrPassword(Exception):
    def __init__(self, message="no login or password"):
        # 1. Сначала вызываем логгер
        nsLib.self.log.error(message, exc_info=True)
        
        # 2. Обязательно вызываем конструктор базового класса Exception
        super().__init__(message)

class UnexpectedResponse(Exception):
    def __init__(self, message="unexpected response"):
        # 1. Сначала вызываем логгер
        nsLib.self.log.error(message, exc_info=True)
        
        # 2. Обязательно вызываем конструктор базового класса Exception
        super().__init__(message)

class NoDataInFile(Exception):
    def __init__(self, message="an error occurred while extracting data from a file"):
        # 1. Сначала вызываем логгер
        nsLib.self.log.error(message, exc_info=True)
        
        # 2. Обязательно вызываем конструктор базового класса Exception
        super().__init__(message)

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

    def esiaLogin(self, login=None, password=None):
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
        
        if not (login or password):
            log.error("No login or password")
            raise 

        response = self.session.post(
            f"{self.url2}/aas/oauth2/api/login/", 
            json={
                'login':login,
                'password':password
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")
        
        if str(response.status_code) == '201':
            log.info(f"{response} {response.url}")
            log.error(f"Неправильный логин или пароль {response.text}")
            raise ValueError()
        if response.json().get('action') == 'ENTER_MFA':
            try:
                tmp = response.json()
                self.mfa_type_asked = tmp['mfa_details']['type']
                sth = {
                    'status':tmp['action'],
                    'desc':tmp['mfa_details']['type'],
                    'details':tmp['mfa_details']
                }
            except (KeyError, IndexError, TypeError):
                raise NoDataInResponse()
            
            return sth
        
        if response.get('action') == 'DONE':
            try:
                tmp = response.json()
                self.redir_url = tmp['redirect_url']
                rnd = {'status':tmp['action']}
            except (KeyError, IndexError, TypeError):
                raise NoDataInResponse()

            return rnd

        log.error(f"Unexpected response")
        raise 
        
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

        try:
            self.redir_url = response.json().get('redirect_url')
            rnd = {'status':response.json().get('action')}
        except (KeyError, IndexError, TypeError):
            raise NoDataInResponse()

        return rnd
            
    def esiaLoginEnd(self, filename=None):
        log = self.log

        response = self.session.get(self.redir_url)
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        response = self.session.get(
            f"{self.url}/webapi/sso/esia/account-info", 
            params={'loginState':self.loginState}
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        try:
            tmp = response.json()        
            data = {
                'idp':'esia',
                'loginState':self.loginState,
                'LoginType':'8',
                'lscope':tmp['users'][0]['id']
            }
        except (KeyError, IndexError, TypeError):
            raise NoDataInResponse()
        response = self.session.post(
            f"{self.url}/webapi/auth/login",
            data=data)
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        try:
            headers = {'at':response.json()['at']}
        except (KeyError, IndexError, TypeError):
            raise NoDataInResponse()
        response = self.session.get(
            f"{self.url}/webapi/mysettings/mobile/pincode",
            headers=headers
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        try:
            data = {
                'grant_type':'urn:ietf:params:oauth:grant-type:device_code',
                'device_code':response.json()['userCode'],
                'client_id':'parent-mobile',
                'client_secret':self.client_secret
            }
        except (KeyError, IndexError, TypeError):
            raise NoDataInResponse()
        response = self.session.post(
            f"{self.url3}/connect/token",
            data=data
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        try:
            tmp = response.json()
            tokens = {
                'access_token':tmp['access_token'],
                'refresh_token':tmp['refresh_token'],
                'expires_in':tmp['expires_in']
            }
        except (KeyError, IndexError, TypeError):
            raise NoDataInResponse()

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

        try:
            tmp = response.json()
            info = {
                'firstName':tmp[0]['firstName'],
                'schoolId':tmp[0]['organizations'][0]['organization']['id'],
                'studentId':tmp[0]['id'],
                'classId':tmp[0]['organizations'][0]['classes'][0]['classId']
            }
        except (KeyError, IndexError, TypeError):
            raise NoDataInResponse()

        return info
    
    def getServerId(self, headers):
        log = self.log

        response = self.session.get(
            f"{self.url3}/users/endpoints", 
            headers=headers,
            params={
                'appVersion':self.appVer,
                'lng':self.lng
            }
        )
        try:
            serverId = response.json()[0].get('serverId')
        except (KeyError, IndexError, TypeError):
            raise NoDataInResponse()
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        return serverId

    def get_week_range(self, pattern, day=None):
        if not day:
            date = datetime.now()
        else:
            date = datetime.strptime(day, pattern)

        start_of_week = date - timedelta(days=date.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        start_of_week = start_of_week.strftime(pattern)
        end_of_week = end_of_week.strftime(pattern)

        return start_of_week, end_of_week

    def diary(
            self,
            headers,
            diaryName,
            startDate=None,
            studentId=None,
            endDate=None,
            day= None,
            pattern='%Y-%m-%d'):
        log = self.log

        if not studentId:
            studentId = self.getInfo(headers=headers).get('studentId')
        if not (startDate and endDate):
            startDate, endDate = self.get_week_range(pattern, day)

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
            try:
                refresh_token = json.load(ddf)['refresh_token']
            except (KeyError, IndexError, TypeError):
                raise NoDataInFile()

        data = {
            'grant_type':'refresh_token',
            'refresh_token':refresh_token,
            'client_id':'parent-mobile',
            'client_secret':self.client_secret
        }
        response = self.session.post(
            f"{self.url3}/connect/token",
            data=data
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        try:
            tmp = response.json()
            tokens = {
                'access_token':tmp['access_token'],
                'refresh_token':tmp['refresh_token'],
                'expires_in':tmp['expires_in']
            }
        except (KeyError, IndexError, TypeError):
            raise NoDataInResponse()
        with open(filename, 'w', encoding='utf_8') as n:
            json.dump(tokens, n)

        return {'authorization':f"Bearer {tokens.get('access_token')}"}

    def getToken(self, filename):
        if not os.path.exists(filename):
            raise FileNotFoundError("Файл не найден")
        with open(filename, 'r', encoding='utf-8') as df:
            try:
                access_token = json.load(df)['access_token']
            except (KeyError, IndexError, TypeError):
                raise NoDataInFile()

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

    def getAssignments(self, headers, studentId, diaryName=None, assignmentFile=None, classmeetingId=None, diary=None):
        if diaryName:
            with open(diaryName, 'r', encoding='utf-8') as d:
                diary = json.load(d)
        
        if diary:
            assignIds = []
            tasks = []
            for i in diary:
                temp = i['assignmentId']
                if temp:
                    assignIds.extend(temp)
            
            return assignIds

        if classmeetingId:
            self.session.get(
                f"{self.url}/api/mobile/assignments",
                params = {
                    'studentId':studentId,
                    'classmeetingId':classmeetingId,
                    'appVersion':self.appVer,
                    'lng':self.lng
                }
            )