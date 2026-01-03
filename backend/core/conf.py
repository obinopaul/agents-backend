from functools import lru_cache
from re import Pattern
from typing import Any, Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.path_conf import BASE_PATH


class Settings(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        env_file=f'{BASE_PATH}/.env',
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=True,
    )

    # .env 当前环境
    ENVIRONMENT: Literal['dev', 'prod']

    # FastAPI
    FASTAPI_API_V1_PATH: str = '/api/v1'
    FASTAPI_TITLE: str = 'AgentsBackend'
    FASTAPI_DESCRIPTION: str = 'Agents Backend Architecture'
    FASTAPI_DOCS_URL: str = '/docs'
    FASTAPI_REDOC_URL: str = '/redoc'
    FASTAPI_OPENAPI_URL: str | None = '/openapi'
    FASTAPI_STATIC_FILES: bool = True

    # .env 数据库
    DATABASE_TYPE: Literal['mysql', 'postgresql']
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USER: str
    DATABASE_PASSWORD: str

    # 数据库
    DATABASE_ECHO: bool | Literal['debug'] = False
    DATABASE_POOL_ECHO: bool | Literal['debug'] = False
    DATABASE_SCHEMA: str = 'agents_backend'
    DATABASE_CHARSET: str = 'utf8mb4'
    DATABASE_PK_MODE: Literal['autoincrement', 'snowflake'] = 'autoincrement'

    # .env Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str
    REDIS_USERNAME: str = 'default'  # For Redis 6+ ACL (cloud Redis typically uses 'default')
    REDIS_DATABASE: int

    # Redis
    REDIS_TIMEOUT: int = 5

    # .env Snowflake
    SNOWFLAKE_DATACENTER_ID: int | None = None
    SNOWFLAKE_WORKER_ID: int | None = None

    # Snowflake
    SNOWFLAKE_REDIS_PREFIX: str = 'agents_backend:snowflake'
    SNOWFLAKE_HEARTBEAT_INTERVAL_SECONDS: int = 30
    SNOWFLAKE_NODE_TTL_SECONDS: int = 60

    # .env Token
    TOKEN_SECRET_KEY: str  # 密钥 secrets.token_urlsafe(32)

    # Token
    TOKEN_ALGORITHM: str = 'HS256'
    TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24  # 1 天
    TOKEN_REFRESH_EXPIRE_SECONDS: int = 60 * 60 * 24 * 7  # 7 天
    TOKEN_REDIS_PREFIX: str = 'agents_backend:token'
    TOKEN_EXTRA_INFO_REDIS_PREFIX: str = 'agents_backend:token_extra_info'
    TOKEN_ONLINE_REDIS_PREFIX: str = 'agents_backend:token_online'
    TOKEN_REFRESH_REDIS_PREFIX: str = 'agents_backend:refresh_token'
    TOKEN_REQUEST_PATH_EXCLUDE: list[str] = [  # JWT / RBAC 路由白名单
        f'{FASTAPI_API_V1_PATH}/auth/login',
    ]
    TOKEN_REQUEST_PATH_EXCLUDE_PATTERN: list[Pattern[str]] = [  # JWT / RBAC 路由白名单（正则）
        rf'^{FASTAPI_API_V1_PATH}/monitors/(redis|server)$',
    ]

    # 用户安全
    USER_LOCK_REDIS_PREFIX: str = 'agents_backend:user:lock'
    USER_LOCK_THRESHOLD: int = 5  # 用户密码错误锁定阈值，0 表示禁用锁定
    USER_LOCK_SECONDS: int = 60 * 5  # 5 分钟
    USER_PASSWORD_EXPIRY_DAYS: int = 365  # 用户密码有效期，0 表示永不过期
    USER_PASSWORD_REMINDER_DAYS: int = 7  # 用户密码到期提醒，0 表示不提醒
    USER_PASSWORD_HISTORY_CHECK_COUNT: int = 3
    USER_PASSWORD_MIN_LENGTH: int = 6
    USER_PASSWORD_MAX_LENGTH: int = 32
    USER_PASSWORD_REQUIRE_SPECIAL_CHAR: bool = False

    # 登录
    LOGIN_CAPTCHA_ENABLED: bool = True
    LOGIN_CAPTCHA_REDIS_PREFIX: str = 'agents_backend:login:captcha'
    LOGIN_CAPTCHA_EXPIRE_SECONDS: int = 60 * 5  # 5 分钟
    LOGIN_FAILURE_PREFIX: str = 'agents_backend:login:failure'

    # JWT
    JWT_USER_REDIS_PREFIX: str = 'agents_backend:user'

    # RBAC
    RBAC_ROLE_MENU_MODE: bool = True
    RBAC_ROLE_MENU_EXCLUDE: list[str] = [
        'sys:monitor:redis',
        'sys:monitor:server',
    ]

    # Cookie
    COOKIE_REFRESH_TOKEN_KEY: str = 'agents_backend_refresh_token'
    COOKIE_REFRESH_TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24 * 7  # 7 天

    # 数据权限
    DATA_PERMISSION_COLUMN_EXCLUDE: list[str] = [  # 排除允许进行数据过滤的 SQLA 模型列
        'id',
        'sort',
        'del_flag',
        'created_time',
        'updated_time',
    ]

    # Socket.IO
    WS_NO_AUTH_MARKER: str = 'internal'

    # CORS
    CORS_ALLOWED_ORIGINS: list[str] = [  # 末尾不带斜杠
        'http://127.0.0.1:8000',
        'http://localhost:5173',
    ]
    CORS_EXPOSE_HEADERS: list[str] = [
        'X-Request-ID',
    ]

    # 中间件配置
    MIDDLEWARE_CORS: bool = True

    # 请求限制配置
    REQUEST_LIMITER_REDIS_PREFIX: str = 'agents_backend:limiter'

    # 时间配置
    DATETIME_TIMEZONE: str = 'Asia/Shanghai'
    DATETIME_FORMAT: str = '%Y-%m-%d %H:%M:%S'

    # 文件上传
    UPLOAD_READ_SIZE: int = 1024
    UPLOAD_IMAGE_EXT_INCLUDE: list[str] = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    UPLOAD_IMAGE_SIZE_MAX: int = 5 * 1024 * 1024  # 5 MB
    UPLOAD_VIDEO_EXT_INCLUDE: list[str] = ['mp4', 'mov', 'avi', 'flv']
    UPLOAD_VIDEO_SIZE_MAX: int = 20 * 1024 * 1024  # 20 MB

    # 演示模式配置
    DEMO_MODE: bool = False
    DEMO_MODE_EXCLUDE: set[tuple[str, str]] = {
        ('POST', f'{FASTAPI_API_V1_PATH}/auth/login'),
        ('POST', f'{FASTAPI_API_V1_PATH}/auth/logout'),
        ('GET', f'{FASTAPI_API_V1_PATH}/auth/captcha'),
        ('POST', f'{FASTAPI_API_V1_PATH}/auth/refresh'),
    }

    # IP 定位配置
    IP_LOCATION_PARSE: Literal['online', 'offline', 'false'] = 'offline'
    IP_LOCATION_REDIS_PREFIX: str = 'agents_backend:ip:location'
    IP_LOCATION_EXPIRE_SECONDS: int = 60 * 60 * 24  # 1 天

    # Trace ID
    TRACE_ID_REQUEST_HEADER_KEY: str = 'X-Request-ID'
    TRACE_ID_LOG_LENGTH: int = 32  # UUID 长度，必须小于等于 32
    TRACE_ID_LOG_DEFAULT_VALUE: str = '-'

    # 日志
    LOG_FORMAT: str = (
        '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</> | <lvl>{level: <8}</> | <cyan>{request_id}</> | <lvl>{message}</>'
    )

    # 日志（控制台）
    LOG_STD_LEVEL: str = 'INFO'

    # 日志（文件）
    LOG_FILE_ACCESS_LEVEL: str = 'INFO'
    LOG_FILE_ERROR_LEVEL: str = 'ERROR'
    LOG_ACCESS_FILENAME: str = 'agents_backend_access.log'
    LOG_ERROR_FILENAME: str = 'agents_backend_error.log'

    # .env 操作日志
    OPERA_LOG_ENCRYPT_SECRET_KEY: str  # 密钥 os.urandom(32), 需使用 bytes.hex() 方法转换为 str

    # 操作日志
    OPERA_LOG_PATH_EXCLUDE: list[str] = [
        '/favicon.ico',
        '/docs',
        '/redoc',
        '/openapi',
        f'{FASTAPI_API_V1_PATH}/auth/login/swagger',
        f'{FASTAPI_API_V1_PATH}/oauth2/github/callback',
        f'{FASTAPI_API_V1_PATH}/oauth2/google/callback',
        f'{FASTAPI_API_V1_PATH}/oauth2/linux-do/callback',
    ]
    OPERA_LOG_ENCRYPT_TYPE: int = 1  # 0: AES (性能损耗); 1: md5; 2: ItsDangerous; 3: 不加密, others: 替换为 ******
    OPERA_LOG_ENCRYPT_KEY_INCLUDE: list[str] = [  # 将加密接口入参参数对应的值
        'password',
        'old_password',
        'new_password',
        'confirm_password',
    ]
    OPERA_LOG_QUEUE_BATCH_CONSUME_SIZE: int = 100
    OPERA_LOG_QUEUE_TIMEOUT: int = 60  # 1 分钟

    # Plugin 配置
    PLUGIN_PIP_CHINA: bool = True
    PLUGIN_PIP_INDEX_URL: str = 'https://mirrors.aliyun.com/pypi/simple/'
    PLUGIN_PIP_MAX_RETRY: int = 3
    PLUGIN_REDIS_PREFIX: str = 'agents_backend:plugin'

    # I18n 配置
    I18N_DEFAULT_LANGUAGE: str = 'en-US'   # zh-CN

    ##################################################
    # [ App ] task
    ##################################################
    # .env Redis
    CELERY_BROKER_REDIS_DATABASE: int

    # .env RabbitMQ
    # docker run -d --hostname agents-backend-mq --name agents-backend-mq  -p 5672:5672 -p 15672:15672 rabbitmq:latest
    CELERY_RABBITMQ_HOST: str
    CELERY_RABBITMQ_PORT: int
    CELERY_RABBITMQ_USERNAME: str
    CELERY_RABBITMQ_PASSWORD: str

    # 基础配置
    CELERY_BROKER: Literal['rabbitmq', 'redis'] = 'redis'
    CELERY_RABBITMQ_VHOST: str = ''
    CELERY_REDIS_PREFIX: str = 'agents_backend:celery'
    CELERY_TASK_MAX_RETRIES: int = 5

    ##################################################
    # [ Plugin ] code_generator
    ##################################################
    CODE_GENERATOR_DOWNLOAD_ZIP_FILENAME: str = 'agents_backend_generator'

    ##################################################
    # [ Plugin ] oauth2
    ##################################################
    # .env
    OAUTH2_GITHUB_CLIENT_ID: str
    OAUTH2_GITHUB_CLIENT_SECRET: str
    OAUTH2_GOOGLE_CLIENT_ID: str
    OAUTH2_GOOGLE_CLIENT_SECRET: str
    OAUTH2_LINUX_DO_CLIENT_ID: str
    OAUTH2_LINUX_DO_CLIENT_SECRET: str

    # 基础配置
    OAUTH2_STATE_REDIS_PREFIX: str = 'agents_backend:oauth2:state'
    OAUTH2_STATE_EXPIRE_SECONDS: int = 60 * 3  # 3 分钟
    OAUTH2_GITHUB_REDIRECT_URI: str = 'http://127.0.0.1:8000/api/v1/oauth2/github/callback'
    OAUTH2_GOOGLE_REDIRECT_URI: str = 'http://127.0.0.1:8000/api/v1/oauth2/google/callback'
    OAUTH2_LINUX_DO_REDIRECT_URI: str = 'http://127.0.0.1:8000/api/v1/oauth2/linux-do/callback'
    OAUTH2_FRONTEND_LOGIN_REDIRECT_URI: str = 'http://localhost:5173/oauth2/callback'
    OAUTH2_FRONTEND_BINDING_REDIRECT_URI: str = 'http://localhost:5173/profile'

    ##################################################
    # [ Plugin ] email
    ##################################################
    # .env
    EMAIL_USERNAME: str
    EMAIL_PASSWORD: str

    # 基础配置
    EMAIL_HOST: str = 'smtp.qq.com'
    EMAIL_PORT: int = 465
    EMAIL_SSL: bool = True
    EMAIL_CAPTCHA_REDIS_PREFIX: str = 'agents_backend:email:captcha'
    EMAIL_CAPTCHA_EXPIRE_SECONDS: int = 60 * 3  # 3 分钟

    ##################################################
    # [ Module ] Agent - LangChain/LangGraph AI Agents
    ##################################################
    
    # --------------------------------------------------------------------------
    # [LLM Provider Configuration]
    # Select provider: openai, anthropic, gemini, deepseek, groq, huggingface, ollama, openai_compat
    # --------------------------------------------------------------------------
    LLM_PROVIDER: Literal['openai', 'anthropic', 'gemini', 'deepseek', 'groq', 'huggingface', 'ollama', 'openai_compat'] = 'openai'
    
    # Common LLM Settings (applies to all providers)
    LLM_MAX_RETRIES: int = 3
    LLM_TOKEN_LIMIT: int = 200000
    LLM_TEMPERATURE: float = 0.7
    
    # Fallback/Supplementary LLM Configuration
    # These are used for middleware operations like summarization, model fallback, etc.
    # If not set, uses the primary LLM provider settings
    FALLBACK_LLM_PROVIDER: str = ''  # Leave empty to use primary provider
    FALLBACK_LLM_MODEL: str = ''  # Model to use for fallback/supplementary operations
    
    # --------------------------------------------------------------------------
    # OpenAI Configuration (provider: openai)
    # Package: langchain-openai
    # --------------------------------------------------------------------------
    OPENAI_API_KEY: str = ''
    OPENAI_MODEL: str = 'gpt-4o'
    OPENAI_BASE_URL: str = ''  # Optional: Custom base URL for proxies/emulators
    
    # --------------------------------------------------------------------------
    # Anthropic Configuration (provider: anthropic)
    # Package: langchain-anthropic
    # --------------------------------------------------------------------------
    ANTHROPIC_API_KEY: str = ''
    ANTHROPIC_MODEL: str = 'claude-sonnet-4-20250514'
    
    # --------------------------------------------------------------------------
    # Google Gemini Configuration (provider: gemini)
    # Package: langchain-google-genai
    # --------------------------------------------------------------------------
    GOOGLE_API_KEY: str = ''
    GEMINI_MODEL: str = 'gemini-2.0-flash'
    GOOGLE_CLOUD_PROJECT: str = ''  # Optional: For Vertex AI
    GOOGLE_GENAI_USE_VERTEXAI: bool = False  # Optional: Enable Vertex AI
    
    # --------------------------------------------------------------------------
    # DeepSeek Configuration (provider: deepseek)
    # Package: langchain-deepseek
    # --------------------------------------------------------------------------
    DEEPSEEK_API_KEY: str = ''
    DEEPSEEK_MODEL: str = 'deepseek-chat'
    
    # --------------------------------------------------------------------------
    # Groq Configuration (provider: groq)
    # Package: langchain-groq
    # --------------------------------------------------------------------------
    GROQ_API_KEY: str = ''
    GROQ_MODEL: str = 'llama-3.1-8b-instant'
    
    # --------------------------------------------------------------------------
    # HuggingFace Configuration (provider: huggingface)
    # Package: langchain-huggingface
    # --------------------------------------------------------------------------
    HUGGINGFACE_API_KEY: str = ''
    HUGGINGFACE_REPO_ID: str = 'microsoft/Phi-3-mini-4k-instruct'
    
    # --------------------------------------------------------------------------
    # Ollama Configuration (provider: ollama)
    # For running open-source models locally
    # Package: langchain-ollama
    # --------------------------------------------------------------------------
    OLLAMA_MODEL: str = 'llama3'
    OLLAMA_BASE_URL: str = 'http://localhost:11434'
    
    # --------------------------------------------------------------------------
    # OpenAI-Compatible API Configuration (provider: openai_compat)
    # For custom deployed models using OpenAI-compatible APIs
    # (e.g., vLLM, TGI, LocalAI, LMStudio, etc.)
    # Package: langchain-openai
    # --------------------------------------------------------------------------
    OPENAI_COMPAT_API_KEY: str = ''
    OPENAI_COMPAT_MODEL: str = ''
    OPENAI_COMPAT_BASE_URL: str = ''  # REQUIRED for this provider
    
    # --------------------------------------------------------------------------
    # Legacy/Fallback API Keys (backward compatibility)
    # --------------------------------------------------------------------------
    AZURE_OPENAI_API_KEY: str = ''
    AZURE_OPENAI_ENDPOINT: str = ''
    AZURE_OPENAI_API_VERSION: str = '2024-02-15-preview'
    TOGETHER_API_KEY: str = ''
    DASHSCOPE_API_KEY: str = ''  # Alibaba Cloud

    # Agent Workflow Configuration
    AGENT_RECURSION_LIMIT: int = 25
    AGENT_MAX_PLAN_ITERATIONS: int = 1
    AGENT_MAX_STEP_NUM: int = 3
    AGENT_MAX_SEARCH_RESULTS: int = 3
    AGENT_ENABLE_DEEP_THINKING: bool = False
    AGENT_ENABLE_CLARIFICATION: bool = False
    AGENT_MAX_CLARIFICATION_ROUNDS: int = 3
    AGENT_ENFORCE_WEB_SEARCH: bool = False
    AGENT_ENFORCE_RESEARCHER_SEARCH: bool = True

    # --------------------------------------------------------------------------
    # [Agent Middleware Configuration]
    # Production-ready middleware for robust agent operation
    # --------------------------------------------------------------------------
    
    # Summarization Middleware - compresses long conversations to fit context windows
    MIDDLEWARE_ENABLE_SUMMARIZATION: bool = True
    MIDDLEWARE_SUMMARIZATION_TRIGGER_TOKENS: int = 100000  # Token count to trigger summarization
    MIDDLEWARE_SUMMARIZATION_KEEP_MESSAGES: int = 10  # Number of recent messages to preserve
    
    # Model Retry Middleware - retries failed model calls with exponential backoff
    MIDDLEWARE_ENABLE_MODEL_RETRY: bool = True
    MIDDLEWARE_MODEL_MAX_RETRIES: int = 3
    MIDDLEWARE_MODEL_BACKOFF_FACTOR: float = 2.0
    MIDDLEWARE_MODEL_INITIAL_DELAY: float = 1.0
    
    # Tool Retry Middleware - retries failed tool calls with exponential backoff
    MIDDLEWARE_ENABLE_TOOL_RETRY: bool = True
    MIDDLEWARE_TOOL_MAX_RETRIES: int = 3
    MIDDLEWARE_TOOL_BACKOFF_FACTOR: float = 2.0
    MIDDLEWARE_TOOL_INITIAL_DELAY: float = 0.5
    
    # Model Call Limit Middleware - prevents runaway costs
    MIDDLEWARE_ENABLE_MODEL_CALL_LIMIT: bool = True
    MIDDLEWARE_MODEL_CALL_THREAD_LIMIT: int = 50  # Max model calls per thread
    MIDDLEWARE_MODEL_CALL_RUN_LIMIT: int = 25  # Max model calls per run
    
    # Tool Call Limit Middleware - prevents excessive tool usage
    MIDDLEWARE_ENABLE_TOOL_CALL_LIMIT: bool = True
    MIDDLEWARE_TOOL_CALL_THREAD_LIMIT: int = 100  # Max tool calls per thread
    MIDDLEWARE_TOOL_CALL_RUN_LIMIT: int = 50  # Max tool calls per run
    
    # Model Fallback Middleware - automatically fallback to alternative models when primary fails
    MIDDLEWARE_ENABLE_MODEL_FALLBACK: bool = True
    # Comma-separated list of fallback model identifiers (e.g., "gpt-4o-mini,claude-3-5-sonnet")
    # Uses provider:model format or just model name for same provider as primary
    MIDDLEWARE_FALLBACK_MODELS: str = ''


    # Tool Interrupts (Human-in-the-loop)
    TOOL_INTERRUPTS_BEFORE: list[str] = []

    # --------------------------------------------------------------------------
    # [Robust Search & Crawler Configuration]
    # Crawler Engine
    CRAWLER_ENGINE: str = 'jina'  # 'jina', 'infoquest'
    CRAWLER_FETCH_TIME: int = 10
    CRAWLER_TIMEOUT: int = 30
    CRAWLER_NAVI_TIMEOUT: int = 15

    # Detailed Search Configuration
    SEARCH_ENGINE_INCLUDE_DOMAINS: list[str] = []
    SEARCH_ENGINE_EXCLUDE_DOMAINS: list[str] = []
    SEARCH_ENGINE_INCLUDE_ANSWER: bool = False
    SEARCH_ENGINE_SEARCH_DEPTH: Literal['basic', 'advanced'] = 'advanced'
    SEARCH_ENGINE_INCLUDE_RAW_CONTENT: bool = True
    SEARCH_ENGINE_INCLUDE_IMAGES: bool = True
    SEARCH_ENGINE_INCLUDE_IMAGE_DESCRIPTIONS: bool = True
    SEARCH_ENGINE_MIN_SCORE_THRESHOLD: float = 0.0
    SEARCH_ENGINE_MAX_CONTENT_LENGTH: int = 4000
    # InfoQuest specific
    SEARCH_ENGINE_TIME_RANGE: int = 30  # Days
    SEARCH_ENGINE_SITE: str = ''
    
    # Production Hardening
    AGENT_SKIP_DB_SETUP: bool = False  # Skip auto-creation of tables (use Alembic in prod)

    # LangGraph Checkpointer (conversation state persistence)
    # Enables PostgreSQL-backed checkpointing for agent graph state
    # This allows resuming conversations and provides fault tolerance
    LANGGRAPH_CHECKPOINT_ENABLED: bool = False
    LANGGRAPH_CHECKPOINT_DB_URL: str = ''  # e.g., postgresql://user:pass@localhost/db
    
    # Connection pool settings for LangGraph checkpointer
    # These control the shared async connection pool used across all agent requests
    LANGGRAPH_CHECKPOINT_POOL_MIN: int = 2   # Minimum pool connections
    LANGGRAPH_CHECKPOINT_POOL_MAX: int = 10  # Maximum pool connections
    LANGGRAPH_CHECKPOINT_POOL_TIMEOUT: int = 60  # Connection acquisition timeout (seconds)
    
    # Legacy: Message stream saving (separate from graph checkpointing)
    LANGGRAPH_CHECKPOINT_SAVER: bool = False  # Enable SSE message persistence

    # MCP (Model Context Protocol) Configuration
    AGENT_MCP_ENABLED: bool = False
    AGENT_MCP_TIMEOUT_SECONDS: int = 300

    # RAG (Retrieval Augmented Generation) Configuration
    AGENT_RAG_PROVIDER: str = ''  # 'milvus', 'qdrant', or empty

    # Milvus Vector DB
    MILVUS_HOST: str = 'localhost'
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = 'agent_documents'

    # Qdrant Vector DB
    QDRANT_HOST: str = 'localhost'
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = 'agent_documents'
    QDRANT_API_KEY: str = ''

    # Web Search Configuration
    AGENT_SEARCH_ENGINE: str = 'tavily'  # 'tavily', 'duckduckgo', 'brave', 'bing', 'infoquest', 'searx', 'arxiv'
    TAVILY_API_KEY: str = ''
    INFOQUEST_API_KEY: str = ''
    BRAVE_SEARCH_API_KEY: str = ''
    BING_SEARCH_API_KEY: str = ''
    SEARX_HOST: str = ''
    JINA_API_KEY: str = ''
    EXA_API_KEY: str = ''  # For People Search tool (Exa.ai)
    SEMANTIC_SCHOLAR_API_KEY: str = ''  # For Paper Search tool (Semantic Scholar)
    NCBI_API_KEY: str = ''  # For Paper Search tool (NCBI)

    # --------------------------------------------------------------------------
    # [Expanded RAG Configuration]
    # Providers: 'milvus', 'qdrant', 'vikingdb', 'ragflow', 'dify', 'moi'
    
    # VikingDB
    VIKINGDB_KNOWLEDGE_BASE_API_URL: str = ''
    VIKINGDB_KNOWLEDGE_BASE_API_AK: str = ''
    VIKINGDB_KNOWLEDGE_BASE_API_SK: str = ''
    VIKINGDB_KNOWLEDGE_BASE_RETRIEVAL_SIZE: int = 15

    # RagFlow
    RAGFLOW_API_URL: str = 'http://localhost:9388'
    RAGFLOW_API_KEY: str = ''
    RAGFLOW_RETRIEVAL_SIZE: int = 10
    RAGFLOW_CROSS_LANGUAGES: list[str] = []

    # Dify
    DIFY_API_URL: str = 'https://api.dify.ai/v1'
    DIFY_API_KEY: str = ''

    # MOI (MatrixOne)
    MOI_API_URL: str = ''
    MOI_API_KEY: str = ''
    MOI_RETRIEVAL_SIZE: int = 10
    MOI_LIST_LIMIT: int = 10
    
    # Vector DB Embeddings (Common)
    EMBEDDING_PROVIDER: str = 'openai'  # openai, dashscope
    EMBEDDING_BASE_URL: str = ''
    EMBEDDING_MODEL: str = 'text-embedding-ada-002'
    EMBEDDING_API_KEY: str = ''
    AUTO_LOAD_EXAMPLES: bool = True

    # TTS (Text-to-Speech) Configuration
    VOLCENGINE_TTS_APPID: str = ''
    VOLCENGINE_TTS_ACCESS_TOKEN: str = ''
    VOLCENGINE_TTS_CLUSTER: str = 'volcano_tts'
    VOLCENGINE_TTS_VOICE_TYPE: str = 'BV700_V2_streaming'

    # Agent API CORS (additional origins for agent frontend)
    AGENT_ALLOWED_ORIGINS: str = 'http://localhost:3000'

    # Agent Report Styles
    AGENT_DEFAULT_REPORT_STYLE: str = 'ACADEMIC'  # ACADEMIC, POPULAR_SCIENCE, NEWS, SOCIAL_MEDIA, STRATEGIC_INVESTMENT

    # --------------------------------------------------------------------------
    # [Evaluation Configuration]
    # --------------------------------------------------------------------------
    EVALUATION_SLEEP_TIME: int = 10

    # Langfuse
    LANGFUSE_PUBLIC_KEY: str = ''
    LANGFUSE_SECRET_KEY: str = ''

    # --------------------------------------------------------------------------
    # [Sandbox Configuration]
    # --------------------------------------------------------------------------
    # Sandbox provider: 'e2b' or 'daytona'
    SANDBOX_PROVIDER: str = 'e2b'
    
    # E2B Configuration
    E2B_API_KEY: str = ''
    E2B_TEMPLATE_ID: str = 'base'
    
    # Daytona Configuration  
    DAYTONA_API_KEY: str = ''
    DAYTONA_SERVER_URL: str = 'https://app.daytona.io/api'
    DAYTONA_TARGET: str = 'us'
    
    # Sandbox Service Ports (inside sandbox container)
    SANDBOX_MCP_SERVER_PORT: int = 6060  # MCP tool server port
    SANDBOX_CODE_SERVER_PORT: int = 9000  # Code-Server (VS Code) port

    # --------------------------------------------------------------------------
    # [File Processing Configuration]
    # Staged file upload and processing for chat attachments
    # --------------------------------------------------------------------------
    
    # Storage Backend: 'local' for filesystem, 's3' for S3-compatible storage
    FILE_STORAGE_BACKEND: str = 'local'
    
    # Local Storage Configuration
    FILE_STORAGE_LOCAL_PATH: str = './uploads/staged-files'
    FILE_STORAGE_LOCAL_BASE_URL: str = ''  # Optional: Base URL for serving files
    
    # S3 Storage Configuration (for FILE_STORAGE_BACKEND='s3')
    FILE_STORAGE_S3_BUCKET: str = 'staged-files'
    FILE_STORAGE_S3_ENDPOINT_URL: str = ''  # For MinIO, Wasabi, etc.
    FILE_STORAGE_S3_REGION: str = 'us-east-1'
    FILE_STORAGE_S3_ACCESS_KEY: str = ''
    FILE_STORAGE_S3_SECRET_KEY: str = ''
    FILE_STORAGE_S3_PUBLIC_URL_BASE: str = ''  # Optional: Public URL for files
    
    # File Size Limits
    FILE_MAX_SIZE_MB: int = 50  # Maximum file size in MB
    FILE_MAX_PARSED_CONTENT_LENGTH: int = 100000  # Max chars stored in DB
    
    # Staged File Expiration
    FILE_STAGED_EXPIRY_HOURS: int = 24  # Hours until staged files expire
    FILE_SIGNED_URL_EXPIRY_SECONDS: int = 3600  # 1 hour
    
    # Image Processing
    FILE_IMAGE_MAX_WIDTH: int = 2048
    FILE_IMAGE_MAX_HEIGHT: int = 2048
    FILE_IMAGE_JPEG_QUALITY: int = 85
    
    # Document Parsing Limits
    FILE_PARSE_MAX_PDF_PAGES: int = 500
    FILE_PARSE_MAX_EXCEL_ROWS: int = 100000
    FILE_PARSE_MAX_TEXT_CHARS: int = 10000000  # 10M chars

    # LangGraph Checkpoint
    LANGGRAPH_CHECKPOINT_ENABLED: bool = True
    LANGGRAPH_CHECKPOINT_DB_URL: str | None = None
    LANGGRAPH_CHECKPOINT_POOL_MIN: int = 2
    LANGGRAPH_CHECKPOINT_POOL_MAX: int = 10
    LANGGRAPH_CHECKPOINT_POOL_TIMEOUT: int = 60

    # --------------------------------------------------------------------------
    # [Billing & Stripe Configuration]
    # Payment processing, subscriptions, and credit management
    # --------------------------------------------------------------------------
    
    # Stripe API Keys
    STRIPE_SECRET_KEY: str = ''  # Stripe secret key (sk_...)
    STRIPE_PUBLISHABLE_KEY: str = ''  # Stripe publishable key (pk_...)
    STRIPE_WEBHOOK_SECRET: str = ''  # Webhook signing secret (whsec_...)
    
    # Free Tier Price ID
    STRIPE_FREE_TIER_ID: str = ''  # $0/month subscription price ID
    
    # Subscription Tier Price IDs - Monthly
    STRIPE_TIER_2_20_ID: str = ''  # Plus tier ~$20/month
    STRIPE_TIER_6_50_ID: str = ''  # Pro tier ~$50/month
    STRIPE_TIER_25_200_ID: str = ''  # Ultra tier ~$200/month
    
    # Subscription Tier Price IDs - Yearly
    STRIPE_TIER_2_20_YEARLY_ID: str = ''  # Plus tier yearly
    STRIPE_TIER_6_50_YEARLY_ID: str = ''  # Pro tier yearly
    STRIPE_TIER_25_200_YEARLY_ID: str = ''  # Ultra tier yearly
    
    # Yearly Commitment Price IDs (discounted, locked for 12 months)
    STRIPE_TIER_2_17_YEARLY_COMMITMENT_ID: str = ''  # Plus yearly commitment
    STRIPE_TIER_6_42_YEARLY_COMMITMENT_ID: str = ''  # Pro yearly commitment
    STRIPE_TIER_25_170_YEARLY_COMMITMENT_ID: str = ''  # Ultra yearly commitment
    
    # Credit Purchase Price IDs (one-time payments)
    STRIPE_CREDITS_10_PRICE_ID: str = ''  # $10 credits
    STRIPE_CREDITS_25_PRICE_ID: str = ''  # $25 credits
    STRIPE_CREDITS_50_PRICE_ID: str = ''  # $50 credits
    STRIPE_CREDITS_100_PRICE_ID: str = ''  # $100 credits
    STRIPE_CREDITS_250_PRICE_ID: str = ''  # $250 credits
    STRIPE_CREDITS_500_PRICE_ID: str = ''  # $500 credits
    
    # Billing Feature Flags
    BILLING_ENABLED: bool = False  # Enable/disable billing features
    BILLING_TRIAL_ENABLED: bool = False  # Enable free trials
    BILLING_TRIAL_DURATION_DAYS: int = 7  # Trial duration
    BILLING_FREE_TIER_AUTO_ENROLL: bool = True  # Auto-enroll new users to free tier

    @model_validator(mode='before')
    @classmethod
    def check_env(cls, values: Any) -> Any:
        """检查环境变量"""
        if values.get('ENVIRONMENT') == 'prod':
            # FastAPI
            values['FASTAPI_OPENAPI_URL'] = None
            values['FASTAPI_STATIC_FILES'] = False

            # task
            values['CELERY_BROKER'] = 'rabbitmq'

        # Auto-configure LangGraph Checkpoint DB URL from main DB if not set
        if not values.get('LANGGRAPH_CHECKPOINT_DB_URL') and values.get('DATABASE_TYPE') == 'postgresql':
            user = values.get('DATABASE_USER')
            password = values.get('DATABASE_PASSWORD')
            host = values.get('DATABASE_HOST')
            port = values.get('DATABASE_PORT')
            db = values.get('DATABASE_SCHEMA')
            if all([user, password, host, port, db]):
                values['LANGGRAPH_CHECKPOINT_DB_URL'] = f"postgresql://{user}:{password}@{host}:{port}/{db}"

        return values


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()


# 创建全局配置实例
settings = get_settings()
