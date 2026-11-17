"""Standalone social deduction and country strategy; all actions are server-owned."""
import copy
import math
import secrets
import time

COUNTRIES=['🇺🇸 США','🇷🇺 Россия','🇨🇳 Китай','🇩🇪 Германия','🇯🇵 Япония','🇧🇷 Бразилия','🇮🇳 Индия','🇸🇦 Саудовская Аравия']
ROLES={'boss':'Босс','saboteur':'Подрывник','commissar':'Комиссар','quiet':'Тихоня','spy':'Шпион','civilian':'Мирный'}

def names(room):return {room['host']:room['host_name'],**{t:p['name'] for t,p in room['players'].items()}}
def log(g,text,scope='all'):g['log'].append({'id':secrets.token_hex(6),'text':text,'scope':scope});g['log']=g['log'][-200:]
def require(condition,message):
    if not condition:raise ValueError(message)
def setup(room,kind):
    room['tabletop']={'kind':kind,'instance':secrets.token_hex(12),'revision':0,'phase':'setup','round':0,'seconds':300 if kind=='boss' else 900,'deadline':None,'members':{},'log':[],'messages':[],'winner':None,'privacy_version':2,'comm_mode':'text','talk_seconds':300,'negotiations':[],'voice_teams':{},'announcements':[]}
    if kind=='domination':add_member(room['tabletop'],room['host'],room['host_name'],'gm')
def members(g):return list(g['members'].values())
def by_id(g,pid):return next((p for p in members(g) if p['id']==pid),None)
def add_member(g,token,name,team):
    old=g['members'].get(token)
    g['members'][token]={'id':old['id'] if old else secrets.token_hex(8),'name':name,'team':team,'ready':False}

def transfer_host(room,target):
    g=room.get('tabletop')
    if not g or g['kind']!='domination':return
    member=g['members'].get(target)
    require(g['phase'] in ('setup','finished') or not member or member['team']=='gm','Во время партии передать ведение можно только наблюдателю: игрок страны не должен видеть чужую статистику')
    g['members'].pop(room['host'],None)
    add_member(g,target,names(room)[target],'gm')
    g['revision']+=1
