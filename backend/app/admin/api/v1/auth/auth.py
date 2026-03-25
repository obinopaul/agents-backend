from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPBasicCredentials
from fastapi_limiter.depends import RateLimiter
from starlette.background import BackgroundTasks

from backend.app.admin.schema.token import GetLoginToken, GetNewToken, GetSwaggerToken
from backend.app.admin.schema.user import AuthLoginParam, RegisterUserParam, RegisterUserResponse
from backend.app.admin.service.auth_service import auth_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.post('/login/swagger', summary='swagger 调试专用', description='用于快捷获取 token 进行 swagger 认证')
async def login_swagger(
    db: CurrentSessionTransaction, obj: Annotated[HTTPBasicCredentials, Depends()]
) -> GetSwaggerToken:
    token, user = await auth_service.swagger_login(db=db, obj=obj)
    return GetSwaggerToken(access_token=token, user=user)  # type: ignore


@router.post(
    '/login',
    summary='用户登录',
    description='json 格式登录, 仅支持在第三方api工具调试, 例如: postman',
    dependencies=[Depends(RateLimiter(times=5, minutes=1))],
)
async def login(
    db: CurrentSessionTransaction,
    response: Response,
    obj: AuthLoginParam,
    background_tasks: BackgroundTasks,
) -> ResponseSchemaModel[GetLoginToken]:
    data = await auth_service.login(db=db, response=response, obj=obj, background_tasks=background_tasks)
    return response_base.success(data=data)


@router.post(
    '/register',
    summary='Public user registration',
    description='Create a new user account with email and password. '
                'Returns JWT access token for immediate login after successful registration. '
                'Email must be unique - returns error if email is already registered.',
    dependencies=[Depends(RateLimiter(times=3, minutes=1))],  # Rate limit: 3 registrations per minute per IP
)
async def register(
    db: CurrentSessionTransaction,
    response: Response,
    obj: RegisterUserParam,
    background_tasks: BackgroundTasks,
) -> ResponseSchemaModel[RegisterUserResponse]:
    """
    Register a new user account.

    This endpoint allows public registration with email/password.
    After successful registration, the user is automatically logged in
    and receives a JWT access token.

    - **email**: User's email address (must be unique, will be used for login)
    - **password**: Password (minimum 6 characters)
    - **name**: Display name / nickname
    - **confirm_password**: Optional password confirmation

    Returns access token that can be used immediately for authenticated requests.
    """
    data = await auth_service.register(
        db=db,
        response=response,
        obj=obj,
        background_tasks=background_tasks,
    )
    return response_base.success(data=data)


@router.get('/codes', summary='获取所有授权码', description='适配 vben admin v5', dependencies=[DependsJwtAuth])
async def get_codes(db: CurrentSession, request: Request) -> ResponseSchemaModel[list[str]]:
    codes = await auth_service.get_codes(db=db, request=request)
    return response_base.success(data=codes)


@router.post('/refresh', summary='刷新 token')
async def refresh_token(db: CurrentSession, request: Request) -> ResponseSchemaModel[GetNewToken]:
    data = await auth_service.refresh_token(db=db, request=request)
    return response_base.success(data=data)


@router.post('/logout', summary='用户登出')
async def logout(request: Request, response: Response) -> ResponseModel:
    await auth_service.logout(request=request, response=response)
    return response_base.success()
