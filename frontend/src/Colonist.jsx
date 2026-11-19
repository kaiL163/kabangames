import React, {useState} from 'react'
import {Link} from 'react-router-dom'
import {AccountLink} from './Account.jsx'
import {PlayerName} from './RoomPeople.jsx'
import {CaseDialog} from './DetectiveUI.jsx'
import './colonist.css'

const RESOURCE = {
  wood: ['Дерево', '🌲', '#417251'], brick: ['Кирпич', '🧱', '#b66a4a'],
  wool: ['Шерсть', '🐑', '#7b955c'], grain: ['Зерно', '🌾', '#c69c50'],
  ore: ['Руда', '🪨', '#717e89'], desert: ['Пустыня', '☀', '#aa8c69'],
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

function ResourceSet({items}) {
  return <div className="isle-resources">{resources.map(r => <div key={r}>
    <span aria-hidden="true">{RESOURCE[r][1]}</span><strong>{items[r]}</strong><small>{RESOURCE[r][0]}</small>
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

function IslandBoard({game, mode, selected, onPick, onConfirm, busy}) {
  const [zoom, setZoom] = useState(false)
  const {vertices, edges, tiles, homes, roads, ports, robber, legal} = game
  const choices = new Set(legal[mode] || [])
  const rolled = game.dice?.reduce((a, b) => a+b, 0)
  return <section className="isle-map">
    <div className="isle-map-title"><div><strong>Остров</strong><small>{BUILD[mode] ? ` · ${BUILD[mode]}` : ''}</small></div>
      <div className="isle-buttons">
        {selected && <button className="isle-button is-primary" disabled={busy} onClick={onConfirm}>Подтвердить</button>}
        <button className="isle-button" aria-pressed={zoom} onClick={() => setZoom(!zoom)}>{zoom ? 'Уменьшить' : 'Приблизить'}</button>
      </div>
    </div>
    <div className={zoom ? 'isle-map-scroll is-zoomed' : 'isle-map-scroll'} tabIndex={zoom ? 0 : undefined}>
      <svg className="isle-field" viewBox="-266 -231 532 462" role="group" aria-label="Игровое поле">
        <defs>
          <pattern id="isle-ripple" width="34" height="25" patternUnits="userSpaceOnUse"><path d="M2 8q5 4 10 0m7 12q5 4 10 0" fill="none" stroke="#8ccdcb" strokeOpacity=".18"/></pattern>
        </defs>
        <rect x="-266" y="-231" width="532" height="462" fill="url(#isle-ripple)"/>
        {tiles.map(({v, x, y, resource, number}, index) => {
          const [name, icon, color] = RESOURCE[resource]
          const props = mode === 'robber' && choices.has(index)
            ? spot(mode, index, `Переместить разбойника: ${name} ${number ?? ''}, участок ${index+1}`, selected, onPick, busy) : {}
          const producing = game.phase === 'action' && index !== robber && number === rolled
          return <g key={index} className={`isle-tile${props.role ? ' is-legal' : ''}${producing ? ' is-producing' : ''}`} {...props}>
            <polygon points={v.map(i => vertices[i].join(',')).join(' ')} fill={color}/>
            <text x={x} y={y-5} className="isle-terrain">{icon}</text>
            {number && <g><rect x={x-13} y={y+4} width="26" height="22" rx="7" fill="#fff2ce"/>
              <text x={x} y={y+20} className={number === 6 || number === 8 ? 'isle-number is-hot' : 'isle-number'}>{number}</text></g>}
            {index === robber && <g><circle cx={x+22} cy={y-7} r="10" fill="#192830" stroke="#fff0c4" strokeWidth="2"/>
              <text x={x+22} y={y-2} className="isle-robber">⛔</text></g>}
          </g>
        })}
        {Object.entries(ports).map(([edge, resource]) => {
          const [a, b] = edges[edge].map(i => vertices[i])
          const x = (a[0]+b[0])/2, y = (a[1]+b[1])/2
          const k = 23/Math.hypot(x, y)
          return <g className="isle-port" key={edge} transform={`translate(${x*(1+k)},${y*(1+k)})`}>
            <rect x="-17" y="-8" width="34" height="16" rx="7"/>
            <text y="4">{resource === 'any' ? '3:1' : `${RESOURCE[resource][1]} 2:1`}</text>
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

function IslandMatch({game, room, act, busy}) {
  const [tool, setTool] = useState(null)
  const [pending, setPending] = useState(null)
  const [trading, setTrading] = useState(false)
  const myTurn = game.active === game.me
  const finished = game.phase === 'finished'
  const forced = {setup_home:'home', setup_road:'road', robber:'robber', free_road:'road'}[game.phase]
  const mode = myTurn && !finished ? (forced ?? (game.phase === 'action' ? tool : null)) : null
  const selected = pending?.action === mode && game.legal[mode]?.includes(pending.target) ? pending : null
  const active = game.players[game.active]?.name
  const status = finished ? `Победа · ${game.players[game.winner].name}`
    : game.discard ? 'Выбери карты для сброса' : game.phase === 'discard' ? `Ждём сброс карт · ${game.pending}`
    : myTurn ? PHASE[game.phase] : `Ходит ${active}`
  return <div className="isle-match">
    <section className="isle-turn">
      <div><small>{game.phase.startsWith('setup') ? `РАССТАНОВКА · ${game.cursor+1} / ${game.players.length*2}` : `ХОД ${game.turn}`}</small><h2 role="status">{status}</h2></div>
      {game.dice && <div className="isle-dice" aria-label={`Кубики: ${game.dice.join(' и ')}`}>{game.dice.map((n,i) => <span key={i}>{n}</span>)}</div>}
      <div className="isle-buttons">
        {finished && room.host && <button className="isle-button is-primary" disabled={busy} onClick={() => act({action:'reset'})}>Новая партия</button>}
        {myTurn && game.phase === 'roll' && <button className="isle-button is-primary" disabled={busy} onClick={() => act({action:'roll'})}>Бросить кубики</button>}
        {myTurn && game.phase === 'action' && <>
          {['road','home','city'].map(kind => <button className="isle-button" key={kind} title={PRICES[kind]} aria-pressed={mode === kind}
            disabled={busy || !game.legal[kind].length} onClick={() => {setTool(kind);setPending(null)}}>{BUILD[kind]}</button>)}
          <button className="isle-button" title={PRICES.buy} disabled={busy || !game.legal.card} onClick={() => act({action:'buy'})}>Карта развития</button>
          <button className="isle-button" aria-expanded={trading} onClick={() => setTrading(!trading)}>Обмен</button>
          <button className="isle-button is-primary" disabled={busy} onClick={() => act({action:'end'})}>Завершить ход</button>
        </>}
        {mode === 'road' && game.phase === 'free_road' && <button className="isle-button" disabled={busy} onClick={() => act({action:'finish_roads'})}>Закончить постройку дорог</button>}
        {myTurn && game.phase === 'steal' && game.legal.steal.map(target => <button className="isle-button" disabled={busy} key={target} onClick={() => act({action:'steal', target})}>{game.players[target].name}</button>)}
      </div>
    </section>
    <div className="isle-main">
      <IslandBoard game={game} mode={mode} selected={selected} onPick={setPending} busy={busy} onConfirm={async () => {
        if (await act(selected)) {setPending(null);setTool(null)}
      }}/>
      {game.hand && <section className="isle-panel"><h2>Твои ресурсы</h2><ResourceSet items={game.hand}/></section>}
      {game.discard > 0 && <Discard key={game.turn} game={game} action={act} busy={busy}/>}
      {game.hand && game.phase === 'action' && ((myTurn && trading) || game.offer) && <Trade key={game.turn} game={game} action={act} busy={busy} myTurn={myTurn}/>}
      <Development game={game} action={act} busy={busy} myTurn={myTurn}/>
    </div>
    <aside className="isle-aside">
      <section className="isle-panel"><h2>Участники</h2><ul className="isle-scores">{game.players.map((p, i) => <li key={i} className={game.active === i && !finished ? 'is-active' : ''}>
        <div><i style={{background:COLORS[i]}}/><PlayerName name={p.name} suffix={game.me === i ? ' · Ты' : p.bot ? ' · Бот' : ''}/></div>
        <strong>{p.points} / 10</strong><small>Ресурсы: {p.size} · Развитие: {p.cards}</small>
        {(game.longest === i || game.army === i) && <small>{[game.longest === i && 'Длинная дорога', game.army === i && 'Большая армия'].filter(Boolean).join(' · ')}</small>}
      </li>)}</ul></section>
      <section className="isle-panel"><h2>Банк</h2><ResourceSet items={game.bank}/><p>Карт развития · {game.deck}</p></section>
      <section className="isle-panel"><h2>Журнал</h2>
        <ol className="isle-log">{game.log.slice(-12).reverse().map((line,i) => <li key={i}>{line}</li>)}</ol>
      </section>
    </aside>
  </div>
}

export default function Colonist({game, room, data, onAction, onLeave, onReady, onManage, busy, error}) {
  const [rules, setRules] = useState(false)
  const [copied, setCopied] = useState(false)
  const [people, setPeople] = useState(false)
  if (!game) return <main className="page-shell">Подключаем Колониста…</main>
  const act = fields => onAction({instance:game.instance, rev:game.rev, ...fields})
  return <main className="isle-page">
    <header className="isle-header">
      <div><Link to="/" className="isle-brand">✳ KABAN GAMES</Link><h1>Колонист</h1></div>
      <div className="isle-buttons">
        <AccountLink game/>
        {!room.seat && <button className="isle-button" onClick={async () => {
          try {await navigator.clipboard.writeText(`${window.location.origin}/join?code=${room.code}`);setCopied(true)} catch {setCopied(false)}
        }}>{copied ? 'Ссылка скопирована' : `Код ${room.code} ↗`}</button>}
        <button className="isle-button" onClick={() => setRules(true)}>Как играть</button>
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
  </main>
}
