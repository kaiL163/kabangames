"""Private-role spy game; public state contains no hidden role before results."""
import random
import secrets
import time

LOCATIONS=['Больница','Космический корабль','Школа','Пляж','Ресторан','Самолёт']
QUESTIONS=['Здесь обычно тихо или шумно?','Что здесь можно увидеть?','В какой одежде сюда приходят?','Ты бы хотел здесь работать?']

def players(room):return {room['host']:room['host_name'],**{k:p['name'] for k,p in room['players'].items()}}
def start(room,rounds=10):
    if len(players(room))<4:raise ValueError('Для «Шпиона» нужны минимум четыре игрока')
    room['party']={'id':'spy','title':'Шпион','instance':secrets.token_urlsafe(12),'round':0,'phase':'result','scores':{},'total_rounds':rounds}
    next_round(room)
def next_round(room):
    g=room['party']
    if g['phase']!='result':raise ValueError('Сначала закончите раунд')
    if g['round']>=g['total_rounds']:g['phase']='finished';return
    roster=players(room)
    if len(roster)<4:raise ValueError('Нужны минимум четыре игрока')
    g['round']+=1;g['eligible']=roster;g['order']=list(roster);g['spy']=random.choice(g['order']);g['location']=random.choice(LOCATIONS)
    g.update({'turn':0,'phase':'ask','question':None,'history':[],'votes':{},'deadline':time.time()+60,'winner':None,'early':False,'chat':[],'voice_done':[], 'ids':{k:secrets.token_urlsafe(8) for k in roster}})
    for k,name in roster.items():g['scores'].setdefault(k,{'name':name,'score':0})
def pair(g):return g['order'][g['turn']%len(g['order'])],g['order'][(g['turn']+1)%len(g['order'])]
def next_turn(g):
    g['turn']+=1;g['question']=None
    g['phase']='discuss' if g['turn']>=len(g['order']) else 'ask'
    g['deadline']=time.time()+(120 if g['phase']=='discuss' else 60)
def finish(g,winner):
    g['phase']='result';g['winner']=winner
    for k in g['eligible']:
        if (winner=='spy')==(k==g['spy']):g['scores'][k]['score']+=300 if winner=='spy' and g['early'] else 200

def update(room):
    g=room['party'];phase=g['phase']
    if phase in ('ask','answer') and time.time()>=g['deadline']:
        asker,target=pair(g);g['history'].append({'asker':g['eligible'][asker],'target':g['eligible'][target],'question':g['question'] or 'Вопрос не выбран','answer':'Время вышло'});next_turn(g)
    elif phase=='discuss' and time.time()>=g['deadline']:g['phase']='vote';g['deadline']=time.time()+30
    elif phase=='vote' and (time.time()>=g['deadline'] or set(g['eligible'])<=set(g['votes'])):
        counts={k:list(g['votes'].values()).count(k) for k in g['eligible']};best=max(counts.values());leaders=[k for k,v in counts.items() if v==best]
        if best>0 and len(leaders)==1 and leaders[0]==g['spy']:finish(g,'citizens')
        else:g['phase']='locate';g['deadline']=time.time()+30
    elif phase=='locate' and time.time()>=g['deadline']:finish(g,'citizens')
def action(room,token,kind,value):
    update(room);g=room['party'];phase=g['phase']
    if token not in g['eligible']:raise ValueError('Вы присоединитесь в следующем раунде')
    asker,target=pair(g)
    if kind=='chat' and phase in ('ask','answer','discuss'):
        text=value.strip()
        if not text or len(text)>500:raise ValueError('Сообщение: от 1 до 500 символов')
        g.setdefault('chat',[]).append({'id':secrets.token_hex(8),'name':g['eligible'][token],'text':text});g['chat']=g['chat'][-100:];return
    if kind=='ask' and phase=='ask' and token==asker:
        text=value.strip()
        if not text or len(text)>300:raise ValueError('Напишите вопрос до 300 символов')
        g['question']=text;g['phase']='answer';g['deadline']=time.time()+60;return
    if kind=='voice_answer' and phase=='answer' and token==target:
        g['history'].append({'asker':g['eligible'][asker],'target':g['eligible'][target],'question':g['question'],'answer':'Ответ дан голосом / в Discord'});next_turn(g);return
    if kind=='ready_vote' and phase=='discuss':
        done=g.setdefault('voice_done',[])
        if token not in done:done.append(token)
        if set(g['eligible'])<=set(done):g['phase']='vote';g['deadline']=time.time()+30
        return
    if kind=='answer' and phase=='answer' and token==target:
        if not value.strip():raise ValueError('Напишите ответ')
        g['history'].append({'asker':g['eligible'][asker],'target':g['eligible'][target],'question':g['question'],'answer':value.strip()});next_turn(g);return
    if kind=='locate' and token==g['spy'] and phase in ('discuss','locate') and value in LOCATIONS:
        g['early']=phase=='discuss';finish(g,'spy' if value==g['location'] else 'citizens');return
    if kind=='vote' and phase=='vote':
        if token in g['votes']:raise ValueError('Голос уже принят')
        who=next((k for k,v in g['ids'].items() if v==value),None)
        if who is None or who==token:raise ValueError('Выберите другого игрока')
        g['votes'][token]=who;update(room);return
    raise ValueError('Сейчас это действие недоступно')
def view(room,token):
    update(room);g=room['party'];asker,target=pair(g);phase=g['phase']
    result={'game_id':'spy','title':'Шпион','instance':g['instance'],'round':g['round'],'total':g['total_rounds'],'phase':phase,'eligible':token in g['eligible'],'remaining':max(0,int(g['deadline']-time.time()+.999)),'is_spy':token==g['spy'],'is_asker':token==asker,'is_target':token==target,'asker':g['eligible'][asker],'target':g['eligible'][target],'chat':g.get('chat',[]),'ready_vote':token in g.get('voice_done',[]),'question':g['question'],'questions':QUESTIONS,'history':g['history'],'voted':token in g['votes'],'votes_count':len(g['votes']),'players_count':len(g['eligible']),'scores':sorted(g['scores'].values(),key=lambda v:-v['score'])}
    if token in g['eligible'] and token!=g['spy']:result['location']=g['location']
    if phase in ('discuss','locate') and token==g['spy']:result['locations']=LOCATIONS
    if phase=='vote':result['choices']=[{'id':g['ids'][k],'text':name,'own':token==k} for k,name in g['eligible'].items()]
    if phase in ('result','finished'):result.update({'location':g['location'],'spy_name':g['eligible'][g['spy']],'winner':g['winner']})
    return result
