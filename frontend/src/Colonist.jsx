import React, {useLayoutEffect, useRef, useState} from 'react'
import {Link} from 'react-router-dom'
import {AccountLink} from './Account.jsx'
import {PlayerName} from './RoomPeople.jsx'
import {CaseDialog} from './DetectiveUI.jsx'
import {Icon, Landmarks} from './ColonistArt.jsx'
import './colonist.css'

const RESOURCE = {
  wood: ['Дерево', '🌲', '#3c7359'], brick: ['Кирпич', '🧱', '#ae6349'],
  wool: ['Шерсть', '🐑', '#8b9960'], grain: ['Зерно', '🌾', '#b78c46'],
  ore: ['Руда', '🪨', '#6e828b'], desert: ['Пустыня', '☀', '#aa8b62'],
}
const resources = Object.keys(RESOURCE).filter(key => key !== 'desert')
const COLORS = ['#ffe162', '#ff8167', '#79d7ff', '#d8aaff']
const CARDS = {
  knight: 'Рыцарь', roads: 'Две дороги', plenty: 'Два ресурса',
  monopoly: 'Монополия', point: 'Победное очко',
}
const BUILD = {road: 'Дорога', home: 'Поселение', city: 'Город', robber: 'Разбойник'}
const PRICES = {
  road: 'Дерево + кирпич', home: 'Дерево + кирпич + шерсть + зерно',
  city: '2 зерна + 3 руды', buy: 'Шерсть + зерно + руда',
}
const PHASE = {
  setup_home: 'Поставь поселение', setup_road: 'Проложи дорогу от поселения',
  roll: 'Брось кубики', action: 'Торгуй, строй или заверши ход', discard: 'Сброс карт',
  robber: 'Перемести разбойника', steal: 'Выбери, у кого забрать карту',
  free_road: 'Построй бесплатную дорогу',
}

function ResourceSelect({label, value, onChange}) {
  return <label>{label}<select value={value} onChange={event => onChange(event.target.value)}>
    {resources.map(r => <option key={r} value={r}>{RESOURCE[r][1]} {RESOURCE[r][0]}</option>)}
  </select></label>
}

function ResourceSet({items, highlighted, compact = false}) {
  return <div className={`isle-resources${compact ? ' is-compact' : ''}`}>{resources.map(r => <div key={r}
    className={highlighted?.[r] ? 'is-highlighted' : undefined} style={{'--resource':RESOURCE[r][2]}}
    title={RESOURCE[r][0]}>
    <Icon kind={r}/><strong>{items[r]}</strong><small>{RESOURCE[r][0]}</small>
  </div>)}</div>
}

function spot(action, target, label, selected, onPick, busy) {
  const choose = () => {if (!busy) onPick({action, target})}
  return {
    role: 'button', tabIndex: busy ? -1 : 0, 'aria-label': label, 'aria-disabled': busy,
    'aria-pressed': selected?.action === action && selected?.target === target,
    onClick: choose, onKeyDown: event => {
      if (event.key === 'Enter' || event.key === ' ') {event.preventDefault();choose()}
    },
  }
}

