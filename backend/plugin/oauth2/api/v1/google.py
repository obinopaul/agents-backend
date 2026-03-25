import json
import uuid

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from fastapi_limiter.depends import RateLimiter
from fastapi_oauth20 import FastAPIOAuth20, GoogleOAuth20
from starlette.responses import RedirectResponse

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.core.conf import settings
from backend.database.db import CurrentSessionTransaction
from backend.database.redis import redis_client
from backend.plugin.oauth2.enums import UserSocialAuthType, UserSocialType
from backend.plugin.oauth2.service.oauth2_service import oauth2_service

router = APIRouter()

google_client = GoogleOAuth20(settings.OAUTH2_GOOGLE_CLIENT_ID, settings.OAUTH2_GOOGLE_CLIENT_SECRET)


@router.get('', summary='获取 google 授权链接')
async def get_google_oauth2_url() -> ResponseSchemaModel[str]:
    state = str(uuid.uuid4())

    await redis_client.setex(
        f'{settings.OAUTH2_STATE_REDIS_PREFIX}:{state}',
        settings.OAUTH2_STATE_EXPIRE_SECONDS,
        json.dumps({'type': UserSocialAuthType.login.value}),
    )

    auth_url = await google_client.get_authorization_url(redirect_uri=settings.OAUTH2_GOOGLE_REDIRECT_URI, state=state)
    return response_base.success(data=auth_url)


@router.get(
    '/callback',
    summary='google 授权自动重定向',
    description='google 授权后，自动重定向到当前地址并获取用户信息，通过用户信息自动创建系统用户',
    dependencies=[Depends(RateLimiter(times=5, minutes=1))],
)
async def google_oauth2_callback(  # noqa: ANN201
    db: CurrentSessionTransaction,
    response: Response,
    background_tasks: BackgroundTasks,
    oauth2: Annotated[
        FastAPIOAuth20,
        Depends(FastAPIOAuth20(google_client, redirect_uri=settings.OAUTH2_GOOGLE_REDIRECT_URI)),
    ],
):
    token_data, state = oauth2
    access_token = token_data['access_token']
    user = await google_client.get_userinfo(access_token)
    data = await oauth2_service.login_or_binding(
        db=db,
        response=response,
        background_tasks=background_tasks,
        user=user,
        social=UserSocialType.google,
        state=state,
    )

    # 绑定流程
    if data is None:
        return RedirectResponse(url=settings.OAUTH2_FRONTEND_BINDING_REDIRECT_URI)

    # 登录流程
    return RedirectResponse(
        url=f'{settings.OAUTH2_FRONTEND_LOGIN_REDIRECT_URI}?access_token={data.access_token}&session_uuid={data.session_uuid}',
    )


@router.get(
    '/callback/code',
    summary='Frontend auth-code exchange',
    description='Exchange Google auth code from @react-oauth/google for JWT tokens. '
                'This endpoint handles the frontend popup OAuth flow where the code is sent directly '
                'without a backend-generated state. Auto-creates user if not exists.',
    dependencies=[Depends(RateLimiter(times=5, minutes=1))],
)
async def google_frontend_login(
    db: CurrentSessionTransaction,
    response: Response,
    background_tasks: BackgroundTasks,
    code: str,
    redirect_uri: str,
) -> ResponseSchemaModel[dict]:
    """
    Handle frontend @react-oauth/google auth-code flow.
    
    This is different from the redirect callback endpoint because:
    1. Frontend sends the auth code directly (no redirect from Google)
    2. No state validation needed (frontend manages the popup flow)
    3. Returns JSON response instead of redirect
    
    Args:
        code: Google authorization code from @react-oauth/google popup
        redirect_uri: The OAuth redirect URI used in the frontend flow
        
    Returns:
        JWT access token and session info
    """
    # Exchange auth code for Google access token
    token_data = await google_client.get_access_token(code=code, redirect_uri=redirect_uri)
    google_access_token = token_data['access_token']
    
    # Get user info from Google
    user = await google_client.get_userinfo(google_access_token)
    
    # Login or create user using existing service logic
    # oauth2_service.login() handles:
    # - Finding existing user by social ID or email
    # - Auto-creating user if not exists
    # - Binding social account
    # - Creating JWT tokens
    # - Logging successful login
    # Use full name (e.g. "Paul Okafor") as nickname so first_name/last_name
    # are properly derived in the user schema. Fall back to given_name → name.
    full_name = user.get('name') or user.get('given_name') or ''
    data = await oauth2_service.login(
        db=db,
        response=response,
        background_tasks=background_tasks,
        sid=str(user.get('id')),
        source=UserSocialType.google,
        username=user.get('name'),
        nickname=full_name,
        email=user.get('email'),
        avatar=user.get('picture'),
    )
    
    # Return token data in format expected by frontend
    return response_base.success(data={
        'access_token': data.access_token,
        'refresh_token': '',  # Stored in httpOnly cookie by oauth2_service.login()
        'token_type': 'Bearer',
        'expires_in': settings.TOKEN_EXPIRE_SECONDS,
    })
