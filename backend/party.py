"""Multiplayer party rounds. Private prompts and votes never leave the server early."""
import random
import secrets
import time
try:
    from . import spy_game, reaction
except ImportError:
    import spy_game, reaction

WORDS=['Космонавт','Зубная щётка','Пингвин','Самолёт','Пицца','Детектив','Будильник','Мороженое','Рыбалка','Балерина','Пылесос','Дракон','Фотограф','Караоке','Осьминог','Черепаха','Парашют']
TRUTHS=['Какой у тебя самый странный талант?','Какой момент из детства ты вспоминаешь чаще всего?','Какую песню ты знаешь наизусть, но редко признаёшься?','Что ты давно хочешь попробовать?','Какая твоя самая смешная привычка?','Куда бы ты отправился прямо сейчас?','Что тебя всегда смешит?']
DARES=['Изобрази животное, пока остальные не угадают.','Придумай рекламный слоган для соседа справа.','Станцуй 15 секунд без музыки.','Изобрази ведущего прогноза погоды.','Скажи каждому игроку по приятной вещи.','Спой строчку любой песни шёпотом.','Покажи свою самую смешную походку.']
WHO=['Кто скорее сорвётся в спонтанное путешествие?','Кто скорее забудет, зачем вошёл в комнату?','Кто скорее станет знаменитым?','Кто скорее уснёт во время фильма?','Кто скорее заведёт необычного питомца?','Кто скорее подружится с незнакомцем?','Кто скорее начнёт танцевать первым?']
STORY=[('Кто наш герой?',['Кот-детектив','Уставший космонавт','Повар-волшебник','Пенсионерка-шпион']),('Где происходит история?',['В космическом лифте','В заброшенном кинотеатре','В круглосуточном супермаркете','На летающем острове']),('Что пошло не так?',['Исчезли все носки','Время пошло назад','Пропал завтрак','Луна упала в пруд']),('Кто злодей?',['Говорящий холодильник','Злобный будильник','Армия пылесосов','Таинственный сосед']),('Какой у героя план?',['Устроить конкурс талантов','Найти волшебную ложку','Притвориться мебелью','Попросить помощи у голубей']),('Неожиданный поворот',['Злодей оказался другом','Всё случилось во сне кота','План придумала бабушка','Появился второй холодильник']),('Кто поможет герою?',['Храбрый хомяк','Говорящая маршрутка','Почтальон из будущего','Команда уток']),('Чем всё закончилось?',['Все открыли кафе','Герой выиграл танцевальный батл','Мир спасла пицца','Все помирились за чаем'])]
WORDS += ['Ананас','Арбуз','Барабан','Батут','Бегемот','Бинокль','Блин','Бобёр','Ботинок','Букет','Велосипед','Вертолёт','Водопад','Воздушный шар','Волшебник','Воробей','Гамак','Гитара','Глобус','Гном','Голубь','Градусник','Гриб','Гусеница','Дельфин','Дирижёр','Дождевик','Дракула','Единорог','Ёжик','Жираф','Жонглёр','Заяц','Зебра','Зонтик','Кабан','Кактус','Кальмар','Кенгуру','Клавиатура','Клоун','Комар','Корабль','Корова','Краб','Кузнечик','Лабиринт','Лампа','Лев','Ледокол','Лягушка','Маяк','Медведь','Мельница','Микрофон','Муравей','Носорог','Обезьяна','Облако','Одуванчик','Официант','Панда','Паровоз','Пельмень','Пианино','Пират','Пожарный','Попкорн','Почтальон','Привидение','Пчела','Радуга','Ракета','Робот','Русалка','Самокат','Светофор','Скрипка','Слон','Снеговик','Собака','Сова','Солдат','Страус','Сыр','Танцор','Телескоп','Тигр','Трактор','Трамвай','Тюлень','Улитка','Утюг','Факел','Фейерверк','Фламинго','Фонтан','Хомяк','Художник','Цирк','Чайник','Часы','Чемодан','Шарф','Шахматы','Шоколад','Щенок','Электрик','Якорь','Ящерица','Аквалангист','Библиотекарь','Вампир','Гладиатор','Дворник','Журналист','Капитан','Маляр','Пекарь','Садовник','Таксист','Фермер','Шахтёр','Астронавт','Будильник','Вулкан','Молния','Подводная лодка','Микроскоп','Сковорода','Карусель','Футболист','Фокусник','Космодром','Медуза','Попугай','Пианино','Скейтборд','Кофемолка','Косилка','Термометр','Самовар','Бутерброд']
WORDS = list(dict.fromkeys(WORDS))
TITLES={'croc':'Крокодил','truth':'Правда или действие','twotruths':'Две правды и одна ложь','screenwriter':'Безумный сценарист','who':'Кто скорее?'}

