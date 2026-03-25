import socketio

from backend.common.log import log
from backend.common.security.jwt import jwt_authentication
from backend.core.conf import settings
from backend.database.redis import redis_client

# Construct Redis URL safely (handle empty password)
redis_url = f'redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DATABASE}'
if settings.REDIS_PASSWORD:
    redis_url = f'redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DATABASE}'

# 创建 Socket.IO 服务器实例
sio = socketio.AsyncServer(
    client_manager=socketio.AsyncRedisManager(redis_url),
    async_mode='asgi',
    cors_allowed_origins=settings.CORS_ALLOWED_ORIGINS,
    cors_credentials=True,
    namespaces=['/ws'],
)


@sio.on('connect', namespace='/ws')
async def connect(sid, environ, auth) -> bool:
    """Socket 连接事件"""
    if not auth:
        log.warning(f"[DEBUG WS] Connect attempt without auth data: {sid}")
        # log.error('WebSocket 连接失败：无授权')
        # return False

    session_uuid = auth.get('session_uuid') if auth else None
    token = auth.get('token') if auth else None
    
    # Only token is strictly required for initial connection
    if not token and not (auth and auth.get('token')):
         # Some clients might send token in query params or headers, but here we expect 'auth' dict
         pass

    if not token:
        log.error('WebSocket 连接失败：无 token')
        return False

    # 免授权直连 (No-Auth marker)
    if token == settings.WS_NO_AUTH_MARKER:
        try:
            if session_uuid:
                await redis_client.sadd(settings.TOKEN_ONLINE_REDIS_PREFIX, session_uuid)
            # Save session data for no-auth connections
            await sio.save_session(sid, {
                'authenticated': True,
                'user_id': None,
                'session_uuid': session_uuid,
            }, namespace='/ws')
            return True
        except Exception as e:
            log.error(f"No-Auth Connection Failed: {e!s}")
            raise socketio.exceptions.ConnectionRefusedError(f"No-Auth Failed: {e!s}")

    try:
        user = await jwt_authentication(token)
    except Exception as e:
        log.info(f'WebSocket 连接失败：{e!s}')
        # Raise exception to send error message to client for debugging
        raise socketio.exceptions.ConnectionRefusedError(f"Auth Failed: {e!s}")

    # Save authentication data to Socket.IO session (CRITICAL for handlers)
    try:
        log.warning(f"[DEBUG WS] Attempting save_session for {sid}")
        await sio.save_session(sid, {
            'authenticated': True,
            'user_id': user.id,
            'session_uuid': session_uuid,
        }, namespace='/ws')
        log.warning(f"[DEBUG WS] save_session success for {sid}")
    except Exception as e:
        log.warning(f"[DEBUG WS] save_session failed for {sid}: {e}")
        # Logging the error but NOT raising it, to allow connection to proceed.
        # 'Session not found' can happen during initial connection in creating the session logic.
        log.warning(f'WebSocket session save failed (Non-fatal) for user {user.id}: {e!s}')
        
        # Fallback: Manually store auth data in Redis for handlers to find


    # ALWAYS store fallback auth data in Redis (sio.save_session is unreliable for quick retrieval)
    try:
        log.warning(f"[DEBUG WS] Attempting fallback store for {sid}")
        fallback_key = f"agents:auth:{sid}"
        fallback_data = {
            'authenticated': True,
            'user_id': user.id,
            'session_uuid': session_uuid
        }
        # Import json to serialize dict
        import json
        await redis_client.setex(fallback_key, 3600, json.dumps(fallback_data))
        log.warning(f"[DEBUG WS] Fallback store success for {sid}")
        log.info(f"Fallback auth data stored for sid {sid}")
    except Exception as ex:
        log.warning(f"[DEBUG WS] Fallback store failed for {sid}: {ex}")
        log.error(f"Fallback auth store failed: {ex}")

    log.info(f'WebSocket 连接成功: user_id={user.id}, sid={sid}')

    # Only track online status if we have a session_uuid
    if session_uuid:
        await redis_client.sadd(settings.TOKEN_ONLINE_REDIS_PREFIX, session_uuid)

    return True


@sio.on('disconnect', namespace='/ws')
async def disconnect(sid) -> None:
    """Socket 断开连接事件"""
    await redis_client.spop(settings.TOKEN_ONLINE_REDIS_PREFIX)
    
    # Clean up fallback auth data
    try:
        await redis_client.delete(f"agents:auth:{sid}")
    except Exception:
        pass