function IslandBoard({game, mode, selected, onPick, onConfirm, onCancel, busy}) {
  const [zoom, setZoom] = useState(false)
  const mapScroll = useRef(null)
  useLayoutEffect(() => {
    const area = mapScroll.current
    if (zoom) area.scrollLeft = (area.scrollWidth-area.clientWidth)/2
  }, [zoom])
  const {vertices, edges, tiles, homes, roads, ports, robber, legal} = game
  const choices = new Set(legal[mode] || [])
  const rolled = game.dice?.reduce((a, b) => a+b, 0)
  return <section className="isle-map">
    <div className="isle-map-title"><div><strong>{BUILD[mode] || 'Остров'}</strong></div>
      <div className="isle-buttons">
        {selected && <button className="isle-button" aria-label="Снять выбор на поле" onClick={onCancel}>×</button>}
        {selected && <button className="isle-button is-primary" disabled={busy} onClick={onConfirm}>Подтвердить</button>}
        <button className="isle-button" aria-pressed={zoom} onClick={() => setZoom(!zoom)}>{zoom ? 'Уменьшить' : 'Приблизить'}</button>
      </div>
    </div>
    <div ref={mapScroll} className={zoom ? 'isle-map-scroll is-zoomed' : 'isle-map-scroll'} tabIndex={zoom ? 0 : undefined}>
      <svg className="isle-field" viewBox="-266 -220 532 440" role="group" aria-label="Игровое поле">
        <defs>
          <pattern id="isle-ripple" width="44" height="37" patternUnits="userSpaceOnUse"><path d="M2 8q5 4 10 0m11 16q5 4 10 0M9 34h4" fill="none" stroke="#8ccdcb" strokeOpacity=".2"/></pattern>
          <linearGradient id="isle-relief" x2="0" y2="1"><stop stopColor="#fff" stopOpacity=".17"/><stop offset="1" stopColor="#162720" stopOpacity=".17"/></linearGradient>
        </defs>
        <rect x="-266" y="-220" width="532" height="440" fill="url(#isle-ripple)"/>
        <g className="isle-shore" aria-hidden="true">{tiles.map((tile, index) => <polygon key={index} points={tile.v.map(i => vertices[i].join(',')).join(' ')}/>)}</g>
        {tiles.map(({v, x, y, resource, number}, index) => {
          const [name,, color] = RESOURCE[resource]
          const shape = v.map(i => vertices[i].join(',')).join(' ')
          const pips = 6-Math.abs(7-number)
          const props = mode === 'robber' && choices.has(index)
            ? spot(mode, index, `Переместить разбойника: ${name} ${number ?? ''}, участок ${index+1}`, selected, onPick, busy) : {}
          const producing = game.phase === 'action' && index !== robber && number === rolled
          return <g key={index} className={`isle-tile${props.role ? ' is-legal' : ''}${producing ? ' is-producing' : ''}`} {...props}>
            <polygon className="isle-land" points={shape} fill={color}/>
            <polygon points={shape} fill="url(#isle-relief)" className="isle-land-relief"/>
            <Landmarks resource={resource} x={x} y={y}/>
            {number && <g className={number === 6 || number === 8 ? 'isle-token is-hot' : 'isle-token'}>
              <circle cx={x} cy={y+12} r="14"/><text x={x} y={y+15}>{number}</text>
              {Array.from({length:pips}, (_, i) => <circle className="isle-pip" key={i} cx={x+(i-(pips-1)/2)*3.1} cy={y+20} r="1.05"/>)}
            </g>}
            {index === robber && <g className="isle-bandit" transform={`translate(${x+23},${y-8})`}>
              <path d="M-8 8v-3l3-5-1-5 6-4 6 4-1 5 3 5v3Z"/><path d="M-3-2h6"/>
            </g>}
          </g>
        })}
        {Object.entries(ports).map(([edge, resource]) => {
          const [a, b] = edges[edge].map(i => vertices[i])
          const x = (a[0]+b[0])/2, y = (a[1]+b[1])/2
          const k = 23/Math.hypot(x, y)
          const px = x*(1+k), py = y*(1+k)
          return <g className="isle-port" key={edge}>
            <path d={`M${a.join(' ')} L${px} ${py} L${b.join(' ')}`}/>
            <g transform={`translate(${px},${py})`}>
              <rect x="-17" y="-8" width="34" height="16" rx="5"/>
              {resource !== 'any' && <svg x="-14" y="-6" width="12" height="12"><Icon kind={resource}/></svg>}
              <text x={resource === 'any' ? 0 : 6} y="4">{resource === 'any' ? '3:1' : '2:1'}</text>
            </g>
          </g>
        })}
        {Object.entries(roads).map(([edge, seat]) => {
          const [[x, y], [xx, yy]] = edges[edge].map(i => vertices[i])
          return <line className="isle-road" key={edge} x1={x} y1={y} x2={xx} y2={yy} stroke={COLORS[seat]}/>
        })}
        {mode === 'road' && [...choices].map(edge => {
          const [[x, y], [xx, yy]] = edges[edge].map(i => vertices[i])
          return <g key={edge} className="isle-road-choice" {...spot(mode, edge, `Дорога ${edge+1}`, selected, onPick, busy)}>
            <line x1={x} y1={y} x2={xx} y2={yy} className="isle-road-hit"/>
            <circle cx={(x+xx)/2} cy={(y+yy)/2} r="7"/>
          </g>
        })}
        {Object.entries(homes).map(([vertex, [seat, kind]]) => {
          const [x,y] = vertices[vertex]
          return <g key={vertex} transform={`translate(${x},${y})`} className="isle-home">
            <path d={kind === 'city' ? 'M-12 8V-5h5l5-7 6 5h8V8Z' : 'M-8 7V-2l8-7 8 7v9Z'} fill={COLORS[seat]}/>
          </g>
        })}
        {(mode === 'home' || mode === 'city') && [...choices].map(vertex => {
          const [x, y] = vertices[vertex]
          return <g key={vertex} className="isle-node-choice" {...spot(mode, vertex, `${BUILD[mode]} ${vertex+1}`, selected, onPick, busy)}>
            <circle cx={x} cy={y} r="16" fill="transparent"/>
            <circle cx={x} cy={y} r={mode === 'city' ? 12 : 7} className="isle-node-visible"/>
          </g>
        })}
      </svg>
    </div>
  </section>
}

