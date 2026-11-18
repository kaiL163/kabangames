"""Exercise the game engines with temporary players and in-memory state."""
import time
from types import SimpleNamespace

try:
    from . import codenames, party, quiz, spy_game, tabletop, writing_game
except ImportError:
    import codenames, party, quiz, spy_game, tabletop, writing_game


def check(condition, message):
    if not condition:
        raise ValueError(message)


def test_room(count):
    return {
        'host': 'host',
        'host_name': 'Тестовый ведущий',
        'players': {f'bot{i}': {'name': f'Бот {i}'} for i in range(1, count)},
    }


def quiz_check(mode):
    room = test_room(3)
    quiz.start(room, mode, 5)
    game = room['quiz']
    for _ in range(5):
        check('correct' not in quiz.view(room, 'bot1'), 'Ответ виден до окончания раунда.')
        correct = game['options'].index(game['correct'])
        wrong = next(i for i in range(len(game['options'])) if i != correct)
        for token, choice in [('host', correct), ('bot1', wrong), ('bot2', correct)]:
            quiz.answer(room, token, choice)
        check(quiz.view(room, 'bot1')['phase'] == 'result', 'Ответы приняты, но итог раунда недоступен.')
        quiz.next_round(room)
    check(game['phase'] == 'finished', 'Викторина не завершилась.')
    host_score = game['scores']['host']['score']
    wrong_score = game['scores']['bot1']['score']
    check(host_score > 0 and wrong_score == 0, 'Ошибочный подсчёт очков.')
    return 'Пять раундов · скрытый ответ, верные и неверные варианты, очки и финал'


def writing_check():
    room = test_room(3)
    writing_game.start(room, 5)
    for _ in range(5):
        for token in writing_game.people(room):
            writing_game.submit(room, token, f'Продолжение от {token}')
        for token in writing_game.people(room):
            choices = writing_game.view(room, token)['choices']
            check(all('author' not in choice for choice in choices), 'Автор виден во время голосования.')
            other = next(choice for choice in choices if not choice['own'])
            writing_game.vote(room, token, other['id'])
        writing_game.next_round(room)
    check(writing_game.view(room, 'host')['phase'] == 'finished', 'Партия не завершилась.')
    return 'Пять раундов · анонимные ответы, голосование и финал'


def spy_round(room, game):
    check('location' not in party.view(room, game['spy']), 'Шпион видит локацию.')
    for _ in game['order']:
        asker, target = spy_game.pair(game)
        party.action(room, asker, 'ask', 'Что находится рядом?')
        party.action(room, target, 'answer', 'Окна и двери')
    for token in game['order']:
        party.action(room, token, 'ready_vote')
    for token in game['order']:
        target = 'host' if token == game['spy'] else game['spy']
        if target == token:
            target = 'bot1'
        party.action(room, token, 'vote', game['ids'][target])
    check(game['winner'] == 'citizens', 'Голосование не определило шпиона.')


def reaction_round(room, game, round_index):
    party.action(room, 'host', 'tap')
    game.update(signal_at=time.time() - 0.05, trap=round_index % 2 == 1)
    for token in room['players']:
        party.action(room, token, 'tap')
    check(game['taps']['host']['points'] < 0, 'Фальстарт не оштрафован.')
    check((game['taps']['bot1']['points'] < 0) == game['trap'], 'Сигнал и ловушка дают неверные очки.')


