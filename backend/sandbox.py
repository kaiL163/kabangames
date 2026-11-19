"""Private test rooms and scripted actions for simulated participants."""
from contextvars import ContextVar
from dataclasses import dataclass
import secrets
import time
from types import SimpleNamespace

from fastapi import HTTPException

try:
    from . import codenames, colonist, party, quiz, spy_game, tabletop, writing_game
except ImportError:
    import codenames, colonist, party, quiz, spy_game, tabletop, writing_game


TEST_CODE = 'TEST'
LIFETIME = 60 * 60
MAX_ACTIVE_ROOMS = 64
MAX_PER_ACCOUNT = 3
active_room = ContextVar('sandbox_room', default=None)
sessions = {}


@dataclass
class Sandbox:
    id: str
    owner_id: int
    game: str
    rooms: dict
    seats: dict

    @property
    def room(self):
        return self.rooms.get(TEST_CODE)

    def participants(self):
        room = self.room
        names = party.people(room)
        return [
            {'id': seat, 'name': names[token], 'host': token == room['host']}
            for seat, token in self.seats.items() if token in names
        ]

    def summary(self):
        return {'id': self.id, 'game': self.game, 'players': len(self.participants())}


def prune():
    cutoff = time.monotonic() - LIFETIME
    for key, session in list(sessions.items()):
        if not session.room or session.room['updated'] < cutoff:
            del sessions[key]


def owned_by(owner_id):
    prune()
    return [session for session in sessions.values() if session.owner_id == owner_id]


def create(owner_id, mode, bot_count, room):
    if len(owned_by(owner_id)) >= MAX_PER_ACCOUNT or len(sessions) >= MAX_ACTIVE_ROOMS:
        raise HTTPException(409, 'Достигнут лимит тестовых комнат. Закрой одну из открытых комнат.')
    tokens = {'host': room['host']}
    for i in range(1, bot_count + 1):
        token = secrets.token_urlsafe(32)
        tokens[f'bot{i}'] = token
        room['players'][token] = {'name': f'Бот {i}', 'seen': time.monotonic()}
    session = Sandbox(secrets.token_hex(16), owner_id, mode, {TEST_CODE: room}, tokens)
    sessions[session.id] = session
    return session


def find(room_id, owner_id):
    prune()
    session = sessions.get(room_id)
    if not session or session.owner_id != owner_id:
        raise HTTPException(404, 'Тестовая комната закрыта, недоступна или истекла.')
    return session


def step(session, seat, detective_step):
    room = session.room
    excluded = {room['host'], session.seats[seat]}
    bots = [token for token in room['players'] if token not in excluded]
    if (island := room.get('colonist')) and island['phase'] != 'lobby':
        seats = {seat_id for token in bots if (seat_id := colonist.seat_for(island, token)) is not None}
        return int(colonist.bot_step(island, seats))
    if room.get('codenames'):
        return step_codenames(room, bots)
    if room.get('tabletop'):
        game = room['tabletop']
        if game['kind'] == 'domination' and game['phase'] == 'dev' and session.seats[seat] != room['host']:
            current = game['members'].get(session.seats[seat], {}).get('team')
            bots = [token for token in bots if game['members'].get(token, {}).get('team') != current]
        return step_tabletop(room, bots)
    if room.get('quiz'):
        quiz.finish_if_needed(room)
        game = room['quiz']
        if game['phase'] != 'question':
            return 0
        pending = [token for token in bots if token in game['eligible'] and token not in game['answers']]
        for index, token in enumerate(pending):
            choice = game['options'].index(game['correct'])
            quiz.answer(room, token, (choice + (index % 2)) % len(game['options']))
        return len(pending)
    if room.get('writing'):
        return step_writing(room, bots)
    if room.get('party'):
        return step_party(room, bots)
    if room.get('detective'):
        return detective_step(room, bots)
    pending = [token for token in bots if not room['ready'].get(token)]
    for token in pending:
        room['ready'][token] = True
    return len(pending)


def step_writing(room, bots):
    writing_game.update(room)
    game = room['writing']
    pending = [token for token in bots if token in game['eligible']]
    if game['phase'] == 'write':
        pending = [token for token in pending if token not in game['answers']]
        for token in pending:
            writing_game.submit(room, token, f"Предложение от {game['eligible'][token]}")
        return len(pending)
    if game['phase'] == 'vote':
        pending = [token for token in pending if token not in game['votes']]
        for token in pending:
            other = next(choice for choice in writing_game.view(room, token)['choices'] if not choice['own'])
            writing_game.vote(room, token, other['id'])
        return len(pending)
    return 0


def step_party(room, bots):
    party.update(room)
    game = room['party']
    mode, phase = game['id'], game['phase']
    bots = [token for token in bots if token in game['eligible']]
    actor = game.get('actor')
    if mode == 'spy':
        return step_spy(room, game, bots)
    if mode == 'reaction':
        if phase != 'signal' or game['trap']:
            return 0
        pending = [token for token in bots if token not in game['taps']]
        for token in pending:
            party.action(room, token, 'tap')
        return len(pending)
    if mode == 'croc' and phase == 'guess':
        guesser = next((token for token in bots if token != actor), None)
        if guesser:
            party.action(room, guesser, 'guess', game['word'])
            return 1
    if mode == 'truth' and actor in bots and phase in ('choose', 'challenge'):
        party.action(room, actor, 'choose' if phase == 'choose' else 'done', 'truth')
        return 1
    if mode == 'twotruths' and actor in bots and phase == 'write':
        party.action(room, actor, 'facts', facts=['Люблю походы', 'Жил у моря', 'Был на Луне'], lie=2)
        return 1
    if mode == 'screenwriter' and phase == 'write':
        pending = [token for token in bots if token not in game['answers']]
        for token in pending:
            party.action(room, token, 'write', f"История от {game['eligible'][token]}")
        return len(pending)
    if phase == 'vote':
        pending = [token for token in bots if token not in game['votes'] and (mode != 'twotruths' or token != actor)]
        for token in pending:
            option = next(choice for choice in game['choices'] if choice.get('owner') != token)
            party.action(room, token, 'vote', option['id'])
        return len(pending)
    return 0