def draw(g,key,values):
    if not g.setdefault('decks',{}).get(key):
        g['decks'][key]=random.sample(values,len(values))
    return g['decks'][key].pop()

def people(room): return {room['host']:room['host_name'],**{k:p['name'] for k,p in room['players'].items()}}
def start(room,mode,rounds=10):
    if mode=='spy':return spy_game.start(room,rounds)
    if mode=='reaction':return reaction.start(room,rounds)
    if mode not in TITLES: raise ValueError('Игра не найдена')
    minimum=3 if mode in ('twotruths','who') else 2
    if len(people(room))<minimum: raise ValueError(f'Нужно минимум {minimum} игрока, включая ведущего')
    game={'id':mode,'title':TITLES[mode],'instance':secrets.token_urlsafe(12),'round':0,'phase':'result','scores':{},'story':[],'total_rounds':8 if mode=='screenwriter' else rounds}
    room['party']=game
    next_round(room)
def next_round(room):
    g=room['party']; mode=g['id']
    if mode=='spy':return spy_game.next_round(room)
    if mode=='reaction':return reaction.next_round(room)
    if g['phase']!='result': raise ValueError('Дождитесь окончания раунда')
    if g['round']>=g['total_rounds']: g['phase']='finished'; return
    players=people(room)
    minimum=3 if mode in ('twotruths','who') else 2
    if len(players)<minimum: raise ValueError(f'Нужно минимум {minimum} игрока, включая ведущего')
    g['round']+=1;g['eligible']=players;g['votes']={};g['choices']=[];g['deadline']=time.time()+60
    for token,name in players.items():g['scores'].setdefault(token,{'name':name,'score':0})
    roster=list(players);g['actor']=roster[(g['round']-1)%len(roster)]
    if mode=='croc': g.update({'phase':'guess','word':draw(g,'words',WORDS),'guesser':None})
    elif mode=='truth':g.update({'phase':'choose','prompt':None,'deadline':None})
    elif mode=='twotruths':g.update({'phase':'write','facts':[],'lie':None})
    elif mode=='screenwriter':
        prompt,options=STORY[g['round']-1];g.update({'phase':'vote','prompt':prompt,'choices':[{'id':str(i),'text':v} for i,v in enumerate(options)],'deadline':time.time()+30})
    else:
        g.update({'phase':'vote','prompt':draw(g,'who',WHO),'choices':[{'id':secrets.token_urlsafe(12),'text':name,'owner':token} for token,name in players.items()],'deadline':time.time()+30})
def end_vote(g):
    if g['id']=='twotruths':
        for voter,choice in g['votes'].items():
            if choice==g['lie']:g['scores'][voter]['score']+=100
            else:g['scores'][g['actor']]['score']+=100
    elif g['id']=='screenwriter':
        counts={choice['id']:list(g['votes'].values()).count(choice['id']) for choice in g['choices']}
        winning=max(g['choices'],key=lambda v:counts[v['id']]) if g['votes'] else None
        g['story'].append({'prompt':g['prompt'],'answer':winning['text'] if winning else 'Нет голосов'})
    elif g['id']=='who':
        for selected in g['votes'].values():
            target=next((c['owner'] for c in g['choices'] if c['id']==selected),None)
            if target:g['scores'][target]['score']+=100
    g['phase']='result'
def update(room):
    g=room.get('party')
    if not g:return
    if g['id']=='spy':return spy_game.update(room)
    if g['id']=='reaction':return reaction.update(room)
    if g['phase']=='guess' and time.time()>=g['deadline']:g['phase']='result'
    if g['phase']=='write' and time.time()>=g['deadline']:g['phase']='result'
    if g['phase']=='vote':
        voters=set(g['eligible'])-({g['actor']} if g['id']=='twotruths' else set())
        if time.time()>=g['deadline'] or voters<=set(g['votes']):end_vote(g)
