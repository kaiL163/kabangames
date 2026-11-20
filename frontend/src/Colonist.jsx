import React, {useEffect, useId, useLayoutEffect, useRef, useState} from 'react'
import {Link} from 'react-router-dom'
import {AccountLink} from './Account.jsx'
import {PlayerName} from './RoomPeople.jsx'
import {CaseDialog} from './DetectiveUI.jsx'
import {Dice, Icon} from './ColonistArt.jsx'
import './colonist.css'

const RESOURCE = {
  wood: ['Дерево', '🌲', '#328052'], brick: ['Кирпич', '🧱', '#be6044'],
  wool: ['Шерсть', '🐑', '#76a345'], grain: ['Зерно', '🌾', '#c39631'],
  ore: ['Руда', '🪨', '#71869a'], desert: ['Пустыня', '☀', '#bb9566'],
}
const resources = Object.keys(RESOURCE).filter(key => key !== 'desert')
const COLORS = ['#ffe162', '#ff8167', '#79d7ff', '#d8aaff']
const PIECE_TINTS = ['-155deg', '150deg', '0deg', '62deg']
const PIECES = {home: '/images/colonist-settlement.webp', city: '/images/colonist-city.webp'}
const TERRAIN_COLORS = {
  wood: '#03853e', brick: '#fd7904', wool: '#a9fb15',
  grain: '#feca03', ore: '#a9aeb8', desert: '#fcdc93',
}
const TERRAIN_CELL = 384
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

function ResourceArt({kind}) {
  return <svg className="isle-resource-art" viewBox="0 0 44 28" aria-hidden="true">
    <use href={`#isle-terrain-${kind}`} width="44" height="28"/>
  </svg>
}

function ResourceSet({items, highlighted, compact = false}) {
  return <div className={`isle-resources${compact ? ' is-compact' : ''}`}>{resources.map(r => <div key={r}
    className={highlighted?.[r] ? 'is-highlighted' : undefined} style={{'--resource-art':TERRAIN_COLORS[r]}}
    title={RESOURCE[r][0]}>
    <ResourceArt kind={r}/><strong>{items[r]}</strong><small>{RESOURCE[r][0]}</small>
  </div>)}</div>
}

