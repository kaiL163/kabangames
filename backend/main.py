import asyncio
import secrets
import time
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal

try:
    from .detective import CASE, ANSWERS, EXPLANATION
    from . import quiz as quiz_game
    from . import writing_game
    from . import party, codenames, tabletop
except ImportError:
    from detective import CASE, ANSWERS, EXPLANATION
    import quiz as quiz_game
    import writing_game
    import party
    import codenames
    import tabletop

app = FastAPI(title="Kaban Games")
rooms = {}
lock = asyncio.Lock()
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"
ROOM_LIFETIME = 6 * 60 * 60
PLAYER_TIMEOUT = 10 * 60
ROOMS_FILE = Path(os.getenv('ROOMS_FILE', '/data/rooms.json'))

@app.on_event('startup')
async def load_rooms():
    try:
        restored = json.loads(ROOMS_FILE.read_text(encoding='utf-8'))
        now = time.monotonic()
        for code, room in restored.items():
            if time.time() - room.pop('saved_at', 0) <= 24 * 60 * 60:
                if room.get('quiz',{}) and room['quiz'].get('id')=='adultquiz':room['quiz']=None
                room.setdefault('ready', {})
                room.setdefault('reactions', [])
                room.setdefault('scores', {})
                room.setdefault('video_room', secrets.token_hex(12))
                room.setdefault('video_password', secrets.token_hex(12))
                room['updated'] = now
                for player in room.get('players', {}).values(): player['seen'] = now
                rooms[code] = room
    except (OSError, ValueError, TypeError):
        pass

@app.middleware('http')
async def persist_rooms(request: Request, call_next):
    response = await call_next(request)
    if request.method == 'POST' and request.url.path.startswith('/api/') and request.url.path != '/api/state':
        try:
            ROOMS_FILE.parent.mkdir(parents=True, exist_ok=True)
            snapshot = {code: {**room, 'saved_at': time.time()} for code, room in rooms.items()}
            temporary = ROOMS_FILE.with_suffix('.' + secrets.token_hex(6) + '.tmp')
            temporary.write_text(json.dumps(snapshot, ensure_ascii=False), encoding='utf-8')
            temporary.replace(ROOMS_FILE)
        except OSError:
            pass
    return response


class Credentials(BaseModel):
    code: str = Field(max_length=4)
    token: str = Field(max_length=128)

GAME_MODES = {game: {'party': game != 'detective', 'standalone': game == 'detective'} for game in ('detective','quiz','croc','truth','who','finish','twotruths','screenwriter','emoji','truefalse','words','cinema','filmguess','carquiz','spy','reaction')}

for mode in ('boss','domination'):GAME_MODES[mode]={'party':False,'standalone':True}

GAME_MODES['codenames'] = {'party': False, 'standalone': True}

class Create(BaseModel):
    client_id: str | None = Field(default=None, min_length=20, max_length=128)
    name: str = Field(max_length=20)
    game_id: str | None = Field(default=None, max_length=20)

class Join(BaseModel):
    client_id: str | None = Field(default=None, min_length=20, max_length=128)
    code: str = Field(max_length=4)
    name: str = Field(max_length=20)

class GameState(BaseModel):
    game_id: str = Field(pattern='^(quiz|croc|truth|who|finish|twotruths|screenwriter|emoji|truefalse|words|cinema|filmguess|carquiz)$')
    host_prompt: str = Field(default='', max_length=500)
    host_answer: str = Field(default='', max_length=500)
    title: str = Field(max_length=80)
    prompt: str = Field(max_length=500)
    answer: str = Field(max_length=500)

class Update(Credentials):
    state: GameState | None

class QuizStart(Credentials):
    difficulty: Literal['normal','hard'] = 'hard'
    game_id: str = Field(max_length=20)
    rounds: Literal[5, 10, 15, 25, 50, 100] = 10

class WritingStart(Credentials):
    rounds: Literal[5, 10, 15, 25, 50, 100] = 5

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
    rounds: Literal[5, 10, 15, 25, 50, 100] = 10

class PartyAction(Credentials):
    instance: str = Field(max_length=40)
    round: int = Field(ge=1)
    action: str = Field(max_length=20)
    value: str = Field(default='', max_length=500)
    facts: list[str] | None = Field(default=None, max_length=3)
    lie: int | None = None

class Inspect(Credentials):
    item_id: str = Field(max_length=30)

