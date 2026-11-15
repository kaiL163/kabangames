"""Server-authoritative simultaneous quiz rounds for one room."""
import json
import random
import secrets
import time
from pathlib import Path

BANK = json.loads((Path(__file__).parent / 'quiz_bank.json').read_text(encoding='utf-8'))
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

def participants(room):
    return {room['host']: room['host_name'], **{token: p['name'] for token, p in room['players'].items()}}

def start(room, game_id):
    if game_id not in BANK:
        raise ValueError('Эта игра не поддерживает викторину')
    questions = list(BANK[game_id]['items'])
    random.shuffle(questions)
    room['quiz'] = {'instance': secrets.token_urlsafe(12), 'id': game_id, 'title': BANK[game_id]['title'], 'questions': questions[:MAX_ROUNDS], 'index': -1, 'scores': {}, 'phase': 'between'}
    next_round(room)

def next_round(room):
    quiz = room['quiz']
    if quiz['phase'] not in ('between', 'result'):
        raise ValueError('Дождитесь результатов раунда')
    if quiz['index'] + 1 >= len(quiz['questions']):
        quiz['phase'] = 'finished'
        return
    quiz['index'] += 1
    question, correct = quiz['questions'][quiz['index']]
    pool = list(dict.fromkeys(answer for _, answer in BANK[quiz['id']]['items'] if answer != correct))
    if quiz['id'] == 'truefalse':
        options = ['Правда', 'Фейк']
    else:
        specific = (QUIZ_DISTRACTORS if quiz['id'] == 'quiz' else CINEMA_DISTRACTORS if quiz['id'] == 'cinema' else {}).get(correct)
        if specific:
            pool = list(specific)
        else:
            random.shuffle(pool)
        options = [correct, *pool[:3]]
        random.shuffle(options)
    quiz.update({'question': question, 'correct': correct, 'options': options, 'answers': {}, 'eligible': participants(room), 'deadline': time.time()+ROUND_SECONDS, 'phase': 'question'})
    for token, name in quiz['eligible'].items():
        quiz['scores'].setdefault(token, {'name': name, 'score': 0})

def finish_if_needed(room, force=False):
    quiz = room.get('quiz')
    if not quiz or quiz['phase'] != 'question':
        return
    if not (force or time.time() >= quiz['deadline'] or set(quiz['eligible']) <= set(quiz['answers'])):
        return
    quiz['phase'] = 'result'
    for token, choice in quiz['answers'].items():
        if quiz['options'][choice] == quiz['correct']:
            quiz['scores'][token]['score'] += 100

def answer(room, token, choice):
    quiz = room['quiz']
    finish_if_needed(room)
    if quiz['phase'] != 'question': raise ValueError('Раунд уже завершён')
    if token not in quiz['eligible']: raise ValueError('Вы присоединитесь со следующего раунда')
    if token in quiz['answers']: raise ValueError('Ответ уже принят')
    if choice < 0 or choice >= len(quiz['options']): raise ValueError('Выберите вариант ответа')
    quiz['answers'][token] = choice
    finish_if_needed(room)

def view(room, token):
    quiz = room.get('quiz')
    if not quiz: return None
    finish_if_needed(room)
    phase = quiz['phase']
    data = {'instance': quiz['instance'], 'game_id': quiz['id'], 'title': quiz['title'], 'phase': phase, 'round': quiz['index']+1, 'total': len(quiz['questions']),
            'question': quiz.get('question'), 'options': quiz.get('options', []), 'remaining': max(0, int(quiz.get('deadline', 0)-time.time()+0.999)),
            'answered': token in quiz.get('answers', {}), 'my_choice': quiz.get('answers', {}).get(token),
            'can_answer': token in quiz.get('eligible', {}), 'answers_count': len(quiz.get('answers', {})), 'players_count': len(quiz.get('eligible', {})),
            'scores': sorted(quiz['scores'].values(), key=lambda p: -p['score'])}
    if phase in ('result', 'finished'):
        data['correct'] = quiz.get('correct')
        data['results'] = [{'name': name, 'choice': quiz['options'][quiz['answers'][key]] if key in quiz['answers'] else None} for key, name in quiz.get('eligible', {}).items()]
    return data
