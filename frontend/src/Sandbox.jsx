import React, {useEffect, useState} from 'react'
import './sandbox.css'

const matchedRoom = window.location.pathname.match(/^\/test-room\/([a-f0-9]{32})(?:\/|$)/)
export const testRoomId = matchedRoom?.[1] ?? null
export const testRoomBase = testRoomId ? `/test-room/${testRoomId}` : undefined
const seatKey = testRoomId ? `kaban-test-seat:${testRoomId}` : null

export async function sandboxRequest(path = '', options = {}) {
  const response = await fetch(`/api/admin/sandbox${path}`, {
    method: options.method ?? 'GET',
    headers: options.body ? {'Content-Type': 'application/json'} : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  })
  const data = await response.json()
  if (!response.ok) {
    const error = new Error(typeof data.detail === 'string' ? data.detail : 'Запрос не выполнен.')
    error.status = response.status
    throw error
  }
  return data
}

export async function selectTestSeat(seat = null, signal) {
  const room = await sandboxRequest(`/${testRoomId}/seat`, {method: 'POST', body: {seat}, signal})
  try {
    sessionStorage.setItem(seatKey, room.seat)
  } catch {
    // Perspective selection also works if browser storage is unavailable.
  }
  return room
}

export function SandboxEntry({children}) {
  const [session, setSession] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    let savedSeat
    try {savedSeat = sessionStorage.getItem(seatKey)} catch {}
    selectTestSeat(savedSeat, controller.signal)
      .catch(error => {
        if (error.status === 404 && savedSeat) return selectTestSeat(null, controller.signal)
        throw error
      })
      .then(setSession)
      .catch(error => {if (error.name !== 'AbortError') setError(error.message)})
    return () => controller.abort()
  }, [])

  if (session) return children(session)
  return <main className="page-shell">
    <a className="back-link" href="/admin">← В админ-панель</a>
    <p role={error ? 'alert' : 'status'}>{error || 'Открываем тестовую комнату…'}</p>
  </main>
}

export function SandboxControls({room, busy, message, onSwitch, onStep, onClose}) {
  return <details className="sandbox-dock">
    <summary>Тестовая комната <span>· {room?.host ? 'Ведущий' : room?.name}</span></summary>
    <div className="sandbox-controls">
      <label>Смотреть от лица
        <select value={room.seat} disabled={busy} onChange={event => onSwitch(event.target.value)}>
          {room.participants.map(player => <option key={player.id} value={player.id}>
            {player.host ? `Ведущий · ${player.name}` : player.name}
          </option>)}
        </select>
      </label>
      <button className="button" disabled={busy} onClick={onStep}>Дать ход ботам</button>
      <p>Боты действуют за других игроков. За выбранного участника и за ведущего играешь ты.</p>
      {message && <p role="status">{message}</p>}
      <div className="sandbox-links">
        <a href="/admin">В админ-панель</a>
        <button className="outline-button" disabled={busy} onClick={onClose}>Закрыть тест</button>
      </div>
    </div>
  </details>
}