function Discard({game, action, busy}) {
  const [counts, setCounts] = useState({})
  const total = Object.values(counts).reduce((sum, n) => sum+n, 0)
  return <section className="isle-panel">
    <h2>Сбрось карты · {total} / {game.discard}</h2>
    <div className="isle-discard">{resources.map(r => <div key={r}>
      <span>{RESOURCE[r][1]} {RESOURCE[r][0]} · {game.hand[r]}</span>
      <button className="isle-button" aria-label={`Убрать из сброса: ${RESOURCE[r][0]}`} disabled={!counts[r] || busy} onClick={() => setCounts({...counts, [r]: counts[r]-1})}>−</button>
      <strong>{counts[r] || 0}</strong>
      <button className="isle-button" aria-label={`Добавить к сбросу: ${RESOURCE[r][0]}`} disabled={(counts[r] || 0) >= game.hand[r] || total >= game.discard || busy} onClick={() => setCounts({...counts, [r]: (counts[r] || 0)+1})}>+</button>
    </div>)}</div>
    <button className="isle-button is-primary" disabled={busy || total !== game.discard} onClick={() => action({action:'discard', counts})}>Сбросить</button>
  </section>
}

function Trade({game, action, busy, myTurn}) {
  const [give, setGive] = useState('wood')
  const [take, setTake] = useState('brick')
  const [giveCount, setGiveCount] = useState(1)
  const [takeCount, setTakeCount] = useState(1)
  const offer = game.offer
  const describe = items => Object.entries(items).map(([r, n]) => `${RESOURCE[r][1]} ${n} · ${RESOURCE[r][0]}`).join(', ')
  return <section className="isle-panel isle-trade">
    <h2>Обмен</h2>
    {offer && <div className="isle-offer"><p><strong>{game.players[offer.from].name}</strong> отдаёт {describe(offer.give)} за {describe(offer.take)}.</p>
      <div className="isle-buttons">{myTurn
        ? <button className="isle-button" disabled={busy} onClick={() => action({action:'cancel'})}>Снять предложение</button>
        : !offer.declined.includes(game.me) && <>
          <button className="isle-button" disabled={busy || !Object.entries(offer.take).every(([r, n]) => game.hand[r] >= n)} onClick={() => action({action:'accept', offer_id:offer.id})}>Принять</button>
          <button className="isle-button" disabled={busy} onClick={() => action({action:'decline', offer_id:offer.id})}>Отклонить</button>
        </>}</div>
    </div>}
    {myTurn && <><div className="isle-fields">
      <ResourceSelect label="Отдаю" value={give} onChange={setGive}/>
      <ResourceSelect label="Получаю" value={take} onChange={setTake}/>
      <label>Отдаю карт<input type="number" min="1" max="19" value={giveCount} onChange={event => setGiveCount(event.target.value)}/></label>
      <label>Прошу карт<input type="number" min="1" max="19" value={takeCount} onChange={event => setTakeCount(event.target.value)}/></label>
    </div>
    <div className="isle-buttons">
      <button className="isle-button" disabled={busy || give === take || game.hand[give] < game.rates[give] || !game.bank[take]} onClick={() => action({action:'bank', give, take})}>Банк · {game.rates[give]}:1</button>
      <button className="isle-button" disabled={busy || give === take || !Number.isInteger(+giveCount) || !Number.isInteger(+takeCount) || +giveCount < 1 || +giveCount > game.hand[give] || +takeCount < 1 || +takeCount > 19}
        onClick={() => action({action:'offer', give, take, give_count:+giveCount, take_count:+takeCount})}>Предложить игрокам</button>
    </div></>}
  </section>
}