def action(room,token,kind,value='',facts=None,lie=None):
    if room['party']['id']=='spy':return spy_game.action(room,token,kind,value)
    if room['party']['id']=='reaction':return reaction.action(room,token,kind,value)
    update(room);g=room['party'];mode=g['id'];phase=g['phase']
    if token not in g['eligible']: raise ValueError('Вы присоединитесь со следующего раунда')
    if kind=='skip' and (token==g['actor'] or token==room['host']) and mode in ('truth','twotruths') and phase in ('choose','challenge','write'):
        g['phase']='result';return
    if mode=='croc' and kind=='guess' and phase=='guess':
        if token==g['actor']:raise ValueError('Показывающий не угадывает')
        if not value.strip():raise ValueError('Введите вариант')
        if value.strip().casefold().replace('ё','е')==g['word'].casefold().replace('ё','е'):
            g['guesser']=token;g['scores'][token]['score']+=100;g['scores'][g['actor']]['score']+=100;g['phase']='result'
        return
    if mode=='truth' and token==g['actor']:
        if kind=='choose' and phase=='choose' and value in ('truth','dare'):
            g['phase']='challenge';g['prompt']=draw(g,value,TRUTHS if value=='truth' else DARES);g['choice']=value;return
        if kind=='done' and phase=='challenge':g['phase']='result';return
    if mode=='twotruths' and token==g['actor'] and kind=='facts' and phase=='write':
        facts=[x.strip() for x in (facts or [])]
        if len(facts)!=3 or any(not x or len(x)>120 for x in facts) or lie not in (0,1,2):raise ValueError('Напишите три факта и отметьте ложь')
        if len(set(x.casefold() for x in facts))<3:raise ValueError('Факты должны отличаться')
        choices=[{'id':secrets.token_urlsafe(8),'text':fact,'is_lie':i==lie} for i,fact in enumerate(facts)];random.shuffle(choices)
        g.update({'choices':choices,'lie':next(c['id'] for c in choices if c['is_lie']),'phase':'vote','deadline':time.time()+30});return
    if kind=='vote' and phase=='vote' and mode in ('twotruths','screenwriter','who'):
        if mode=='twotruths' and token==g['actor']:raise ValueError('Автор не голосует')
        if token in g['votes']:raise ValueError('Вы уже проголосовали')
        selected=next((c for c in g['choices'] if c['id']==value),None)
        if not selected:raise ValueError('Вариант не найден')
        if mode=='who' and selected['owner']==token:raise ValueError('За себя голосовать нельзя')
        g['votes'][token]=value;update(room);return
    raise ValueError('Сейчас это действие недоступно')
def view(room,token):
    g=room.get('party')
    if not g:return None
    if g['id']=='spy':return spy_game.view(room,token)
    if g['id']=='reaction':return reaction.view(room,token)
    update(room);mode=g['id'];phase=g['phase'];actor=g['actor']
    result={'game_id':mode,'title':g['title'],'instance':g['instance'],'round':g['round'],'total':g['total_rounds'],'phase':phase,'actor':g['eligible'].get(actor),'is_actor':actor==token,'eligible':token in g['eligible'],'remaining':max(0,int(g['deadline']-time.time()+.999)) if g['deadline'] else None,'scores':sorted(g['scores'].values(),key=lambda p:-p['score']),'voted':token in g['votes'],'votes_count':len(g['votes']),'players_count':len(g['eligible']),'story':g['story']}
    if mode=='croc':
        if token==actor or phase=='result':result['word']=g['word']
        if phase=='result':result['guesser']=g['eligible'].get(g['guesser'])
    if mode=='truth' and phase in ('challenge','result'):result['prompt']=g.get('prompt');result['choice']=g.get('choice')
    if mode in ('screenwriter','who'):result['prompt']=g.get('prompt')
    if phase in ('vote','result','finished') and g.get('choices'):
        result['choices']=[{'id':c['id'],'text':c['text'],'own':c.get('owner')==token,**({'votes':list(g['votes'].values()).count(c['id']),'is_lie':c.get('is_lie',False)} if phase in ('result','finished') else {})} for c in g['choices']]
    return result