def alive(t):return any(not c['destroyed'] for c in t['cities'])
def team(g,tid):return next((t for t in g['countries'] if t['id']==tid),None)
def start_hat(g):
    roster=members(g);require(6<=len(roster)<=16 and len(roster)%2==0,'Нужно чётное число игроков: от 6 до 16')
    rng=secrets.SystemRandom();rng.shuffle(roster)
    colors=['blue']*(len(roster)//2)+['red']*(len(roster)//2);rng.shuffle(colors)
    for index,p in enumerate(roster):p.update(color=colors[index],role='civilian',room='A' if index<len(roster)//2 else 'B',shown=False,checked=None,used=False)
    boss=rng.choice([p for p in roster if p['color']=='blue']);boss['role']='boss'
    bomber=rng.choice([p for p in roster if p['color']=='red']);bomber['role']='saboteur'
    rest=[p for p in roster if p not in (boss,bomber)];rng.shuffle(rest)
    for p,role in zip(rest,['commissar','quiet','spy']):p['role']=role
    for p in roster:p['allegiance']=('red' if p['color']=='blue' else 'blue') if p['role']=='spy' else p['color']
    g.update(round=1,phase='play',deadline=time.time()+g['seconds'],votes={},sent={},hats={r:rng.choice([p['id'] for p in roster if p['room']==r]) for r in ('A','B')})
    log(g,'Роли розданы. Обсуждайте, выбирайте лидера и решайте, кого отправить.')
def finish_hat(g):
    boss=next(p for p in members(g) if p['role']=='boss');bomber=next(p for p in members(g) if p['role']=='saboteur')
    g.update(phase='finished',deadline=None,winner='red' if boss['room']==bomber['room'] else 'blue')
    log(g,'Победа '+('красных: Босс и Подрывник вместе.' if g['winner']=='red' else 'синих: Босс и Подрывник в разных комнатах.'))
def exchange(g):
    for r,pid in g['sent'].items():by_id(g,pid)['room']='B' if r=='A' else 'A'
    if g['round']==3:finish_hat(g);return
    g.update(round=g['round']+1,phase='play',deadline=time.time()+g['seconds'],votes={},sent={})
    for r in ('A','B'):
        if not any(p['id']==g['hats'][r] and p['room']==r for p in members(g)):g['hats'][r]=secrets.choice([p['id'] for p in members(g) if p['room']==r])
    log(g,'Обмен завершён. Начинается следующий раунд.')
def start_world(g):
    require(any(p['team']=='gm' for p in members(g)),'Для игры нужен отдельный ведущий')
    ids=sorted({p['team'] for p in members(g) if p['team']!='gm'})
    require(len(ids)>=2,'Займите хотя бы две страны')
    g['countries']=[{'id':i,'name':COUNTRIES[int(i)],'money':500,'eco':0,'research':False,'research_round':None,'nukes':0,'sanction':False,'income':0,'done':False,'used':{},'cities':[{'id':str(c),'name':n,'level':0,'shield':False,'destroyed':False} for c,n in enumerate(['Столица','Промышленный город','Курорт'])]} for i in ids]
    g.update(round=1,phase='dev',deadline=time.time()+g['seconds']);log(g,'Первый раунд. У каждой страны 500 монет и три города.')
def finish_world(g):
    ranking=sorted(g['countries'],key=lambda t:(sum(not c['destroyed'] for c in t['cities']),t['money']),reverse=True)
    best=(sum(not c['destroyed'] for c in ranking[0]['cities']),ranking[0]['money'])
    winners=[t['name'] for t in ranking if (sum(not c['destroyed'] for c in t['cities']),t['money'])==best]
    g.update(phase='finished',deadline=None,winner=', '.join(winners));log(g,'Итог: '+g['winner'])
def world_next(g):
    if g['phase']=='dev':
        g.update(phase='talk',deadline=time.time()+g.get('talk_seconds',300))
    elif g['phase']=='talk':
        for t in g['countries']:
            t['income']=math.floor(sum(50+30*c['level'] for c in t['cities'] if not c['destroyed'])*(1+t['eco']*.1)*(.8 if t['sanction'] else 1))
            t['money']+=t['income']
        g.update(phase='review',deadline=None);log(g,'Доход начислен. Сверьте результаты раунда.')
    elif g['phase']=='review':
        if g['round']>=5 or sum(alive(t) for t in g['countries'])<=1:finish_world(g);return
        for t in g['countries']:t.update(used={},done=False,sanction=False)
        g.update(round=g['round']+1,phase='dev',deadline=time.time()+g['seconds'])
def tick(g):
    if g['kind']=='domination':
        if g.get('privacy_version')!=2:
            g['log']=[entry for entry in g['log'] if entry['scope']!='all']
            g['messages']=[entry for entry in g['messages'] if entry['scope']!='all'];g['privacy_version']=2
        g.setdefault('comm_mode','text');g.setdefault('talk_seconds',300);g.setdefault('negotiations',[]);g.setdefault('voice_teams',{});g.setdefault('announcements',[])
        for country in g.get('countries',[]):country.setdefault('research_round',1 if country['research'] else None)
        if g['phase']!='talk':
            for n in g['negotiations']:n['closed']=True
    if g['deadline'] is not None and time.time()>=g['deadline']:
        if g['kind']=='boss' and g['phase']=='play':
            g.update(phase='exchange',deadline=None);log(g,'Время вышло. Лидеры выбирают по одному игроку для обмена.')
        elif g['kind']=='domination' and g['phase'] in ('dev','talk'):world_next(g)
        g['revision']+=1

def action(room,token,b):
    g=room['tabletop'];tick(g);kind=b['action'];host=token==room['host']
    require(b['instance']==g['instance'],'Партия уже сменилась. Обновите страницу.')
    require(b['revision']==g['revision'],'Состояние изменилось. Повторите действие.')
    if kind=='reset':
        require(host,'Только ведущий может начать новую партию');setup(room,g['kind']);return
    if g['phase']=='setup':
        if kind=='seat':
            tid=b.get('team','join')
            if tid=='spectator':g['members'].pop(token,None)
            else:
                require(g['kind']=='boss' and tid=='join' or g['kind']=='domination' and tid in [str(i) for i in range(8)]+['gm'],'Выберите место')
                require(tid!='gm' or host,'Место ведущего доступно хозяину комнаты')
                require(tid in ('join','gm') or sum(p['team']==tid for t,p in g['members'].items() if t!=token)<3,'В стране уже три участника')
                if g['kind']=='domination' and host:require(tid=='gm','Ведущий не занимает страну')
                add_member(g,token,names(room)[token],tid)
        elif kind=='ready':
            require(token in g['members'],'Сначала займите место');g['members'][token]['ready']=not g['members'][token]['ready']
        elif kind=='configure':
            require(host,'Настройки меняет ведущий');value=b.get('seconds',300)
            require(type(value)==int and 60<=value<=1800,'Выберите время от 60 до 1800 секунд');g['seconds']=value
            if g['kind']=='domination':
                mode=b.get('comm_mode',g['comm_mode']);require(mode in ('text','voice'),'Выберите способ общения')
                duration=b.get('talk_seconds',g['talk_seconds']);require(type(duration)==int and 60<=duration<=900,'Переговоры: от 60 до 900 секунд')
                g.update(comm_mode=mode,talk_seconds=duration)
            for p in members(g):p['ready']=False
        elif kind=='start':
            require(host,'Партию запускает ведущий');require(g['members'] and all(p['ready'] and t in names(room) for t,p in g['members'].items()),'Все участники должны быть в комнате и готовы')
            if g['kind']=='domination':require(g['members'].get(token,{}).get('team')=='gm','Ведущий должен занять отдельное место')
            start_hat(g) if g['kind']=='boss' else start_world(g)
        else:raise ValueError('Дождитесь старта')
    else:
        require(g['phase']!='finished','Партия завершена')
        p=g['members'].get(token)
        if kind=='advance':
            require(host,'Этап переключает ведущий')
            if g['kind']=='boss':
                require(g['phase']=='play','Дождитесь обмена');g.update(phase='exchange',deadline=None)
            else:world_next(g)
        else:
            require(p is not None,'Вы наблюдатель до следующей партии')
            if g['kind']=='boss':hat_action(g,p,b)
            else:world_action(g,p,b,host)
    g['revision']+=1

def hat_action(g,p,b):
    kind=b['action'];target=by_id(g,b.get('target'))
    if kind=='chat':
        require(g['phase'] in ('play','exchange'),'Чат закрыт');text=b.get('text','').strip();require(0<len(text)<=500,'Сообщение: от 1 до 500 символов')
        g['messages'].append({'id':secrets.token_hex(8),'name':p['name'],'text':text,'room':p['room']});g['messages']=g['messages'][-150:];return
    if kind=='show':
        require(g['phase']=='play' and p['role']!='quiet','Сейчас нельзя показать карту');p['shown']=True;log(g,p['name']+' показывает '+('красную' if p['color']=='red' else 'синюю')+' карту.',p['room']);return
    require(target and target['room']==p['room'],'Выберите игрока своей комнаты')
    if kind=='check':
        require(g['phase']=='play' and p['role']=='commissar' and not p['used'] and target!=p,'Проверка недоступна')
        p['used']=True;p['checked']={'name':target['name'],'color':target['color'],'role':target['role']};return
    if kind=='vote':
        require(g['phase']=='play','Голосование завершено');g['votes'][p['id']]=target['id']
        roster=[x for x in members(g) if x['room']==p['room']];counts={x['id']:sum(g['votes'].get(v['id'])==x['id'] for v in roster) for x in roster}
        most=max(counts.values());leaders=[pid for pid,count in counts.items() if count==most]
        if len(leaders)==1:g['hats'][p['room']]=leaders[0]
    elif kind=='send':
        require(g['phase']=='exchange' and g['hats'][p['room']]==p['id'],'Отправляет лидер во время обмена')
        require(p['room'] not in g['sent'],'Выбор уже подтверждён');g['sent'][p['room']]=target['id']
        if len(g['sent'])==2:exchange(g)
    else:raise ValueError('Действие недоступно')

def world_action(g,p,b,host):
    kind=b['action'];own=team(g,p['team']);dest=team(g,b.get('target'))
    if kind in ('negotiate','accept','decline','close'):
        require(g['phase']=='talk' and own and alive(own),'Личные переговоры доступны странам на втором этапе')
        talks=g.setdefault('negotiations',[])
        if kind=='negotiate':
            require(dest and dest!=own,'Выберите другую страну')
            require(not any(not n['closed'] and set((n['a'],n['b']))==set((own['id'],dest['id'])) for n in talks),'Переговоры уже предложены')
            talks.append({'id':secrets.token_hex(12),'a':own['id'],'b':dest['id'],'accepted':False,'closed':False,'room':secrets.token_hex(16),'password':secrets.token_hex(20)})
        else:
            n=next((n for n in talks if n['id']==b.get('negotiation')),None)
            require(n and not n['closed'] and own['id'] in (n['a'],n['b']),'Переговоры недоступны')
            if kind=='accept':
                require(n['b']==own['id'],'Приглашение принимает адресат')
                require(not any(other['accepted'] and not other['closed'] and (n['a'] in (other['a'],other['b']) or n['b'] in (other['a'],other['b'])) for other in talks if other!=n),'Одна из стран уже ведёт личные переговоры')
                n['accepted']=True
            else:n['closed']=True
        return
    if kind=='announce':
        require(host and p['team']=='gm' and g['phase']=='review','Сводку публикует ведущий на третьем этапе')
        text=b.get('text','').strip();require(0<len(text)<=500,'Сводка: от 1 до 500 символов')
        g['announcements'].append({'id':secrets.token_hex(8),'text':text,'round':g['round']});g['announcements']=g['announcements'][-30:];return
    if kind=='chat':
        text=b.get('text','').strip();require(0<len(text)<=500,'Сообщение: от 1 до 500 символов')
        require(own,'Ведущий использует сводку на третьем этапе')
        dest_id=b.get('target','')
        if dest_id:
            require(g['phase']=='talk' and dest and dest!=own,'Личные сообщения доступны на втором этапе')
            require(any(n['accepted'] and not n['closed'] and set((n['a'],n['b']))==set((own['id'],dest_id)) for n in g['negotiations']),'Сначала дождитесь согласия на переговоры')
        g['messages'].append({'id':secrets.token_hex(8),'name':p['name'],'text':text,'scope':own['id'],'to':dest_id or own['id'],'round':g['round']});g['messages']=g['messages'][-150:];return
    if kind=='reward':
        require(host and p['team']=='gm' and dest and g['phase']=='review','Баланс меняет ведущий на третьем этапе');amount=b.get('amount',0)
        require(type(amount)==int and -1000<=amount<=1000 and dest['money']+amount>=0,'Сумма: от −1000 до 1000, баланс не может быть отрицательным')
        dest['money']+=amount;log(g,f'Ведущий изменил ваш баланс на {amount:+}.',dest['id']);return
    require(g['phase']=='dev' and own and alive(own) and not own['done'],'Действия доступны живой стране в фазе развития')
    if kind=='done':
        own['done']=True
        if all(t['done'] or not alive(t) for t in g['countries']):world_next(g)
        return
    city=next((c for c in (dest if kind=='attack' and dest else own)['cities'] if c['id']==b.get('city')),None)
    costs={'invest':100,'shield':150,'eco':150,'research':200,'build':300,'transfer':100,'sanction':0,'attack':0}
    require(kind in costs,'Неизвестное действие');require(own['money']>=costs[kind],'Не хватает денег')
    if kind in ('invest','shield'):require(city and not city['destroyed'],'Город недоступен')
    if kind=='attack':require(city,'Выберите город')
    if kind in ('transfer','sanction','attack'):require(dest and dest!=own,'Выберите другую страну')
    if kind=='invest':require(own['used'].get('invest',0)<3,'Не больше трёх инвестиций за раунд');city['level']+=1
    elif kind=='shield':require(not own['used'].get('shield') and not city['shield'],'Щит уже есть или действие использовано');city['shield']=True
    elif kind=='eco':require(not own['used'].get('eco'),'Экология уже улучшена в этом раунде');own['eco']+=1
    elif kind=='research':
        require(not own['research'],'Ядерная технология уже разработана');own['research']=True;own['research_round']=g['round']
    elif kind=='build':require(own['research'] and g['round']>own.get('research_round',1) and own['nukes']<2 and not own['used'].get('build'),'Ракеты строятся со следующего раунда после разработки; нужны деньги и свободный запас');own['nukes']+=1
    elif kind=='transfer':dest['money']+=100
    elif kind=='sanction':require(not own['used'].get('sanction'),'Не больше одних санкций за раунд');dest['sanction']=True
    elif kind=='attack':
        require(own['nukes']>0,'Нет ракет');own['nukes']-=1
        if city['shield']:city['shield']=False
        else:city['destroyed']=True
    own['money']-=costs[kind];own['used'][kind]=own['used'].get(kind,0)+1
    labels={'invest':'инвестиции','shield':'щит','eco':'экология','research':'разработка ракет','build':'постройка ракеты','transfer':'перевод 100 монет','sanction':'санкции','attack':'ракетный удар'}
    log(g,labels[kind]+(' → '+dest['name'] if dest else '')+(' · '+city['name'] if city else ''),own['id'])
    if kind in ('attack','sanction','transfer'):log(g,{'attack':'По вашему городу нанесён ракетный удар.','sanction':'На вашу страну наложены санкции.','transfer':'Ваша страна получила перевод 100 монет.'}[kind],dest['id'])

def view(room,token):
    g=room.get('tabletop')
    if not g:return None
    tick(g);p=g['members'].get(token);finished=g['phase']=='finished';setup_phase=g['phase']=='setup'
    data={key:copy.deepcopy(g[key]) for key in ('kind','instance','revision','phase','round','seconds','winner')}
    data['remaining']=None if g['deadline'] is None else max(0,math.ceil(g['deadline']-time.time()))
    data['me']=copy.deepcopy(p)
    if data['me']:data['me'].pop('allegiance',None)
    data['roster']=[{'id':x['id'],'name':x['name'],'team':x['team'],'ready':x['ready'],'present':t in names(room)} for t,x in g['members'].items()]
    scope=p.get('room') if p else None
    data['log']=[x for x in g['log'] if x['scope']=='all' or x['scope']==scope or finished]
    if g['kind']=='boss':
        data['roles']=ROLES;data['hats']=g.get('hats',{});data['submitted']=list(g.get('sent',{}))
        data['players']=[{'id':x['id'],'name':x['name'],'room':x.get('room'),'color':x.get('color') if finished or x.get('shown') else None,**({'role':x['role'],'allegiance':x['allegiance']} if finished else {})} for x in members(g) if setup_phase or finished or scope and x.get('room')==scope]
        data['messages']=[m for m in g['messages'] if finished or m['room']==scope]
        data['my_vote']=g.get('votes',{}).get(p['id']) if p else None
    else:
        gm=token==room['host'] and bool(p and p['team']=='gm')
        own=team(g,p['team']) if p and not setup_phase else None
        can_report=gm and g['phase']=='review'
        data['countries']=copy.deepcopy(g.get('countries',[])) if can_report else ([copy.deepcopy(own)] if own else [])
        data.update(comm_mode=g['comm_mode'],talk_seconds=g['talk_seconds'],is_gm=gm,can_report=can_report,country_names=COUNTRIES)
        data['directory']=[{'id':t['id'],'name':t['name']} for t in g.get('countries',[])]
        if not setup_phase:data['roster']=[x for x in data['roster'] if p and x['team']==p['team']]
        country=p['team'] if p else None
        data['log']=[x for x in g['log'] if x['scope']=='all' or x['scope']==country]
        data['messages']=[m for m in g['messages'] if country and (m['scope']==country or m.get('to')==country)]
        data['announcements']=[a for a in g['announcements'] if a['round']==g['round']] if g['phase']=='review' else []
        talks=[n for n in g['negotiations'] if country in (n['a'],n['b']) and not n['closed']] if g['phase']=='talk' else []
        data['negotiations']=[{k:n[k] for k in ('id','a','b','accepted')} for n in talks]
        data['voice_channels']=[]
        if g['comm_mode']=='voice' and p and not setup_phase and not finished:
            def channel(key,label,listen=False):
                credentials=g['voice_teams'].setdefault(key,{'room':secrets.token_hex(16),'password':secrets.token_hex(20)})
                return {'id':key,'label':label,'listen_only':listen,**credentials}
            if own:data['voice_channels'].append(channel('team:'+country,'Голос своей команды'))
            for n in talks:
                if n['accepted']:data['voice_channels'].append({'id':n['id'],'label':'Личные переговоры: '+team(g,n['b'] if n['a']==country else n['a'])['name'],'room':n['room'],'password':n['password'],'listen_only':False})
            if g['phase']=='review':data['voice_channels'].append(channel('report:'+str(g['round']),'Сводка ведущего',not gm))
    return data