function Development({game, action, busy, myTurn}) {
  const [first, setFirst] = useState('wood')
  const [second, setSecond] = useState('brick')
  if (!game.cards.length) return null
  const playable = myTurn && ['roll', 'action'].includes(game.phase)
  const canChoose = game.cards.some(card => card.ready && ['plenty','monopoly'].includes(card.kind))
  return <section className="isle-panel">
    <h2>Карты развития</h2>
    {playable && canChoose && <div className="isle-fields">
      <ResourceSelect label="Ресурс для карты" value={first} onChange={setFirst}/>
      {game.cards.some(card => card.ready && card.kind === 'plenty') && <ResourceSelect label="Второй ресурс" value={second} onChange={setSecond}/>}
    </div>}
    <div className="isle-buttons">{game.cards.map(({kind, ready}, index) => kind === 'point'
      ? <span className="isle-tag" key={index}>★ {CARDS[kind]}</span>
      : <button className="isle-button" key={index} disabled={!ready || !playable || busy}
        onClick={() => action({action:'play', card:kind, resources:[first,second], take:first})}>{CARDS[kind]}</button>)}</div>
  </section>
}

function IslandLobby({game, room, data, act, onReady, onManage, busy}) {
  const humans = [{name:data.host_name, host:true}, ...data.players]
  const count = humans.length+game.bots
  return <div className="isle-lobby">
    <section className="isle-lobby-art"><img src="/images/colonist-boar.webp" alt="Кабан строит поселение на острове"/>
      <div><h2>Соберите экспедицию</h2><p>3–4 участника. Позови друзей по коду комнаты или добавь ботов.</p></div>
    </section>
    <section className="isle-panel">
      <h2>Участники · {count} / 4</h2>
      <ul className="isle-seats">{humans.map((player, i) => <li key={player.id ?? 'host'}>
        <PlayerName name={player.name}/><span>{player.host ? 'Ведущий' : player.ready ? 'Готов' : 'Ждём'}</span>
        {room.host && i > 0 && <button className="isle-button" disabled={busy} onClick={() => onManage(player, 'kick')}>Исключить</button>}
      </li>)}{Array.from({length:game.bots}, (_, i) => <li key={`bot${i}`}><strong>Бот {i+1}</strong><span>Готов</span></li>)}</ul>
      <div className="isle-buttons">{room.host ? <>
        <button className="isle-button" disabled={busy || count >= 4} onClick={() => act({action:'add_bot'})}>Добавить бота</button>
        <button className="isle-button" disabled={busy || !game.bots} onClick={() => act({action:'remove_bot'})}>Убрать бота</button>
        <button className="isle-button is-primary" disabled={busy || count < 3 || data.players.some(p => !p.ready)} onClick={() => act({action:'start'})}>Начать партию</button>
      </> : <button className="isle-button is-primary" disabled={busy} onClick={onReady}>{data.me_ready ? 'Готов ✓' : 'Я готов'}</button>}</div>
    </section>
  </div>
}

function CostStrip({cost, hand}) {
  return <span className="isle-cost">{Object.entries(cost).map(([r, count]) => <span key={r}
    className={hand?.[r] < count ? 'is-short' : undefined} style={{'--resource':RESOURCE[r][2]}}
    title={`${RESOURCE[r][0]} × ${count}`} aria-label={`${RESOURCE[r][0]}: ${count}`}>
    <Icon kind={r}/><b>{count}</b></span>)}</span>
}

