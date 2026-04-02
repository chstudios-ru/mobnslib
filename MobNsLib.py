import getpass, requests, json, os
from datetime import datetime, timedelta

class nsLib:
    def __init__(self, url):
        self.session = requests.Session()

        url1 = 'https://mobile.ir-tech.ru'
        url2 = 'https://esia.gosuslugi.ru'
        url3 = 'https://identity.ir-tech.ru'
        appVer = '1.3.9'
        lng = "&lng=ru"
        self.vars = {
            'client_secret':"04064338-13df-4747-8dea-69849f9ecdf0",
            
            'url_1':url + "/webapi/auth/login-state",
            'url_2':url + "/webapi/sso/esia/crosslogin?loginState=",
            'url_2_end':"&esia_permissions=1&esia_role=1",
            'url_3':url + "/webapi/sso/esia/account-info?loginState=",
            'url_4':url + "/webapi/auth/login",
            'url_5':url + "/webapi/mysettings/mobile/pincode",
            'url_6':url + "/api/mobile/users?v=2&appVersion=" + appVer + lng,
            'url_logout':url + "/logout",
            'url_diary':url + "/api/mobile/classmeetings?studentIds=",
            'url_diary_end':"&extraActivity=null&appVersion=" + appVer + lng,
            'url_init':url + "/api/mobile/initialize?version=" + appVer,

            'url1_ver':f"{url1}/api/v1/mobile/parent/app-versions/published?appVersion={appVer}{lng}",

            'url2_1':url2 + "/rs/dscl?ondate=",
            'url2_2':url2 + "/aas/oauth2/api/login/",

            'url3_1':url3 + "/connect/token",
            'url3_2':url3 + "/users/endpoints?appVersion=" + appVer + lng
        }

    def esiaLogin(self, filename=None, login_esia=None):

        totp = {
            'TTP':'totp',
            'MAX':'из макса',
            'SMS':'из смс',
        }
        url = {
            'TTP':'totp',
            'SMS':'otp',
            'MAX':'otp-max'
        }
        data = {'mobile':'1'}
        response = self.session.post(self.vars['url_1'], data=data)
        loginState = response.text
        loginState = loginState.replace('"','')

        temp_url = self.vars['url_2'] + loginState + self.vars['url_2_end']
        response = self.session.get(temp_url)

        pattern = '%d-%m-%Y_%H-%M-%S'
        ondate = datetime.now().strftime(pattern)
        self.session.get(self.vars['url2_1']+ondate)

        if login_esia == None:
            login_esia = {
            'login': input("Ваш логин:"),
            'password': getpass.getpass("Ваш пароль:")
            }
        response = self.session.post(self.vars['url2_2'], json=login_esia)
        print(response.text)
        if str(response.status_code) == '201':
            print("Неправильные данные")
        else:
            mfa_type_asked = response.json().get('mfa_details').get('type')
            mfa_code = input(f"Введите код {totp[mfa_type_asked]}:")
            response = self.session.post(self.vars['url2_2'] + url[mfa_type_asked] + '/verify?code=' + mfa_code)

            if response.json().get("action") == "MAX_QUIZ":
                print(response.text)
                response = self.session.post(self.vars['url2_2'] + 'quiz-max/skip')
            tmp = response.json().get('redirect_url')
            response = self.session.get(tmp)

            response = self.session.get(self.vars['url_3']+loginState)
            tmp = response.json()

            id = tmp['users'][0]['id']
            data = {
                'idp':'esia',
                'loginState':loginState,
                'LoginType':'8',
                'lscope':id
            }
            response = self.session.post(self.vars['url_4'], data)
            at = response.json()['at']

            headers = {
                'at':at
            }
            response = self.session.get(self.vars['url_5'], headers=headers)
            device_code = response.json()['userCode']

            data = {
                'grant_type':'urn:ietf:params:oauth:grant-type:device_code',
                'device_code':device_code,
                'client_id':'parent-mobile',
                'client_secret':self.vars['client_secret']
            }
            response = self.session.post(self.vars['url3_1'], data=data)
            tokens = {
                'access_token':response.json()['access_token'],
                'refresh_token':response.json()['refresh_token'],
                'expires_in':response.json()['expires_in']
            }

            self.session.get(self.vars['url_logout'], headers=headers)
            if filename != None:
                with open(filename, 'w', encoding='utf_8') as n:
                    json.dump(tokens, n)

        return {'authorization':f"Bearer {tokens.get('access_token')}"}

    def getInfo(self, headers):
        response = self.session.get(self.vars['url3_2'], headers=headers)
        serverId = response.json()[0]['serverId']

        response = self.session.get(self.vars['url_6'], headers=headers)

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
        if studentId == None:
            studentId = self.getInfo(headers=headers).get('studentId')
        if startDate == None and endDate == None:
            startDate, endDate = self.get_week_range('%Y-%m-%d', day)

        response = self.session.get(f"{self.vars['url_diary']}{studentId}&startDate={startDate}&endDate={endDate}{self.vars['url_diary_end']}", headers=headers)

        with open(diaryName, 'w', encoding='utf_8') as diary:
            diary.write(response.text)
        
        return response.json()

    def tokenRefresh(self, filename):
        if not os.path.exists(filename):
            print('Файл не найден')
            return False
        with open(filename, 'r', encoding='utf-8') as ddf:
            refresh_token = json.load(ddf)['refresh_token']

        data = {
            'grant_type':'refresh_token',
            'refresh_token':refresh_token,
            'client_id':'parent-mobile',
            'client_secret':self.vars['client_secret']
        }
        response = requests.post(self.vars['url3_1'], data=data)
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