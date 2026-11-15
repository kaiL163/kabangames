"""Anonymous collaborative writing and voting rounds."""
import random
import secrets
import time

PROMPTS = ['На самом деле понедельник придумали, чтобы…','Главное правило идеальной вечеринки — никогда не…','Я открыл холодильник и увидел там…','Мой супергеройский костюм состоит из…','Если бы коты управляли миром, они бы первым делом…','Самая странная причина опоздать на работу — это…','В моём тайном резюме написано…','Вместо будильника меня каждое утро будит…']

def people(room):
    return {room['host']:room['host_name'], **{token:p['name'] for token,p in room['players'].items()}}

def start(room):
    if len(people(room)) < 3: raise ValueError('Для игры нужно минимум три участника, включая ведущего')
    prompts = PROMPTS[:]; random.shuffle(prompts)
    room['writing']={'instance':secrets.token_urlsafe(12),'id':'finish','title':'Закончи фразу','prompts':prompts[:5],'index':-1,'phase':'result','scores':{}}
    next_round(room)

def next_round(room):
    game=room['writing']
    if game['phase']!='result': raise ValueError('Дождитесь окончания раунда')
    if game['index']+1 >= len(game['prompts']): game['phase']='finished'; return
    game['index']+=1
    game.update({'eligible':people(room),'answers':{},'votes':{},'order':[], 'phase':'write','deadline':time.time()+60})
    for token,name in game['eligible'].items(): game['scores'].setdefault(token,{'name':name,'score':0})

def update(room):
    game=room.get('writing')
    if not game: return
    if game['phase']=='write' and (time.time() >= game['deadline'] or set(game['eligible']) <= set(game['answers'])):
        game['order']=list(game['answers']);random.shuffle(game['order'])
        if len(game['order']) < 2:
            game['phase']='result'
        else:
            game['phase']='vote';game['deadline']=time.time()+30
    if game['phase']=='vote' and (time.time() >= game['deadline'] or set(game['eligible']) <= set(game['votes'])):
        game['phase']='result'
        for author in game['votes'].values(): game['scores'][author]['score'] += 100

def submit(room,token,text):
    update(room);game=room['writing']
    if game['phase']!='write': raise ValueError('Приём ответов уже завершён')
    if token not in game['eligible']: raise ValueError('Вы присоединитесь в следующем раунде')
    if token in game['answers']: raise ValueError('Ответ уже отправлен')
    text=text.strip()
    if not text: raise ValueError('Напишите продолжение фразы')
    game['answers'][token]={'id':secrets.token_urlsafe(12),'text':text}
    update(room)

def vote(room,token,answer_id):
    update(room);game=room['writing']
    if game['phase']!='vote': raise ValueError('Голосование уже завершено')
    if token not in game['eligible']: raise ValueError('Вы присоединитесь в следующем раунде')
    if token in game['votes']: raise ValueError('Вы уже проголосовали')
    target=next((author for author,answer in game['answers'].items() if answer['id']==answer_id),None)
    if target is None: raise ValueError('Ответ не найден')
    if target==token: raise ValueError('За свой ответ голосовать нельзя')
    game['votes'][token]=target
    update(room)

def view(room,token):
    game=room.get('writing')
    if not game:return None
    update(room); phase=game['phase']
    result={'game_id':'finish','instance':game['instance'],'title':game['title'],'phase':phase,'round':game['index']+1,'total':len(game['prompts']),'prompt':game['prompts'][game['index']], 'remaining':max(0,int(game['deadline']-time.time()+.999)), 'eligible':token in game['eligible'], 'submitted':token in game['answers'],'voted':token in game['votes'], 'submitted_count':len(game['answers']),'votes_count':len(game['votes']),'players_count':len(game['eligible']), 'scores':sorted(game['scores'].values(),key=lambda v:-v['score'])}
    if phase in ('vote','result','finished'):
        result['choices']=[{'id':game['answers'][author]['id'],'text':game['answers'][author]['text'],'own':author==token,**({'author':game['eligible'][author],'votes':sum(v==author for v in game['votes'].values())} if phase in ('result','finished') else {})} for author in game['order']]
    return result