function Road({x1, y1, x2, y2, color}) {
  return <g className="isle-road">
    <line className="isle-road-edge" x1={x1} y1={y1} x2={x2} y2={y2}/>
    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color}/>
  </g>
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
          <filter id="isle-piece-alpha" colorInterpolationFilters="sRGB">
            <feComponentTransfer><feFuncA type="linear" slope="1.55" intercept="-.55"/></feComponentTransfer>
          </filter>
          <pattern id="isle-ripple" width="44" height="37" patternUnits="userSpaceOnUse"><path d="M2 8q5 4 10 0m11 16q5 4 10 0M9 34h4" fill="none" stroke="#8ccdcb" strokeOpacity=".2"/></pattern>
          <image id="isle-terrain-atlas" href="/images/colonist-terrain.webp" width={TERRAIN_CELL*3} height={TERRAIN_CELL*2}/>
          {Object.keys(TERRAIN_COLORS).map((resource, index) => {
            const x = (index%3)*TERRAIN_CELL
            const y = Math.floor(index/3)*TERRAIN_CELL
            return <symbol key={resource} id={`isle-terrain-${resource}`} viewBox={`${x+8} ${y+8} ${TERRAIN_CELL-16} 232`}>
              <use href="#isle-terrain-atlas"/>
            </symbol>
          })}
        </defs>
        <rect x="-266" y="-220" width="532" height="440" fill="url(#isle-ripple)"/>
        <g className="isle-shore" aria-hidden="true">{tiles.map((tile, index) => <polygon key={index} points={tile.v.map(i => vertices[i].join(',')).join(' ')}/>)}</g>
        {tiles.map(({v, x, y, resource, number}, index) => {
          const [name] = RESOURCE[resource]
          const shape = v.map(i => vertices[i].join(',')).join(' ')
          const pips = 6-Math.abs(7-number)
          const props = mode === 'robber' && choices.has(index)
            ? spot(mode, index, `Переместить разбойника: ${name} ${number ?? ''}, участок ${index+1}`, selected, onPick, busy) : {}
          const producing = game.phase === 'action' && index !== robber && number === rolled
          return <g key={index} className={`isle-tile${props.role ? ' is-legal' : ''}${producing ? ' is-producing' : ''}`} {...props}>
            <polygon className="isle-land" points={shape} fill={TERRAIN_COLORS[resource]}/>
            <use href={`#isle-terrain-${resource}`} x={x-22} y={y-30} width="44" height="28" pointerEvents="none" aria-hidden="true"/>
            {number && <g className={number === 6 || number === 8 ? 'isle-token is-hot' : 'isle-token'}>
              <circle cx={x} cy={y+12} r="14"/><text x={x} y={y+15}>{number}</text>
              {Array.from({length:pips}, (_, i) => <circle className="isle-pip" key={i} cx={x+(i-(pips-1)/2)*3.1} cy={y+20} r="1.05"/>)}
            </g>}
            {index === robber && <g className="isle-bandit" transform={`translate(${x+24},${y+4})`}>
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
          return <Road key={edge} x1={x} y1={y} x2={xx} y2={yy} color={COLORS[seat]}/>
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
          const size = kind === 'city' ? 40 : 33
          return <g key={vertex} transform={`translate(${x},${y})`} className="isle-home">
            <title>{BUILD[kind]} · {game.players[seat].name}</title>
            <ellipse cy="4" rx={size*.39} ry="4" fill={COLORS[seat]}/>
            <image className="isle-piece" href={PIECES[kind]} x={-size/2} y={6-size} width={size} height={size}
              style={{'--piece-tint':PIECE_TINTS[seat]}}/>
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

function Discard({game, action, busy, error}) {
  const [selected, setSelected] = useState([])
  const cards = resources.flatMap(kind => Array.from({length:game.hand[kind]}, (_, index) => ({kind, id:`${kind}-${index}`, number:index+1})))
  const picked = cards.filter(card => selected.includes(card.id))
  const total = picked.length
  function submit(event) {
    event.preventDefault()
    if (busy || total !== game.discard) return
    const counts = {}
    for (const {kind} of picked) counts[kind] = (counts[kind] ?? 0)+1
    action({action:'discard', counts})
  }
  return <CaseDialog title="Сброс ресурсов" wide>
    <form className="isle-discard" onSubmit={submit}>
      <p>Выбери карты для сброса. Нажми на выбранную карту ещё раз, чтобы вернуть её в руку.</p>
      <div className="isle-discard-cards" role="group" aria-label="Карты в твоей руке">
        {cards.map(({kind, id, number}) => {
          const marked = selected.includes(id)
          return <button key={id} type="button" className="isle-discard-card" aria-pressed={marked}
            aria-label={`${RESOURCE[kind][0]}, карта ${number} из ${game.hand[kind]}`}
            style={{'--resource-art':TERRAIN_COLORS[kind]}} disabled={busy || !marked && total >= game.discard}
            onClick={() => setSelected(current => marked ? current.filter(card => card !== id) : [...current, id])}>
            <ResourceArt kind={kind}/>
            <span>{RESOURCE[kind][0]}</span>
            {marked && <span className="isle-discard-mark" aria-hidden="true">✓</span>}
          </button>
        })}
      </div>
      {error && <p className="isle-error" role="alert">{error}</p>}
      <div className="isle-discard-footer">
        <strong role="status">Выбрано {total} из {game.discard}</strong>
        <button className="isle-button is-primary" disabled={busy || total !== game.discard}>Сбросить карты</button>
      </div>
    </form>
  </CaseDialog>
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

function ActionHint({id, action, hand, touch, anchor}) {
  return <div className="isle-action-hint" id={id} role="tooltip" style={{'--hint-x':`${anchor}px`}}>
    <strong>{action.label}</strong>
    {action.cost && <ul className="isle-hint-cost">{Object.entries(action.cost).map(([r, needed]) => {
      const owned = hand?.[r] ?? 0
      const missing = Math.max(0, needed-owned)
      return <li key={r} className={missing ? 'is-short' : 'is-enough'}>
        <ResourceArt kind={r}/><span>{RESOURCE[r][0]} <b>{owned}/{needed}</b></span>
        <small>{missing ? `Не хватает ${missing}` : 'Хватает ✓'}</small>
      </li>
    })}</ul>}
    {action.reason && <p>{action.reason}</p>}
    {touch && action.cost && !action.disabled && <p>Нажми ещё раз, чтобы выбрать действие.</p>}
  </div>
}

function IslandActions({game, mode, building, canTrade, myTurn, busy, act, onBuild, onTrade}) {
  const [preview, setPreview] = useState(null)
  const pointer = useRef(null)
  const toolbar = useRef(null)
  const hintId = useId()

  useEffect(() => {
    if (preview?.source !== 'touch') return
    const dismiss = event => {if (!toolbar.current?.contains(event.target)) setPreview(null)}
    document.addEventListener('pointerdown', dismiss)
    return () => document.removeEventListener('pointerdown', dismiss)
  }, [preview?.source])

  const costActions = ['road', 'home', 'city', 'buy'].map(kind => {
    const cost = game.cost[kind]
    const enough = Object.entries(cost).every(([r,n]) => (game.hand?.[r] ?? 0) >= n)
    const supply = game.pieces[kind]
    const buying = kind === 'buy'
    const legal = buying ? game.legal.card : game.legal[kind].length > 0
    const free = myTurn && mode === kind && ['setup_home','setup_road','free_road'].includes(game.phase)
    const reason = !myTurn ? 'Сейчас ход другого игрока.'
      : free ? 'Бесплатная постройка. Выбери место на поле.'
      : !building ? 'Доступно на этапе строительства.'
      : supply === 0 ? 'Фигуры этого типа закончились.'
      : buying && !game.deck ? 'Колода закончилась.'
      : enough && !legal ? 'На поле нет доступных мест.' : null
    return {kind, cost:free ? null : cost, supply, label: buying ? 'Купить карту' : BUILD[kind],
      disabled: busy || !building || !legal, reason, run: buying ? () => act({action:'buy'}) : () => onBuild(kind)}
  })
  const rolling = game.phase === 'roll'
  const actions = [...costActions, {
    kind:'trade', label:game.offer && !myTurn ? 'Предложение обмена' : 'Обмен', alert:Boolean(game.offer && !myTurn),
    disabled:!canTrade, reason:canTrade ? null : 'Обмен доступен после броска или по предложению другого игрока.', run:onTrade,
  }, {
    kind:rolling ? 'dice' : 'end', label:rolling ? 'Бросить кубики' : 'Конец хода', primary:true,
    disabled:busy || (rolling ? !myTurn : !building),
    reason:!myTurn ? 'Сейчас ход другого игрока.' : !rolling && !building ? 'Сначала закончи текущее действие.' : null,
    run:() => act({action:rolling ? 'roll' : 'end'}),
  }]
  const shown = actions.find(action => action.kind === preview?.kind)
  function show(action, source, button) {
    setPreview({kind:action.kind, source, anchor:button.offsetLeft + button.offsetWidth/2})
  }
  return <div className="isle-actions" ref={toolbar} onKeyDown={event => {
    if (event.key === 'Escape') setPreview(null)
  }}>
    {actions.map(action => <button key={action.kind} type="button"
      className={`isle-action${action.primary ? ' is-primary' : ''}${action.alert ? ' has-offer' : ''}`}
      aria-label={action.label} aria-describedby={shown === action ? hintId : undefined}
      aria-disabled={action.disabled || undefined} aria-pressed={action.cost && action.kind !== 'buy' ? building && mode === action.kind : undefined}
      onPointerEnter={event => {
        if (event.pointerType === 'mouse') show(action, 'hover', event.currentTarget)
      }}
      onPointerLeave={() => setPreview(current => current?.source === 'hover' ? null : current)}
      onPointerDown={event => {pointer.current = event.pointerType}}
      onFocus={event => {
        if (event.currentTarget.matches(':focus-visible')) show(action, 'focus', event.currentTarget)
      }}
      onBlur={() => setPreview(current => current?.kind === action.kind && current.source === 'focus' ? null : current)}
      onClick={event => {
        const touch = event.detail > 0 && ['touch','pen'].includes(pointer.current)
        if (touch && (action.cost || action.disabled) && (preview?.kind !== action.kind || preview.source !== 'touch')) {
          show(action, 'touch', event.currentTarget)
          return
        }
        if (!action.disabled) {
          setPreview(null)
          action.run()
        }
      }}>
      {action.supply !== undefined && <small className="isle-supply">{action.supply}</small>}
      {action.kind === 'road' ? <svg viewBox="0 0 34 34" aria-hidden="true">
        <Road x1={7} y1={26} x2={27} y2={8} color={COLORS[game.me]}/>
      </svg> : PIECES[action.kind] ? <img className="isle-piece isle-action-piece" src={PIECES[action.kind]} alt=""
        style={{'--piece-tint':PIECE_TINTS[game.me]}}/> : <Icon kind={action.kind}/>}
    </button>)}
    {shown && <ActionHint id={hintId} action={shown} hand={game.hand} touch={preview.source === 'touch'} anchor={preview.anchor}/>}
  </div>
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

function MatchSidebar({game, act, busy, finished, dice}) {
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
      <div className="isle-feed-dice">
        <strong>Кубики</strong>
        {dice || <span>Ждём броска</span>}
      </div>
    </section>
  </aside>
}

function IslandMatch({game, room, act, busy}) {
  const [tool, setTool] = useState(null)
  const [pending, setPending] = useState(null)
  const [panel, setPanel] = useState(null)
  const initialRoll = useRef(game.phase === 'roll' || !game.dice ? null : game.turn)
  const myTurn = game.active === game.me
  const finished = game.phase === 'finished'
  const building = myTurn && game.phase === 'action'
  const canTrade = game.hand && game.phase === 'action' && (building || game.offer)
  const forced = {setup_home:'home', setup_road:'road', robber:'robber', free_road:'road'}[game.phase]
  const mode = myTurn && !finished ? (forced ?? (building && tool && game.legal[tool].length ? tool : null)) : null
  const selected = pending?.action === mode && game.legal[mode]?.includes(pending.target) ? pending : null
  const active = game.players[game.active]?.name
  const dice = game.dice && game.phase !== 'roll'
    ? <Dice key={game.turn} values={game.dice} animate={initialRoll.current !== game.turn}/> : null
  const status = finished ? `Победа · ${game.players[game.winner].name}`
    : game.discard ? 'Выбери карты для сброса' : game.phase === 'discard' ? `Ждём сброс карт · ${game.pending}`
    : myTurn ? PHASE[game.phase] : `Ходит ${active}`
  return <div className="isle-match">
    <section className="isle-turn">
      <div className="isle-turn-heading"><i style={{background:COLORS[game.active]}}/><div><small>{game.phase.startsWith('setup') ? `РАССТАНОВКА · ${game.cursor+1} / ${game.players.length*2}` : `ХОД ${game.turn}`}{myTurn && !finished ? ' · ТВОЙ ХОД' : ''}</small><h2 role="status">{status}</h2></div></div>
      {(game.phase === 'steal' || mode === 'road' && game.phase === 'free_road' || finished && room.host) && <div className="isle-buttons">
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
      <IslandActions game={game} mode={mode} building={building} canTrade={canTrade} myTurn={myTurn}
        busy={busy} act={act} onBuild={kind => {setTool(kind);setPending(null)}} onTrade={() => setPanel('trade')}/>
    </section>
    <MatchSidebar game={game} act={act} busy={busy} finished={finished} dice={dice}/>
    {panel === 'trade' && canTrade && <CaseDialog title="Обмен ресурсами" onClose={() => setPanel(null)}><Trade key={game.turn} game={game} action={act} busy={busy} myTurn={myTurn}/></CaseDialog>}
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
    {error && !game.discard && <p className="isle-error" role="alert">{error}</p>}
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
    {game.discard > 0 && <Discard key={`${game.instance}-${game.turn}`} game={game} action={act} busy={busy} error={error}/>}
  </main>
}
