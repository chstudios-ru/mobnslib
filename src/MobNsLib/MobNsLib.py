import logging, httpx, asyncio
from datetime import datetime, timedelta

class HTMLTruncateHandler(logging.FileHandler):
    """Специальный обработчик для файла, который режет HTML"""
    def emit(self, record):
        original_msg = record.msg
        msg_lower = record.msg.lower()
        # Если в сообщении есть признаки HTML — режем его
        if "<!doctype html>" in msg_lower:
            record.msg = "<!DOCTYPE html>..."

        sensitive_keys = ["access", "code=ey", "classmeeting"]
        if any(key in msg_lower for key in sensitive_keys):
            # Проверяем, не обрезали ли мы её уже (на случай длинных цепочек)
            if len(record.msg) > 250:
                record.msg = record.msg[:250] + "..."
        super().emit(record)
        self.flush()

class NoDataInResponse(Exception):
    def __init__(self, message="no expected data in response"):
        super().__init__(message)

class NoLoginOrPassword(Exception):
    def __init__(self, message="no login or password"):
        super().__init__(message)

class UnexpectedResponse(Exception):
    def __init__(self, message="unexpected response"):
        super().__init__(message)

class WrongLoginOrPassword(Exception):
    def __init__(self, message="wrong login or password"):
        super().__init__(message)

