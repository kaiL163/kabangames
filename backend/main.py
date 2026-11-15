import asyncio
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal

try:
    from .detective import CASE, ANSWERS, EXPLANATION
    from . import quiz as quiz_game
    from . import writing_game
    from . import party
except ImportError:
    from detective import CASE, ANSWERS, EXPLANATION
    import quiz as quiz_game
    import writing_game
    import party

app = FastAPI(title="Kaban Games")
rooms = {}
lock = asyncio.Lock()
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"
ROOM_LIFETIME = 6 * 60 * 60
PLAYER_TIMEOUT = 10 * 60

class Credentials(BaseModel):
    code: str = Field(max_length=4)
    token: str = Field(max_length=128)

class Create(BaseModel):
    name: str = Field(max_length=20)

class Join(BaseModel):
    code: str = Field(max_length=4)
    name: str = Field(max_length=20)

class GameState(BaseModel):
    game_id: str = Field(pattern='^(quiz|croc|truth|who|finish|twotruths|screenwriter|emoji|truefalse|words|cinema|filmguess|carquiz|adultquiz)$')
    host_prompt: str = Field(default='', max_length=500)
    host_answer: str = Field(default='', max_length=500)
    title: str = Field(max_length=80)
    prompt: str = Field(max_length=500)
    answer: str = Field(max_length=500)

class Update(Credentials):
    state: GameState | None

class QuizStart(Credentials):
    game_id: str = Field(max_length=20)
    rounds: Literal[5, 10, 15] = 10

class WritingStart(Credentials):
    rounds: Literal[5, 10, 15] = 5

class QuizAnswer(Credentials):
    instance: str = Field(max_length=40)
    choice: int
    round: int = Field(ge=1)

class WritingAction(Credentials):
    instance: str = Field(max_length=40)
    round: int = Field(ge=1)
    value: str = Field(max_length=200)

class PartyStart(Credentials):
    game_id: str = Field(max_length=20)
    rounds: Literal[5, 10, 15] = 10

class PartyAction(Credentials):
    instance: str = Field(max_length=40)
    round: int = Field(ge=1)
    action: str = Field(max_length=20)
    value: str = Field(default='', max_length=200)
    facts: list[str] | None = Field(default=None, max_length=3)
    lie: int | None = None

class Inspect(Credentials):
    item_id: str = Field(max_length=30)

class Theory(Credentials):
    suspect: str = Field(max_length=30)
    reason: str = Field(max_length=300)

class Accusation(Credentials):
    answers: dict[str, str]

def prune():
    now = time.monotonic()
    for code, room in list(rooms.items()):
        if now - room['updated'] > ROOM_LIFETIME:
            del rooms[code]
        else:
            room['players'] = {key: player for key, player in room['players'].items() if now - player['seen'] < PLAYER_TIMEOUT}

def get_room(code):
    room = rooms.get(code.upper())
    if room is None:
        raise HTTPException(404, 'Комната не найдена. Проверьте код.')
    return room

def authenticate(room, token):
    host = secrets.compare_digest(room['host'], token)
    player = room['players'].get(token)
    if not host and not player:
        raise HTTPException(403, 'Подключение завершено. Войдите снова.')
    if player:
        player['seen'] = time.monotonic()
    room['updated'] = time.monotonic()
    return host

@app.get('/api/health')
async def health():
    return {'ok': True}

@app.post('/api/create')
async def create(body: Create):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, 'Введите имя ведущего')
    async with lock:
        prune()
        if len(rooms) >= 5000:
            raise HTTPException(503, 'Сейчас нельзя создать комнату. Попробуйте позже.')
        while True:
            code = ''.join(secrets.choice(ALPHABET) for _ in range(4))
            if code not in rooms:
                break
        token = secrets.token_urlsafe(32)
        rooms[code] = {'host': token, 'host_name': name, 'video_room': secrets.token_hex(12), 'video_password': secrets.token_hex(12), 'players': {}, 'state': None, 'detective': None, 'quiz': None, 'writing': None, 'party': None, 'updated': time.monotonic()}
        return {'code': code, 'token': token, 'host': True, 'name': name}

