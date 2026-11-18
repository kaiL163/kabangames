import React, {createContext, useContext, useEffect, useState} from 'react'
import {Link, Navigate, useLocation, useNavigate, useSearchParams} from 'react-router-dom'
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
const PROVIDERS = [
  {id: 'vk', name: 'ВК'},
  {id: 'yandex', name: 'Яндекс ID'},
]
const OAUTH_ERRORS = {
  expired: 'Срок входа истёк. Попробуйте ещё раз.',
  failed: 'Не удалось завершить вход. Попробуйте ещё раз.',
  conflict: 'Этот аккаунт привязан к другому профилю или у вашего профиля уже есть привязка.',
}

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
  const [providers, setProviders] = useState({})
  useEffect(() => {
    let active = true
    accountRequest('me').then(value => {
      if (active) setProfile(value)
    }).catch(() => {
      if (active) setLoadError(true)
    }).finally(() => {
      if (active) setLoading(false)
    })
    accountRequest('providers').then(value => {
      if (active) setProviders(value)
    }).catch(() => {})
    return () => {active = false}
  }, [])
  return <AccountContext.Provider value={{profile, setProfile, loading, loadError, providers}}>{children}</AccountContext.Provider>
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
    return loadError ? <main className="page-shell"><p role="alert">Не удалось загрузить профиль.</p><Link className="back-link" to="/"><span className="link-icon" aria-hidden="true">←</span> На главную</Link></main>
      : <Navigate to="/account/login" replace/>
  }
  if (mode !== 'profile' && profile) return <Navigate to="/profile" replace/>
  return <AccountForm key={mode} mode={mode}/>
}