function ActionTile({icon, label, onClick, disabled, selected, supply, cost, hand, primary}) {
  const costLabel = cost && Object.entries(cost).map(([r, count]) => `${RESOURCE[r][0]} × ${count}`).join(', ')
  return <button type="button" className={`isle-action${primary ? ' is-primary' : ''}`}
    aria-label={label} aria-description={costLabel} aria-disabled={disabled || undefined} aria-pressed={selected} onClick={() => {if (!disabled) onClick()}}>
    {supply !== undefined && <small className="isle-supply" title="Доступно фигур">{supply}</small>}
    <Icon kind={icon}/><strong>{label}</strong>
    {cost && <CostStrip cost={cost} hand={hand}/>}
  </button>
}

function IslandChat({chat, act, busy}) {
  const [draft, setDraft] = useState('')
  return <>
    <ol className="isle-log" aria-label="Сообщения комнаты">
      {chat.length === 0 && <li>Здесь можно обсудить обмен или просто поговорить.</li>}
      {chat.slice().reverse().map(item => <li key={item.id}><strong>{item.name}</strong><br/>{item.text}</li>)}
    </ol>
    <form className="isle-chat-form" onSubmit={async event => {
      event.preventDefault()
      if (draft.trim() && await act({action:'chat', text:draft})) setDraft('')
    }}>
      <input aria-label="Сообщение" placeholder="Сообщение…" maxLength={240} value={draft} onChange={event => setDraft(event.target.value)}/>
      <button className="isle-button" disabled={busy || !draft.trim()}>Отправить</button>
    </form>
  </>
}

function MatchSidebar({game, act, busy, finished}) {
  const [tab, setTab] = useState('log')
  return <aside className="isle-aside" aria-label="Участники и события партии">
    <section className="isle-side-panel">
      <div className="isle-side-title"><h2>Участники</h2><span>Цель · {game.target} очков</span></div>
      <ul className="isle-scores">{game.players.map((p, i) => <li key={i}
        className={game.active === i && !finished ? 'is-active' : ''} style={{'--seat':COLORS[i]}}>
        <div><PlayerName name={p.name} suffix={game.me === i ? ' · Ты' : p.bot ? ' · Бот' : ''}/></div>
        <strong>{p.points}<small>/{game.target}</small></strong>
        <small>Ресурсы {p.size} · Развитие {p.cards}</small>
        {(game.longest === i || game.army === i) &&
          <small className="isle-award">{[game.longest === i && 'Длинная дорога', game.army === i && 'Большая армия'].filter(Boolean).join(' · ')}</small>}
      </li>)}</ul>
    </section>
    <section className="isle-side-panel">
      <div className="isle-side-title"><h2>Банк</h2><span>Колода · {game.deck}</span></div>
      <ResourceSet items={game.bank} compact/>
    </section>
    <section className="isle-side-panel isle-feed">
      <div className="isle-tab-bar" aria-label="События комнаты">
        <button type="button" aria-pressed={tab === 'log'} onClick={() => setTab('log')}>Журнал</button>
        <button type="button" aria-pressed={tab === 'chat'} onClick={() => setTab('chat')}>Чат{game.chat.length > 0 && ` · ${game.chat.length}`}</button>
      </div>
      {tab === 'log' ? <ol className="isle-log" aria-label="Последние ходы">
        {game.log.length === 0 && <li>Здесь будут ходы игроков.</li>}
        {game.log.slice(-20).reverse().map((line, i) => <li key={i}>{line}</li>)}
      </ol> : <IslandChat chat={game.chat} act={act} busy={busy}/>}
    </section>
  </aside>
}

