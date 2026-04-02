import json, httpx, os, asyncio
from tqdm import tqdm

sem = asyncio.Semaphore(1)
custom_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{rate_fmt}]"
url = 'https://net-school.cap.ru'
url_att = url + '/api/mobile/attachments?assignmentId='
url_att_end = '&appVersion=1.3.9&lng=ru'
url_load = url + '/api/mobile/attachments/'

with open('diary.json', 'r', encoding='utf_8') as d:
    week = json.load(d)
with open('token.txt','r',encoding='utf_8') as n:
    access_token = n.read()
headers = {'authorization': f'Bearer {access_token}'}
if not os.path.exists('downloads'):
    os.makedirs('downloads')

async def loadfile(client, item):
    async with sem:
        # print()
        # print(item['subjectName'], ' ', item['assignmentId'])
        # tqdm.write(f"\n{item['subjectName']}   {item['assignmentId'][0]}")
        response = await client.get(url_att + str(item['assignmentId'][0]) + url_att_end, headers=headers)
        attId = str(response.json()[0]['attachmentId'])
        fileName = response.json()[0]['fileName']

        async with client.stream("GET", url_load + attId, follow_redirects=True) as response:
            response.raise_for_status()
            #print()
            #print(item['subjectName'], ' ', item['assignmentId'])
            tqdm.write(f"\n{item['subjectName']}   {item['assignmentId'][0]}")
            total_size = int(response.headers.get('content-length', 0))
            progress_bar = tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                desc=fileName,
                bar_format=custom_format,
                ascii='_#'
            )
            path = os.path.join('downloads', fileName)

            with open(path, 'wb') as w:
                async for chunk in response.aiter_bytes():
                    if chunk:
                        w.write(chunk)
                        progress_bar.update(len(chunk))
            progress_bar.close()

async def main():
    async with httpx.AsyncClient(headers=headers) as client:
        tasks = []
        for i in week:
            if i.get('attachmentsExists'):
                tasks.append(loadfile(client, i))

        # Запускаем всё одновременно
        print('lol')
        await asyncio.gather(*tasks)

asyncio.run(main())
