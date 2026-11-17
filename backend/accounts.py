import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import asynccontextmanager, suppress
from typing import Literal
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix='/api/account')
COOKIE = 'kaban_session'
Provider = Literal['vk', 'yandex']
OAUTH_PREFIX = '/api/account/oauth'
VK_ORIGIN = 'https://id.vk.ru'
YANDEX_ORIGIN = 'https://oauth.yandex.ru'
SESSION_SECONDS = 30 * 86400
password_slots = asyncio.Semaphore(3)
Avatar = Literal['brand', 'detective', 'domination', 'hat', 'bunker', 'monopoly', 'boss', 'codenames']

SCHEMA = '''
CREATE TABLE IF NOT EXISTS accounts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    nickname text NOT NULL,
    avatar text NOT NULL DEFAULT 'brand',
    version bigint NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS account_sessions (
    digest text PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS account_sessions_expiry ON account_sessions(expires_at);
ALTER TABLE accounts ALTER COLUMN password_hash DROP NOT NULL;
CREATE TABLE IF NOT EXISTS account_identities (
    provider text NOT NULL,
    subject text NOT NULL,
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    PRIMARY KEY (provider, subject),
    UNIQUE (account_id, provider)
);
'''


@asynccontextmanager
async def storage(app):
    app.state.account_db = None
    app.state.account_cache = None
    if not os.getenv('DATABASE_HOST'):
        yield
        return

    import asyncpg
    from redis.asyncio import Redis

    async with asyncpg.create_pool(
        host=os.environ['DATABASE_HOST'], user=os.environ['POSTGRES_USER'],
        database=os.environ['POSTGRES_DB'], password=os.environ['POSTGRES_PASSWORD'],
        min_size=1, max_size=8, command_timeout=5,
    ) as db:
        await db.execute(SCHEMA)
        app.state.account_db = db
        async with Redis.from_url(os.environ['REDIS_URL'], decode_responses=True,
                                  socket_connect_timeout=0.5, socket_timeout=0.5) as cache:
            app.state.account_cache = cache
            yield


class Login(BaseModel):
    username: str = Field(min_length=3, max_length=24, pattern=r'^[A-Za-z0-9_]+$')
    password: str = Field(min_length=10, max_length=128)


class Profile(BaseModel):
    nickname: str = Field(min_length=1, max_length=20)
    avatar: Avatar = 'brand'

    @field_validator('nickname', mode='before')
    @classmethod
    def trim_nickname(cls, value):
        return value.strip() if isinstance(value, str) else value


class Registration(Login, Profile):
    pass


def password_digest(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=32768, r=8, p=1,
                          maxmem=64 * 1024 * 1024).hex()


async def hash_password(password, salt):
    async with password_slots:
        return await asyncio.to_thread(password_digest, password, salt)


def session_digest(request):
    token = request.cookies.get(COOKIE, '')
    return hashlib.sha256(token.encode()).hexdigest() if len(token) == 43 else None


def database(request):
    db = getattr(request.app.state, 'account_db', None)
    if db is None:
        raise HTTPException(503, 'Аккаунты сейчас недоступны.')
    return db


def require_same_origin(request):
    origin = request.headers.get('origin')
    host = request.headers.get('host')
    if origin and origin not in (f'http://{host}', f'https://{host}'):
        raise HTTPException(403, 'Запрос должен быть отправлен с этого сайта.')


async def limit_attempts(request, action, identity, maximum):
    from redis.exceptions import RedisError

    window = int(time.time()) // 600
    identity_hash = hashlib.sha256(identity.encode()).hexdigest()
    key = f'kaban:auth:{action}:{window}:{identity_hash}'
    try:
        async with request.app.state.account_cache.pipeline(transaction=True) as pipe:
            count, _ = await pipe.incr(key).expire(key, 600).execute()
    except RedisError as error:
        raise HTTPException(503, 'Вход и регистрация временно недоступны.') from error
    if count > maximum:
        raise HTTPException(429, 'Слишком много попыток. Подождите несколько минут.')


async def start_session(connection, response, request, account_id, *, require_https=False):
    token = secrets.token_urlsafe(32)
    await connection.execute('DELETE FROM account_sessions WHERE expires_at <= now() OR digest = $1', session_digest(request))
    await connection.execute(
        "INSERT INTO account_sessions VALUES ($1, $2, now() + interval '30 days')",
        hashlib.sha256(token.encode()).hexdigest(), account_id,
    )
    secure = require_https or request.url.scheme == 'https' or request.headers.get('origin', '').startswith('https://')
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=secure, samesite='lax')


