"""Rules and public projections for the island game."""
from collections import Counter
from math import atan2, cos, pi, sin, sqrt
import random
import secrets
import time

RESOURCES = ('wood', 'brick', 'wool', 'grain', 'ore')
NAMES = dict(zip(RESOURCES, ('дерево', 'кирпич', 'шерсть', 'зерно', 'руда')))
COST = {
    'road': {'wood': 1, 'brick': 1},
    'home': {'wood': 1, 'brick': 1, 'wool': 1, 'grain': 1},
    'city': {'grain': 2, 'ore': 3},
    'card': {'wool': 1, 'grain': 1, 'ore': 1},
}
LIMIT = {'road': 15, 'home': 5, 'city': 4}
DECK = ['knight'] * 14 + ['roads', 'plenty', 'monopoly'] * 2 + ['point'] * 5


def geometry():
    vertices, edges, tiles = [], [], []
    by_point, by_edge = {}, {}
    for r in range(-2, 3):
        for q in range(-2, 3):
            if abs(q+r) > 2:
                continue
            x, y = sqrt(3)*48*(q+r/2), 72*r
            corners = []
            for side in range(6):
                angle = pi*(side/3-1/6)
                point = (round(x+48*cos(angle), 3), round(y+48*sin(angle), 3))
                if point not in by_point:
                    by_point[point] = len(vertices)
                    vertices.append(point)
                corners.append(by_point[point])
            tiles.append({'x': round(x, 3), 'y': y, 'v': corners})
            for i, a in enumerate(corners):
                edge = tuple(sorted((a, corners[(i+1) % 6])))
                if edge not in by_edge:
                    by_edge[edge] = len(edges)
                    edges.append(edge)
    return vertices, edges, tiles