class Theory(Credentials):
    suspect: str = Field(max_length=30)
    reason: str = Field(max_length=300)

class Accusation(Credentials):
    answers: dict[str, str]


def require_game(room, game_id):
    if room.get('selected_game') and room['selected_game'] != game_id:
        raise HTTPException(403, 'Эта комната создана для другой игры')
    if not room.get('selected_game') and not GAME_MODES.get(game_id, {}).get('party'):
        raise HTTPException(403, 'Эта игра доступна только в отдельной комнате')

def require_ready(room):
    connected = [token for token, player in room['players'].items() if time.monotonic() - player['seen'] < 20]
    if connected and any(not room['ready'].get(token, False) for token in connected):
        raise HTTPException(409, 'Подождите, пока все игроки отметятся готовыми')

def merged_scores(room):
    merged = {token: dict(row) for token, row in room.get('scores', {}).items()}
    for key in ('quiz', 'party', 'writing'):
        for token, row in (room.get(key) or {}).get('scores', {}).items():
            total = merged.setdefault(token, {'name': row['name'], 'score': 0})
            total['score'] += row['score']
            total['name'] = row['name']
    return sorted(merged.values(), key=lambda row: -row['score'])

def archive_scores(room):
    for key in ('quiz', 'party', 'writing'):
        game = room.get(key)
        if not game: continue
        for token, row in game.get('scores', {}).items():
            total = room['scores'].setdefault(token, {'name': row['name'], 'score': 0})
            total['name'] = row['name']
            total['score'] += row['score']
        room[key] = None

def prune():
    now = time.monotonic()
    for code, room in list(rooms.items()):
        if now - room['updated'] > ROOM_LIFETIME:
            del rooms[code]
        else:
            room['ready'] = {key: value for key, value in room['ready'].items() if key in room['players']}

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

def existing_client(client_id):
    if not client_id:
        return None
    for code, room in rooms.items():
        if room.get('host_client') == client_id:
            return {'code': code, 'token': room['host'], 'host': True, 'name': room['host_name']}
        for token, player in room['players'].items():
            if player.get('client_id') == client_id:
                player['seen'] = time.monotonic()
                return {'code': code, 'token': token, 'host': False, 'name': player['name']}
    return None

@app.get('/api/health')
async def health():
    return {'ok': True}

@app.post('/api/create')
async def create(body: Create):
    name = body.name.strip()
    if body.game_id is not None and not GAME_MODES.get(body.game_id, {}).get('standalone'):
        raise HTTPException(400, 'Игра недоступна')
    if not name:
        raise HTTPException(400, 'Введите имя ведущего')
    async with lock:
        prune()
        existing = existing_client(body.client_id)
        if existing:
            return existing
        if len(rooms) >= 5000:
            raise HTTPException(503, 'Сейчас нельзя создать комнату. Попробуйте позже.')
        while True:
            code = ''.join(secrets.choice(ALPHABET) for _ in range(4))
            if code not in rooms:
                break
        token = secrets.token_urlsafe(32)
        rooms[code] = {'host': token, 'host_client': body.client_id, 'host_name': name, 'selected_game': body.game_id, 'ready': {}, 'reactions': [], 'scores': {}, 'video_room': secrets.token_hex(12), 'video_password': secrets.token_hex(12), 'players': {}, 'state': None, 'detective': None, 'quiz': None, 'writing': None, 'party': None, 'updated': time.monotonic()}
        if body.game_id in ('boss','domination'):tabletop.setup(rooms[code],body.game_id)
        if body.game_id == 'codenames': codenames.setup(rooms[code])
        return {'code': code, 'token': token, 'host': True, 'name': name}