def profile_data(row):
    return {key: row[key] for key in ('username', 'nickname', 'avatar', 'vk_linked', 'yandex_linked')}


async def current_profile(request):
    digest = session_digest(request)
    db = getattr(request.app.state, 'account_db', None)
    if not digest or db is None:
        return None
    from redis.exceptions import RedisError

    session = await db.fetchrow('''
        SELECT a.id, a.version FROM account_sessions s JOIN accounts a ON a.id = s.account_id
        WHERE s.digest = $1 AND s.expires_at > now()
    ''', digest)
    if session is None:
        return None
    cache = request.app.state.account_cache
    key = f"kaban:profile:{session['id']}:{session['version']}"
    with suppress(RedisError):
        value = await cache.get(key)
        if value:
            cached_profile = json.loads(value)
            if 'yandex_linked' in cached_profile:
                return cached_profile
    row = await db.fetchrow('''
        SELECT username, nickname, avatar, version,
               EXISTS (SELECT FROM account_identities i WHERE i.account_id = a.id AND i.provider = 'vk') AS vk_linked,
               EXISTS (SELECT FROM account_identities i WHERE i.account_id = a.id AND i.provider = 'yandex') AS yandex_linked
        FROM accounts a WHERE id = $1
    ''', session['id'])
    if row is None:
        return None
    profile = profile_data(row)
    with suppress(RedisError):
        await cache.set(f"kaban:profile:{session['id']}:{row['version']}", json.dumps(profile), ex=300)
    return profile


@router.post('/register', status_code=201)
async def register(body: Registration, request: Request, response: Response):
    require_same_origin(request)
    db = database(request)
    await limit_attempts(request, 'register', request.client.host if request.client else 'unknown', 15)
    salt = secrets.token_bytes(16)
    digest = await hash_password(body.password, salt)
    async with db.acquire() as connection, connection.transaction():
        row = await connection.fetchrow('''
            INSERT INTO accounts (username, password_hash, nickname, avatar) VALUES ($1, $2, $3, $4)
            ON CONFLICT (username) DO NOTHING RETURNING id, username, nickname, avatar, false AS vk_linked, false AS yandex_linked
        ''', body.username.lower(), f'{salt.hex()}:{digest}', body.nickname, body.avatar)
        if row is None:
            raise HTTPException(409, 'Этот логин уже занят.')
        await start_session(connection, response, request, row['id'])
        return profile_data(row)


@router.post('/login')
async def login(body: Login, request: Request, response: Response):
    require_same_origin(request)
    db = database(request)
    username = body.username.lower()
    await limit_attempts(request, 'login-ip', request.client.host if request.client else 'unknown', 60)
    await limit_attempts(request, 'login-user', username, 10)
    row = await db.fetchrow('''
        SELECT id, username, password_hash, nickname, avatar,
               EXISTS (SELECT FROM account_identities i WHERE i.account_id = a.id AND i.provider = 'vk') AS vk_linked,
               EXISTS (SELECT FROM account_identities i WHERE i.account_id = a.id AND i.provider = 'yandex') AS yandex_linked
        FROM accounts a WHERE username = $1
    ''', username)
    stored_hash = row['password_hash'] if row else None
    salt, expected = stored_hash.split(':') if stored_hash else ('0' * 32, '0' * 128)
    digest = await hash_password(body.password, bytes.fromhex(salt))
    if not hmac.compare_digest(digest, expected) or not stored_hash:
        raise HTTPException(401, 'Неверный логин или пароль.')
    async with db.acquire() as connection, connection.transaction():
        await start_session(connection, response, request, row['id'])
    return profile_data(row)


@router.get('/me')
async def me(request: Request):
    return await current_profile(request)


@router.patch('/me')
async def update_profile(body: Profile, request: Request):
    require_same_origin(request)
    row = await database(request).fetchrow('''
        UPDATE accounts a SET nickname = $1, avatar = $2, version = version + 1
        FROM account_sessions s WHERE a.id = s.account_id AND s.digest = $3 AND s.expires_at > now()
        RETURNING a.username, a.nickname, a.avatar,
                  EXISTS (SELECT FROM account_identities i WHERE i.account_id = a.id AND i.provider = 'vk') AS vk_linked,
               EXISTS (SELECT FROM account_identities i WHERE i.account_id = a.id AND i.provider = 'yandex') AS yandex_linked
    ''', body.nickname, body.avatar, session_digest(request))
    if row is None:
        raise HTTPException(401, 'Войдите в аккаунт.')
    return profile_data(row)


