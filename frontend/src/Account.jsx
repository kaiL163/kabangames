import React, {createContext, useContext, useEffect, useState} from 'react'
import {Link, Navigate, useNavigate} from 'react-router-dom'
import './account.css'

const avatars = {
  brand: ['Кабан Kaban Games', 'kaban-brand-v2.webp'],
  detective: ['Детектив', 'detective-boar.png'],
  domination: ['Стратег', 'domination-boar.webp'],
  hat: ['Фокусник', 'hat-boar.webp'],
  bunker: ['Выживальщик', 'bunker-boar.webp'],
  monopoly: ['Магнат', 'monopoly-boar.webp'],
  boss: ['Босс', 'boss-boars.webp'],
  codenames: ['Агент', 'codenames-boars.webp'],
}

const AccountContext = createContext(null)

async function accountRequest(path, method = 'GET', data) {
  const response = await fetch(`/api/account/${path}`, {
    method,
    headers: data ? {'Content-Type': 'application/json'} : undefined,
    body: data ? JSON.stringify(data) : undefined,
  })
  if (response.status === 204) return null
  const result = await response.json()
  if (!response.ok) {
    throw new Error(typeof result.detail === 'string' ? result.detail : 'Проверьте введённые данные.')
  }
  return result
}

export function AccountProvider({children}) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  useEffect(() => {
    let active = true
    accountRequest('me').then(value => {
      if (active) setProfile(value)
    }).catch(() => {
      if (active) setLoadError(true)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => {active = false}
  }, [])
  return <AccountContext.Provider value={{profile, setProfile, loading, loadError}}>{children}</AccountContext.Provider>
}

export function useAccount() {
  return useContext(AccountContext)
}

export function Avatar({id, fallback = '☺'}) {
  const avatar = avatars[id]
  return avatar ? <img className="account-avatar" src={`/images/${avatar[1]}`} alt="" width="36" height="36"/> : <span aria-hidden="true">{fallback}</span>
}

export function AccountLink() {
  const {profile, loading} = useAccount()
  if (loading) return null
  return profile
    ? <Link className="account-nav" to="/profile"><Avatar id={profile.avatar}/>Профиль</Link>
    : <Link className="account-nav" to="/account/login">Аккаунт</Link>
}

export function AccountPage({mode}) {
  const {profile, loading, loadError} = useAccount()
  if (loading) return <main className="page-shell"><p>Загружаем аккаунт…</p></main>
  if (mode === 'profile' && !profile) {
    return loadError ? <main className="page-shell"><p role="alert">Не удалось загрузить профиль.</p><Link to="/">На главную</Link></main>
      : <Navigate to="/account/login" replace/>
  }
  if (mode !== 'profile' && profile) return <Navigate to="/profile" replace/>
  return <AccountForm key={mode} mode={mode}/>
}

function AccountForm({mode}) {
  const {profile, setProfile} = useAccount()
  const navigate = useNavigate()
  const [avatar, setAvatar] = useState(profile?.avatar || 'brand')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const editing = mode === 'profile'
  const registering = mode === 'register'

  async function submit(event) {
    event.preventDefault()
    const data = Object.fromEntries(new FormData(event.currentTarget))
    if (editing) data.avatar = avatar
    setBusy(true)
    setError('')
    setSaved(false)
    try {
      const next = await accountRequest(editing ? 'me' : mode, editing ? 'PATCH' : 'POST', data)
      setProfile(next)
      if (editing) setSaved(true)
      else navigate('/profile', {replace: true})
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function logout() {
    setBusy(true)
    setError('')
    try {
      await accountRequest('logout', 'POST')
      setProfile(null)
      navigate('/', {replace: true})
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return <main className="page-shell">
    <Link className="back-link" to="/">← На главную</Link>
    <section className="join-panel account-panel">
      <h1>{editing ? 'Профиль' : registering ? 'Регистрация' : 'Вход'}</h1>
      {editing && <p>Логин: <strong>{profile.username}</strong></p>}
      <form onSubmit={submit}>
        {!editing && <><label htmlFor="account-username">Логин</label>
          <input id="account-username" name="username" autoComplete="username" minLength={3} maxLength={24} pattern="[A-Za-z0-9_]+" title="Латинские буквы, цифры и подчёркивание" required/>
          <label htmlFor="account-password">Пароль{registering ? ' (от 10 символов)' : ''}</label>
          <input id="account-password" name="password" type="password" autoComplete={registering ? 'new-password' : 'current-password'} minLength={10} maxLength={128} required/>
        </>}
        {(editing || registering) && <><label htmlFor="account-nickname">Ник в играх</label>
          <input id="account-nickname" name="nickname" autoComplete="nickname" maxLength={20} defaultValue={profile?.nickname} required/>
        </>}
        {editing && <fieldset className="account-avatar-picker"><legend>Аватар</legend>
          {Object.entries(avatars).map(([id, [label]]) => <button key={id} type="button" aria-label={label}
            aria-pressed={id === avatar} title={label} onClick={() => {setAvatar(id);setSaved(false)}}><Avatar id={id}/></button>)}
        </fieldset>}
        <button className="button" disabled={busy}>{editing ? 'Сохранить профиль' : registering ? 'Создать аккаунт' : 'Войти'}</button>
      </form>
      {error && <p className="room-error" role="alert">{error}</p>}
      {editing && saved && <p role="status">Профиль сохранён.</p>}
      {editing ? <button type="button" className="text-button account-secondary" disabled={busy} onClick={logout}>Выйти из аккаунта</button>
        : <Link className="back-link account-secondary" to={registering ? '/account/login' : '/account/register'}>{registering ? 'Уже есть аккаунт? Войти' : 'Создать аккаунт ↗'}</Link>}
    </section>
  </main>
}
