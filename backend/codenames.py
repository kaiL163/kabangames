"""Server-owned Codenames state, private keys and individual team clocks."""
import math
import json
import random
import re
import secrets
import time
from pathlib import Path

ROOT=Path(__file__).parent
normalize=lambda text:re.sub(r'\s+',' ',text.strip()).casefold().replace('ё','е')
WORDS=sorted({normalize(word).upper() for filename in ('codenames_words.txt','codenames_extra.txt') for word in (ROOT/filename).read_text(encoding='utf-8-sig').split()})
THEMES={'normal':{'title':'Обычная','words':WORDS},**json.loads((ROOT/'codenames_themes.json').read_text(encoding='utf-8-sig'))}
for theme in THEMES.values():theme['words']=sorted({normalize(word).upper() for word in theme['words']})
TEAMS=('red','blue','green')
NAMES={'red':'Красные','blue':'Синие','green':'Зелёные'}
def other(team):return 'blue' if team=='red' else 'red'
def teams(game):return TEAMS[:game.get('team_count',2)]
def people(room):return {room['host']:room['host_name'],**{token:p['name'] for token,p in room['players'].items()}}
def seats(game,team):return [(token,seat) for token,seat in game['seats'].items() if seat['team']==team]
def log(game,text):
    game['history'].append({'id':secrets.token_hex(6),'text':text})
    game['history']=game['history'][-150:]
def remaining(game,team):return sum(c['color']==team and not c['revealed'] for c in game['cards'])
def alive(game):return [team for team in teams(game) if team not in game['eliminated']]

def migrate(game):
    game.setdefault('team_count',2);game.setdefault('theme','normal');game.setdefault('bonus',0)
    game.setdefault('time_limits',{team:game.get('seconds',0) for team in TEAMS})
    game.setdefault('eliminated',[])
    if 'clocks' not in game:
        game['clocks']={team:(max(0,game['deadline']-time.time()) if team==game.get('turn') and game.get('deadline') else game.get('seconds') or None) for team in teams(game)}
        game['running_since']=time.time() if game['phase'] in ('clue','guess') else None

def setup(room):
    room['codenames']={'instance':secrets.token_hex(12),'phase':'setup','seats':{},'traitor':False,'seconds':0,'team_count':2,'theme':'normal','bonus':0,'time_limits':{team:0 for team in TEAMS},'clocks':{},'running_since':None,'eliminated':[],'cards':[],'turn_number':0,'history':[],'clue':None,'winner':None,'reason':'','deadline':None}

def clocks(game,now=None):
    now=time.time() if now is None else now
    result=dict(game['clocks'])
    team=game.get('turn');started=game.get('running_since')
    if started is not None and result.get(team) is not None:result[team]=max(0,result[team]-(now-started))
    return result

def settle(game):
    game['clocks']=clocks(game)
    game['running_since']=None

def finish(game,winner,reason):
    settle(game);game.update(phase='finished',winner=winner,reason=reason,deadline=None)
    log(game,reason)

def following(game):
    order=teams(game);index=order.index(game['turn'])
    return next(order[(index+step)%len(order)] for step in range(1,len(order)+1) if order[(index+step)%len(order)] not in game['eliminated'])

def next_turn(game,bonus=True,penalty=False):
    previous=game['turn'];settle(game)
    if bonus and previous not in game['eliminated'] and game['clocks'].get(previous) is not None:game['clocks'][previous]+=game['bonus']
    game['turn']=following(game);game['turn_number']+=1
    game.update(phase='penalty' if penalty else 'clue',clue=None,running_since=None if penalty else time.time(),deadline=None)

def eliminate(game,reason):
    team=game['turn'];settle(game)
    game['eliminated'].append(team)
    # Eliminated agents are neutralised and publicly opened, keeping remaining keys fair.
    for card in game['cards']:
        if card['color']==team:card['revealed']=True
    log(game,f'{NAMES[team]} выбыли: {reason}')
    if len(alive(game))==1:finish(game,alive(game)[0],f'{NAMES[alive(game)[0]]} — последняя команда в игре. {reason}')
    else:next_turn(game,bonus=False)