@app.post('/api/join')
async def join(body: Join):
    async with lock:
        prune()
        room = get_room(body.code)
        name = body.name.strip()
        if not name:
            raise HTTPException(400, 'Введите имя')
        existing_names = [room['host_name'], *[p['name'] for p in room['players'].values()]]
        if name.casefold() in {n.casefold() for n in existing_names}:
            raise HTTPException(400, 'Этот ник уже занят в лобби')
        if len(room['players']) >= 15:
            raise HTTPException(400, 'Комната заполнена')
        token = secrets.token_urlsafe(32)
        room['players'][token] = {'name': name, 'seen': time.monotonic()}
        room['updated'] = time.monotonic()
        return {'code': body.code.upper(), 'token': token, 'host': False}

@app.post('/api/state')
async def state(body: Credentials):
    async with lock:
        prune()
        room = get_room(body.code)
        is_host = authenticate(room, body.token)
        state = room['state']
        if state is not None and not is_host:
            state = {k: v for k, v in state.items() if k not in ('host_prompt', 'host_answer')}
        return {'host_name': room['host_name'], 'video': {'room': room['video_room'], 'password': room['video_password'], 'name': room['host_name'] if is_host else room['players'][body.token]['name']}, 'players': [p['name'] for p in room['players'].values()], 'state': state, 'detective': detective_view(room['detective']), 'quiz': quiz_game.view(room, body.token), 'writing': writing_game.view(room, body.token), 'party': party.view(room, body.token), 'active_game': 'detective' if room['detective'] is not None else (room['quiz']['id'] if room.get('quiz') else ('finish' if room.get('writing') else (room['party']['id'] if room.get('party') else (state['game_id'] if state else None))))}

@app.post('/api/update')
async def update(body: Update):
    async with lock:
        prune()
        room = get_room(body.code)
        if not authenticate(room, body.token):
            raise HTTPException(403, 'Только ведущий управляет игрой')
        room['state'] = body.state.model_dump() if body.state else None
        room['detective'] = None
        room['quiz'] = None
        room['writing'] = None
        room['party'] = None
        return {'ok': True}

@app.post('/api/quiz/start')
async def quiz_start(body: QuizStart):
    async with lock:
        prune()
        room = get_room(body.code)
        if not authenticate(room, body.token): raise HTTPException(403, 'Только ведущий запускает игру')
        try: quiz_game.start(room, body.game_id, body.rounds)
        except ValueError as error: raise HTTPException(400, str(error))
        room['state'] = None
        room['detective'] = None
        room['writing'] = None
        room['party'] = None
        return quiz_game.view(room, body.token)

@app.post('/api/quiz/answer')
async def quiz_answer(body: QuizAnswer):
    async with lock:
        prune()
        room = get_room(body.code)
        authenticate(room, body.token)
        if not room.get('quiz'): raise HTTPException(400, 'Игра не запущена')
        if body.instance != room['quiz']['instance']: raise HTTPException(409, 'Игра уже сменилась')
        if body.round != room['quiz']['index'] + 1: raise HTTPException(409, 'Раунд сменился — ответ не принят')
        try: quiz_game.answer(room, body.token, body.choice)
        except ValueError as error: raise HTTPException(400, str(error))
        return quiz_game.view(room, body.token)

@app.post('/api/quiz/next')
async def quiz_next(body: Credentials):
    async with lock:
        prune()
        room = get_room(body.code)
        if not authenticate(room, body.token): raise HTTPException(403, 'Только ведущий управляет раундами')
        if not room.get('quiz'): raise HTTPException(400, 'Игра не запущена')
        quiz_game.finish_if_needed(room)
        try: quiz_game.next_round(room)
        except ValueError as error: raise HTTPException(400, str(error))
        return quiz_game.view(room, body.token)

