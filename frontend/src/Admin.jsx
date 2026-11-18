import React, {useEffect, useState} from 'react'
import {Link, Navigate} from 'react-router-dom'
import {useAccount} from './Account.jsx'
import {sandboxRequest} from './Sandbox.jsx'
import './admin.css'

async function adminRequest(path, data, signal) {
  const response = await fetch(`/api/admin/${path}`, {
    method: data ? 'POST' : 'GET',
    headers: data ? {'Content-Type': 'application/json'} : undefined,
    body: data ? JSON.stringify(data) : undefined,
    signal,
  })
  const result = await response.json()
  if (!response.ok) {
    throw new Error(typeof result.detail === 'string' ? result.detail : 'Запрос не выполнен.')
  }
  return result
}

function TesterAccess() {
  const [users, setUsers] = useState(null)
  const [username, setUsername] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    adminRequest('access', undefined, controller.signal)
      .then(result => setUsers(result.users))
      .catch(error => {if (error.name !== 'AbortError') setError(error.message)})
    return () => controller.abort()
  }, [])

  async function changeAccess(login, enabled) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await adminRequest('access', {username: login, enabled})
      const result = await adminRequest('access')
      setUsers(result.users)
      if (enabled) setUsername('')
      setNotice(enabled ? `Доступ выдан: ${login}` : `Доступ отозван: ${login}`)
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return <section className="admin-panel">
    <h2>Доступ к панели</h2>
    <p>Выдай роль тестировщика по логину Kaban Games.</p>
    <form className="admin-access-form" onSubmit={event => {
      event.preventDefault()
      changeAccess(username.trim(), true)
    }}>
      <label>Логин пользователя<input value={username} onChange={event => setUsername(event.target.value)} maxLength={64} required/></label>
      <button className="button" disabled={busy || !username.trim()}>Выдать доступ</button>
    </form>
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert" className="room-error">{error}</p>}
    {users && <ul className="admin-access-list">
      {users.map(user => <li key={user.username}>
        <div><strong>{user.nickname}</strong> <small>@{user.username}</small></div>
        {user.admin_role === 'owner' ? <span>Владелец</span> : <button className="outline-button" disabled={busy} onClick={() => {
          if (window.confirm(`Отозвать доступ у @${user.username}?`)) changeAccess(user.username, false)
        }}>Отозвать доступ</button>}
      </li>)}
    </ul>}
  </section>
}

const DEFAULT_BOTS = {boss: 5, codenames: 5, domination: 2, spy: 3}