def step_spy(room, game, bots):
    asker, target = spy_game.pair(game)
    phase = game['phase']
    if phase == 'ask' and asker in bots:
        party.action(room, asker, 'ask', 'Что обычно здесь происходит?')
        return 1
    if phase == 'answer' and target in bots:
        party.action(room, target, 'answer', 'Иногда тут бывает людно.')
        return 1
    if phase == 'discuss':
        pending = [token for token in bots if token not in game['voice_done']]
        for token in pending:
            party.action(room, token, 'ready_vote')
        return len(pending)
    if phase == 'vote':
        pending = [token for token in bots if token not in game['votes']]
        for token in pending:
            other = next(player for player in game['order'] if player != token)
            party.action(room, token, 'vote', game['ids'][other])
        return len(pending)
    if phase == 'locate' and game['spy'] in bots:
        party.action(room, game['spy'], 'locate', spy_game.LOCATIONS[0])
        return 1
    return 0


def step_codenames(room, bots):
    game = room['codenames']
    codenames.tick(game)

    def act(token, action, **fields):
        codenames.action(room, token, SimpleNamespace(
            action=action, instance=game['instance'], turn=game['turn_number'], **fields,
        ))

    if game['phase'] == 'setup':
        changes = 0
        for token in bots:
            if token not in game['seats']:
                team = min(codenames.teams(game), key=lambda team: len(codenames.seats(game, team)))
                role = 'operative' if any(seat['role'] == 'captain' for _, seat in codenames.seats(game, team)) else 'captain'
                act(token, 'seat', team=team, role=role)
            if not game['seats'][token]['ready']:
                act(token, 'ready')
                changes += 1
        return changes
    if game['phase'] == 'finished':
        return 0
    team = game['turn']
    role = 'operative' if game['phase'] == 'guess' else 'captain'
    candidate = next((token for token, seat in codenames.seats(game, team)
                      if token in bots and (seat['role'] == 'captain') == (role == 'captain')), None)
    if candidate is None:
        return 0
    if game['phase'] == 'clue':
        act(candidate, 'clue', text='Ассоциация — 1')
    elif game['phase'] == 'penalty':
        card = next(card for card in game['cards'] if card['color'] == team and not card['revealed'])
        act(candidate, 'guess', card_id=card['id'])
    else:
        card = next(card for card in game['cards'] if not card['revealed'])
        act(candidate, 'guess', card_id=card['id'])
    return 1


def step_tabletop(room, bots):
    game = room['tabletop']
    tabletop.tick(game)

    def act(token, action, **fields):
        tabletop.action(room, token, {
            'action': action, 'instance': game['instance'], 'revision': game['revision'], **fields,
        })

    if game['phase'] == 'setup':
        changes = 0
        for token in bots:
            if token not in game['members']:
                team = 'join'
                if game['kind'] == 'domination':
                    size = max(2, (len(room['players']) + 2) // 3)
                    team = min(map(str, range(size)), key=lambda candidate: sum(
                        member['team'] == candidate for member in game['members'].values()
                    ))
                act(token, 'seat', team=team)
            if not game['members'][token]['ready']:
                act(token, 'ready')
                changes += 1
        return changes
    if game['phase'] == 'exchange':
        submitters = [
            (token, member) for token, member in game['members'].items()
            if token in bots and member['id'] in game['hats'].values() and member['room'] not in game['sent']
        ]
        for token, member in submitters:
            act(token, 'send', target=member['id'])
        return len(submitters)
    if game['phase'] == 'play':
        actions = 0
        for token in bots:
            member = game['members'].get(token)
            if not member or member['id'] in game['votes']:
                continue
            act(token, 'chat', text='Предлагаю обсудить, кого отправим на обмен.')
            act(token, 'vote', target=game['hats'][member['room']])
            actions += 2
        return actions
    if game['phase'] == 'talk':
        for talk in game['negotiations']:
            if talk['accepted'] or talk['closed']:
                continue
            if any(other['accepted'] and not other['closed'] and
                   {talk['a'], talk['b']} & {other['a'], other['b']} for other in game['negotiations']):
                continue
            token = next((token for token in bots if game['members'].get(token, {}).get('team') == talk['b']), None)
            country = tabletop.team(game, talk['b'])
            if token and country and tabletop.alive(country):
                act(token, 'accept', negotiation=talk['id'])
                act(token, 'chat', target=talk['a'], text='Готовы обсудить условия соглашения.')
                return 2
        return 0
    if game['phase'] == 'dev':
        actions = 0
        for token in bots:
            team = game['members'].get(token, {}).get('team')
            country = tabletop.team(game, team)
            if not country or country['done'] or not tabletop.alive(country):
                continue
            city = next(city for city in country['cities'] if not city['destroyed'])
            if country['money'] >= 100 and country['used'].get('invest', 0) < 3:
                act(token, 'invest', city=city['id'])
            act(token, 'done')
            actions += 1
        return actions
    return 0