@router.post('/logout', status_code=204)
async def logout(request: Request):
    require_same_origin(request)
    digest = session_digest(request)
    if digest:
        await database(request).execute('DELETE FROM account_sessions WHERE digest = $1', digest)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE)
    return response


def oauth_settings(request, provider):
    if provider == 'vk':
        app_id = os.getenv('VK_ID_APP_ID', '')
        callback = os.getenv('VK_ID_REDIRECT_URL', '')
        secret = ''
        origin = VK_ORIGIN
        if not (app_id.isascii() and app_id.isdigit()):
            return None
    else:
        app_id = os.getenv('YANDEX_CLIENT_ID', '')
        secret = os.getenv('YANDEX_CLIENT_SECRET', '')
        callback = os.getenv('YANDEX_REDIRECT_URL', '')
        origin = YANDEX_ORIGIN
        if not app_id or not secret:
            return None
    url = urlsplit(callback)
    if (url.scheme == 'https' and url.netloc == request.headers.get('host')
            and url.path == f'{OAUTH_PREFIX}/{provider}/callback'
            and not (url.query or url.fragment) and getattr(request.app.state, 'account_db', None)):
        return app_id, callback, secret, origin
    return None


@router.get('/providers')
async def providers(request: Request):
    return {provider: oauth_settings(request, provider) is not None for provider in ('vk', 'yandex')}


async def begin_oauth(request, provider, *, link=False):
    from redis.exceptions import RedisError

    settings = oauth_settings(request, provider)
    if settings is None:
        raise HTTPException(404, 'Этот способ входа на данном адресе не настроен.')
    app_id, callback, _, origin = settings
    digest = session_digest(request) if link else None
    if link:
        require_same_origin(request)
        if not digest or await current_profile(request) is None:
            raise HTTPException(401, 'Сначала войдите в аккаунт Kaban Games.')
    await limit_attempts(request, f'{provider}-start', request.client.host if request.client else 'unknown', 60)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    try:
        await request.app.state.account_cache.set(
            f'kaban:{provider}:flow:{state}', json.dumps({'verifier': verifier, 'link_session': digest}), ex=600,
        )
    except RedisError as error:
        raise HTTPException(503, 'Вход через внешний сервис временно недоступен.') from error
    params = urlencode({'client_id': app_id, 'redirect_uri': callback, 'response_type': 'code',
                        'state': state, 'code_challenge': challenge,
                        'code_challenge_method': 's256' if provider == 'vk' else 'S256',
                        'scope': '' if provider == 'vk' else 'login:info'})
    response = RedirectResponse(f'{origin}/authorize?{params}', status_code=303)
    response.set_cookie(f'kaban_{provider}_flow', state, max_age=600, httponly=True, secure=True,
                        samesite='lax', path=f'{OAUTH_PREFIX}/{provider}/callback')
    return response


@router.get('/oauth/{provider}/start')
async def oauth_start(provider: Provider, request: Request):
    return await begin_oauth(request, provider)


@router.post('/oauth/{provider}/link')
async def oauth_link(provider: Provider, request: Request):
    return await begin_oauth(request, provider, link=True)


class OAuthLoginError(Exception):
    pass


async def vk_user(app_id, callback, code, device_id, state, verifier):
    import httpx

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            exchange = await client.post(f'{VK_ORIGIN}/oauth2/auth', params={
                'grant_type': 'authorization_code', 'redirect_uri': callback, 'client_id': app_id,
                'code_verifier': verifier, 'state': state, 'device_id': device_id,
            }, data={'code': code})
            exchange.raise_for_status()
            token = exchange.json()
            if 'error' in token or token.get('state') != state or not token.get('access_token'):
                raise OAuthLoginError
            info = await client.post(f'{VK_ORIGIN}/oauth2/user_info', params={'client_id': app_id},
                                     data={'access_token': token['access_token']})
            info.raise_for_status()
            user = info.json()['user']
            subject = str(user['user_id'])
            if not subject.isascii() or not subject.isdecimal() or len(subject) > 32 or subject != str(token['user_id']):
                raise OAuthLoginError
    except (httpx.HTTPError, KeyError, TypeError, ValueError, AttributeError) as error:
        raise OAuthLoginError from error
    name = user.get('first_name')
    return subject, (name.strip()[:20] or 'Игрок ВК') if isinstance(name, str) else 'Игрок ВК'


