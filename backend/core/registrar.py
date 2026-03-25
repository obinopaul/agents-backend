import os

from asyncio import create_task
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import socketio

from fastapi import Depends, FastAPI
from fastapi_limiter import FastAPILimiter
from fastapi_pagination import add_pagination
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp
from starlette_context.middleware import ContextMiddleware
from starlette_context.plugins import RequestIdPlugin

from backend import __version__
from backend.common.exception.exception_handler import register_exception
from backend.common.log import log, set_custom_logfile, setup_logging
from backend.common.response.response_code import StandardResponseCode
from backend.core.conf import settings
from backend.core.path_conf import STATIC_DIR, UPLOAD_DIR
from backend.database.db import create_tables
from backend.database.redis import redis_client
from backend.middleware.access_middleware import AccessMiddleware
from backend.middleware.i18n_middleware import I18nMiddleware
from backend.middleware.jwt_auth_middleware import JwtAuthMiddleware
from backend.middleware.opera_log_middleware import OperaLogMiddleware
from backend.middleware.state_middleware import StateMiddleware
from backend.plugin.tools import build_final_router
from backend.utils.demo_site import demo_site
from backend.utils.health_check import ensure_unique_route_names, http_limit_callback
from backend.utils.openapi import simplify_operation_ids
from backend.utils.serializers import MsgSpecJSONResponse
from backend.utils.snowflake import snowflake
from backend.src.services.sandbox_service import sandbox_service
from backend.src.graph.checkpointer import checkpointer_manager
from backend.src.scripts.runner import start_runner as start_scripts, stop_runner as stop_scripts