VERTICES, EDGES, TILES = geometry()
NEIGHBORS = [[b if a == i else a for a, b in EDGES if i in (a, b)] for i in range(len(VERTICES))]
INCIDENT = [[e for e, edge in enumerate(EDGES) if i in edge] for i in range(len(VERTICES))]
ADJACENT_TILES = [[i for i, tile in enumerate(TILES) if v in tile['v']] for v in range(len(VERTICES))]
COAST = sorted(
    (e for e, (a, b) in enumerate(EDGES) if len(set(ADJACENT_TILES[a]) & set(ADJACENT_TILES[b])) == 1),
    key=lambda e: atan2(sum(VERTICES[v][1] for v in EDGES[e]), sum(VERTICES[v][0] for v in EDGES[e])),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def setup(room):
    room['colonist'] = {'phase': 'lobby', 'instance': secrets.token_hex(12), 'rev': 0, 'bots': 0}


def start(room):
    game = room['colonist']
    humans = [(room['host'], room['host_name']), *((token, player['name']) for token, player in room['players'].items())]
    require(3 <= len(humans) + game['bots'] <= 4, 'Для партии нужно 3–4 участника вместе с ботами.')
    players = [{'name': name, 'token': token, 'bot': False} for token, name in humans]
    used = {player['name'].casefold() for player in players}
    for seat in range(game['bots']):
        name = f'Бот {seat+1}'
        while name.casefold() in used:
            name += ' ·'
        used.add(name.casefold())
        players.append({'name': name, 'token': None, 'bot': True})
    for player in players:
        player.update(hand=dict.fromkeys(RESOURCES, 0), cards=[], knights=0)
    land = ['wood']*4 + ['wool']*4 + ['grain']*4 + ['brick']*3 + ['ore']*3 + ['desert']
    random.shuffle(land)
    numbers = [2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12]
    numbered = [i for i, resource in enumerate(land) if resource != 'desert']
    for _ in range(120):
        random.shuffle(numbers)
        hot = [i for i, n in zip(numbered, numbers) if n in (6, 8)]
        if all(len(set(TILES[i]['v']) & set(TILES[j]['v'])) < 2 for i in hot for j in hot if i != j):
            break
    values = dict(zip(numbered, numbers))
    port_types = [*RESOURCES, 'any', 'any', 'any', 'any']
    random.shuffle(port_types)
    offset = random.randrange(len(COAST))
    ports = {str(COAST[(offset + (i * len(COAST))//9) % len(COAST)]): item for i, item in enumerate(port_types)}
    order = list(range(len(players)))
    deck = list(DECK)
    random.shuffle(deck)
    game.update(
        phase='setup_home', players=players, tiles=list(zip(land, [values.get(i) for i in range(len(land))])),
        robber=land.index('desert'), ports=ports, bank=dict.fromkeys(RESOURCES, 19), homes={}, roads={},
        order=order + order[::-1], cursor=0, active=0, anchor=None, turn=1, dice=None, deck=deck,
        longest=None, army=None, offer=None, pending={}, winner=None, card_used=False, free=0,
        resume='action', log=[], next_bot=time.time() + .45,
    )


def log(game, text):
    game['log'] = [*game['log'][-39:], text]


def phase_home(game, vertex, seat):
    homes = game['homes']
    return (str(vertex) not in homes and not any(str(v) in homes for v in NEIGHBORS[vertex])
            and (any(str(e) not in game['roads'] for e in INCIDENT[vertex]) if game['phase'] == 'setup_home'
                 else any(game['roads'].get(str(e)) == seat for e in INCIDENT[vertex])))


def phase_road(game, edge, seat):
    if str(edge) in game['roads']:
        return False
    ends = EDGES[edge]
    if game['phase'] == 'setup_road':
        return game['anchor'] in ends
    for vertex in ends:
        building = game['homes'].get(str(vertex))
        if building:
            if building[0] == seat:
                return True
        elif any(game['roads'].get(str(adjacent)) == seat for adjacent in INCIDENT[vertex]):
            return True
    return False


def can_pay(hand, cost):
    return all(hand[r] >= n for r, n in cost.items())


def transfer(give, receive, amount):
    for r, n in amount.items():
        give[r] -= n
        receive[r] += n


def available(game, seat):
    empty = {'home': [], 'road': [], 'city': [], 'robber': [], 'steal': [], 'card': False}
    if seat is None or game['phase'] == 'lobby' or seat != game['active']:
        return empty
    phase = game['phase']
    own = game['players'][seat]
    homes = game['homes']
    counts = Counter(kind for owner, kind in homes.values() if owner == seat)
    if phase == 'setup_home' or (phase == 'action' and counts['home'] < LIMIT['home'] and can_pay(own['hand'], COST['home'])):
        empty['home'] = [v for v in range(len(VERTICES)) if phase_home(game, v, seat)]
    can_build = phase in ('free_road', 'setup_road') or (phase == 'action' and can_pay(own['hand'], COST['road']))
    if can_build and list(game['roads'].values()).count(seat) < LIMIT['road']:
        empty['road'] = [e for e in range(len(EDGES)) if phase_road(game, e, seat)]
    if phase == 'action' and counts['city'] < LIMIT['city'] and can_pay(own['hand'], COST['city']):
        empty['city'] = [int(v) for v, (owner, kind) in homes.items() if owner == seat and kind == 'home']
    if phase == 'robber':
        empty['robber'] = [i for i in range(len(TILES)) if i != game['robber']]
    if phase == 'steal':
        empty['steal'] = victims(game, seat)
    empty['card'] = phase == 'action' and bool(game['deck']) and can_pay(own['hand'], COST['card'])
    return empty


def victims(game, seat):
    owners = {game['homes'][str(v)][0] for v in TILES[game['robber']]['v'] if str(v) in game['homes']}
    return sorted(i for i in owners if i != seat and sum(game['players'][i]['hand'].values()))


def road_length(game, seat):
    own = {int(e) for e, owner in game['roads'].items() if owner == seat}
    if not own:
        return 0

    def walk(vertex, used):
        building = game['homes'].get(str(vertex))
        if used and building and building[0] != seat:
            return 0
        lengths = []
        for edge in INCIDENT[vertex]:
            if edge in own and edge not in used:
                a, b = EDGES[edge]
                lengths.append(1 + walk(b if a == vertex else a, used | {edge}))
        return max(lengths, default=0)

    return max(walk(vertex, set()) for edge in own for vertex in EDGES[edge])


def bonus(values, minimum, incumbent):
    high = max(values)
    if high < minimum:
        return None
    leaders = [i for i, n in enumerate(values) if n == high]
    return leaders[0] if len(leaders) == 1 else (incumbent if incumbent in leaders else None)


def points(game, seat, hidden=False):
    buildings = sum(2 if kind == 'city' else 1 for owner, kind in game['homes'].values() if owner == seat)
    awards = 2 * ((game['longest'] == seat) + (game['army'] == seat))
    cards = sum(card['kind'] == 'point' for card in game['players'][seat]['cards']) if hidden else 0
    return buildings + awards + cards


def produce(game, number):
    demand = {r: Counter() for r in RESOURCES}
    for i, (r, n) in enumerate(game['tiles']):
        if n != number or i == game['robber']:
            continue
        for vertex in TILES[i]['v']:
            if str(vertex) in game['homes']:
                seat, kind = game['homes'][str(vertex)]
                demand[r][seat] += 2 if kind == 'city' else 1
    delivered = False
    for r, seats in demand.items():
        if len(seats) > 1 and sum(seats.values()) > game['bank'][r]:
            continue
        for seat, amount in seats.items():
            n = min(amount, game['bank'][r])
            transfer(game['bank'], game['players'][seat]['hand'], {r: n})
            delivered = delivered or bool(n)
    if delivered:
        log(game, 'Банк выдал ресурсы за постройки около выпавших участков.')


def rate(game, seat, resource):
    owned = {int(v) for v, (owner, _) in game['homes'].items() if owner == seat}
    ports = [value for edge, value in game['ports'].items() if owned.intersection(EDGES[int(edge)])]
    return 2 if resource in ports else 3 if 'any' in ports else 4


def trade(game, seat, kind, body):
    hand = game['players'][seat]['hand']
    offer = game['offer']
    if kind == 'cancel':
        require(seat == game['active'] and offer, 'Нет предложения для отмены.')
        game['offer'] = None
        return
    if kind in ('accept', 'decline'):
        require(offer and seat != offer['from'] and seat not in offer['declined'] and body.get('offer_id') == offer['id'],
                'Это предложение уже недоступно.')
        if kind == 'decline':
            offer['declined'].append(seat)
            if len(offer['declined']) == len(game['players'])-1:
                game['offer'] = None
            return
        seller = game['players'][offer['from']]
        give, take = offer['give'], offer['take']
        require(can_pay(seller['hand'], give) and can_pay(hand, take), 'Для обмена уже не хватает ресурсов.')
        transfer(seller['hand'], hand, give)
        transfer(hand, seller['hand'], take)
        log(game, f"{seller['name']} и {game['players'][seat]['name']} обменялись ресурсами.")
        game['offer'] = None
        return
    give, take = body['give'], body['take']
    require(give in RESOURCES and take in RESOURCES and give != take, 'Выбери разные ресурсы.')
    if kind == 'bank':
        price = rate(game, seat, give)
        require(hand[give] >= price and game['bank'][take] > 0, 'Обмен с банком недоступен.')
        transfer(hand, game['bank'], {give: price})
        transfer(game['bank'], hand, {take: 1})
        log(game, f"{game['players'][seat]['name']} обменял ресурсы с банком.")
    else:
        n, m = body.get('give_count', 1), body.get('take_count', 1)
        require(hand[give] >= n, 'Не хватает ресурсов для предложения.')
        game['offer'] = {'id': secrets.token_hex(6), 'from': seat, 'give': {give: n}, 'take': {take: m}, 'declined': []}


def play_card(game, seat, body):
    player = game['players'][seat]
    kind = body.get('card')
    card = next((card for card in player['cards'] if card['kind'] == kind and card['turn'] < game['turn']), None)
    require(card is not None and kind != 'point' and not game['card_used'], 'Эту карту пока нельзя сыграть.')
    if kind == 'plenty':
        resources = body.get('resources', [])
        require(len(resources) == 2 and all(r in RESOURCES for r in resources), 'Выбери два ресурса.')
        amount = Counter(resources)
        require(can_pay(game['bank'], amount), 'В банке недостаточно этих ресурсов.')
        transfer(game['bank'], player['hand'], amount)
    elif kind == 'monopoly':
        resource = body.get('take')
        require(resource in RESOURCES, 'Выбери ресурс.')
        for i, other in enumerate(game['players']):
            if i != seat:
                transfer(other['hand'], player['hand'], {resource: other['hand'][resource]})
    elif kind == 'roads':
        previous = game['phase']
        game['phase'] = 'free_road'
        if not available(game, seat)['road']:
            game['phase'] = previous
            raise ValueError('Нет доступной дороги.')
        game.update(resume=previous, free=2)
    elif kind == 'knight':
        player['knights'] += 1
        game['army'] = bonus([p['knights'] for p in game['players']], 3, game['army'])
        game.update(resume=game['phase'], phase='robber')
    player['cards'].remove(card)
    game['card_used'] = True
    log(game, f"{player['name']} сыграл карту развития.")


def build(game, seat, kind, target):
    require(target in available(game, seat)[kind], 'Здесь сейчас нельзя строить.')
    phase = game['phase']
    if phase == 'action':
        transfer(game['players'][seat]['hand'], game['bank'], COST[kind])
    if kind == 'road':
        game['roads'][str(target)] = seat
    else:
        game['homes'][str(target)] = [seat, kind]
    label = {'road': 'дорогу', 'home': 'поселение', 'city': 'город'}[kind]
    log(game, f"{game['players'][seat]['name']} строит {label}.")
    if phase == 'setup_home':
        if game['cursor'] >= len(game['players']):
            for i in ADJACENT_TILES[target]:
                resource = game['tiles'][i][0]
                if game['bank'].get(resource, 0):
                    transfer(game['bank'], game['players'][seat]['hand'], {resource: 1})
        game.update(phase='setup_road', anchor=target)
    elif phase == 'setup_road':
        cursor = game['cursor'] + 1
        if cursor == len(game['order']):
            game.update(cursor=cursor, active=0, phase='roll')
        else:
            game.update(cursor=cursor, active=game['order'][cursor], phase='setup_home')
    elif phase == 'free_road':
        game['free'] -= 1
        if not game['free'] or not available(game, seat)['road']:
            game['phase'] = game['resume']
    game['longest'] = bonus([road_length(game, i) for i in range(len(game['players']))], 5, game['longest'])


def move(game, seat, body):
    kind, phase = body['action'], game['phase']
    require(seat is not None and phase != 'finished', 'Партия уже закончена.')
    player = game['players'][seat]
    hand = player['hand']
    if kind == 'discard':
        pending = game['pending'].get(str(seat))
        counts = body.get('counts') or {}
        require(phase == 'discard' and pending and set(counts) <= set(RESOURCES)
                and sum(counts.values()) == pending and can_pay(hand, counts), 'Выбери нужное количество карт для сброса.')
        transfer(hand, game['bank'], counts)
        del game['pending'][str(seat)]
        if not game['pending']:
            game['phase'] = 'robber'
    elif kind in ('accept', 'decline'):
        require(phase == 'action', 'Обмен сейчас закрыт.')
        trade(game, seat, kind, body)
    else:
        require(seat == game['active'], 'Сейчас ход другого игрока.')
        if kind in ('home', 'road', 'city'):
            build(game, seat, kind, body.get('target'))
        elif kind == 'roll' and phase == 'roll':
            dice = [random.randint(1, 6), random.randint(1, 6)]
            number = sum(dice)
            game['dice'] = dice
            log(game, f"{player['name']} бросает кубики: {dice[0]} + {dice[1]}.")
            if number == 7:
                totals = [sum(p['hand'].values()) for p in game['players']]
                game['pending'] = {str(i): n//2 for i, n in enumerate(totals) if n > 7}
                game.update(phase='discard' if game['pending'] else 'robber', resume='action')
            else:
                produce(game, number)
                game['phase'] = 'action'
        elif kind == 'robber' and phase == 'robber':
            require(body.get('target') in available(game, seat)['robber'], 'Выбери другой участок.')
            game['robber'] = body['target']
            game['phase'] = 'steal' if victims(game, seat) else game['resume']
            log(game, f"{player['name']} перемещает разбойника.")
        elif kind == 'steal' and phase == 'steal':
            target = body.get('target')
            require(target in victims(game, seat), 'Здесь нет доступной цели.')
            other = game['players'][target]
            resource = random.choice(list(Counter(other['hand']).elements()))
            transfer(other['hand'], hand, {resource: 1})
            log(game, f"{player['name']} забирает одну карту у {other['name']}.")
            game['phase'] = game['resume']
        elif kind in ('bank', 'offer', 'cancel') and phase == 'action':
            trade(game, seat, kind, body)
        elif kind == 'buy' and available(game, seat)['card']:
            transfer(hand, game['bank'], COST['card'])
            player['cards'].append({'kind': game['deck'].pop(), 'turn': game['turn']})
            log(game, f"{player['name']} покупает карту развития.")
        elif kind == 'play' and phase in ('roll', 'action'):
            play_card(game, seat, body)
        elif kind == 'finish_roads' and phase == 'free_road':
            game.update(phase=game['resume'], free=0)
        elif kind == 'end' and phase == 'action':
            game.update(active=(seat+1) % len(game['players']), turn=game['turn']+1,
                        phase='roll', offer=None, card_used=False)
        else:
            raise ValueError('Это действие сейчас недоступно.')
    if not game['phase'].startswith('setup') and points(game, game['active'], True) >= 10:
        game.update(phase='finished', winner=game['active'], offer=None)
        log(game, f"{game['players'][game['active']]['name']} набирает 10 очков и побеждает.")
    if (offer := game['offer']) and not can_pay(game['players'][offer['from']]['hand'], offer['give']):
        game['offer'] = None
    game['rev'] += 1
    game['next_bot'] = time.time() + .45


def seat_for(game, token):
    return next((i for i, p in enumerate(game.get('players', [])) if token is not None and p['token'] == token), None)


def replace_player(game, token):
    if not game or game['phase'] in ('lobby', 'finished'):
        return
    seat = seat_for(game, token)
    if seat is not None:
        game['players'][seat].update(token=None, bot=True)
        game['bots'] += 1
        game['rev'] += 1


def view(room, token):
    game = room.get('colonist')
    if not game:
        return None
    public = {key: game[key] for key in ('phase', 'instance', 'rev', 'bots')}
    if game['phase'] == 'lobby':
        return public
    seat = seat_for(game, token)
    own = game['players'][seat] if seat is not None else None
    public.update({key: game[key] for key in ('active', 'turn', 'dice', 'bank', 'homes', 'roads', 'robber',
                                              'ports', 'offer', 'log', 'winner', 'longest', 'army', 'cursor')})
    public.update(
        players=[{'name': p['name'], 'bot': p['bot'], 'cards': len(p['cards']), 'size': sum(p['hand'].values()),
                  'points': points(game, i, seat == i or game['phase'] == 'finished')}
                 for i, p in enumerate(game['players'])],
        vertices=VERTICES, edges=EDGES,
        tiles=[{**tile, 'resource': r, 'number': n} for tile, (r, n) in zip(TILES, game['tiles'])],
        me=seat, hand=own['hand'] if own else None, deck=len(game['deck']),
        cards=[{'kind': c['kind'], 'ready': c['turn'] < game['turn'] and not game['card_used']} for c in own['cards']] if own else [],
        discard=game['pending'].get(str(seat), 0), pending=len(game['pending']),
        legal=available(game, seat),
        rates={r: rate(game, seat, r) for r in RESOURCES} if own else {},
    )
    return public


def site_value(game, vertex):
    tiles = [game['tiles'][i] for i in ADJACENT_TILES[vertex]]
    return sum(6-abs(7-n) for _, n in tiles if n) + 2*len({r for r, n in tiles if n})


def bot_turn(game, seat):
    phase = game['phase']
    legal = available(game, seat)
    player = game['players'][seat]
    if phase == 'setup_home':
        target = max(legal['home'], key=lambda v: site_value(game, v))
        return {'action': 'home', 'target': target}
    if phase in ('setup_road', 'free_road', 'action') and legal['road']:
        def route_score(edge):
            a, b = EDGES[edge]
            sites = [v for v in (a, b) if str(v) not in game['homes']
                     and not any(str(n) in game['homes'] for n in NEIGHBORS[v])]
            return max((site_value(game, v) for v in sites), default=0)
        road = max(legal['road'], key=route_score)
        if phase != 'action':
            return {'action': 'road', 'target': road}
    if phase == 'free_road':
        return {'action': 'finish_roads'}
    if phase == 'roll':
        return {'action': 'roll'}
    if phase == 'robber':
        def pressure(index):
            return sum(2 if owner != seat else -4 for v in TILES[index]['v']
                       if (owner := game['homes'].get(str(v), [None])[0]) is not None)
        return {'action': 'robber', 'target': max(legal['robber'], key=pressure)}
    if phase == 'steal':
        return {'action': 'steal', 'target': random.choice(legal['steal'])}
    if phase != 'action':
        return None
    for kind in ('city', 'home'):
        if legal[kind]:
            return {'action': kind, 'target': max(legal[kind], key=lambda v: site_value(game, v))}
    hand = player['hand']
    for card in player['cards']:
        kind = card['kind']
        if card['turn'] >= game['turn'] or game['card_used'] or kind == 'point':
            continue
        if kind == 'roads' and not any(phase_road(game, e, seat) for e in range(len(EDGES))):
            continue
        if kind == 'roads' and list(game['roads'].values()).count(seat) >= LIMIT['road']:
            continue
        if kind == 'plenty':
            stock = [r for r in sorted(RESOURCES, key=hand.get) for _ in range(min(game['bank'][r], 2))]
            if len(stock) >= 2:
                return {'action': 'play', 'card': kind, 'resources': stock[:2]}
        elif kind == 'monopoly':
            return {'action': 'play', 'card': kind, 'take': min(RESOURCES, key=hand.get)}
        else:
            return {'action': 'play', 'card': kind}
    city_count = sum(owner == seat and kind == 'city' for owner, kind in game['homes'].values())
    home_count = sum(owner == seat and kind == 'home' for owner, kind in game['homes'].values())
    goals = ['home', 'city', 'road', 'card']
    goals = [goal for goal in goals if (
        goal == 'city' and home_count and city_count < LIMIT['city']
        or goal == 'home' and home_count < LIMIT['home'] and any(phase_home(game, v, seat) for v in range(len(VERTICES)))
        or goal == 'road' and list(game['roads'].values()).count(seat) < LIMIT['road'] and any(phase_road(game, e, seat) for e in range(len(EDGES)))
        or goal == 'card' and game['deck']
    )]
    goals.sort(key=lambda goal: sum(max(0, n-hand[r]) for r, n in COST[goal].items()))
    for goal in goals:
        if can_pay(hand, COST[goal]):
            if goal == 'road':
                return {'action': 'road', 'target': road}
            if goal == 'card':
                return {'action': 'buy'}
        for wanted, count in COST[goal].items():
            if hand[wanted] >= count or not game['bank'][wanted]:
                continue
            for surplus in RESOURCES:
                if surplus != wanted and hand[surplus]-COST[goal].get(surplus, 0) >= rate(game, seat, surplus):
                    return {'action': 'bank', 'give': surplus, 'take': wanted}
    return {'action': 'end'}


def bot_step(game, eligible=None, *, paced=False):
    if not game or game['phase'] in ('lobby', 'finished'):
        return False
    if paced and time.time() < game['next_bot']:
        return False
    bots = {i for i, p in enumerate(game['players']) if p['bot']} if eligible is None else eligible
    if game['phase'] == 'discard':
        for seat in sorted(bots):
            if str(seat) in game['pending']:
                hand = game['players'][seat]['hand']
                pool = list(Counter(hand).elements())
                counts = Counter(random.sample(pool, game['pending'][str(seat)]))
                move(game, seat, {'action': 'discard', 'counts': counts})
                return True
    if (offer := game['offer']) and game['phase'] == 'action':
        for seat in sorted(bots-{offer['from'], *offer['declined']}):
            hand = game['players'][seat]['hand']
            offered, requested = next(iter(offer['give'])), next(iter(offer['take']))
            acceptable = (can_pay(hand, offer['take']) and hand[requested] > hand[offered]
                          and sum(offer['give'].values()) >= sum(offer['take'].values()))
            move(game, seat, {'action': 'accept' if acceptable else 'decline', 'offer_id': offer['id']})
            return True
    if game['active'] in bots:
        body = bot_turn(game, game['active'])
        if body:
            move(game, game['active'], body)
            return True
    return False


def check():
    room = {'host': 'host', 'host_name': 'Ведущий', 'players': {}}
    setup(room)
    game = room['colonist']
    game['bots'] = 3
    start(room)
    for _ in range(2400):
        if game['phase'] == 'finished':
            return f"Полная партия из 4 участников, победа на ходу {game['turn']}."
        require(bot_step(game, {0, 1, 2, 3}), 'Партия остановилась без доступного действия.')
    raise ValueError('Партия не завершилась за лимит действий.')
