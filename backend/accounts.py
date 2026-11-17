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
VK_FLOW_COOKIE = 'kaban_vk_flow'
VK_CALLBACK = '/api/account/oauth/vk/callback'
VK_ORIGIN = 'https://id.vk.ru'
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
    return {key: row[key] for key in ('username', 'nickname', 'avatar', 'vk_linked')}


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
            if 'vk_linked' in cached_profile:
                return cached_profile
    row = await db.fetchrow('''
        SELECT username, nickname, avatar, version,
               EXISTS (SELECT FROM account_identities i WHERE i.account_id = a.id AND i.provider = 'vk') AS vk_linked
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
            ON CONFLICT (username) DO NOTHING RETURNING id, username, nickname, avatar, false AS vk_linked
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
               EXISTS (SELECT FROM account_identities i WHERE i.account_id = a.id AND i.provider = 'vk') AS vk_linked
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
                  EXISTS (SELECT FROM account_identities i WHERE i.account_id = a.id AND i.provider = 'vk') AS vk_linked
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


def vk_settings(request):
    app_id = os.getenv('VK_ID_APP_ID', '')
    callback = os.getenv('VK_ID_REDIRECT_URL', '')
    url = urlsplit(callback)
    if (app_id.isascii() and app_id.isdigit() and url.scheme == 'https'
            and url.netloc == request.headers.get('host') and url.path == VK_CALLBACK
            and not (url.query or url.fragment) and getattr(request.app.state, 'account_db', None)):
        return app_id, callback
    return None


@router.get('/providers')
async def providers(request: Request):
    return {'vk': vk_settings(request) is not None}


async def begin_vk(request, *, link=False):
    from redis.exceptions import RedisError

    settings = vk_settings(request)
    if settings is None:
        raise HTTPException(404, 'Вход через ВК на этом адресе не настроен.')
    app_id, callback = settings
    digest = session_digest(request) if link else None
    if link:
        require_same_origin(request)
        if not digest or await current_profile(request) is None:
            raise HTTPException(401, 'Сначала войдите в аккаунт Kaban Games.')
    await limit_attempts(request, 'vk-start', request.client.host if request.client else 'unknown', 60)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    try:
        await request.app.state.account_cache.set(
            f'kaban:vk:flow:{state}', json.dumps({'verifier': verifier, 'link_session': digest}), ex=600,
        )
    except RedisError as error:
        raise HTTPException(503, 'Вход через ВК временно недоступен.') from error
    params = urlencode({'client_id': app_id, 'redirect_uri': callback, 'response_type': 'code',
                        'state': state, 'code_challenge': challenge, 'code_challenge_method': 's256', 'scope': ''})
    response = RedirectResponse(f'{VK_ORIGIN}/authorize?{params}', status_code=303)
    response.set_cookie(VK_FLOW_COOKIE, state, max_age=600, httponly=True, secure=True,
                        samesite='lax', path=VK_CALLBACK)
    return response


@router.get('/oauth/vk/start')
async def vk_start(request: Request):
    return await begin_vk(request)


@router.post('/oauth/vk/link')
async def vk_link(request: Request):
    return await begin_vk(request, link=True)


class VKLoginError(Exception):
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
                raise VKLoginError
            info = await client.post(f'{VK_ORIGIN}/oauth2/user_info', params={'client_id': app_id},
                                     data={'access_token': token['access_token']})
            info.raise_for_status()
            user = info.json()['user']
            subject = str(user['user_id'])
            if not subject.isascii() or not subject.isdecimal() or len(subject) > 32 or subject != str(token['user_id']):
                raise VKLoginError
    except (httpx.HTTPError, KeyError, TypeError, ValueError, AttributeError) as error:
        raise VKLoginError from error
    name = user.get('first_name')
    return subject, (name.strip()[:20] or 'Игрок ВК') if isinstance(name, str) else 'Игрок ВК'


def vk_redirect(path):
    response = RedirectResponse(path, status_code=303, headers={'Referrer-Policy': 'no-referrer'})
    response.delete_cookie(VK_FLOW_COOKIE, path=VK_CALLBACK, secure=True, httponly=True, samesite='lax')
    return response


@router.get('/oauth/vk/callback')
async def vk_callback(request: Request, state: str = '', code: str = '', device_id: str = '', error: str = ''):
    from redis.exceptions import RedisError

    settings = vk_settings(request)
    cookie = request.cookies.get(VK_FLOW_COOKIE, '')
    if settings is None or len(state) != 43 or not hmac.compare_digest(state.encode(), cookie.encode()):
        return vk_redirect('/account/login?vk=expired')
    try:
        raw_flow = await request.app.state.account_cache.getdel(f'kaban:vk:flow:{state}')
    except RedisError:
        return vk_redirect('/account/login?vk=failed')
    if raw_flow is None:
        return vk_redirect('/account/login?vk=expired')

    flow = json.loads(raw_flow)
    link_session = flow['link_session']
    back = '/profile' if link_session else '/account/login'
    if error or not (0 < len(code) <= 2048 and 0 < len(device_id) <= 512):
        return vk_redirect(f'{back}?vk=failed')
    if link_session and link_session != session_digest(request):
        return vk_redirect('/account/login?vk=expired')
    try:
        subject, nickname = await vk_user(*settings, code, device_id, state, flow['verifier'])
    except VKLoginError:
        return vk_redirect(f'{back}?vk=failed')

    response = vk_redirect('/profile?vk=linked' if link_session else '/profile')
    async with database(request).acquire() as connection, connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('vk:' || $1, 0))", subject)
        existing = await connection.fetchval("SELECT account_id FROM account_identities WHERE provider = 'vk' AND subject = $1", subject)
        if link_session:
            account_id = await connection.fetchval('''
                SELECT account_id FROM account_sessions WHERE digest = $1 AND expires_at > now() FOR UPDATE
            ''', link_session)
            if account_id is None:
                return vk_redirect('/account/login?vk=expired')
            if existing == account_id:
                return response
            if existing is not None:
                return vk_redirect('/profile?vk=conflict')
            inserted = await connection.fetchval('''
                INSERT INTO account_identities (provider, subject, account_id) VALUES ('vk', $1, $2)
                ON CONFLICT DO NOTHING RETURNING account_id
            ''', subject, account_id)
            if inserted is None:
                return vk_redirect('/profile?vk=conflict')
            await connection.execute('UPDATE accounts SET version = version + 1 WHERE id = $1', account_id)
        else:
            account_id = existing
            if account_id is None:
                account_id = await connection.fetchval('''
                    INSERT INTO accounts (username, nickname) VALUES ($1, $2) RETURNING id
                ''', 'vk_' + secrets.token_hex(10), nickname)
                await connection.execute("INSERT INTO account_identities (provider, subject, account_id) VALUES ('vk', $1, $2)", subject, account_id)
            await start_session(connection, response, request, account_id, require_https=True)
    return response