@app.post('/api/join')
async def join(body: Join):
    async with lock:
        prune()
        room = get_room(body.code)
        existing = existing_client(body.client_id)
        if existing:
            if existing['code'] != body.code.upper():
                raise HTTPException(409, 'Сначала выйди из текущего лобби.')
            return existing
        name = body.name.strip()
        if not name:
            raise HTTPException(400, 'Введите имя')
        existing_names = [room['host_name'], *[p['name'] for p in room['players'].values()]]
        if name.casefold() in {n.casefold() for n in existing_names}:
            raise HTTPException(400, 'Этот ник уже занят в лобби')
        if len(room['players']) >= (24 if room.get('selected_game')=='domination' else 15):
            raise HTTPException(400, 'Комната заполнена')
        token = secrets.token_urlsafe(32)
        room['players'][token] = {'name': name, 'client_id': body.client_id, 'seen': time.monotonic()}
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
        return {'tabletop':tabletop.view(room,body.token), 'codenames': codenames.view(room, body.token), 'selected_game': room.get('selected_game'), 'is_host': is_host, 'my_camera': (room.setdefault('host_camera_id', secrets.token_hex(12)) if is_host else room['players'][body.token].setdefault('camera_id', secrets.token_hex(12))), 'host_camera': room.setdefault('host_camera_id', secrets.token_hex(12)), 'host_name': room['host_name'], 'video': {'code': body.code.upper(), 'room': room['video_room'], 'password': room['video_password'], 'name': room['host_name'] if is_host else room['players'][body.token]['name']}, 'players': [{'id': p.setdefault('public_id', secrets.token_urlsafe(12)), 'camera_id': p.setdefault('camera_id', secrets.token_hex(12)), 'name': p['name'], 'ready': room['ready'].get(token, False), 'connected': time.monotonic() - p['seen'] < 20} for token, p in room['players'].items()], 'connected_count': sum(time.monotonic() - p['seen'] < 20 for p in room['players'].values()), 'ready_count': sum(room['ready'].get(t, False) and time.monotonic() - p['seen'] < 20 for t, p in room['players'].items()), 'me_ready': True if is_host else room['ready'].get(body.token, False), 'reactions': room['reactions'][-20:], 'scores': merged_scores(room), 'state': state, 'detective': detective_view(room['detective']), 'quiz': quiz_game.view(room, body.token), 'writing': writing_game.view(room, body.token), 'party': party.view(room, body.token), 'active_game': room['selected_game'] if room.get('selected_game') in ('boss','domination') else 'codenames' if room.get('selected_game') == 'codenames' else 'detective' if room['detective'] is not None else (room['quiz']['id'] if room.get('quiz') else ('finish' if room.get('writing') else (room['party']['id'] if room.get('party') else (state['game_id'] if state else None))))}


class ManagePlayer(Credentials):
    player_id: str = Field(max_length=64)
    action: Literal['kick', 'transfer']

@app.post('/api/manage-player')
async def manage_player(body: ManagePlayer):
    async with lock:
        room = get_room(body.code)
        if not authenticate(room, body.token):
            raise HTTPException(403, 'Только ведущий управляет участниками')
        target = next((token for token, player in room['players'].items() if player.get('public_id') == body.player_id), None)
        if not target:
            raise HTTPException(404, 'Игрок уже вышел из комнаты')
        if body.action == 'transfer':
            try: tabletop.transfer_host(room, target)
            except ValueError as error: raise HTTPException(409, str(error))
        player = room['players'].pop(target)
        if room.get('codenames', {}).get('phase') == 'setup': room['codenames']['seats'].pop(target, None)
        if body.action=='kick' and room.get('tabletop', {}).get('phase') == 'setup': room['tabletop']['members'].pop(target,None)
        room['ready'].pop(target, None)
        if body.action == 'transfer':
            old_token, old_name = room['host'], room['host_name']
            room['players'][old_token] = {'name': old_name, 'seen': time.monotonic(), 'public_id': secrets.token_urlsafe(12), 'camera_id': room.get('host_camera_id', secrets.token_hex(12)), 'client_id': room.get('host_client')}
            room['host_camera_id'] = player.get('camera_id', secrets.token_hex(12))
            room['host'], room['host_name'] = target, player['name']
            room['host_client'] = player.get('client_id')
        return {'ok': True}

class CodenamesAction(Credentials):
    instance: str = Field(max_length=40)
    turn: int = Field(default=0, ge=0)
    action: Literal['seat', 'ready', 'configure', 'start', 'reset', 'clue', 'guess', 'end_turn', 'invalid_clue']
    team: Literal['red', 'blue', 'green', 'spectator'] = 'spectator'
    role: Literal['captain', 'operative'] = 'operative'
    traitor: bool = False
    seconds: Literal[0, 60, 90, 120, 180, 300] = 0
    team_count: Literal[2, 3] = 2
    theme: Literal['normal', 'minecraft', 'cs2', 'dota2'] = 'normal'
    time_red: int = Field(default=60, ge=0, le=3600)
    time_blue: int = Field(default=60, ge=0, le=3600)
    time_green: int = Field(default=60, ge=0, le=3600)
    bonus: int = Field(default=0, ge=0, le=120)
    text: str = Field(default='', max_length=200)
    word: str = Field(default='', max_length=200)
    number: int = Field(default=1, ge=0, le=9)
    card_id: str = Field(default='', max_length=3)

