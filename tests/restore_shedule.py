from datetime import datetime
import os

def today_shed(week, today=None):
    lessons_sum = []
    day = []
    num = 0
    if today == None:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today = today.strftime('%Y-%m-%dT%H:%M:%S')
    for i in week:
       if i.get('day') == today:
           day.append(i)
           lessons_sum.append(i.get('order'))
           if int(i.get('order')) > num:
               num = i.get('order')

    lessons_map = {l['order']: l for l in day}

    today_shed = []
    for d in range(1, num+1):
        if d in lessons_sum:
            today_shed.append(lessons_map.get(d))
        else:
            today_shed.append({'order':d, 'subjectName':'нет урока'})

    for y in today_shed:
        print(f"{y.get('order')} {y.get('subjectName')}")

    with open('att.txt', 'w', encoding='utf-8') as hd:
        hd.write(str(today_shed))