function LiveTestRooms({games, gameNames}) {
  const [game, setGame] = useState(games.includes('quiz') ? 'quiz' : games[0])
  const [bots, setBots] = useState(DEFAULT_BOTS[game] ?? 3)
  const [rooms, setRooms] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    sandboxRequest('', {signal: controller.signal}).then(result => setRooms(result.rooms))
      .catch(error => {if (error.name !== 'AbortError') setError(error.message)})
    return () => controller.abort()
  }, [])

  async function create(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const room = await sandboxRequest('', {method: 'POST', body: {game, bots: Number(bots)}})
      window.location.assign(`/test-room/${room.id}`)
    } catch (error) {
      setError(error.message)
      setBusy(false)
    }
  }

  async function close(id) {
    if (!window.confirm('Закрыть эту тестовую комнату?')) return
    setBusy(true)
    setError('')
    try {
      await sandboxRequest(`/${id}`, {method: 'DELETE'})
      setRooms(previous => previous.filter(room => room.id !== id))
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return <section className="admin-panel" aria-labelledby="live-tests-title">
    <h2 id="live-tests-title">Тестовое лобби с ботами</h2>
    <p>Открой игру как ведущий и переключайся на любого игрока. Действия ботов можно запускать по шагам.</p>
    <form className="admin-access-form admin-sandbox-form" onSubmit={create}>
      <label>Игра
        <select value={game} disabled={busy} onChange={event => {
          setGame(event.target.value)
          setBots(DEFAULT_BOTS[event.target.value] ?? 3)
        }}>
          {games.map(mode => <option key={mode} value={mode}>{gameNames[mode] ?? mode}</option>)}
        </select>
      </label>
      <label>Число ботов
        <input type="number" min="1" max="12" required value={bots} disabled={busy} onChange={event => setBots(event.target.value)}/>
      </label>
      <button className="button" disabled={busy}>{busy ? 'Подождите…' : 'Открыть тестовое лобби ↗'}</button>
    </form>
    {error && <p role="alert" className="room-error">{error}</p>}
    {rooms.length > 0 && <ul className="admin-access-list">
      {rooms.map(room => <li key={room.id}>
        <div><strong>{gameNames[room.game] ?? room.game}</strong> <small>Участников: {room.players}</small></div>
        <div className="admin-sandbox-actions">
          <a className="back-link" href={`/test-room/${room.id}`}>Вернуться ↗</a>
          <button className="outline-button" disabled={busy} onClick={() => close(room.id)}>Закрыть</button>
        </div>
      </li>)}
    </ul>}
  </section>
}

export default function AdminPage({gameNames}) {
  const {profile, loading, loadError} = useAccount()
  const [catalog, setCatalog] = useState(null)
  const [results, setResults] = useState({})
  const [running, setRunning] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!profile) return
    const controller = new AbortController()
    adminRequest('checks', undefined, controller.signal)
      .then(setCatalog)
      .catch(error => {if (error.name !== 'AbortError') setError(error.message)})
    return () => controller.abort()
  }, [profile])

  async function run(game) {
    setRunning(game ?? 'all')
    setError('')
    try {
      const report = await adminRequest('checks', {game})
      setResults(previous => ({
        ...previous, ...Object.fromEntries(report.results.map(result => [result.game, result])),
      }))
    } catch (error) {
      setError(error.message)
    } finally {
      setRunning(null)
    }
  }

  if (!loading && !profile && !loadError) return <Navigate to="/account/login" replace/>
  const completed = Object.values(results)
  const passed = completed.filter(result => result.ok).length

  return <main className="page-shell admin-page">
    <Link to="/profile" className="back-link"><span className="link-icon" aria-hidden="true">←</span> К профилю</Link>
    <header className="admin-heading">
      <div><h1>Админ-панель</h1><p>Тестовые комнаты и проверки игр</p></div>
      {catalog && <button className="button" disabled={running !== null} onClick={() => run(null)}>{running === 'all' ? 'Проверяем…' : 'Запустить все проверки'}</button>}
    </header>
    {loadError && <p role="alert">Не удалось загрузить аккаунт.</p>}
    {error && <p role="alert" className="room-error">{error}</p>}
    {!catalog && !error && !loadError && <p role="status">Проверяем доступ…</p>}
    {catalog && <>
      <LiveTestRooms games={catalog.games} gameNames={gameNames}/>
      <section className="admin-panel" aria-labelledby="game-checks-title">
        <div className="admin-section-heading">
          <div><h2 id="game-checks-title">Автоматические проверки</h2><p>Проверка серверной логики без открытия лобби.</p></div>
          <p className="admin-summary" aria-live="polite">{passed} успешно · {completed.length - passed} с ошибкой · {catalog.games.length - completed.length} ожидают</p>
        </div>
        <ul className="admin-checks">
          {catalog.games.map(game => {
            const result = results[game]
            const isRunning = running === game || running === 'all'
            return <li key={game}>
              <div>
                <h3>{gameNames[game] ?? game}</h3>
                <span className="admin-status" data-state={isRunning ? 'busy' : result?.ok ? 'ok' : result ? 'fail' : 'idle'}>{isRunning ? 'Проверяем…' : result?.ok ? 'Пройдено' : result ? 'Ошибка' : 'Ожидает проверки'}</span>
              </div>
              {result && <p>{result.detail} <small>· {result.duration_ms} мс</small></p>}
              <button className="outline-button" disabled={running !== null} onClick={() => run(game)} aria-label={`Проверить ${gameNames[game] ?? game}`}>Проверить</button>
            </li>
          })}
        </ul>
      </section>
      {catalog.role === 'owner' && <TesterAccess/>}
    </>}
  </main>
}