@app.post('/api/codenames/action')
async def codenames_action(body: CodenamesAction):
    async with lock:
        room = get_room(body.code)
        authenticate(room, body.token)
        require_game(room, 'codenames')
        if not room.get('codenames'): codenames.setup(room)
        try: codenames.action(room, body.token, body)
        except ValueError as error: raise HTTPException(409, str(error))
        return {'ok': True}

class TabletopAction(Credentials):
    comm_mode: Literal['text','voice'] = 'text'
    talk_seconds: int = Field(default=300,ge=60,le=900)
    negotiation: str = Field(default='',max_length=32)
    instance: str = Field(max_length=40)
    revision: int = Field(ge=0)
    action: Literal['seat','ready','configure','start','reset','advance','chat','show','check','vote','send','reward','done','invest','shield','eco','research','build','transfer','sanction','attack','negotiate','accept','decline','close','announce']
    team: str = Field(default='join',max_length=16)
    target: str = Field(default='',max_length=32)
    city: str = Field(default='',max_length=2)
    text: str = Field(default='',max_length=500)
    seconds: int = Field(default=300,ge=60,le=1800)
    amount: int = Field(default=0,ge=-1000,le=1000)

@app.post('/api/tabletop/action')
async def tabletop_action(body:TabletopAction):
    async with lock:
        room=get_room(body.code)
        authenticate(room,body.token)
        if room.get('selected_game') not in ('boss','domination'):
            raise HTTPException(403,'Создайте отдельную комнату для этой игры')
        if not room.get('tabletop'):tabletop.setup(room,room['selected_game'])
        try:tabletop.action(room,body.token,body.model_dump())
        except ValueError as error:raise HTTPException(409,str(error))
        return {'ok':True}

@app.post('/api/ready')
async def set_ready(body: Credentials):
    async with lock:
        room = get_room(body.code)
        is_host = authenticate(room, body.token)
        if not is_host: room['ready'][body.token] = not room['ready'].get(body.token, False)
        return {'ready': room['ready'].get(body.token, True)}

class Reaction(Credentials):
    emoji: str = Field(pattern='^(😂|🔥|👀|👏|❤️|😮)$')

@app.post('/api/reaction')
async def send_reaction(body: Reaction):
    async with lock:
        room = get_room(body.code)
        is_host = authenticate(room, body.token)
        name = room['host_name'] if is_host else room['players'][body.token]['name']
        room['reactions'].append({'id': secrets.token_urlsafe(8), 'name': name, 'emoji': body.emoji, 'at': time.time()})
        room['reactions'] = [item for item in room['reactions'] if time.time() - item['at'] < 12][-20:]
        return {'ok': True}

