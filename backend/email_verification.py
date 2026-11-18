import asyncio
import hashlib
import logging
import os
import secrets
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

if __package__:
    from .accounts import database, limit_attempts, lock_account, require_same_origin, session_digest
else:
    from accounts import database, limit_attempts, lock_account, require_same_origin, session_digest

router = APIRouter(prefix='/api/account/email')
logger = logging.getLogger(__name__)
VERIFY_PATH = '/account/verify-email'
MAIL_TIMEOUT = 8
send_slots = asyncio.Semaphore(3)


@dataclass(frozen=True)
class MailSettings:
    origin: str
    host: str
    port: int
    security: str
    sender: str
    username: str
    password: str = field(repr=False)


class Address(BaseModel):
    email: EmailStr = Field(max_length=254)


class Verification(BaseModel):
    token: str = Field(pattern=r'^[A-Za-z0-9_-]{43}$')


def mail_settings():
    origin = os.getenv('PUBLIC_SITE_URL', '').rstrip('/')
    host = os.getenv('SMTP_HOST', '')
    sender = os.getenv('SMTP_FROM', '')
    username = os.getenv('SMTP_USERNAME', '')
    password = os.getenv('SMTP_PASSWORD', '')
    security = os.getenv('SMTP_SECURITY', 'starttls')
    try:
        port = int(os.getenv('SMTP_PORT', '587'))
        url = urlsplit(origin)
    except ValueError:
        return None
    if (not all((host, sender, username, password)) or security not in ('starttls', 'ssl')
            or not 1 <= port <= 65535 or url.scheme != 'https' or not url.hostname
            or url.username or url.password or url.path or url.query or url.fragment):
        return None
    return MailSettings(origin, host, port, security, sender, username, password)


def send_message(settings, address, token):
    message = EmailMessage()
    message['From'] = settings.sender
    message['To'] = address
    message['Subject'] = 'Подтвердите почту в Kaban Games'
    link = f'{settings.origin}{VERIFY_PATH}#token={token}'
    message.set_content(f'Откройте ссылку и нажмите «Подтвердить почту»:\n\n{link}\n\n'
                        'Ссылка действует 30 минут. Если вы не запрашивали подтверждение, проигнорируйте письмо.')
    context = ssl.create_default_context()
    if settings.security == 'ssl':
        connection = smtplib.SMTP_SSL(settings.host, settings.port, timeout=MAIL_TIMEOUT, context=context)
    else:
        connection = smtplib.SMTP(settings.host, settings.port, timeout=MAIL_TIMEOUT)
    try:
        if settings.security == 'starttls':
            connection.starttls(context=context)
        connection.login(settings.username, settings.password)
        connection.send_message(message)
    finally:
        connection.close()


def token_digest(token):
    return hashlib.sha256(token.encode('ascii')).hexdigest()


@router.get('')
async def email_status(request: Request):
    row = await database(request).fetchrow('''
        SELECT e.email AS verified, v.email AS pending
        FROM account_sessions s
        LEFT JOIN account_emails e USING (account_id)
        LEFT JOIN email_verifications v ON v.account_id = s.account_id AND v.expires_at > now()
        WHERE s.digest = $1 AND s.expires_at > now()
    ''', session_digest(request))
    if row is None:
        raise HTTPException(401, 'Войдите в аккаунт.')
    return {**dict(row), 'enabled': mail_settings() is not None}


@router.post('/send', status_code=202)
async def send_verification(body: Address, request: Request):
    require_same_origin(request)
    settings = mail_settings()
    if settings is None:
        raise HTTPException(503, 'Отправка писем пока не настроена.')
    db = database(request)
    address = body.email.casefold()
    token = secrets.token_urlsafe(32)
    digest = token_digest(token)
    async with db.acquire() as connection, connection.transaction():
        account = await lock_account(connection, session_digest(request))
        if account is None:
            raise HTTPException(401, 'Войдите в аккаунт.')
        account_id = account['id']
        if await connection.fetchval('SELECT email FROM account_emails WHERE account_id = $1', account_id) == address:
            raise HTTPException(409, 'Эта почта уже подтверждена.')
        await limit_attempts(request, 'email-account', str(account_id), 3)
        await limit_attempts(request, 'email-recipient', address, 3)
        await limit_attempts(request, 'email-ip', request.client.host if request.client else 'unknown', 15)
        await connection.execute('''
            INSERT INTO email_verifications (account_id, email, digest, expires_at)
            VALUES ($1, $2, $3, now() + interval '30 minutes')
            ON CONFLICT (account_id) DO UPDATE SET email = EXCLUDED.email, digest = EXCLUDED.digest,
                expires_at = EXCLUDED.expires_at
        ''', account_id, address, digest)

    try:
        async with send_slots:
            await asyncio.to_thread(send_message, settings, address, token)
    except (OSError, ValueError) as error:
        logger.warning('Verification email failed: %s', type(error).__name__)
        await db.execute('DELETE FROM email_verifications WHERE digest = $1', digest)
        raise HTTPException(503, 'Не удалось отправить письмо. Попробуйте позже.') from error
    await db.execute('DELETE FROM email_verifications WHERE expires_at <= now()')
    return {'pending': address}


@router.post('/verify', status_code=204)
async def verify_email(body: Verification, request: Request):
    from asyncpg import UniqueViolationError

    require_same_origin(request)
    digest = token_digest(body.token)
    try:
        async with database(request).acquire() as connection, connection.transaction():
            account_id = await connection.fetchval('''
                SELECT a.id FROM accounts a JOIN email_verifications v ON v.account_id = a.id
                WHERE v.digest = $1 AND v.expires_at > now() FOR UPDATE OF a
            ''', digest)
            pending = await connection.fetchrow('''
                DELETE FROM email_verifications WHERE digest = $1 AND account_id = $2 AND expires_at > now()
                RETURNING email
            ''', digest, account_id) if account_id is not None else None
            if pending is None:
                raise HTTPException(400, 'Ссылка устарела или уже использована. Запросите новое письмо в профиле.')
            await connection.execute('''
                INSERT INTO account_emails (account_id, email) VALUES ($1, $2)
                ON CONFLICT (account_id) DO UPDATE SET email = EXCLUDED.email, verified_at = now()
            ''', account_id, pending['email'])
    except UniqueViolationError as error:
        raise HTTPException(409, 'Эта почта уже подтверждена в другом аккаунте.') from error
