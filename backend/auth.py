import logging
import os
import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models import Principal, Role

security = HTTPBearer(auto_error=False)
logger = logging.getLogger('syntrix.authorization')


async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if not credentials:
        raise HTTPException(401, 'Sign in to access your workspace')
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(os.environ['SUPABASE_URL'].rstrip('/') + '/auth/v1/user', headers={
                'apikey': os.environ['SUPABASE_ANON_KEY'], 'Authorization': f'Bearer {credentials.credentials}'})
        if response.status_code != 200:
            raise HTTPException(401, 'Invalid or expired session. Please sign in again.')
        user = response.json()
        if not user.get('id'):
            raise HTTPException(401, 'Invalid identity')
        role = (user.get('app_metadata') or {}).get('role', 'VIEWER')
        if not isinstance(role, str) or role not in Role.__members__:
            role = 'VIEWER'
        if user.get('email_confirmed_at') and user.get('email', '').lower() == os.environ['OWNER_EMAIL'].lower():
            role = 'ADMIN'
        return Principal(id=user['id'], email=user.get('email', ''), role=Role(role))
    except httpx.HTTPError:
        raise HTTPException(503, 'Supabase sign-in is temporarily unavailable')
    except (ValueError, TypeError, KeyError):
        raise HTTPException(401, 'Invalid identity response')


def authorize(principal, action):
    permissions = {
        Role.VIEWER: {'read', 'export'},
        Role.ANALYST: {'read', 'export', 'simulate', 'optimize', 'select'},
        Role.ADMIN: {'read', 'export', 'simulate', 'optimize', 'select', 'delete'},
    }
    allowed = action in permissions.get(principal.role, set())
    logger.info('authorization principal=%s action=%s allowed=%s', principal.id, action, allowed)
    if not allowed:
        raise HTTPException(403, 'Your role does not permit this action')


def require(action):
    async def dependency(user: Principal = Depends(current_user)):
        authorize(user, action)
        return user
    return dependency


async def auth_status():
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(os.environ['SUPABASE_URL'].rstrip('/') + '/auth/v1/settings', headers={'apikey': os.environ['SUPABASE_ANON_KEY']})
        return {'available': r.status_code == 200, 'message': 'Supabase connected' if r.status_code == 200 else 'Supabase rejected the configured public key. Ask the workspace owner to update it.'}
    except httpx.HTTPError:
        return {'available': False, 'message': 'Supabase is unreachable. The sample workspace remains available.'}