@app.post('/api/update')
async def update(body: Update):
    async with lock:
        prune()
        room = get_room(body.code)
        if not authenticate(room, body.token):
            raise HTTPException(403, 'Только ведущий управляет игрой')
        if body.state:
            require_game(room, body.state.game_id)
        archive_scores(room)
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
        require_game(room, body.game_id)
        require_ready(room)
        archive_scores(room)
        try: quiz_game.start(room, body.game_id, body.rounds, body.difficulty)
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
        require_game(room, 'finish')
        require_ready(room)
        archive_scores(room)
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
        require_game(room, body.game_id)
        require_ready(room)
        archive_scores(room)
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
        'instance': progress.setdefault('instance', secrets.token_hex(12)),
        'board': progress.setdefault('board', {'cards': {}, 'links': [], 'timeline': []}),
        'title': CASE['title'], 'intro': CASE['intro'],
        'items': [{**{k: item[k] for k in ('id', 'group', 'title', 'icon')},
                   'text': item['text'] if item['id'] in opened else None,
                   'image': item.get('image') if item['id'] in opened else None,
                   'caption': item.get('caption'),
                   'requires_ids': item.get('requires', []),
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
        require_game(room, 'detective')
        require_ready(room)
        room['detective'] = {'instance': secrets.token_hex(12), 'board': {'cards': {}, 'links': [], 'timeline': []}, 'opened': [], 'result': None, 'theories': {}}
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

class BoardAction(Credentials):
    instance: str = Field(max_length=40)
    action: Literal['pin', 'move', 'remove', 'link', 'unlink', 'event', 'update_event', 'delete_event']
    item_id: str = Field(default='', max_length=40)
    target: str = Field(default='', max_length=40)
    entry_id: str = Field(default='', max_length=40)
    label: str = Field(default='', max_length=120)
    time: str = Field(default='', pattern=r'^(?:[0-2][0-9]:[0-5][0-9])?$')
    text: str = Field(default='', max_length=300)
    x: int = Field(default=30, ge=0, le=800)
    y: int = Field(default=30, ge=0, le=500)

@app.post('/api/detective/board')
async def detective_board(body: BoardAction):
    async with lock:
        room = get_room(body.code)
        is_host = authenticate(room, body.token)
        progress = room.get('detective')
        if not progress or body.instance != progress.setdefault('instance', secrets.token_hex(12)):
            raise HTTPException(409, 'Расследование сменилось. Обновите страницу.')
        if progress['result'] is not None:
            raise HTTPException(409, 'Дело закрыто. Доска доступна для просмотра.')
        board = progress.setdefault('board', {'cards': {}, 'links': [], 'timeline': []})
        if body.action in ('pin', 'move', 'remove', 'link') and body.item_id not in progress['opened']:
            raise HTTPException(400, 'Сначала изучите этот материал')
        if body.action == 'pin':
            board['cards'].setdefault(body.item_id, {'x': body.x, 'y': body.y})
        elif body.action == 'move':
            if body.item_id not in board['cards']: raise HTTPException(409, 'Карточку сняли с доски')
            board['cards'][body.item_id] = {'x': body.x, 'y': body.y}
        elif body.action == 'remove':
            board['cards'].pop(body.item_id, None)
            board['links'] = [link for link in board['links'] if body.item_id not in (link['source'], link['target'])]
        elif body.action == 'link':
            if body.item_id == body.target or any(key not in board['cards'] for key in (body.item_id, body.target)):
                raise HTTPException(400, 'Выберите две разные карточки на доске')
            if not body.label.strip(): raise HTTPException(400, 'Подпишите связь')
            existing = next((link for link in board['links'] if {link['source'], link['target']} == {body.item_id, body.target}), None)
            if existing: existing['label'] = body.label.strip()
            else:
                if len(board['links']) >= 100: raise HTTPException(400, 'На доске уже 100 связей')
                board['links'].append({'id': secrets.token_hex(8), 'source': body.item_id, 'target': body.target, 'label': body.label.strip()})
        elif body.action == 'unlink':
            board['links'] = [link for link in board['links'] if link['id'] != body.entry_id]
        elif body.action in ('event', 'update_event'):
            if not body.text.strip(): raise HTTPException(400, 'Опишите событие')
            if body.time and int(body.time[:2]) > 23: raise HTTPException(400, 'Проверьте время')
            if body.item_id and body.item_id not in progress['opened']: raise HTTPException(400, 'Материал ещё не изучен')
            if body.action == 'event' and len(board['timeline']) >= 100: raise HTTPException(400, 'В хронологии уже 100 событий')
            name = room['host_name'] if is_host else room['players'][body.token]['name']
            if body.action == 'update_event':
                entry = next((event for event in board['timeline'] if event['id'] == body.entry_id), None)
                if not entry: raise HTTPException(409, 'Событие уже удалено другим участником')
                entry.update({'time': body.time, 'text': body.text.strip(), 'item_id': body.item_id, 'editor': name})
            else:
                board['timeline'].append({'id': secrets.token_hex(8), 'time': body.time, 'text': body.text.strip(), 'item_id': body.item_id, 'author': name})
        elif body.action == 'delete_event':
            board['timeline'] = [event for event in board['timeline'] if event['id'] != body.entry_id]
        return {'ok': True}

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
            if room.get('codenames', {}).get('phase') == 'setup': room['codenames']['seats'].pop(body.token, None)
            if room.get('tabletop', {}).get('phase') == 'setup': room['tabletop']['members'].pop(body.token,None)
            room['ready'].pop(body.token, None)
        return {'ok': True}

static = Path(__file__).resolve().parent / 'static'
if static.is_dir():
    app.mount('/images', StaticFiles(directory=static / 'images', check_dir=False), name='images')
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
    @app.get('/games')
    @app.get('/join')
    @app.get('/create')
    @app.get('/lobby/{code}')
    @app.get('/lobby/{code}/game/{game_id}')
    async def index(code: str = '', game_id: str = ''):
        return FileResponse(static / 'index.html')

