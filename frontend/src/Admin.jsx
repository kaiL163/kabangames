import React, {useEffect, useState} from 'react'
import {Link, Navigate} from 'react-router-dom'
import {useAccount} from './Account.jsx'
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
      <div><h1>Админ-панель</h1><p>Проверка игровых сценариев с ботами</p></div>
      {catalog && <button className="button" disabled={running !== null} onClick={() => run(null)}>{running === 'all' ? 'Проверяем…' : 'Запустить все проверки'}</button>}
    </header>
    {loadError && <p role="alert">Не удалось загрузить аккаунт.</p>}
    {error && <p role="alert" className="room-error">{error}</p>}
    {!catalog && !error && !loadError && <p role="status">Проверяем доступ…</p>}
    {catalog && <>
      <section className="admin-panel" aria-labelledby="game-checks-title">
        <div className="admin-section-heading">
          <div><h2 id="game-checks-title">Игровые сценарии</h2><p>Боты играют на сервере в тестовых комнатах. Здесь проверяется игровая логика.</p></div>
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
