import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import asynccontextmanager, suppress
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix='/api/account')
COOKIE = 'kaban_session'
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


async def start_session(connection, response, request, account_id):
    token = secrets.token_urlsafe(32)
    await connection.execute('DELETE FROM account_sessions WHERE expires_at <= now() OR digest = $1', session_digest(request))
    await connection.execute(
        "INSERT INTO account_sessions VALUES ($1, $2, now() + interval '30 days')",
        hashlib.sha256(token.encode()).hexdigest(), account_id,
    )
    secure = request.url.scheme == 'https' or request.headers.get('origin', '').startswith('https://')
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=secure, samesite='lax')


def profile_data(row):
    return {key: row[key] for key in ('username', 'nickname', 'avatar')}


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
            return json.loads(value)
    row = await db.fetchrow('SELECT username, nickname, avatar, version FROM accounts WHERE id = $1', session['id'])
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
            ON CONFLICT (username) DO NOTHING RETURNING id, username, nickname, avatar
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
    row = await db.fetchrow('SELECT id, username, password_hash, nickname, avatar FROM accounts WHERE username = $1', username)
    salt, expected = row['password_hash'].split(':') if row else ('0' * 32, '0' * 128)
    digest = await hash_password(body.password, bytes.fromhex(salt))
    if not hmac.compare_digest(digest, expected) or row is None:
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
        RETURNING a.username, a.nickname, a.avatar
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