@app.post('/api/writing/start')
async def writing_start(body: WritingStart):
    async with lock:
        prune(); room = get_room(body.code)
        if not authenticate(room, body.token): raise HTTPException(403, 'Только ведущий запускает игру')
        try: writing_game.start(room, body.rounds)
        except ValueError as error: raise HTTPException(400, str(error))
        room['state'] = None; room['detective'] = None; room['quiz'] = None; room['party'] = None
        return writing_game.view(room, body.token)

@app.post('/api/writing/{action}')
async def writing_action(action: str, body: WritingAction):
    async with lock:
        prune(); room = get_room(body.code); authenticate(room, body.token)
        game = room.get('writing')
        if not game: raise HTTPException(400, 'Игра не запущена')
        if body.instance != game['instance'] or body.round != game['index'] + 1: raise HTTPException(409, 'Раунд сменился')
        try:
            if action == 'submit': writing_game.submit(room, body.token, body.value)
            elif action == 'vote': writing_game.vote(room, body.token, body.value)
            else: raise HTTPException(404, 'Неизвестное действие')
        except ValueError as error: raise HTTPException(400, str(error))
        return writing_game.view(room, body.token)

@app.post('/api/writing-next')
async def writing_next(body: Credentials):
    async with lock:
        prune(); room = get_room(body.code)
        if not authenticate(room, body.token): raise HTTPException(403, 'Только ведущий управляет раундами')
        if not room.get('writing'): raise HTTPException(400, 'Игра не запущена')
        writing_game.update(room)
        try: writing_game.next_round(room)
        except ValueError as error: raise HTTPException(400, str(error))
        return writing_game.view(room, body.token)

@app.post('/api/party/start')
async def party_start(body: PartyStart):
    async with lock:
        prune(); room = get_room(body.code)
        if not authenticate(room, body.token): raise HTTPException(403, 'Только ведущий запускает игру')
        try: party.start(room, body.game_id, body.rounds)
        except ValueError as error: raise HTTPException(400, str(error))
        room['state'] = None; room['detective'] = None; room['quiz'] = None; room['writing'] = None
        return party.view(room, body.token)

@app.post('/api/party/action')
async def party_action(body: PartyAction):
    async with lock:
        prune(); room = get_room(body.code); authenticate(room, body.token)
        game = room.get('party')
        if not game: raise HTTPException(400, 'Игра не запущена')
        if body.instance != game['instance'] or body.round != game['round']: raise HTTPException(409, 'Раунд сменился')
        try: party.action(room, body.token, body.action, body.value, body.facts, body.lie)
        except ValueError as error: raise HTTPException(400, str(error))
        return party.view(room, body.token)

@app.post('/api/party/next')
async def party_next(body: Credentials):
    async with lock:
        prune(); room = get_room(body.code)
        if not authenticate(room, body.token): raise HTTPException(403, 'Только ведущий начинает раунд')
        if not room.get('party'): raise HTTPException(400, 'Игра не запущена')
        party.update(room)
        try: party.next_round(room)
        except ValueError as error: raise HTTPException(400, str(error))
        return party.view(room, body.token)

def detective_view(progress):
    if progress is None:
        return None
    opened = set(progress['opened'])
    return {
        'title': CASE['title'], 'intro': CASE['intro'],
        'items': [{**{k: item[k] for k in ('id', 'group', 'title', 'icon')},
                   'text': item['text'] if item['id'] in opened else None,
                   'image': item.get('image') if item['id'] in opened else None,
                   'caption': item.get('caption'),
                   'portrait_position': item.get('portrait_position'),
                   'locked': not set(item.get('requires', [])).issubset(opened),
                   'requires': [i['title'] for i in CASE['items'] if i['id'] in item.get('requires', []) and i['id'] not in opened]} for item in CASE['items']],
        'questions': CASE['questions'], 'result': progress['result'],
        'theories': list(progress.get('theories', {}).values()),
    }

