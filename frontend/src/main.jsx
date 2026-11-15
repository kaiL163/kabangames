import React, {useEffect, useRef, useState} from 'react'
import {createRoot} from 'react-dom/client'
import {games} from './games.js'
import Detective from './Detective.jsx'
import './style.css'

const cards = [
  ['detective','00 / ДЛЯ СЫЩИКОВ','🕵️','Детективное дело','Соберите улики и раскройте преступление'],
  ['quiz','01 / ДЛЯ ЛЮБОЗНАТЕЛЬНЫХ','🧠','Викторина','Вопросы, ответы и немного азарта'],
  ['croc','02 / ДЛЯ АРТИСТОВ','🐊','Крокодил','Покажи слово без единого звука'],
  ['truth','03 / ДЛЯ СМЕЛЫХ','🔥','Правда или действие','Узнайте друг друга получше'],
  ['who','04 / ДЛЯ СВОИХ','👀','Кто скорее?','Выбирайте того, кому подходит вопрос'],
]
async function api(action, body={}) {
  const response = await fetch(`/api/${action}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  const result = await response.json()
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Ошибка соединения')
  return result
}
function choose(list, previous) {
  let index = Math.floor(Math.random() * list.length)
  if (list.length > 1 && index === previous) index = (index + 1) % list.length
  return index
}
function App() {
  const [room,setRoom] = useState(() => { try { return JSON.parse(sessionStorage.getItem('sbor-room')) } catch { return null } })
  const [roomView,setRoomView] = useState(null)
  const [players,setPlayers] = useState([])
  const [shared,setShared] = useState(null)
  const [detective,setDetective] = useState(null)
  const [error,setError] = useState('')
  const [code,setCode] = useState('')
  const [name,setName] = useState('')
  const [game,setGame] = useState(null)
  const [card,setCard] = useState(null)
  const [revealed,setRevealed] = useState(false)
  const last = useRef({})
  const updates = useRef(Promise.resolve())
  useEffect(() => { if(room) sessionStorage.setItem('sbor-room',JSON.stringify(room)); else sessionStorage.removeItem('sbor-room') },[room])
  useEffect(() => {
    if (!room) return
    let stopped = false
    const poll = async () => {
      try {
        const data = await api('state',room)
        if (!stopped) { setPlayers(data.players); setShared(data.state); setDetective(data.detective); setError('') }
      } catch (err) {
        if (stopped) return
        if (/не найдена|завершено/.test(err.message)) { setRoom(null); setGame(null); setRoomView('closed') }
        else setError('Нет соединения. Пытаемся подключиться…')
      }
    }
    poll(); const id = setInterval(poll,1500)
    return () => { stopped = true; clearInterval(id) }
  },[room])
  useEffect(() => { if(room && !room.host) setRoomView('room') },[]) // Restore a participant's room after refresh.
  function publish(state) {
    if (!room?.host) return
    const credentials = {code:room.code,token:room.token}
    updates.current = updates.current.then(() => api('update',{...credentials,state})).catch(() => setError('Не удалось обновить игру. Проверьте соединение.'))
  }
  function selectCard(id, type='items') {
    const list=games[id][type], key=id+type, index=choose(list,last.current[key]); last.current[key]=index
    const value=list[index], next=Array.isArray(value)?{prompt:value[0],answer:`Ответ: ${value[1]}`}:{prompt:value,answer:''}
    setCard(next); setRevealed(false)
    publish({title:games[id].title,prompt:id==='croc'?'Ведущий показывает слово. Угадайте его!':next.prompt,answer:''})
  }
  function openGame(id) {
    if (room && !room.host) {setRoomView('room');return}
    if (id === 'detective') { startDetective(); return }
    setGame(id); setRevealed(false)
    if(id==='truth') {setCard({prompt:'Выбирай: правда или действие?',answer:''});publish({title:games[id].title,prompt:'Выбирай: правда или действие?',answer:''})}
    else selectCard(id)
  }
  async function startDetective() {
    try {
      setError('')
      let currentRoom = room
      if (!currentRoom) { currentRoom = await api('create'); setRoom(currentRoom) }
      if (!detective) setDetective(await api('detective/start',currentRoom))
      setRoomView(null); setGame('detective')
    } catch (err) { setError(err.message); setRoomView('menu') }
  }
  async function detectiveAction(action, body) {
    try { setError(''); const data=await api(`detective/${action}`,{...room,...body}); setDetective(data) }
    catch(err) { setError(err.message) }
  }
  function closeGame(){if(game==='detective'){setGame(null);return}setGame(null);setCard(null);publish(null)}
  async function createRoom(){try{setError('');const result=await api('create');setRoom(result);setRoomView('room')}catch(e){setError(e.message)}}
  async function joinRoom(e){e.preventDefault();try{setError('');const result=await api('join',{code:code.trim().toUpperCase(),name:name.trim()});setRoom(result);setRoomView('room')}catch(err){setError(err.message)}}
  async function leaveRoom(){const previous=room;setRoom(null);setRoomView(null);setGame(null);setShared(null);setDetective(null);try{await api('leave',previous)}catch{/* The room may already have expired. */}}
  function showAnswer(){setRevealed(true);publish({title:games[game].title,prompt:card.prompt,answer:card.answer})}
  const dialogOpen=roomView !== null || game !== null
  useEffect(()=>{document.body.style.overflow=dialogOpen?'hidden':'';return()=>{document.body.style.overflow=''}},[dialogOpen])
  useEffect(()=>{const handle=e=>{if(e.key==='Escape'){if(roomView)setRoomView(null);else if(game)closeGame()}};window.addEventListener('keydown',handle);return()=>window.removeEventListener('keydown',handle)})
  return <>
    <header><a className="logo" href="#">СБОР<span>✳</span></a><nav><a href="#games">Игры</a><a href="#how">Как играть</a><a className="pill" href="#games">Выбрать игру ↗</a></nav></header>
    <div className="roombar"><span>{room?`Комната ${room.code} · ${room.host?'вы ведущий':'вы в игре'}`:'Играете с друзьями? Создайте комнату или войдите по коду.'}</span><button onClick={()=>{setError('');setRoomView(room?'room':'menu')}}>{room?`Комната ${room.code}`:'Комнаты ↗'}</button></div>
    <main><div className="wrap"><section className="hero"><div><div className="eyebrow"><span className="dot"/>Для тех, кто сегодня вместе</div><h1>СОБРАЛИСЬ?<br/><em>ИГРАЕМ.</em></h1><p>Игры, которые превращают обычный вечер в истории, которые вы ещё долго будете вспоминать.</p><a className="button" href="#games">Выбрать игру <span>↗</span></a><span className="small">Бесплатно. Без регистрации.</span></div><div className="art" aria-hidden="true"><div className="art-label">ХОРОШИЙ ВЕЧЕР НАЧИНАЕТСЯ ЗДЕСЬ ↗</div><div className="card one"><small>СБОР / 01</small><div className="face">✳</div><strong>ВСЕ<br/>СВОИ.</strong></div><div className="card two"><small>СБОР / 02</small><div className="face">☺</div><strong>ВСЕ<br/>В ИГРЕ.</strong></div><div className="spark">✴</div></div></section>
    <div className="strip"><span>✳ БЕЗ СКАЧИВАНИЙ</span><span>✳ ДЛЯ ЛЮБОЙ КОМПАНИИ</span><span>✳ ВСЁ БЕСПЛАТНО</span></div>
    <section className="section" id="games"><div className="section-head"><div><div className="eyebrow"><span className="dot"/>ВЫБИРАЙТЕ НАСТРОЕНИЕ</div><h2>ВО ЧТО ИГРАЕМ?</h2></div><p>Игры для компании и одно загадочное дело.</p></div><div className="grid">{cards.map(([id,label,icon,title,desc])=><button className="game" key={id} onClick={()=>openGame(id)}><span className="num">{label}</span><span className="icon">{icon}</span><h3>{title}</h3><p>{desc}</p><span className="go">↗</span></button>)}</div></section>
    <section className="how" id="how"><div><div className="eyebrow" style={{color:'#c6e755'}}>ПРОЩЕ ПРОСТОГО</div><h2>НИЧЕГО<br/>ЛИШНЕГО.</h2></div><div className="steps"><div className="step"><b>01</b><p>Ведущий создаёт комнату и показывает друзьям её код.</p></div><div className="step"><b>02</b><p>Игроки открывают сайт на своих устройствах и входят по коду.</p></div><div className="step"><b>03</b><p>Ведущий выбирает игру и управляет карточками. Играем!</p></div></div></section><footer className="footer"><span className="logo" style={{color:'var(--ink)'}}>СБОР<span>✳</span></span><span>Сделано для хороших вечеров.</span><span>Играйте вместе ♡</span></footer></div></main>
    {game==='detective' && <Detective caseData={detective} isHost={room?.host} roomCode={room?.code} onRestart={()=>detectiveAction('start',{})} onInspect={item_id=>detectiveAction('inspect',{item_id})} onAccuse={answers=>detectiveAction('accuse',{answers})} onTheory={(suspect,reason)=>detectiveAction('theory',{suspect,reason})} onClose={()=>setGame(null)} error={error}/>}
    {game && game!=='detective' && <div className="modal open" onClick={e=>{if(e.target===e.currentTarget)closeGame()}}><div className="dialog" role="dialog" aria-modal="true" aria-labelledby="gameTitle"><div className="dialog-top"><span className="eyebrow">СБОР ✳ ИГРАЕМ ВМЕСТЕ</span><button className="close" onClick={closeGame} aria-label="Закрыть">×</button></div><h2 id="gameTitle">{games[game].title}</h2><p className="desc">{games[game].desc}</p><div className="prompt">{card?.prompt}</div><div className="actions">{game==='truth'?<><button className="primary" onClick={()=>selectCard(game,'truth')}>Правда</button><button className="secondary" onClick={()=>selectCard(game,'dare')}>Действие</button></>:<><button className="primary" onClick={()=>selectCard(game)}>{game==='quiz'?'Следующий вопрос':'Следующая карточка'}</button>{game==='quiz'&&<button className="secondary" onClick={showAnswer}>Показать ответ</button>}</>}</div>{revealed&&<div className="answer">{card?.answer}</div>}{error&&<p className="room-error" role="alert">{error}</p>}</div></div>}
    {roomView && <div className="room-overlay open" onClick={e=>{if(e.target===e.currentTarget)setRoomView(null)}}><div className="room-box" role="dialog" aria-modal="true" aria-labelledby="roomTitle"><div className="room-top"><span className="eyebrow">СБОР ✳ КОМНАТЫ</span><button className="close" onClick={()=>setRoomView(null)} aria-label="Закрыть">×</button></div>
      {roomView==='menu'&&<><h2 id="roomTitle">Играем вместе?</h2><p>Ведущий создаёт комнату на общем экране. Игроки открывают этот же сайт на своих телефонах и вводят код.</p><div className="actions"><button className="primary" onClick={createRoom}>Создать комнату</button><button className="secondary" onClick={()=>{setError('');setRoomView('join')}}>Войти по коду</button></div></>}
      {roomView==='join'&&<form onSubmit={joinRoom}><h2 id="roomTitle">Войти в комнату</h2><p>Введите код с экрана ведущего и своё имя.</p><label htmlFor="joinCode">Код комнаты</label><input id="joinCode" placeholder="Например, ABCD" maxLength="4" autoCapitalize="characters" value={code} onChange={e=>setCode(e.target.value)} required/><label htmlFor="joinName">Ваше имя</label><input id="joinName" placeholder="Как вас зовут?" maxLength="20" value={name} onChange={e=>setName(e.target.value)} required/><div className="actions"><button className="primary">Войти</button><button type="button" className="secondary" onClick={()=>setRoomView('menu')}>Назад</button></div></form>}
      {roomView==='room'&&room&&<><h2 id="roomTitle">{room.host?'Ваша комната':'Вы в комнате'}</h2><p>{room.host?'Попросите друзей открыть этот сайт и ввести код. Выберите игру на общем экране.':'Ожидайте, пока ведущий выберет игру.'}</p><div className="room-code">{room.code}</div><p className="room-players">Игроки ({players.length}): {players.join(', ')||'пока никто не подключился'}</p>{!room.host&&detective&&<div className="actions"><button className="primary" onClick={()=>{setRoomView(null);setGame('detective')}}>Открыть расследование ↗</button></div>}{room.host&&detective&&<div className="actions"><button className="primary" onClick={()=>{setRoomView(null);setGame('detective')}}>Продолжить расследование ↗</button></div>}{!room.host&&!detective&&<div className="guest-screen">{shared?<><small>{shared.title.toUpperCase()}</small><div>{shared.prompt}</div>{shared.answer&&<p>{shared.answer}</p>}</>:'Ждём, когда ведущий выберет игру…'}</div>}<div className="actions">{room.host&&<button className="primary" onClick={()=>{setRoomView(null);document.querySelector('#games').scrollIntoView({behavior:'smooth'})}}>Выбрать игру</button>}<button className="secondary" onClick={leaveRoom}>{room.host?'Закрыть комнату':'Выйти'}</button></div></>}
      {roomView==='closed'&&<><h2 id="roomTitle">Комната закрыта</h2><p>Войдите в другую комнату или создайте новую.</p><div className="actions"><button className="primary" onClick={()=>setRoomView('menu')}>К комнатам</button></div></>}{error&&<p className="room-error" role="alert">{error}</p>}</div></div>}
  </>
}

createRoot(document.getElementById('root')).render(<App />)
