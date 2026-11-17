"""Server-authoritative simultaneous quiz rounds for one room."""
import json
import random
import secrets
import time
from pathlib import Path

BANK = json.loads((Path(__file__).parent / 'quiz_bank.json').read_text(encoding='utf-8'))
CAR_BRANDS = json.loads((Path(__file__).parent / 'car_brands.json').read_text(encoding='utf-8'))
CAR_PUZZLES=json.loads((Path(__file__).parent/'car_puzzles.json').read_text(encoding='utf-8'))
BANK.pop('adultquiz',None)
BANK['carquiz']['items'] = [['Угадай марку автомобиля по эмблеме', name] for name in CAR_PUZZLES]
ROUND_SECONDS = 30
MAX_ROUNDS = 10
QUIZ_DISTRACTORS = {
 'Марс':['Венера','Меркурий','Юпитер'], 'Три':['Одно','Два','Четыре'],
 'Тихий':['Атлантический','Индийский','Северный Ледовитый'], 'Пингвин':['Орёл','Ласточка','Сокол'],
 'Шесть':['Четыре','Пять','Семь'], 'Токио':['Киото','Сеул','Осака'],
 'Золото':['Серебро','Алюминий','Медь'], '150':['120','135','180'],
 'Италия':['Испания','Греция','Португалия'], 'Виноград':['Слива','Яблоко','Абрикос'],
 'Юпитер':['Сатурн','Нептун','Земля'], 'Александр Пушкин':['Лев Толстой','Николай Гоголь','Михаил Лермонтов'],
}
CINEMA_DISTRACTORS = {
 'Вуди':['Базз Лайтер','Рекс','Булзай'], 'Хогвартс':['Нарния','Готэм','Мордор'],
 'Симба':['Тимон','Пумба','Зазу'], 'Шрек':['Салли','Грю','Кунг-фу Панда'],
 'Титаник':['Британия','Аврора','Бисмарк'], 'Немо':['Дори','Марлин','Гилл'],
 'Персонаж «Властелина колец»':['Персонаж «Звёздных войн»','Персонаж «Аватара»','Персонаж «Матрицы»'],
 'Дарт Вейдер':['Люк Скайуокер','Хан Соло','Йода'],
}

LOGO_FAMILIES=[
 ['Aston Martin','Bentley','Genesis','Chrysler','MINI','Morgan','Lagonda'],
 ['Audi','Toyota','Lexus','Subaru','Hyundai','Honda','Acura','Infiniti'],
 ['BMW','Mercedes-Benz','Volkswagen','Opel','Nissan','Alfa Romeo','Saab','Buick','Volvo'],
 ['Porsche','Ferrari','Lamborghini','Peugeot','Jaguar','Abarth','MG','Cadillac'],
 ['Kia','BYD','GMC','JAC','JMC','Haval','Isuzu','Jeep','Lotus','Lada'],
 ['NIO','XPENG','Zeekr','Li Auto','Xiaomi','AITO','Aion','Aiways','Leapmotor','Yangwang'],
 ['Renault','Dacia','Mitsubishi','Suzuki','SEAT','Cupra','Citroen','DS'],
]

def car_options(correct,previous):
    family=next((group for group in LOGO_FAMILIES if correct in group),[])
    preferred=[name for name in family if name in CAR_BRANDS and name!=correct]
    fallback=[name for name in CAR_BRANDS if name!=correct and name not in preferred]
    random.shuffle(preferred);random.shuffle(fallback)
    preferred.sort(key=lambda value:value in previous)
    fallback.sort(key=lambda value:value in previous)
    return (preferred+fallback)[:3]

def participants(room):
    return {room['host']: room['host_name'], **{token: p['name'] for token, p in room['players'].items()}}

def start(room, game_id, rounds=10, difficulty="hard"):
    if game_id not in BANK:
        raise ValueError('Эта игра не поддерживает викторину')
    if difficulty not in ('normal','hard'):raise ValueError('Выберите сложность эмблем')
    questions = list(BANK[game_id]['items'])
    random.shuffle(questions)
    room['quiz'] = {'instance': secrets.token_urlsafe(12), 'id': game_id, 'title': BANK[game_id]['title'], 'difficulty':difficulty, 'questions': questions[:rounds], 'index': -1, 'scores': {}, 'phase': 'between'}
    next_round(room)