async def yandex_user(app_id, secret, code, verifier):
    import httpx

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            exchange = await client.post(f'{YANDEX_ORIGIN}/token', auth=(app_id, secret), data={
                'grant_type': 'authorization_code', 'code': code, 'code_verifier': verifier,
            })
            exchange.raise_for_status()
            token = exchange.json()['access_token']
            if not isinstance(token, str) or not token.strip():
                raise OAuthLoginError
            info = await client.get('https://login.yandex.ru/info', params={'format': 'json'},
                                    headers={'Authorization': f'OAuth {token}'})
            info.raise_for_status()
            user = info.json()
            subject = str(user['id'])
            if user.get('client_id') != app_id or not subject.isascii() or not subject.isdecimal() or len(subject) > 32:
                raise OAuthLoginError
    except (httpx.HTTPError, KeyError, TypeError, ValueError, AttributeError) as error:
        raise OAuthLoginError from error
    name = user.get('first_name') or user.get('login')
    return subject, (name.strip()[:20] or 'Игрок') if isinstance(name, str) else 'Игрок'


def oauth_redirect(provider, path, status=None):
    location = f'{path}?{provider}={status}' if status else path
    response = RedirectResponse(location, status_code=303, headers={'Referrer-Policy': 'no-referrer'})
    response.delete_cookie(f'kaban_{provider}_flow', path=f'{OAUTH_PREFIX}/{provider}/callback',
                           secure=True, httponly=True, samesite='lax')
    return response


@router.get('/oauth/{provider}/callback')
async def oauth_callback(provider: Provider, request: Request, state: str = '', code: str = '',
                         device_id: str = '', error: str = ''):
    from redis.exceptions import RedisError

    settings = oauth_settings(request, provider)
    cookie = request.cookies.get(f'kaban_{provider}_flow', '')
    if settings is None or len(state) != 43 or not hmac.compare_digest(state.encode(), cookie.encode()):
        return oauth_redirect(provider, '/account/login', 'expired')
    try:
        raw_flow = await request.app.state.account_cache.getdel(f'kaban:{provider}:flow:{state}')
    except RedisError:
        return oauth_redirect(provider, '/account/login', 'failed')
    if raw_flow is None:
        return oauth_redirect(provider, '/account/login', 'expired')

    flow = json.loads(raw_flow)
    link_session = flow['link_session']
    back = '/profile' if link_session else '/account/login'
    if error or not 0 < len(code) <= 2048 or (provider == 'vk' and not 0 < len(device_id) <= 512):
        return oauth_redirect(provider, back, 'failed')
    if link_session and link_session != session_digest(request):
        return oauth_redirect(provider, '/account/login', 'expired')
    app_id, callback, secret, _ = settings
    try:
        if provider == 'vk':
            subject, nickname = await vk_user(app_id, callback, code, device_id, state, flow['verifier'])
        else:
            subject, nickname = await yandex_user(app_id, secret, code, flow['verifier'])
    except OAuthLoginError:
        return oauth_redirect(provider, back, 'failed')

    response = oauth_redirect(provider, '/profile', 'linked' if link_session else None)
    async with database(request).acquire() as connection, connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f'{provider}:{subject}')
        existing = await connection.fetchval("SELECT account_id FROM account_identities WHERE provider = $1 AND subject = $2", provider, subject)
        if link_session:
            account_id = await connection.fetchval('''
                SELECT account_id FROM account_sessions WHERE digest = $1 AND expires_at > now() FOR UPDATE
            ''', link_session)
            if account_id is None:
                return oauth_redirect(provider, '/account/login', 'expired')
            if existing == account_id:
                return response
            if existing is not None:
                return oauth_redirect(provider, '/profile', 'conflict')
            inserted = await connection.fetchval('''
                INSERT INTO account_identities (provider, subject, account_id) VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING RETURNING account_id
            ''', provider, subject, account_id)
            if inserted is None:
                return oauth_redirect(provider, '/profile', 'conflict')
            await connection.execute('UPDATE accounts SET version = version + 1 WHERE id = $1', account_id)
        else:
            account_id = existing
            if account_id is None:
                account_id = await connection.fetchval('''
                    INSERT INTO accounts (username, nickname) VALUES ($1, $2) RETURNING id
                ''', f'{provider}_' + secrets.token_hex(8), nickname)
                await connection.execute("INSERT INTO account_identities (provider, subject, account_id) VALUES ($1, $2, $3)", provider, subject, account_id)
            await start_session(connection, response, request, account_id, require_https=True)
    return response
