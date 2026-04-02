import requests, asyncio, os, json, argparse, getpass
from datetime import datetime, timedelta
from restore_shedule import today_shed
session = requests.Session()

client_secret = "04064338-13df-4747-8dea-69849f9ecdf0"
appVer = '1.3.9'
lng = "&lng=ru"
day: datetime | None=None
#startDate: str | None=None
#endDate: str | None=None
# day = datetime(2026, 3, 2)
parser = argparse.ArgumentParser(description='lol')
parser.add_argument("--startDate", type=str, help="Первый день", default=None)
parser.add_argument("--endDate", type=str, help="Последний день", default=None)
args = parser.parse_args()
startDate, endDate = args.startDate, args.endDate
#print(startDate, endDate)
mfa_types = {
    'TTP':'totp',
    'MAX':'из макса',
    'SMS':'из смс'
}


# ------------------------URL's------------------------
url = 'https://net-school.cap.ru/'
url1 = 'https://mobile.ir-tech.ru'
url2 = 'https://esia.gosuslugi.ru'
url3 = 'https://identity.ir-tech.ru'

url_1 = url + "webapi/auth/login-state"
url_2 = url + "webapi/sso/esia/crosslogin?loginState="
url_2_end = "&esia_permissions=1&esia_role=1"
url_3 = url + "webapi/sso/esia/account-info?loginState="
url_4 = url + "webapi/auth/login"
url_5 = url + "webapi/mysettings/mobile/pincode"
url_6 = url + "api/mobile/users?v=2&appVersion=" + appVer + lng
url_logout = url + "logout"
url_diary = url + "api/mobile/classmeetings?studentIds="
url_diary_end = "&extraActivity=null&appVersion=" + appVer + lng
url_init = url + "api/mobile/initialize?version=" + appVer

url1_ver = f"{url1}/api/v1/mobile/parent/app-versions/published?appVersion={appVer}&lng=ru"

url2_1 = url2 + "/rs/dscl?ondate="
url2_2 = url2 + "/aas/oauth2/api/login"
url2_3 = url2_2 + "/totp/verify?code="

url3_1 = url3 + "/connect/token"
url3_2 = url3 + "/users/endpoints?appVersion=" + appVer + lng
# ------------------------URL's------------------------

# -----------------------DEBUG-------------------------
def dprint(*d):
    print(d)
# -----------------------DEBUG-------------------------

# ------------------------AUTH-------------------------
def esiaLogin():
    data = {'mobile':'1'}
    response = session.post(url_1, data=data)
    loginState = response.text
    loginState = loginState.replace('"','')
    print(response)

    temp_url = url_2 + loginState + url_2_end
    response = session.get(temp_url)
    print(response)

    pattern = '%d-%m-%Y_%H-%M-%S'
    ondate = datetime.now().strftime(pattern)
    print(session.get(url2_1+ondate))

    login_esia = {
    'login': input("Ваш логин:"),
    'password': getpass.getpass("Ваш пароль:")
    }
    response = session.post(url2_2, json=login_esia)
    print(response.text)
    if str(response.status_code) == '201':
        print("Неправильные данные")
    else:
        mfa_type_asked = response.json().get('mfa_details').get('type')
        mfa_code = input(f"Введите код {mfa_types.get(mfa_type_asked)}:")
        response = session.post(url2_3+mfa_code)
        print(response)

        tmp = response.json().get('redirect_url')
        response = session.get(tmp)
        print(response)

        response = session.get(url_3+loginState)
        tmp = response.json()
        print(response)

        id = tmp['users'][0]['id']
        data = {
            'idp':'esia',
            'loginState':loginState,
            'LoginType':'8',
            'lscope':id
        }
        response = session.post(url_4, data)
        at = response.json()['at']
        print(response)

        headers = {
            'at':at
        }
        response = session.get(url_5, headers=headers)
        device_code = response.json()['userCode']
        print(response)

        data = {
            'grant_type':'urn:ietf:params:oauth:grant-type:device_code',
            'device_code':device_code,
            'client_id':'parent-mobile',
            'client_secret':client_secret
        }
        response = session.post(url3_1, data=data)
        access_token = response.json()['access_token']
        print(response)

        print(session.get(url_logout, headers=headers))
        with open('token.txt', 'w', encoding='utf_8') as n:
            n.write(access_token)

    return access_token
# ------------------------AUTH-------------------------

# --------------------GETTING INFO---------------------
def getInfo(response, headers):
    print(response)
    serverId = response.json()[0]['serverId']

    response = session.get(url_6, headers=headers)
    print(response)
    firstName = response.json()[0]['firstName']
    schoolId = response.json()[0]['organizations'][0]['organization']['id']
    studentId = response.json()[0]['id']
    classId = response.json()[0]['organizations'][0]['classes'][0]['classId']

    print(f'Здравствуйте, {firstName}')
    return studentId, schoolId, classId, serverId
# --------------------GETTING INFO---------------------

# --------------------GETTING WEEK---------------------
def get_week_range(pattern, date=None):
    if date is None:
        date = datetime.now()

    start_of_week = date - timedelta(days=date.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    start_of_week = start_of_week.strftime(pattern)
    end_of_week = end_of_week.strftime(pattern)

    return start_of_week, end_of_week
# --------------------GETTING WEEK---------------------

# --------------------GETTING DIARY--------------------
def diary(studentId, headers, startDate=None, endDate=None):
    if startDate == None and endDate == None:
        startDate, endDate = get_week_range('%Y-%m-%d', day)
    response = session.get(f'{url_diary}{studentId}&startDate={startDate}&endDate={endDate}{url_diary_end}', headers=headers)
    with open('diary.json', 'w', encoding='utf_8') as diary:
        diary.write(response.text)
    print(response)
    return response.json()
# --------------------GETTING DIARY--------------------

# -------------------GETTING SHEDULE-------------------
def shedule(week, date=None):
    if date == None:
        date = datetime.now()

    pattern ='%Y-%m-%dT%H:%M:%S'
    date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    date = date.strftime(pattern)

    for s in week:
        if s['day'] == date:
            attachment = " \U0001F4C4" if s['attachmentsExists'] else ""
            print(s['order'], ' ', s['subjectName'], attachment)
# -------------------GETTING SHEDULE-------------------

def nsLogin():
    if os.path.exists('token.txt'):
        with open('token.txt', 'r', encoding='utf_8') as n:
            access_token = n.read()
        # with open('cookies.pkl', 'rb') as cookies:
        #     session.cookies.update(pickle.load(cookies))
    else:
        access_token = esiaLogin()

    headers = {'authorization':f'Bearer {access_token}'}
#    print(headers)

    try:
        response = session.get(url1_ver, timeout=10)
        print(response.text)
        response = session.get(url3_2, headers=headers, timeout=10)
        print(response)
    except requests.exceptions.Timeout:
        timeout = True
    if response.ok:
        studentId, schoolId, classId, serverId = getInfo(response, headers)
        week = diary(studentId, headers, startDate, endDate)
        today_shed(week, day)
    elif str(response.status_code) == '401':
        access_token = esiaLogin()
    else:
        today_shed(week, day)

nsLogin()
