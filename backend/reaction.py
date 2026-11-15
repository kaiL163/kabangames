"""Server-timed reaction rounds with false-start and trap penalties."""
import random
import secrets
import time

def people(room):return {room['host']:room['host_name'],**{k:p['name'] for k,p in room['players'].items()}}
def start(room,rounds=10):
    if len(people(room))<2:raise ValueError('Нужны минимум два игрока')
    room['party']={'id':'reaction','instance':secrets.token_urlsafe(12),'title':'Реакция','round':0,'phase':'result','scores':{},'total_rounds':rounds}
    next_round(room)
def next_round(room):
    g=room['party']
    if g['phase']!='result':raise ValueError('Раунд ещё идёт')
    if g['round']>=g['total_rounds']:g['phase']='finished';return
    g['round']+=1;g['eligible']=people(room);g['taps']={};g['phase']='wait';g['signal_at']=time.time()+random.uniform(2,5);g['trap']=random.random()<.3
    for k,name in g['eligible'].items():g['scores'].setdefault(k,{'name':name,'score':0})
def update(room):
    g=room['party']
    if g['phase']=='wait' and time.time()>=g['signal_at']:g['phase']='signal'
    if g['phase'] in ('wait','signal') and (set(g['eligible'])<=set(g['taps']) or time.time()>g['signal_at']+8):g['phase']='result'
def action(room,token,kind,value):
    update(room);g=room['party']
    if token not in g['eligible']:raise ValueError('Вы присоединитесь в следующем раунде')
    if kind!='tap' or g['phase'] not in ('wait','signal'):raise ValueError('Раунд уже завершён')
    if token in g['taps']:raise ValueError('Нажатие уже принято')
    ms=int((time.time()-g['signal_at'])*1000)
    points=-200 if ms<0 else -300 if g['trap'] else max(100,1000-ms//2)
    g['taps'][token]={'name':g['eligible'][token],'ms':max(0,ms),'points':points,'reason':'Фальстарт' if ms<0 else 'Ловушка' if g['trap'] else 'Сигнал'}
    g['scores'][token]['score']+=points;update(room)
def view(room,token):
    update(room);g=room['party']
    return {'game_id':'reaction','title':'Реакция','instance':g['instance'],'round':g['round'],'total':g['total_rounds'],'phase':g['phase'],'eligible':token in g['eligible'],'tapped':token in g['taps'],'color':'grey' if g['phase']=='wait' else 'red' if g['trap'] else 'green','scores':sorted(g['scores'].values(),key=lambda x:-x['score']),'results':list(g['taps'].values()) if g['phase'] in ('result','finished') else [],'players_count':len(g['eligible'])}