@asynccontextmanager
async def register_init(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    启动初始化

    :param app: FastAPI 应用实例
    :return:
    """
    # Load all database models for SQLAlchemy table creation
    print("DEBUG: Loading all models...")
    from backend import load_all_models
    load_all_models()
    
    # 创建数据库表
    print("DEBUG: Creating tables...")
    try:
        await create_tables()
        print("DEBUG: Tables created successfully")
    except Exception as e:
        # Ignore errors if tables already exist to allow server to start
        import logging
        print(f"DEBUG: Error creating tables: {e}")
        logging.getLogger(__name__).error(f"Error creating tables (safe to ignore if using migrations): {e}")

    # 初始化 redis
    print("DEBUG: Opening Redis...")
    await redis_client.open()

    # 初始化 limiter
    print("DEBUG: Initializing limiter...")
    await FastAPILimiter.init(
        redis=redis_client,
        prefix=settings.REQUEST_LIMITER_REDIS_PREFIX,
        http_callback=http_limit_callback,
    )

    # 初始化 snowflake 节点
    print("DEBUG: Initializing Snowflake...")
    await snowflake.init()

    # 创建操作日志任务
    create_task(OperaLogMiddleware.consumer())

    # Initialize LangGraph PostgreSQL Checkpointer (shared connection pool)
    print("DEBUG: Initializing Checkpointer...")
    await checkpointer_manager.initialize()

    # Initialize Sandbox Service (graceful - don't crash app if sandbox fails)
    try:
        await sandbox_service.initialize()
        log.info("Sandbox Service initialized successfully")
    except Exception as e:
        log.warning(f"Sandbox Service initialization failed (sandbox features disabled): {e}")

    # Start Scheduled Scripts Runner (APScheduler)
    print("DEBUG: Starting Scripts Runner...")
    try:
        start_scripts()
        from backend.src.scripts.runner import is_running, get_scheduler
        print(f"DEBUG: Scripts Runner - is_running={is_running()}, jobs={len(get_scheduler().get_jobs())}")
        log.info("Scheduled Scripts Runner started successfully")
    except Exception as e:
        import traceback
        print(f"DEBUG: Scripts Runner FAILED: {e}")
        traceback.print_exc()
        log.warning(f"Scheduled Scripts Runner failed to start: {e}")

    # Initialize Socket.IO Chat Handlers
    print("DEBUG: Initializing Socket.IO Chat Handlers...")
    try:
        from backend.common.socketio.handlers import init_chat_handlers
        await init_chat_handlers()
        log.info("Socket.IO Chat Handlers initialized successfully")
    except Exception as e:
        log.warning(f"Socket.IO Chat Handlers initialization failed: {e}")

    # Seed Slide Templates
    print("DEBUG: Seeding Slide Templates...")
    try:
        from backend.src.services.template_seeder import seed_templates_on_startup
        await seed_templates_on_startup()
        log.info("Slide Templates seeded successfully")
    except Exception as e:
        log.warning(f"Slide Templates seeding failed: {e}")

    yield
    
    print("DEBUG: Shutting down...")
    
    # Stop Scheduled Scripts Runner
    try:
        stop_scripts()
        log.info("Scheduled Scripts Runner stopped")
    except Exception as e:
        log.warning(f"Scheduled Scripts Runner shutdown error: {e}")
    
    # Shutdown Sandbox Service
    await sandbox_service.shutdown()

    # Shutdown LangGraph Checkpointer
    await checkpointer_manager.shutdown()

    # 释放 snowflake 节点
    await snowflake.shutdown()

    # 关闭 redis 连接
    await redis_client.aclose()


def register_app() -> FastAPI:
    """注册 FastAPI 应用"""

    class MyFastAPI(FastAPI):
        if settings.MIDDLEWARE_CORS:
            # Related issues
            # https://github.com/fastapi/fastapi/discussions/7847
            # https://github.com/fastapi/fastapi/discussions/8027
            def build_middleware_stack(self) -> ASGIApp:
                return CORSMiddleware(
                    super().build_middleware_stack(),
                    allow_origins=settings.CORS_ALLOWED_ORIGINS,
                    allow_credentials=True,
                    allow_methods=['*'],
                    allow_headers=['*'],
                    expose_headers=settings.CORS_EXPOSE_HEADERS,
                )

    app = MyFastAPI(
        title=settings.FASTAPI_TITLE,
        version=__version__,
        description=settings.FASTAPI_DESCRIPTION,
        docs_url=settings.FASTAPI_DOCS_URL,
        redoc_url=settings.FASTAPI_REDOC_URL,
        openapi_url=settings.FASTAPI_OPENAPI_URL,
        default_response_class=MsgSpecJSONResponse,
        lifespan=register_init,
    )

    # 注册组件
    register_logger()
    register_socket_app(app)
    register_static_file(app)
    register_middleware(app)
    register_router(app)
    register_page(app)
    register_exception(app)
    register_health_endpoint(app)
    register_debug_endpoints(app)

    return app


def register_health_endpoint(app: FastAPI) -> None:
    """
    Register health check endpoint for monitoring and load balancers.
    
    :param app: FastAPI application instance
    :return:
    """
    from datetime import datetime, timezone
    
    @app.get("/health", tags=["Health"])
    async def health_check():
        """
        Health check endpoint.
        
        Returns basic health status of the API including:
        - Status: 'healthy' if the API is operational
        - Timestamp: Current UTC time
        - Version: API version
        """
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": __version__,
            "service": "agents-backend"
        }


def register_debug_endpoints(app: FastAPI) -> None:
    """
    Register debug endpoints for monitoring internal state.
    
    These endpoints allow debugging of internal components like the
    scripts scheduler from within the running FastAPI process.
    
    :param app: FastAPI application instance
    :return:
    """
    from datetime import datetime, timezone
    
    @app.get("/debug/scripts/status", tags=["Debug"])
    async def debug_scripts_status():
        """
        Get the current status of the scripts scheduler.
        
        This queries the actual scheduler state from within the
        running FastAPI process.
        """
        try:
            from backend.src.scripts.runner import is_running, get_scheduler, _is_running, _scheduler
            
            scheduler = _scheduler
            
            response = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "runner": {
                    "_is_running_flag": _is_running,
                    "is_running()": is_running(),
                    "scheduler_exists": scheduler is not None,
                },
                "scheduler": None,
                "jobs": [],
            }
            
            if scheduler:
                response["scheduler"] = {
                    "state": str(scheduler.state),
                    "running": scheduler.running,
                    "job_count": len(scheduler.get_jobs()),
                }
                
                for job in scheduler.get_jobs():
                    response["jobs"].append({
                        "id": job.id,
                        "name": job.name,
                        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                        "trigger": str(job.trigger),
                    })
            
            return response
            
        except Exception as e:
            import traceback
            return {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
    
    @app.post("/debug/scripts/start", tags=["Debug"])
    async def debug_scripts_start():
        """
        Manually start the scripts runner if it didn't start during lifespan.
        """
        try:
            from backend.src.scripts.runner import start_runner, is_running, get_scheduler
            
            was_running = is_running()
            
            if not was_running:
                start_runner()
            
            scheduler = get_scheduler()
            
            return {
                "success": True,
                "was_already_running": was_running,
                "is_now_running": is_running(),
                "job_count": len(scheduler.get_jobs()) if scheduler else 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


def register_logger() -> None:
    """Register logging handlers."""
    setup_logging()
    # TEMPORARILY DISABLED: Log file rotation has issues on Windows
    # set_custom_logfile()


def register_static_file(app: FastAPI) -> None:
    """
    注册静态资源服务

    :param app: FastAPI 应用实例
    :return:
    """
    # 上传静态资源
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    app.mount('/static/upload', StaticFiles(directory=UPLOAD_DIR), name='upload')

    # 固有静态资源
    if settings.FASTAPI_STATIC_FILES:
        app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')


def register_middleware(app: FastAPI) -> None:
    """
    注册中间件（执行顺序从下往上）

    :param app: FastAPI 应用实例
    :return:
    """
    # Opera log
    app.add_middleware(OperaLogMiddleware)

    # State
    app.add_middleware(StateMiddleware)

    # JWT auth
    app.add_middleware(
        AuthenticationMiddleware,
        backend=JwtAuthMiddleware(),
        on_error=JwtAuthMiddleware.auth_exception_handler,
    )

    # I18n
    app.add_middleware(I18nMiddleware)

    # Access log
    app.add_middleware(AccessMiddleware)

    # ContextVar
    app.add_middleware(
        ContextMiddleware,
        plugins=[RequestIdPlugin(validate=True)],
        default_error_response=MsgSpecJSONResponse(
            content={'code': StandardResponseCode.HTTP_400, 'msg': 'BAD_REQUEST', 'data': None},
            status_code=StandardResponseCode.HTTP_400,
        ),
    )


def register_router(app: FastAPI) -> None:
    """
    注册路由

    :param app: FastAPI 应用实例
    :return:
    """
    dependencies = [Depends(demo_site)] if settings.DEMO_MODE else None

    # API
    router = build_final_router()
    app.include_router(router, dependencies=dependencies)

    # Extra
    ensure_unique_route_names(app)
    simplify_operation_ids(app)


def register_page(app: FastAPI) -> None:
    """
    注册分页查询功能

    :param app: FastAPI 应用实例
    :return:
    """
    add_pagination(app)


def register_socket_app(app: FastAPI) -> None:
    """
    注册 Socket.IO 应用

    :param app: FastAPI 应用实例
    :return:
    """
    from backend.common.socketio.server import sio

    socket_app = socketio.ASGIApp(
        socketio_server=sio,
        other_asgi_app=app,
        # 切勿删除此配置：https://github.com/pyropy/fastapi-socketio/issues/51
        socketio_path='/ws/socket.io',
    )
    app.mount('/ws', socket_app)
