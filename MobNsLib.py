import json, os, logging, httpx, asyncio, aiofiles
import redis.asyncio as redis
from datetime import datetime, timedelta

from requests import session

class HTMLTruncateHandler(logging.FileHandler):
    """Специальный обработчик для файла, который режет HTML"""
    def emit(self, record):
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

class NoDataInResponse(Exception):
    def __init__(self, message="no expected data in response"):
        super().__init__(message)

class NoLoginOrPassword(Exception):
    def __init__(self, message="no login or password"):
        super().__init__(message)

class UnexpectedResponse(Exception):
    def __init__(self, message="unexpected response"):
        super().__init__(message)

class NoDataInFile(Exception):
    def __init__(self, message="an error occurred while extracting data from a file"):
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
        self.url1 = 'https://mobile.ir-tech.ru'
        self.url2 = 'https://esia.gosuslugi.ru'
        self.url3 = 'https://identity.ir-tech.ru'
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
        self.loginState = response.text
        self.loginState = self.loginState.replace('"','')
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        response = await session.get(
            f"{self.url}webapi/sso/esia/crosslogin",
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
        response = await session.get(
            f"{self.url2}/rs/dscl",
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
            f"{self.url2}/aas/oauth2/api/login/", 
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
                    'cookies':cookies
                }
            except (KeyError, IndexError, TypeError) as e:
                log.error("no expected data in response", exc_info=True)
                raise NoDataInResponse() from e

            return rnd

        log.error("unexpected response", exc_info=True)
        raise UnexpectedResponse()

    async def esiaMFA(self, mfa_code, mfa_type,LoginCookies):
        session = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            cookies=httpx.Cookies()
        )
        log = self.log
        for c in LoginCookies:
            session.cookies.set(c['name'], c['value'], domain=c['domain'], path=c['path'])

        url = {
            'TTP':'totp',
            'SMS':'otp',
            'MAX':'otp-max'
        }

        response = await session.post(
            f"{self.url2}/aas/oauth2/api/login/{url[mfa_type]}/verify",
            params={
                'code':mfa_code
            }
        )
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        if response.json().get("action") == "MAX_QUIZ":
            response = await session.post(
                f"{self.url2}/aas/oauth2/api/login/quiz-max/skip"
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
                'cookies':cookies
            }
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e

        return rnd

    async def esiaLoginEnd(self, redirect_url, LoginOrMfaCookies, filename=None):
        session = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
        log = self.log
        for c in LoginOrMfaCookies:
            session.cookies.set(c['name'], c['value'], domain=c['domain'], path=c['path'])

        response = await session.get(redirect_url)
        log.info(f"{response} {response.url}")
        log.debug(f"{response.text}")

        response = await session.get(
            f"{self.url}webapi/sso/esia/account-info", 
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

        if filename:
            async with aiofiles.open(filename, 'w', encoding='utf_8') as n:
                await n.write(json.dumps(tokens, ensure_ascii=False, indent=4))

        return {'authorization':f"Bearer {tokens.get('access_token')}"}

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
            info = {
                'firstName':tmp[0]['firstName'],
                'schoolId':tmp[0]['organizations'][0]['organization']['id'],
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
            f"{self.url3}/users/endpoints", 
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
            diaryName,
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

        async with aiofiles.open(diaryName, 'w', encoding='utf_8') as diary:
            await diary.write(json.dumps(response.json(), ensure_ascii=False, indent=4))
        
        return response.json()

    async def tokenRefresh(self, filename):
        log = self.log

        if not os.path.exists(filename):
            print('Файл не найден')
            return False
        async with aiofiles.open(filename, 'r', encoding='utf-8') as ddf:
            try:
                refresh_token = json.loads(await ddf.read())['refresh_token']
            except (KeyError, IndexError, TypeError) as e:
                log.error("an error occurred while extracting data from a file", exc_info=True)
                raise NoDataInFile()

        data = {
            'grant_type':'refresh_token',
            'refresh_token':refresh_token,
            'client_id':'parent-mobile',
            'client_secret':self.client_secret
        }
        response = await self.session.post(
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
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e
        async with aiofiles.open(filename, 'w', encoding='utf_8') as n:
            await n.write(json.dumps(response.json(), ensure_ascii=False, indent=4))

        return {'authorization':f"Bearer {tokens.get('access_token')}"}
    
    async def getHeader(self, filename):
        if not os.path.exists(filename):
            raise FileNotFoundError("Файл не найден")
        async with aiofiles.open(filename, 'r', encoding='utf-8') as df:
            try:
                access_token = json.loads(await df.read())['access_token']
            except (KeyError, IndexError, TypeError) as e:
                self.log.error("an error occurred while extracting data from a file", exc_info=True)
                raise NoDataInFile()

        return {'authorization':f"Bearer {access_token}"}

    async def getVer(self):
        response = await self.session.get(
            f"{self.url1}/api/v1/mobile/parent/app-versions/published",
            params={
                'appVersion':self.appVer,
                'lng':self.lng
            }
        )
        self.log.info(f"{response} {response.url}")
        self.log.debug(f"{response.text}")
        return response.text.replace('"','')

    async def getAssignments(self, headers, studentId, diaryName, assignmentFile, diary=None):
        log = self.log
        limit = 10
        delay = 0.1

        async with aiofiles.open(diaryName, 'r', encoding='utf-8') as d:
            diary = json.loads(await d.read())
        
        if diary:
            assignIds = []
            for day in diary:
                id = day.get("classmeetingId", [])
                if id:
                    assignIds.append(id)
        assigns = []
        for i in range(0, len(assignIds), limit):
            chunk = assignIds[i : i + limit]
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
            
            if i + limit < len(assignIds):
                log.debug(f"Waiting {delay}s before next request...")
                await asyncio.sleep(delay)
            

        async with aiofiles.open(assignmentFile, 'w', encoding='utf-8') as dtrf:
            await dtrf.write(json.dumps(assigns, ensure_ascii=False, indent=4))

    async def loadAttachment(self, headers, assignmentId, save=False, attachName=None):
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

        if save:
            response = await self.session.get(
                f"{self.api}attachments/{attachmentId}",
                headers=headers
            )
            log.info(f"{response} {response.url}")

            async with aiofiles.open(attachName, 'w', encoding='utf-8') as atfile:
                atfile.write(response.text)

        else:
            temp.append({'url':f"{self.api}attachments/{attachmentId}"})
        return temp

    async def getSchoolYear(self, headers, studentId, fileName=None):
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

        if fileName:
            async with aiofiles.open(fileName, 'w', encoding='utf-8') as syf:
                await syf.write(json.dumps(response.json(), ensure_ascii=False, indent=4))
        try:
            year = response.json()[0]['schoolyear']['id']
        except (KeyError, IndexError, TypeError) as e:
            log.error("no expected data in response", exc_info=True)
            raise NoDataInResponse() from e
        return year

    async def getSubjects(self, headers, studentId, schoolYearId, fileName=None, diaryName=None):
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
        if diaryName and fileName:
            async with aiofiles.open(diaryName, 'r', encoding='utf-8') as d:
                diary = json.loads(await d.read())

            group_mapping = {
                item['subjectId']: item['subjectGroupId'] 
                for item in diary if item.get('subjectGroupId')
                }
            for subject in subjects:
                subject['subjectGroupId'] = group_mapping.get(subject['id'])

            async with aiofiles.open(fileName, 'w', encoding='utf-8') as d:
                await d.write(json.dumps(subjects, ensure_ascii=False, indent=4))

        elif fileName:
            async with aiofiles.open(fileName, 'w', encoding='utf-8') as syf:
                await syf.write(json.dumps(subjects, ensure_ascii=False, indent=4))

        return subjects

    async def getTotals(self, headers, studentId, schoolYearId, fileName=None):
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
        if fileName:
            async with aiofiles.open(fileName, 'w', encoding='utf-8') as syf:
                await syf.write(json.dumps(data, ensure_ascii=False, indent=4))
        return data

    async def getTerms(self, headers, studentId, schoolYearId, fileName=None):
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

        if fileName:
            async with aiofiles.open(fileName, 'w', encoding='utf-8') as syf:
                await syf.write(json.dumps(response.json(), ensure_ascii=False, indent=4))
        return response.json()

    async def getAnnoucements(self, headers, studentId, fileName=None):
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

        if fileName:
            async with aiofiles.open(fileName, 'w', encoding='utf-8') as syf:
                await syf.write(json.dumps(response.json(), ensure_ascii=False, indent=4))
        return response.json()

    async def Events(self, event_type, headers, studentId, periodDays, subjectGroupIds, fileName=None, limit=None, offset=None):
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

        if fileName:
            async with aiofiles.open(fileName, 'w', encoding='utf-8') as syf:
                await syf.write(json.dumps(response.json(), ensure_ascii=False, indent=4))
        return response.json()

    async def getHomeworkInfoEvents(self, headers, studentId, periodDays, subjectGroupIds=None, fileName=None, limit=None, offset=None):
        return await self.Events('HomeworkInfo', headers, studentId, periodDays, subjectGroupIds, fileName, limit, offset)

    async def getResultInfoEvents(self, headers, studentId, periodDays, subjectGroupIds=None, fileName=None, limit=None, offset=None):
        return await self.Events('ResultInfo', headers, studentId, periodDays, subjectGroupIds, fileName, limit, offset)

    async def getTermTotalInfoEvents(self, headers, studentId, periodDays, subjectGroupIds=None, fileName=None, limit=None, offset=None):
        return await self.Events('TermTotalInfo', headers, studentId, periodDays, subjectGroupIds, fileName, limit, offset)

    async def getYearTotalInfoEvents(self, headers, studentId, periodDays, subjectGroupIds=None, fileName=None, limit=None, offset=None):
        return await self.Events('YearTotalInfo', headers, studentId, periodDays, subjectGroupIds, fileName, limit, offset)

    async def getAllEvents(self, headers, studentId, periodDays, subjectGroupIds=None, fileName=None, limit=None, offset=None):
        return await self.Events(['HomeworkInfo', 'ResultInfo', 'TermTotalInfo', 'YearTotalInfo'], headers, studentId, periodDays, subjectGroupIds, fileName, limit, offset)

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
    async def getServerList(fileName=None):
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.get(
                f"https://mobile.ir-tech.ru/api/v1/mobile/parent/end-points",
                params={
                    'appVersion':'1.3.9',
                    'lng':'ru'
                }
            )
            
            data = response.json()
            if fileName:
                async with aiofiles.open(fileName, 'w', encoding='utf-8') as syf:
                    await syf.write(json.dumps(data, ensure_ascii=False, indent=4))
            return data