def tick(game):
    migrate(game)
    if game['phase'] in ('clue','guess') and clocks(game).get(game['turn']) is not None and clocks(game)[game['turn']]<=0:
        eliminate(game,'закончилось время команды.')

def begin(room):
    game=room['codenames'];roster=people(room)
    for team in teams(game):
        members=seats(game,team);minimum=3 if game['traitor'] else 2
        if len(members)<minimum:raise ValueError(f'{NAMES[team]}: нужно минимум {minimum} игрока')
        if sum(seat['role']=='captain' for _,seat in members)!=1:raise ValueError('У каждой команды должен быть один капитан')
        if any(token not in roster or not seat['ready'] for token,seat in members):raise ValueError('Все участники команд должны быть в комнате и готовы')
    first=secrets.choice(teams(game));three=game['team_count']==3
    colors=[team for team in teams(game) for _ in range((10 if team==first else 9) if three else (9 if team==first else 8))]+['neutral']*7+['assassin']
    random.SystemRandom().shuffle(colors)
    words=random.SystemRandom().sample(THEMES[game['theme']]['words'],len(colors))
    game['cards']=[{'id':str(index),'word':word,'color':colors[index],'revealed':False} for index,word in enumerate(words)]
    if game['traitor']:
        for team in teams(game):
            candidates=[token for token,seat in seats(game,team) if seat['role']=='operative']
            game['seats'][secrets.choice(candidates)]['role']='traitor'
    game.update(phase='clue',turn=first,turn_number=1,clue=None,running_since=time.time(),clocks={team:game['time_limits'][team] or None for team in teams(game)})
    log(game,f'Партия началась. Первыми ходят {NAMES[first].lower()}. Тема: {THEMES[game["theme"]]["title"]}.')