def next_round(room):
    quiz = room['quiz']
    if quiz['phase'] not in ('between', 'result'):
        raise ValueError('Дождитесь результатов раунда')
    if quiz['id']=='carquiz':
        quiz['questions']=quiz['questions'][:quiz['index']+1]+[item for item in quiz['questions'][quiz['index']+1:] if item[1] in CAR_PUZZLES]
    if quiz['index'] + 1 >= len(quiz['questions']):
        quiz['phase'] = 'finished'
        return
    quiz['index'] += 1
    item = quiz['questions'][quiz['index']]
    question, correct = item[:2]
    pool = list(dict.fromkeys(entry[1] for entry in BANK[quiz['id']]['items'] if entry[1] != correct))
    if quiz['id'] == 'truefalse':
        options = ['Правда', 'Фейк']
    else:
        specific = item[2] if len(item)>2 else (QUIZ_DISTRACTORS if quiz['id'] == 'quiz' else CINEMA_DISTRACTORS if quiz['id'] == 'cinema' else {}).get(correct)
        if specific:
            pool = list(specific)
        else:
            previous=set(quiz.get('options',[]))
            random.shuffle(pool)
            pool.sort(key=lambda value:value in previous)
        if quiz['id']=='carquiz':pool=car_options(correct,set(quiz.get('options',[])))
        options = [correct, *pool[:3]]
        random.shuffle(options)
    quiz.update({'question': question, 'correct': correct, 'image': '/car-logos/'+CAR_BRANDS[correct] if quiz['id']=='carquiz' else None, 'options': options, 'answers': {}, 'answer_times':{}, 'started':time.time(), 'eligible': participants(room), 'deadline': time.time()+ROUND_SECONDS, 'phase': 'question'})
    quiz['mask']=(quiz.get('mask',-1)+1+secrets.randbelow(4))%5
    for token, name in quiz['eligible'].items():
        quiz['scores'].setdefault(token, {'name': name, 'score': 0})

def points(quiz,token):
    elapsed=max(0,quiz.get('answer_times',{}).get(token,quiz['deadline'])-quiz.get('started',quiz['deadline']-ROUND_SECONDS))
    return 100+round(200*max(0,1-elapsed/ROUND_SECONDS))

def finish_if_needed(room, force=False):
    quiz = room.get('quiz')
    if not quiz or quiz['phase'] != 'question':
        return
    if not (force or time.time() >= quiz['deadline'] or set(quiz['eligible']) <= set(quiz['answers'])):
        return
    quiz['phase'] = 'result'
    for token, choice in quiz['answers'].items():
        if quiz['options'][choice] == quiz['correct']:
            quiz['scores'][token]['score'] += points(quiz,token)

def answer(room, token, choice):
    quiz = room['quiz']
    finish_if_needed(room)
    if quiz['phase'] != 'question': raise ValueError('Раунд уже завершён')
    if token not in quiz['eligible']: raise ValueError('Вы присоединитесь со следующего раунда')
    if token in quiz['answers']: raise ValueError('Ответ уже принят')
    if choice < 0 or choice >= len(quiz['options']): raise ValueError('Выберите вариант ответа')
    quiz.setdefault('answer_times',{})[token]=time.time()
    quiz['answers'][token] = choice
    finish_if_needed(room)

def view(room, token):
    quiz = room.get('quiz')
    if not quiz: return None
    finish_if_needed(room,force=quiz['id']=='carquiz' and quiz.get('correct') not in CAR_PUZZLES)
    phase = quiz['phase']
    data = {'instance': quiz['instance'], 'game_id': quiz['id'], 'title': quiz['title'], 'phase': phase, 'round': quiz['index']+1, 'total': len(quiz['questions']),
            'emblem':CAR_PUZZLES.get(quiz.get('correct')) if quiz['id']=='carquiz' and phase=='question' else None, 'difficulty':quiz.get('difficulty','normal'), 'speed_scoring':True,'mask':quiz.get('mask',0), 'question': quiz.get('question'), 'image': quiz.get('image'), 'options': quiz.get('options', []), 'remaining': max(0, int(quiz.get('deadline', 0)-time.time()+0.999)),
            'answered': token in quiz.get('answers', {}), 'my_choice': quiz.get('answers', {}).get(token),
            'can_answer': token in quiz.get('eligible', {}), 'answers_count': len(quiz.get('answers', {})), 'players_count': len(quiz.get('eligible', {})),
            'scores': sorted(quiz['scores'].values(), key=lambda p: -p['score'])}
    if quiz['id']=='carquiz' and phase=='question':
        safe=CAR_PUZZLES.get(quiz.get('correct'))
        data['image']='/car-logos/'+safe.get('asset',CAR_BRANDS[quiz['correct']]) if safe else None
    if phase in ('result', 'finished'):
        data['correct'] = quiz.get('correct')
        data['results'] = [{'name': name, 'choice': quiz['options'][quiz['answers'][key]] if key in quiz['answers'] else None, 'points':points(quiz,key) if key in quiz['answers'] and quiz['options'][quiz['answers'][key]]==quiz['correct'] else 0} for key, name in quiz.get('eligible', {}).items()]
    return data