function EmailSettings() {
  const [email, setEmail] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  useEffect(() => {
    let active = true
    accountRequest('email').then(value => {
      if (active) setEmail(value)
    }).catch(() => {
      if (active) setError('Не удалось загрузить настройки почты.')
    })
    return () => { active = false }
  }, [])

  async function send(event) {
    event.preventDefault()
    if (busy) return
    const data = Object.fromEntries(new FormData(event.currentTarget))
    setBusy(true)
    setError('')
    setSent(false)
    try {
      const {pending} = await accountRequest('email/send', 'POST', data)
      setEmail(previous => ({...previous, pending}))
      setSent(true)
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return <section className="account-manage" aria-labelledby="account-email-heading">
    <h2 id="account-email-heading">Почта</h2>
    {email?.verified && <p>Подтверждена: <strong>{email.verified}</strong></p>}
    {email?.pending && <p role={sent ? 'status' : undefined}>Письмо отправлено на <strong>{email.pending}</strong>. Ссылка действует 30 минут.</p>}
    {email && !email.enabled && <p>Отправка писем пока недоступна.</p>}
    {email?.enabled && <form onSubmit={send}>
      <label htmlFor="account-email">{email.verified ? 'Новый адрес' : 'Адрес электронной почты'}</label>
      <input id="account-email" name="email" type="email" autoComplete="email" maxLength={254} defaultValue={email.pending || ''} required/>
      <button className="button" disabled={busy}>{busy ? 'Отправляем…' : email.pending ? 'Отправить новое письмо' : 'Отправить письмо'}</button>
    </form>}
    {error && <p className="room-error" role="alert">{error}</p>}
  </section>
}

export function VerifyEmailPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const token = new URLSearchParams(location.hash.slice(1)).get('token') || ''
  const [busy, setBusy] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [error, setError] = useState('')
  const valid = /^[A-Za-z0-9_-]{43}$/.test(token)

  async function confirmEmail() {
    setBusy(true)
    setError('')
    try {
      await accountRequest('email/verify', 'POST', {token})
      setConfirmed(true)
      navigate(location.pathname, {replace: true})
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return <main className="page-shell"><section className="join-panel account-panel">
    <h1>Подтверждение почты</h1>
    {confirmed ? <p role="status">Почта подтверждена.</p>
      : valid ? <button type="button" className="button" disabled={busy} onClick={confirmEmail}>Подтвердить почту</button>
        : <p>Откройте ссылку из письма или запросите новое письмо в профиле.</p>}
    {error && <p className="room-error" role="alert">{error}</p>}
    <p><Link className="back-link" to="/profile">Открыть профиль ↗</Link></p>
  </section></main>
}

function AccountForm({mode}) {
  const {profile, setProfile, providers} = useAccount()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [avatar, setAvatar] = useState(profile?.avatar || 'brand')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [accountNotice, setAccountNotice] = useState('')
  const [showDeletion, setShowDeletion] = useState(false)
  const editing = mode === 'profile'
  const registering = mode === 'register'

  async function submit(event) {
    event.preventDefault()
    if (PROVIDERS.some(({id}) => params.has(id))) setParams({}, {replace: true})
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

  async function updateAccess(path, method, data, notice) {
    if (busy) return
    setBusy(true)
    setError('')
    setAccountNotice('')
    setSaved(false)
    try {
      const updated = await accountRequest(path, method, data)
      setProfile(updated)
      if (updated) {
        setParams({}, {replace: true})
        setAccountNotice(notice)
      } else {
        navigate('/', {replace: true})
      }
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  function unlink(id, name) {
    if (window.confirm(`Отвязать ${name} от профиля Kaban Games?`)) {
      updateAccess(`me/identities/${id}`, 'DELETE', undefined, `${name} отвязан.`)
    }
  }

  function submitAccess(event, path, method, notice) {
    event.preventDefault()
    updateAccess(path, method, Object.fromEntries(new FormData(event.currentTarget)), notice)
  }

  return <main className="page-shell">
    <Link className="back-link" to="/"><span className="link-icon" aria-hidden="true">←</span> На главную</Link>
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
      {editing && accountNotice && <p role="status">{accountNotice}</p>}
      {PROVIDERS.map(({id, name}) => {
        const status = params.get(id)
        const linked = editing && profile[`${id}_linked`]
        const path = `/api/account/oauth/${id}`
        const buttonClass = `button account-provider account-provider-${id}`
        const canUnlink = editing && (profile.has_password || PROVIDERS.some(
          other => other.id !== id && providers[other.id] && profile[`${other.id}_linked`],
        ))
        return <React.Fragment key={id}>
          {Object.hasOwn(OAUTH_ERRORS, status) && <p className="room-error" role="alert">{name}. {OAUTH_ERRORS[status]}</p>}
          {linked && <div className="account-identity">
            <span role={status === 'linked' ? 'status' : undefined}>{name} привязан</span>
            <button type="button" className="text-button" disabled={busy || !canUnlink} onClick={() => unlink(id, name)}>Отвязать {name}</button>
          </div>}
          {providers[id] && editing && !linked && <form action={`${path}/link`} method="post">
            <button className={buttonClass} type="submit" disabled={busy}>Привязать {name}</button>
          </form>}
          {providers[id] && !editing && <a className={buttonClass} href={`${path}/start`}>Войти через {name}</a>}
        </React.Fragment>
      })}
      {editing && !profile.has_password && <form className="account-manage" onSubmit={event => submitAccess(event, 'me/password', 'POST', 'Пароль установлен.')}>
        <p>Задайте пароль, чтобы входить по логину и при желании отвязать последний внешний аккаунт.</p>
        <label htmlFor="account-new-password">Новый пароль (от 10 символов)</label>
        <input id="account-new-password" name="password" type="password" autoComplete="new-password" minLength={10} maxLength={128} required/>
        <button className="button" disabled={busy}>Установить пароль</button>
      </form>}
      {editing && <EmailSettings/>}
      {editing ? <button type="button" className="text-button account-secondary" disabled={busy} onClick={logout}>Выйти из аккаунта</button>
        : <Link className="back-link account-secondary" to={registering ? '/account/login' : '/account/register'}>{registering ? 'Уже есть аккаунт? Войти' : 'Создать аккаунт ↗'}</Link>}
      {editing && <div className="account-manage account-danger">
        <button type="button" className="text-button" aria-expanded={showDeletion} disabled={busy}
          onClick={() => {setShowDeletion(!showDeletion);setError('')}}>{showDeletion ? 'Отмена' : 'Удалить аккаунт'}</button>
        {showDeletion && <form onSubmit={event => submitAccess(event, 'me', 'DELETE')}>
          <p>Профиль и привязки будут удалены без восстановления. Вы выйдете из аккаунта на всех устройствах.</p>
          {profile.has_password && <>
            <label htmlFor="account-delete-password">Текущий пароль</label>
            <input id="account-delete-password" name="password" type="password" autoComplete="current-password" maxLength={128} required/>
          </>}
          <label htmlFor="account-delete-word">Введите «УДАЛИТЬ» для подтверждения</label>
          <input id="account-delete-word" name="confirmation" pattern="УДАЛИТЬ" autoComplete="off" required/>
          <button className="button account-delete" disabled={busy}>Удалить аккаунт навсегда</button>
        </form>}
      </div>}
    </section>
  </main>
}
