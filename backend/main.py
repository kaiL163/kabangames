import asyncio
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from .detective import CASE, ANSWERS, EXPLANATION
except ImportError:
    from detective import CASE, ANSWERS, EXPLANATION

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
        rooms[code] = {'host': token, 'host_name': name, 'players': {}, 'state': None, 'detective': None, 'updated': time.monotonic()}
        return {'code': code, 'token': token, 'host': True, 'name': name}

@app.post('/api/join')
async def join(body: Join):
    async with lock:
        prune()
        room = get_room(body.code)
        name = body.name.strip()
        if not name:
            raise HTTPException(400, 'Введите имя')
        if len(room['players']) >= 16:
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
        return {'host_name': room['host_name'], 'players': [p['name'] for p in room['players'].values()], 'state': state, 'detective': detective_view(room['detective']), 'active_game': 'detective' if room['detective'] is not None else (state['game_id'] if state else None)}

@app.post('/api/update')
async def update(body: Update):
    async with lock:
        prune()
        room = get_room(body.code)
        if not authenticate(room, body.token):
            raise HTTPException(403, 'Только ведущий управляет игрой')
        room['state'] = body.state.model_dump() if body.state else None
        room['detective'] = None
        return {'ok': True}

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
    app.mount('/evidence', StaticFiles(directory=static / 'evidence', check_dir=False), name='evidence')
    app.mount('/assets', StaticFiles(directory=static / 'assets'), name='assets')
    @app.get('/')
    @app.get('/join')
    @app.get('/create')
    @app.get('/lobby/{code}')
    @app.get('/lobby/{code}/game/{game_id}')
    async def index(code: str = '', game_id: str = ''):
        return FileResponse(static / 'index.html')