function IslandMatch({game, room, act, busy}) {
  const [tool, setTool] = useState(null)
  const [pending, setPending] = useState(null)
  const [panel, setPanel] = useState(null)
  const myTurn = game.active === game.me
  const finished = game.phase === 'finished'
  const building = myTurn && game.phase === 'action'
  const canTrade = game.hand && game.phase === 'action' && (building || game.offer)
  const forced = {setup_home:'home', setup_road:'road', robber:'robber', free_road:'road'}[game.phase]
  const mode = myTurn && !finished ? (forced ?? (building && tool && game.legal[tool].length ? tool : null)) : null
  const selected = pending?.action === mode && game.legal[mode]?.includes(pending.target) ? pending : null
  const active = game.players[game.active]?.name
  const status = finished ? `Победа · ${game.players[game.winner].name}`
    : game.discard ? 'Выбери карты для сброса' : game.phase === 'discard' ? `Ждём сброс карт · ${game.pending}`
    : myTurn ? PHASE[game.phase] : `Ходит ${active}`
  return <div className="isle-match">
    <section className="isle-turn">
      <div className="isle-turn-heading"><i style={{background:COLORS[game.active]}}/><div><small>{game.phase.startsWith('setup') ? `РАССТАНОВКА · ${game.cursor+1} / ${game.players.length*2}` : `ХОД ${game.turn}`}{myTurn && !finished ? ' · ТВОЙ ХОД' : ''}</small><h2 role="status">{status}</h2></div></div>
      {game.dice && game.phase !== 'roll' && <div className="isle-dice" aria-label={`Кубики: ${game.dice.join(' и ')}`}>{game.dice.map((n,i) => <span key={i}>{n}</span>)}</div>}
      {(game.discard > 0 || game.phase === 'steal' || mode === 'road' && game.phase === 'free_road' || finished && room.host) && <div className="isle-buttons">
        {game.discard > 0 && <button className="isle-button is-primary" onClick={() => setPanel('discard')}>Сбросить карты</button>}
        {finished && room.host && <button className="isle-button is-primary" disabled={busy} onClick={() => act({action:'reset'})}>Новая партия</button>}
        {mode === 'road' && game.phase === 'free_road' && <button className="isle-button" disabled={busy} onClick={() => act({action:'finish_roads'})}>Закончить постройку дорог</button>}
        {myTurn && game.phase === 'steal' && game.legal.steal.map(target => <button className="isle-button" disabled={busy} key={target} onClick={() => act({action:'steal', target})}>{game.players[target].name}</button>)}
      </div>}
    </section>
    <IslandBoard game={game} mode={mode} selected={selected} onPick={setPending} onCancel={() => setPending(null)} busy={busy} onConfirm={async () => {
        if (await act(selected)) {setPending(null);setTool(null)}
      }}/>
    <section className="isle-console" aria-label="Ресурсы и действия">
      {game.hand && <div className="isle-hand">
        <div className="isle-console-title"><strong>Твои ресурсы</strong><button className="isle-text-button" disabled={game.cards.length === 0} onClick={() => setPanel('development')}>Развитие · {game.cards.length}</button></div>
        <ResourceSet items={game.hand} highlighted={building ? game.cost[mode] : null}/>
      </div>}
      <div className="isle-actions">
        {['road','home','city'].map(kind => <ActionTile key={kind} icon={kind} label={BUILD[kind]}
          cost={game.cost[kind]} hand={game.hand} supply={game.pieces[kind]} selected={building && mode === kind}
          disabled={busy || !building || !game.legal[kind].length} onClick={() => {setTool(kind);setPending(null)}}/>)}
        <ActionTile icon="buy" label="Купить карту" cost={game.cost.buy} hand={game.hand}
          disabled={busy || !game.legal.card} onClick={() => act({action:'buy'})}/>
        <ActionTile icon="trade" label={game.offer && !myTurn ? 'Предложение' : 'Обмен'} disabled={!canTrade} onClick={() => setPanel('trade')}/>
        {game.phase === 'roll' ? <ActionTile icon="dice" label="Бросить кубики" primary
          disabled={busy || !myTurn} onClick={() => act({action:'roll'})}/> :
          <ActionTile icon="end" label="Конец хода" primary disabled={busy || !building} onClick={() => act({action:'end'})}/>}
      </div>
    </section>
    <MatchSidebar game={game} act={act} busy={busy} finished={finished}/>
    {panel === 'trade' && canTrade && <CaseDialog title="Обмен ресурсами" onClose={() => setPanel(null)}><Trade key={game.turn} game={game} action={act} busy={busy} myTurn={myTurn}/></CaseDialog>}
    {panel === 'discard' && game.discard > 0 && <CaseDialog title="Сброс ресурсов" onClose={() => setPanel(null)}>
      <Discard key={game.turn} game={game} action={async fields => {if (await act(fields)) setPanel(null)}} busy={busy}/>
    </CaseDialog>}
    {panel === 'development' && <CaseDialog title="Карты развития" onClose={() => setPanel(null)}>
      {game.cards.length ? <Development game={game} action={async fields => {if (await act(fields)) setPanel(null)}} busy={busy} myTurn={myTurn}/> : <p>Карты развития можно купить в свой ход.</p>}
    </CaseDialog>}
  </div>
}

