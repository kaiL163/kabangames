import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

try:
    from . import accounts, game_checks
except ImportError:
    import accounts
    import game_checks

logger = logging.getLogger(__name__)


async def require_admin(request: Request):
    if request.method != 'GET':
        accounts.require_same_origin(request)
    profile = await accounts.current_profile(request)
    if not profile:
        raise HTTPException(401, 'Войдите в аккаунт.')
    if profile['admin_role'] not in ('owner', 'tester'):
        raise HTTPException(403, 'Доступ к админ-панели не выдан.')
    return profile


Admin = Annotated[dict, Depends(require_admin)]


async def require_owner(profile: Admin):
    if profile['admin_role'] != 'owner':
        raise HTTPException(403, 'Доступ выдаёт владелец сайта.')
    return profile


Owner = Annotated[dict, Depends(require_owner)]


class RunCheck(BaseModel):
    game: str | None = Field(default=None, max_length=20)


class AccessChange(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    enabled: bool


def build_router(games, detective_check):
    router = APIRouter(prefix='/api/admin')

    @router.get('/checks')
    async def catalog(profile: Admin):
        return {'games': list(games), 'role': profile['admin_role']}

    @router.post('/checks')
    async def run_checks(body: RunCheck, profile: Admin):
        if body.game is not None and body.game not in games:
            raise HTTPException(404, 'Режим не найден.')
        results = []
        for mode in games if body.game is None else (body.game,):
            start = time.perf_counter()
            try:
                detail = game_checks.simulate(mode, detective_check)
                ok = True
            except ValueError as error:
                detail = str(error)
                ok = False
            except Exception:
                logger.exception('Game check failed: %s', mode)
                detail = 'Ошибка выполнения. Подробности в журнале сервера.'
                ok = False
            results.append({
                'game': mode, 'ok': ok, 'detail': detail,
                'duration_ms': round((time.perf_counter() - start) * 1000, 1),
            })
        return {'results': results}

    @router.get('/access')
    async def list_access(request: Request, owner: Owner):
        rows = await accounts.database(request).fetch('''
            SELECT username, nickname, admin_role FROM accounts
            WHERE admin_role IS NOT NULL ORDER BY admin_role, username
        ''')
        return {'users': [dict(row) for row in rows]}

    @router.post('/access')
    async def change_access(body: AccessChange, request: Request, owner: Owner):
        username = body.username.strip().lower()
        row = await accounts.database(request).fetchrow('''
            UPDATE accounts SET admin_role = $2
            WHERE username = $1 AND admin_role IS DISTINCT FROM 'owner'
            RETURNING username
        ''', username, 'tester' if body.enabled else None)
        if row is None:
            raise HTTPException(404, 'Укажите логин существующего пользователя без роли владельца.')
        logger.info('Tester access changed by %s: %s (enabled=%s)', owner['username'], username, body.enabled)
        return {'ok': True}

    return router
