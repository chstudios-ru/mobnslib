import json, requests, os
from tqdm import tqdm

custom_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{rate_fmt}]"
url = 'https://net-school.cap.ru'
url_att = url + '/api/mobile/attachments?assignmentId='
url_att_end = '&appVersion=1.3.9&lng=ru'
url_load = url + '/api/mobile/attachments/'

num = 0
total = 0
with open('diary.json', 'r', encoding='utf_8') as d:
    week = json.load(d)
with open('token.txt','r',encoding='utf_8') as n:
    access_token = n.read()
headers = {
    'authorization': f'Bearer {access_token}'
}
if not os.path.exists('downloads'):
    os.makedirs('downloads')

def loadfile(item, count):
    print()
    print(item['subjectName'], ' ', item['assignmentId'])
    for dz in item['assignmentId']:
        response = requests.get(url_att + str(dz) + url_att_end, headers=headers)
        if int(response.headers.get('content-length', 0)) > 2:
            for z in response.json():
                attId = str(z.get('attachmentId'))
                fileName = z.get('fileName')
                response = requests.get(url_load + attId, headers=headers, stream=True)
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                block_size = 1024
                count = count + 1
                progress_bar = tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    desc=fileName,
                    bar_format=custom_format,
                    ascii='-#'
                )
                path = os.path.join('downloads', fileName)

                with open(path, 'wb') as w:
                    for chunk in response.iter_content(chunk_size=block_size):
                        w.write(chunk)
                        progress_bar.update(len(chunk))
                progress_bar.close()
    return total_size, count

for i in week:
    if i['attachmentsExists'] == True:
        size, num = loadfile(i, num)
        total = total + size
print('\n', '\n', f"Скачано: {total/1024:.0f}KB, файлов: {num}", '\n')