def action(room,token,body):
    game=room['codenames'];migrate(game)
    if body.instance!=game['instance']:raise ValueError('Партия уже сменилась. Обновите страницу.')
    tick(game);host=token==room['host'];kind=body.action
    if kind=='reset':
        if not host:raise ValueError('Новую партию создаёт ведущий')
        setup(room);return
    if game['phase']=='setup':
        if kind=='configure':
            if not host:raise ValueError('Настройки меняет ведущий')
            theme=getattr(body,'theme',game['theme']);count=getattr(body,'team_count',game['team_count'])
            if theme not in THEMES or count not in (2,3):raise ValueError('Проверьте тему и число команд')
            game.update(traitor=body.traitor,theme=theme,team_count=count,bonus=getattr(body,'bonus',0),time_limits={team:getattr(body,'time_'+team,0) for team in TEAMS})
            game['seats']={key:seat for key,seat in game['seats'].items() if seat['team'] in teams(game)}
            for seat in game['seats'].values():seat['ready']=False
            return
        if kind=='seat':
            if body.team not in teams(game) and body.team!='spectator':raise ValueError('Выберите команду')
            if body.team=='spectator':game['seats'].pop(token,None);return
            if body.role not in ('captain','operative'):raise ValueError('Выберите роль')
            if body.role=='captain' and any(key!=token and seat['role']=='captain' for key,seat in seats(game,body.team)):raise ValueError('В этой команде уже есть капитан')
            game['seats'][token]={'team':body.team,'role':body.role,'ready':False,'name':people(room)[token]};return
        if kind=='ready':
            seat=game['seats'].get(token)
            if not seat:raise ValueError('Сначала выберите команду и роль')
            seat['ready']=not seat['ready'];return
        if kind=='start':
            if not host:raise ValueError('Партию запускает ведущий')
            begin(room);return
        raise ValueError('Дождитесь начала партии')
    if game['phase']=='finished':raise ValueError('Партия завершена')
    if body.turn!=game['turn_number']:raise ValueError('Ход сменился. Действие не принято.')
    seat=game['seats'].get(token)
    if not seat and not(host and kind=='invalid_clue'):raise ValueError('Вы наблюдатель до следующей партии')
    if seat and seat['team'] in game['eliminated']:raise ValueError('Ваша команда выбыла. Дождитесь следующей партии.')
    current=bool(seat and seat['team']==game['turn'])
    if kind=='clue':
        if not current or seat['role']!='captain' or game['phase']!='clue':raise ValueError('Сейчас шифр даёт капитан команды, которая ходит')
        clue=(getattr(body,'text','') or body.word).strip()
        if not clue or len(clue)>200 or any(ord(char)<32 for char in clue):raise ValueError('Введите шифр длиной до 200 символов')
        game.update(clue={'text':clue},phase='guess');log(game,f'Шифр команды «{NAMES[game["turn"]]}»: {clue}');return
    if kind=='invalid_clue':
        if game['phase']!='guess' or not(host or current and seat['role']=='captain'):raise ValueError('Нарушение подтверждает ведущий или капитан, давший шифр')
        log(game,'Шифр признан неверным. Следующая команда бесплатно открывает своё слово.')
        next_turn(game,bonus=False,penalty=True);return
    if kind=='end_turn':
        if not current or seat['role']=='captain' or game['phase']!='guess':raise ValueError('Ход завершают угадывающие игроки текущей команды')
        log(game,'Команда завершила ход.');next_turn(game);return
    if kind=='guess':
        penalty=game['phase']=='penalty'
        if not current or penalty and seat['role']!='captain' or not penalty and (seat['role']=='captain' or game['phase']!='guess'):raise ValueError('Сейчас вы не можете открывать карты')
        card=next((card for card in game['cards'] if card['id']==body.card_id),None)
        if not card or card['revealed']:raise ValueError('Карточка недоступна')
        if penalty and card['color']!=game['turn']:raise ValueError('При штрафе капитан выбирает только своё слово')
        card['revealed']=True
        color_names={**NAMES,'neutral':'мирный житель','assassin':'убийца'}
        log(game,f'Открыто «{card["word"]}» — {color_names[card["color"]]}.')
        if card['color']=='assassin':eliminate(game,'открыт убийца.');return
        for team in alive(game):
            if remaining(game,team)==0:finish(game,team,f'{NAMES[team]} нашли всех своих агентов.');return
        if penalty:game.update(phase='clue',running_since=time.time())
        elif card['color']!=game['turn']:next_turn(game)
        return
    raise ValueError('Действие недоступно')

def view(room,token):
    game=room.get('codenames')
    if not game:return None
    tick(game);roster=people(room);me=game['seats'].get(token);phase=game['phase']
    values=clocks(game)
    result={key:game[key] for key in ('instance','phase','traitor','seconds','turn_number','history','clue','winner','reason','team_count','theme','bonus','time_limits','eliminated')}
    result.update(turn=game.get('turn'),team_order=list(teams(game)),columns=6 if game['team_count']==3 else 5,
        team_clocks={team:None if value is None else max(0,math.ceil(value)) for team,value in values.items()},
        remaining=None if values.get(game.get('turn')) is None else max(0,math.ceil(values[game['turn']])),
        themes=[{'id':key,'title':theme['title'],'count':len(theme['words'])} for key,theme in THEMES.items()],
        me={'team':me['team'],'role':me['role'],'ready':me['ready']} if me else None,
        teams={team:[{'id':str(index),'name':roster.get(key,seat['name']),'role':seat['role'] if phase=='finished' or seat['role']=='captain' else 'operative','ready':seat['ready'],'present':key in roster} for index,(key,seat) in enumerate(seats(game,team))] for team in teams(game)},
        spectators=[name for key,name in roster.items() if key not in game['seats']],counts={team:remaining(game,team) for team in teams(game)})
    result['cards']=[]
    for card in game['cards']:
        see=phase=='finished' or card['revealed'] or me and (me['role']=='captain' or me['role']=='traitor' and (card['color'] in teams(game) and card['color']!=me['team'] or card['color']=='assassin'))
        result['cards'].append({'id':card['id'],'word':card['word'],'revealed':card['revealed'],'color':card['color'] if see else None})
    return result