@app.post('/api/detective/start')
async def detective_start(body: Credentials):
    async with lock:
        prune()
        room = get_room(body.code)
        if not authenticate(room, body.token):
            raise HTTPException(403, 'Только ведущий начинает дело')
        room['detective'] = {'opened': [], 'result': None, 'theories': {}}
        room['state'] = None
        room['quiz'] = None
        room['writing'] = None
        room['party'] = None
        return detective_view(room['detective'])

@app.post('/api/detective/inspect')
async def detective_inspect(body: Inspect):
    async with lock:
        prune()
        room = get_room(body.code)
        authenticate(room, body.token)
        progress = room['detective']
        if progress is None:
            raise HTTPException(400, 'Дело ещё не начато')
        if not any(item['id'] == body.item_id for item in CASE['items']):
            raise HTTPException(404, 'Улика не найдена')
        item = next(i for i in CASE['items'] if i['id'] == body.item_id)
        if not set(item.get('requires', [])).issubset(progress['opened']):
            raise HTTPException(400, 'Сначала изучите связанные материалы')
        if body.item_id not in progress['opened']:
            progress['opened'].append(body.item_id)
        return detective_view(progress)

@app.post('/api/detective/theory')
async def detective_theory(body: Theory):
    async with lock:
        prune()
        room = get_room(body.code)
        is_host = authenticate(room, body.token)
        progress = room['detective']
        if progress is None or progress['result'] is not None:
            raise HTTPException(400, 'Обсуждение сейчас недоступно')
        if body.suspect not in ('Марина', 'Олег', 'Вера', 'Пока не знаю'):
            raise HTTPException(400, 'Выберите подозреваемого')
        reason = body.reason.strip()
        if not reason:
            raise HTTPException(400, 'Добавьте краткое обоснование')
        name = room['host_name'] if is_host else room['players'][body.token]['name']
        progress['theories'][body.token] = {'name': name, 'suspect': body.suspect, 'reason': reason}
        return detective_view(progress)

@app.post('/api/detective/accuse')
async def detective_accuse(body: Accusation):
    async with lock:
        prune()
        room = get_room(body.code)
        if not authenticate(room, body.token):
            raise HTTPException(403, 'Обвинение отправляет ведущий')
        progress = room['detective']
        if progress is None:
            raise HTTPException(400, 'Дело ещё не начато')
        if progress['result'] is not None:
            raise HTTPException(400, 'Обвинение уже отправлено')
        if any(body.answers.get(q['id']) not in q['options'] for q in CASE['questions']):
            raise HTTPException(400, 'Ответьте на все вопросы')
        progress['result'] = {
            'score': sum(body.answers[key] == value for key, value in ANSWERS.items()),
            'answers': ANSWERS, 'submitted': body.answers, 'explanation': EXPLANATION,
        }
        return detective_view(progress)

@app.post('/api/leave')
async def leave(body: Credentials):
    async with lock:
        prune()
        room = get_room(body.code)
        if authenticate(room, body.token):
            del rooms[body.code.upper()]
        else:
            room['players'].pop(body.token, None)
        return {'ok': True}

static = Path(__file__).resolve().parent / 'static'
if static.is_dir():
    app.mount('/car-logos', StaticFiles(directory=static / 'car-logos', check_dir=False), name='car-logos')
    app.mount('/evidence', StaticFiles(directory=static / 'evidence', check_dir=False), name='evidence')
    app.mount('/assets', StaticFiles(directory=static / 'assets'), name='assets')
    @app.get('/favicon.svg')
    async def favicon():
        return FileResponse(static / 'favicon.svg', media_type='image/svg+xml')

    @app.get('/kaban-logo.svg')
    async def logo():
        return FileResponse(static / 'kaban-logo.svg', media_type='image/svg+xml')

    @app.get('/')
    @app.get('/join')
    @app.get('/create')
    @app.get('/lobby/{code}')
    @app.get('/lobby/{code}/game/{game_id}')
    async def index(code: str = '', game_id: str = ''):
        return FileResponse(static / 'index.html')