def party_check(mode):
    room = test_room(4)
    party.start(room, mode, 5)
    game = room['party']
    tokens = list(party.people(room))
    for index in range(5):
        actor = game.get('actor')
        if mode == 'spy':
            spy_round(room, game)
        elif mode == 'reaction':
            reaction_round(room, game, index)
        elif mode == 'croc':
            other = next(token for token in tokens if token != actor)
            check('word' not in party.view(room, other), 'Загаданное слово видно угадывающему.')
            party.action(room, other, 'guess', game['word'])
        elif mode == 'truth':
            party.action(room, actor, 'choose', 'truth' if index % 2 == 0 else 'dare')
            party.action(room, actor, 'done')
        elif mode == 'twotruths':
            party.action(room, actor, 'facts', facts=['Первый факт', 'Второй факт', 'Выдумка'], lie=2)
            for token in tokens:
                if token != actor:
                    party.action(room, token, 'vote', game['lie'])
        else:
            if mode == 'screenwriter':
                for token in tokens:
                    party.action(room, token, 'write', f'Вариант от {token}')
            for token in tokens:
                choice = next(choice for choice in party.view(room, token)['choices'] if not choice['own'])
                party.action(room, token, 'vote', choice['id'])
        check(game['phase'] == 'result', 'Раунд остался открыт после действий игроков.')
        party.next_round(room)
    check(game['phase'] == 'finished', 'Партия не завершилась.')
    return 'Пять раундов · действия участников, итоги раундов и финал'


def codenames_check():
    for count in (2, 3):
        room = test_room(count * 2)
        codenames.setup(room)
        game = room['codenames']

        def act(token, action, **fields):
            codenames.action(room, token, SimpleNamespace(
                action=action, instance=game['instance'], turn=game['turn_number'], **fields,
            ))

        act('host', 'configure', traitor=False, team_count=count)
        tokens = iter(codenames.people(room))
        for team in codenames.teams(game):
            for role in ('captain', 'operative'):
                token = next(tokens)
                act(token, 'seat', team=team, role=role)
                act(token, 'ready')
        act('host', 'start')
        captain, operative = (token for token, _ in codenames.seats(game, game['turn']))
        check(all(card['color'] is None for card in codenames.view(room, operative)['cards']), 'Агент видит скрытые цвета.')
        act(captain, 'clue', text='Общий смысл')
        for card in game['cards']:
            if card['color'] == game['turn']:
                act(operative, 'guess', card_id=card['id'])
        check(game['phase'] == 'finished', 'Победа не завершила игру.')
    return 'Две и три команды · скрытые цвета, шифр, открытие карточек и победа'


def tabletop_check(mode):
    room = test_room(6 if mode == 'boss' else 3)
    tabletop.setup(room, mode)
    game = room['tabletop']

    def act(token, action, **fields):
        tabletop.action(room, token, {
            'action': action, 'instance': game['instance'], 'revision': game['revision'], **fields,
        })

    for index, token in enumerate(tabletop.names(room)):
        team = 'join' if mode == 'boss' else ('gm' if index == 0 else str(index - 1))
        act(token, 'seat', team=team)
        act(token, 'ready')
    act('host', 'start')
    if mode == 'boss':
        for _ in range(3):
            check(all('role' not in p for p in tabletop.view(room, 'host')['players']), 'Чужая роль видна до финала.')
            act('host', 'advance')
            hats = list(game['hats'].values())
            for player_id in hats:
                token = next(token for token, player in game['members'].items() if player['id'] == player_id)
                act(token, 'send', target=player_id)
        detail = 'Три обмена · готовность, тайные роли и победа'
    else:
        for _ in range(5):
            check(not tabletop.view(room, 'host')['countries'], 'Ведущий получил сводку до третьего этапа.')
            act('bot1', 'done')
            act('bot2', 'done')
            act('host', 'advance')
            check(tabletop.view(room, 'host')['can_report'], 'Сводка ведущего недоступна.')
            check(len(tabletop.view(room, 'bot1')['countries']) == 1, 'Игрок видит чужую страну.')
            act('host', 'advance')
        detail = 'Пять раундов · закрытые панели стран, сводка ведущего и финал'
    check(game['phase'] == 'finished', 'Партия не завершилась.')
    return detail


def simulate(mode, detective_check):
    if mode == 'detective':
        return detective_check()
    if mode == 'codenames':
        return codenames_check()
    if mode in ('boss', 'domination'):
        return tabletop_check(mode)
    if mode == 'finish':
        return writing_check()
    if mode in quiz.BANK or mode == 'carquiz':
        return quiz_check(mode)
    if mode in party.TITLES or mode in ('spy', 'reaction'):
        return party_check(mode)
    raise ValueError('Для режима ещё нет сценария проверки.')