class nsLib:
    def __init__(self, url, logName=None, log_level=None):
        self.session = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
            timeout=httpx.Timeout(30.0),
            follow_redirects=True
        )

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
        self.appVer = '1.3.9'
        self.lng = "ru"

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

    async def esiaLogin(self, login=None, password=None):
        session = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            cookies=httpx.Cookies()
        )
        log = self.log

        data = {'mobile':'1'}
        response = await session.post(
            f"{self.url}webapi/auth/login-state",
            data=data
        )
        loginState = response.text
        loginState = loginState.replace('"','')
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        response = await session.get(
            f"{self.url}webapi/sso/esia/crosslogin",
            params={
                'loginState':loginState,
                'esia_permissions':'1',
                'esia_role':'1'
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        pattern = '%d-%m-%Y_%H-%M-%S'
        ondate = datetime.now().strftime(pattern)
        response = await session.get(
            f"{self.url2}rs/dscl",
            params={
            'ondate':ondate
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")
        
        if not (login or password):
            log.error("No login or password")
            log.error("no login or password", exc_info=True)
            raise NoLoginOrPassword()

        response = await session.post(
            f"{self.url2}aas/oauth2/api/login/", 
            json={
                'login':login,
                'password':password
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")
        cookies = []
        for cookie in session.cookies.jar:
            cookies.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
            })
        await session.aclose()
        
        if response.status_code == 201:
            log.error("Неправильный логин или пароль")
            raise WrongLoginOrPassword()
        if response.json().get('action') == 'ENTER_MFA':
            try:
                tmp = response.json()
                self.mfa_type_asked = tmp['mfa_details']['type']
                sth = {
                    'status':tmp['action'],
                    'desc':tmp['mfa_details']['type'],
                    'details':tmp['mfa_details'],
                    'loginState':loginState,
                    'cookies':cookies
                }
            except (KeyError, IndexError, TypeError) as e:
                log.error("no expected data in response", exc_info=True)
                raise NoDataInResponse() from e
            
            return sth
        
        if response.json().get('action') == 'DONE':
            try:
                tmp = response.json()
                rnd = {
                    'status':tmp['action'],
                    'redirect_url':tmp['redirect_url'],
                    'loginState':loginState,
                    'cookies':cookies
                }
            except (KeyError, IndexError, TypeError) as e:
                log.error("no expected data in response", exc_info=True)
                raise NoDataInResponse() from e

            return rnd

        log.error("unexpected response", exc_info=True)
        raise UnexpectedResponse()

    async def esiaMFA(self, mfa_code, LoginData):
        session = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            cookies=httpx.Cookies()
        )
        log = self.log
        for c in LoginData['cookies']:
            session.cookies.set(c['name'], c['value'], domain=c['domain'], path=c['path'])

        url = {
            'TTP':'totp',
            'SMS':'otp',
            'MAX':'otp-max'
        }

        response = await session.post(
            f"{self.url2}aas/oauth2/api/login/{url[LoginData['desc']]}/verify",
            params={
                'code':mfa_code
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        if response.json().get("action") == "MAX_QUIZ":
            response = await session.post(
                f"{self.url2}aas/oauth2/api/login/quiz-max/skip"
            )
            log.info(f"{response} {response.url}")
            log.debug(f"{response.text}")

        cookies = []
        for cookie in session.cookies.jar:
            cookies.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
            })
        await session.aclose()
        try:
            temp = response.json()
            rnd = {
                'status':temp['action'],
                'redirect_url':temp['redirect_url'],
                'loginState':LoginData['loginState'],
                'cookies':cookies
            }
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e

        return rnd

    async def esiaLoginEnd(self, LoginOrMfaData):
        session = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
        log = self.log
        for c in LoginOrMfaData['cookies']:
            session.cookies.set(c['name'], c['value'], domain=c['domain'], path=c['path'])

        response = await session.get(LoginOrMfaData['redirect_url'])
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        response = await session.get(
            f"{self.url}webapi/sso/esia/account-info", 
            params={'loginState':LoginOrMfaData['loginState']}
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        try:
            tmp = response.json()        
            data = {
                'idp':'esia',
                'loginState':LoginOrMfaData['loginState'],
                'LoginType':'8',
                'lscope':tmp['users'][0]['id']
            }
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e
        response = await session.post(
            f"{self.url}webapi/auth/login",
            data=data)
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        try:
            headers = {'at':response.json()['at']}
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e
        response = await session.get(
            f"{self.url}webapi/mysettings/mobile/pincode",
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
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e
        response = await session.post(
            f"{self.url3}connect/token",
            data=data
        )
        tmp = response.json()
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        created_at = (await session.get(
            f'{self.url1}api/v1/mobile/parent/time'
        )).text.replace('"','')

        try:
            tokens = {
                'access_token':tmp['access_token'],
                'refresh_token':tmp['refresh_token'],
                'expires_in':int(tmp['expires_in']),
                'created_at':int(created_at)
            }
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e

        response = await session.get(
            f"{self.url}logout",
            headers=headers
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")
        await session.aclose()

        return tokens

    async def getInfo(self, headers):
        log = self.log

        response = await self.session.get(
            f"{self.api}users",
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
            if tmp[0]['isStudent']:
                role = 'student'
            elif tmp[0]['isParent']:
                role = 'parent'
            elif tmp[0]['isStaff']:
                role = 'staff'
            info = {
                'firstName':tmp[0]['firstName'],
                'nickName':tmp[0]['nickName'],
                'role':role,
                'schoolName':tmp[0]['organizations'][0]['organization']['name'],
                'studentId':tmp[0]['id'],
                'classId':tmp[0]['organizations'][0]['classes'][0]['classId']
            }
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e

        return info

    async def getServerId(self, headers):
        log = self.log

        response = await self.session.get(
            f"{self.url3}users/endpoints", 
            headers=headers,
            params={
                'appVersion':self.appVer,
                'lng':self.lng
            }
        )
        try:
            serverId = response.json()[0].get('serverId')
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e
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

    async def diary(
            self,
            headers,
            startDate=None,
            studentId=None,
            endDate=None,
            day= None,
            pattern='%Y-%m-%d'):
        log = self.log

        if not studentId:
            info = await self.getInfo(headers=headers)
            studentId = info.get('studentId')
        if not (startDate and endDate):
            startDate, endDate = self.get_week_range(pattern, day)

        response = await self.session.get(
            f"{self.api}classmeetings",
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

        return response.json()

    async def tokenRefresh(self, refresh_token):
        log = self.log

        data = {
            'grant_type':'refresh_token',
            'refresh_token':refresh_token,
            'client_id':'parent-mobile',
            'client_secret':self.client_secret
        }
        response = await self.session.post(
            f"{self.url3}connect/token",
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
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e

        return tokens

    async def getVer(self):
        response = await self.session.get(
            f"{self.url1}api/v1/mobile/parent/app-versions/published",
            params={
                'appVersion':self.appVer,
                'lng':self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return response.text.replace('"','')

    async def getAssignments(self, headers, studentId, classmetingIds=None, diary=None, limit=10, delay=0.1):
        log = self.log
        
        if diary and not classmetingIds:
            classmetingIds = []
            for day in diary:
                id = day.get("classmeetingId", [])
                if id:
                    classmetingIds.append(id)
        assigns = []
        for i in range(0, len(classmetingIds), limit):
            chunk = classmetingIds[i : i + limit]
            response = await self.session.get(
                f"{self.api}assignments",
                headers=headers,
                params = {
                    "studentId":studentId,
                    "classmeetingId":chunk,
                    "appVersion":self.appVer,
                    "lng":self.lng
                }
            )
            log.info(f"{response} {response.url}")
            log.debug(f"{response.text}")
            try:
                assigns.extend(response.json())
            except (KeyError, IndexError, TypeError) as e:
                log.error("no expected data in response", exc_info=True)
                raise NoDataInResponse() from e
            
            if i + limit < len(classmetingIds):
                log.debug(f"Waiting {delay}s before next request...")
                await asyncio.sleep(delay)

        return assigns

    async def loadAttachment(self, headers, assignmentId):
        log = self.log

        response = await self.session.get(
            f"{self.api}attachments",
            headers=headers,
            params = {
                "assignmentId":assignmentId,
                "appVersion":self.appVer,
                "lng":self.lng
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        temp = response.json()
        try:
            attachmentId = temp[0]["attachmentId"]
            if not attachName:
                attachName = temp[0]['fileName']
        except (KeyError, IndexError, TypeError) as e:
                log.error("no expected data in response", exc_info=True)
                raise NoDataInResponse() from e

        temp.append({'url':f"{self.api}attachments/{attachmentId}"})
        return temp

    async def getSchoolYear(self, headers, studentId):
        log = self.log

        response = await self.session.get(
            f"{self.api}education",
             headers=headers,
             params = {
                 'studentId':studentId,
                 'appVersion':self.appVer,
                 'lng':self.lng
             }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        try:
            json_data = response.json()
            year = {
                'nowYear':json_data[0]['schoolyear']['id'],
                'allYears':json_data
            }
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e

        return year

    async def getSubjects(self, headers, studentId, schoolYearId, diary=None):
        log = self.log

        response = await self.session.get(
            f"{self.api}subjects",
            headers=headers,
            params = {
                'studentId':studentId,
                'schoolYearId':schoolYearId,
                'appVersion':self.appVer,
                'lng':self.lng
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")
        subjects = response.json()

        if diary:
            group_mapping = {
                item['subjectId']: item['subjectGroupId'] 
                for item in diary if item.get('subjectGroupId')
                }
            for subject in subjects:
                subject['subjectGroupId'] = group_mapping.get(subject['id'])

        return subjects

    async def getTotals(self, headers, studentId, schoolYearId):
        log = self.log

        response = await self.session.get(
            f"{self.api}totals",
             headers=headers,
             params = {
                 'studentId':studentId,
                 'schoolYearId':schoolYearId,
                 'appVersion':self.appVer,
                 'lng':self.lng
             }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        data = response.json()
        return data

    async def getTerms(self, headers, studentId, schoolYearId):
        log = self.log

        response = await self.session.get(
            f"{self.api}terms",
             headers=headers,
             params = {
                 'studentId':studentId,
                 'schoolYearId':schoolYearId,
                 'appVersion':self.appVer,
                 'lng':self.lng
             }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        return response.json()

    async def getAnnoucements(self, headers, studentId):
        log = self.log

        response = await self.session.get(
            f"{self.api}announcements",
             headers=headers,
             params = {
                 'studentId':studentId,
                 'appVersion':self.appVer,
                 'lng':self.lng
             }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        return response.json()

    async def Events(self, event_type, headers, studentId, periodDays, subjectGroupIds, limit=None, offset=None):
        log = self.log
        if not limit:
            limit = 100
        if not offset:
            offset = 0

        response = await self.session.get(
            f"{self.api}period-events",
             headers=headers,
             params = {
                 'studentId':studentId,
                 'limit':limit,
                 'offset':offset,
                 'subjectGroupId':subjectGroupIds,
                 'Types':event_type,
                 'periodDays':periodDays,
                 'appVersion':self.appVer,
                 'lng':self.lng
             }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        return response.json()

    async def getHomeworkInfoEvents(self, headers, studentId, periodDays, subjectGroupIds=None, limit=None, offset=None):
        return await self.Events('HomeworkInfo', headers, studentId, periodDays, subjectGroupIds, limit, offset)

    async def getResultInfoEvents(self, headers, studentId, periodDays, subjectGroupIds=None, limit=None, offset=None):
        return await self.Events('ResultInfo', headers, studentId, periodDays, subjectGroupIds, limit, offset)

    async def getTermTotalInfoEvents(self, headers, studentId, periodDays, subjectGroupIds=None, limit=None, offset=None):
        return await self.Events('TermTotalInfo', headers, studentId, periodDays, subjectGroupIds, limit, offset)

    async def getYearTotalInfoEvents(self, headers, studentId, periodDays, subjectGroupIds=None, limit=None, offset=None):
        return await self.Events('YearTotalInfo', headers, studentId, periodDays, subjectGroupIds, limit, offset)

    async def getAllEvents(self, headers, studentId, periodDays, subjectGroupIds=None, limit=None, offset=None):
        return await self.Events(['HomeworkInfo', 'ResultInfo', 'TermTotalInfo', 'YearTotalInfo'], headers, studentId, periodDays, subjectGroupIds, limit, offset)

    async def getMailUnreadCount(self, headers, studentId):
        log = self.log

        response = await self.session.get(
            f"{self.api}mail/messages/unread-count",
            headers=headers,
            params={
                'userId':studentId,
                'appVersion':self.appVer,
                'lng':self.lng
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        return response.text

    async def getMails(self, headers):
        log = self.log
        # Ох зря я сюда полез...

    @staticmethod
    async def getServerList():
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.get(
                f"https://mobile.ir-tech.ru/api/v1/mobile/parent/end-points",
                params={
                    'appVersion':'1.3.9',
                    'lng':'ru'
                }
            )
            
            data = response.json()
            return data