export default function Colonist({game, room, data, onAction, onLeave, onReady, onManage, busy, error}) {
  const [rules, setRules] = useState(false)
  const [copied, setCopied] = useState(false)
  const [people, setPeople] = useState(false)
  const [scoring, setScoring] = useState(false)
  if (!game) return <main className="page-shell">Подключаем Колониста…</main>
  const act = fields => onAction({instance:game.instance, rev:game.rev, ...fields})
  return <main className={`isle-page${game.phase === 'lobby' ? ' is-lobby' : ' is-playing'}`}>
    <header className="isle-header">
      <div><Link to="/" className="isle-brand">✳ KABAN GAMES</Link><h1>Колонист</h1></div>
      <div className="isle-buttons">
        <AccountLink game/>
        {!room.seat && <button className="isle-button" onClick={async () => {
          try {await navigator.clipboard.writeText(`${window.location.origin}/join?code=${room.code}`);setCopied(true)} catch {setCopied(false)}
        }}>{copied ? 'Ссылка скопирована' : `Код ${room.code} ↗`}</button>}
        <button className="isle-button" onClick={() => setRules(true)}>Как играть</button>
        <button className="isle-button" onClick={() => setScoring(true)}>Очки</button>
        {room.host && game.phase !== 'lobby' && data.players.length > 0 && <button className="isle-button" onClick={() => setPeople(true)}>Участники</button>}
        <button className="isle-button" onClick={onLeave}>{room.host ? 'Закрыть комнату' : 'Выйти'}</button>
      </div>
    </header>
    {error && <p className="isle-error" role="alert">{error}</p>}
    {game.phase === 'lobby'
      ? <IslandLobby game={game} room={room} data={data} act={act} onReady={onReady} onManage={onManage} busy={busy}/>
      : <IslandMatch key={game.instance} game={game} room={room} act={act} busy={busy}/>}
    {rules && <CaseDialog title="Как играть в Колонист" onClose={() => setRules(false)}>
      <p>Набери 10 очков. Поселение приносит 1 очко, город — 2. Дорога из пяти звеньев и три сыгранных рыцаря могут принести по 2 очка.</p>
      <p>Сначала поставь два поселения и по дороге рядом с каждым. Между поселениями оставляй свободный перекрёсток. Затем бросай кубики, получай ресурсы за постройки и строй дальше.</p>
      <p>На семёрке все с 8 и более картами сбрасывают половину. Активный игрок передвигает разбойника и забирает карту у одного соседа участка. Заблокированный участок ресурсов не даёт.</p>
      <ul>{Object.entries(PRICES).map(([kind, price]) => <li key={kind}><strong>{BUILD[kind] || 'Карта развития'}</strong> · {price}</li>)}</ul>
      <p>Банк меняет ресурсы по курсу 4:1. Постройка у порта даёт курс 3:1 или 2:1 для указанного ресурса. Можно обмениваться с другими игроками.</p>
    </CaseDialog>}
    {people && room.host && <CaseDialog title="Управление участниками" onClose={() => setPeople(false)}>
      <p>Если игрок выйдет во время партии, его место займёт бот.</p>
      <ul className="isle-seats">{data.players.map(player => <li key={player.id}>
        <PlayerName name={player.name}/><button className="isle-button" disabled={busy} onClick={() => onManage(player, 'kick')}>Исключить</button>
      </li>)}</ul>
    </CaseDialog>}
    {scoring && <CaseDialog title="Как набрать очки" onClose={() => setScoring(false)}>
      <p>Цель партии — <strong>{game.target ?? 10} очков</strong>.</p>
      <dl className="isle-point-list">
        <dt>Поселение</dt><dd>+1</dd>
        <dt>Улучшение поселения до города</dt><dd>+1</dd>
        <dt>Карта победного очка</dt><dd>+1</dd>
        <dt>Самая длинная дорога · от 5 звеньев</dt><dd>+2</dd>
        <dt>Самая большая армия · от 3 рыцарей</dt><dd>+2</dd>
      </dl>
    </CaseDialog>}
  </main>
}
