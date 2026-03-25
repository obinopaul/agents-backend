export enum TAB {
    CODE = 'code',
    TERMINAL = 'terminal',
    RESULT = 'result',
    BUILD = 'build'
}

export enum VIEW_MODE {
    CHAT = 'chat',
    DESIGN = 'design'
}

export enum QUESTION_MODE {
    AGENT = 'agent',
    CHAT = 'chat'
}

export const AVAILABLE_MODELS = [
    'claude-sonnet-4@20250514',
    'claude-opus-4@20250514',
    'claude-3-7-sonnet@20250219',
    'gemini-2.5-pro-preview-05-06',
    'gpt-4.1'
]

export enum WebSocketConnectionState {
    CONNECTING = 'connecting',
    CONNECTED = 'connected',
    DISCONNECTED = 'disconnected'
}

export type Source = {
    title: string
    url: string
}

export enum AgentEvent {
    AGENT_INITIALIZED = 'agent_initialized',
    USER_MESSAGE = 'user_message',
    CONNECTION_ESTABLISHED = 'connection_established',
    WORKSPACE_INFO = 'workspace_info',
    PROCESSING = 'processing',
    AGENT_THINKING = 'agent_thinking',
    TOOL_CALL = 'tool_call',
    TOOL_RESULT = 'tool_result',
    AGENT_RESPONSE = 'agent_response',
    COMPLETE = 'complete',
    ERROR = 'error',
    SYSTEM = 'system',
    PONG = 'pong',
    UPLOAD_SUCCESS = 'upload_success',
    BROWSER_USE = 'browser_use',
    FILE_EDIT = 'file_edit',
    PROMPT_GENERATED = 'prompt_generated',
    AGENT_RESPONSE_INTERRUPTED = 'agent_response_interrupted',
    STATUS_UPDATE = 'status_update',
    SANDBOX_STATUS = 'sandbox_status',
    SUB_AGENT_COMPLETE = 'sub_agent_complete',
    TOOL_PROGRESS = 'tool_progress',
    MODEL_COMPACT = 'model_compact',
    SESSION_UPDATED = 'session_updated'
}

export enum TOOL {
    // =========================================================================
    // Core Agent Tools
    // =========================================================================
    SEQUENTIAL_THINKING = 'sequential_thinking',
    MESSAGE_USER = 'message_user',
    RETURN_CONTROL_TO_USER = 'return_control_to_user',
    COMPLETE = 'complete',

    // =========================================================================
    // Browser Use
    // =========================================================================
    BROWSER_USE = 'browser_use',
    PRESENTATION = 'presentation',

    // =========================================================================
    // Web Tools
    // =========================================================================
    WEB_SEARCH = 'web_search',
    WEB_BATCH_SEARCH = 'web_batch_search',
    IMAGE_SEARCH = 'image_search',
    VISIT = 'web_visit',
    VISIT_COMPRESS = 'web_visit_compress',
    TAVILY_SEARCH = 'tavily_search_results_json',

    // =========================================================================
    // Shell Tools
    // =========================================================================
    SHELL_EXEC = 'shell_exec',
    SHELL_KILL_PROCESS = 'shell_kill_process',
    SHELL_VIEW = 'shell_view',
    SHELL_WRITE_TO_PROCESS = 'shell_write_to_process',
    SHELL_WAIT = 'shell_wait',

    // =========================================================================
    // Dev & Deployment Tools
    // =========================================================================
    FULLSTACK_PROJECT_INIT = 'fullstack_project_init',
    SAVE_CHECKPOINT = 'save_checkpoint',
    STATIC_DEPLOY = 'static_deploy',
    REGISTER_DEPLOYMENT = 'register_deployment',
    REGISTER_PORT = 'register_port',
    GET_DATABASE_CONNECTION = 'get_database_connection',
    GET_OPENAI_KEY = 'get_openai_api_key',

    // =========================================================================
    // Media Tools
    // =========================================================================
    PDF_TEXT_EXTRACT = 'pdf_text_extract',
    AUDIO_TRANSCRIBE = 'audio_transcribe',
    GENERATE_AUDIO_RESPONSE = 'generate_audio_response',
    VIDEO_GENERATE = 'generate_video',
    LONG_VIDEO_GENERATE = 'generate_long_video_from_text',
    LONG_VIDEO_GENERATE_FROM_IMAGE = 'generate_long_video_from_image',
    IMAGE_GENERATE = 'generate_image',
    DISPLAY_IMAGE = 'display_image',
    LIST_HTML_LINKS = 'list_html_links',
    READ_REMOTE_IMAGE = 'read_remote_image',

    // =========================================================================
    // Research & Agent Tools
    // =========================================================================
    DEEP_RESEARCH = 'deep_research',
    REVIEWER_AGENT = 'reviewer_agent',
    SUB_AGENT = 'sub_agent',
    SUB_AGENT_RESEARCHER = 'sub_agent_researcher',
    DESIGN_DOCUMENT_AGENT = 'design_document_agent',
    CODEX_AGENT = 'codex_agent',
    CODEX_DELEGATE = 'codex_delegate',
    BROWSER_SUBAGENT = 'browser_subagent',
    REQUEST_HUMAN_INPUT = 'request_human_input',

    // =========================================================================
    // Slide Tools
    // =========================================================================
    SLIDE_DECK_INIT = 'slide_deck_init',
    SLIDE_DECK_COMPLETE = 'slide_deck_complete',
    SLIDE_WRITE = 'SlideWrite',
    SLIDE_EDIT = 'SlideEdit',
    SLIDE_APPLY_PATCH = 'slide_apply_patch',
    SLIDE_TEMPLATE_INIT = 'slide_template_init',

    // =========================================================================
    // Browser Tools - synced with SELECTED_TOOLS in playwright.py
    // =========================================================================
    BROWSER_CLICK = 'browser_click',
    BROWSER_CLOSE = 'browser_close',
    BROWSER_CONSOLE_MESSAGES = 'browser_console_messages',
    BROWSER_DRAG = 'browser_drag',
    BROWSER_EVALUATE = 'browser_evaluate',
    BROWSER_HANDLE_DIALOG = 'browser_handle_dialog',
    BROWSER_HOVER = 'browser_hover',
    BROWSER_NAVIGATE = 'browser_navigate',
    BROWSER_NETWORK_REQUESTS = 'browser_network_requests',
    BROWSER_PRESS_KEY = 'browser_press_key',
    BROWSER_SELECT_OPTION = 'browser_select_option',
    BROWSER_SNAPSHOT = 'browser_snapshot',
    BROWSER_TAKE_SCREENSHOT = 'browser_take_screenshot',
    BROWSER_TYPE = 'browser_type',
    BROWSER_WAIT_FOR = 'browser_wait_for',
    BROWSER_TAB_CLOSE = 'browser_tab_close',
    BROWSER_TAB_LIST = 'browser_tab_list',
    BROWSER_TAB_NEW = 'browser_tab_new',
    BROWSER_TAB_SELECT = 'browser_tab_select',
    BROWSER_MOUSE_CLICK_XY = 'browser_mouse_click_xy',
    BROWSER_MOUSE_DRAG_XY = 'browser_mouse_drag_xy',
    BROWSER_MOUSE_MOVE_XY = 'browser_mouse_move_xy',
    BROWSER_NAVIGATION = 'browser_navigation',
    BROWSER_WAIT = 'browser_wait',
    BROWSER_VIEW_INTERACTIVE_ELEMENTS = 'browser_view_interactive_elements',
    BROWSER_SCROLL_DOWN = 'browser_scroll_down',
    BROWSER_SCROLL_UP = 'browser_scroll_up',
    BROWSER_SWITCH_TAB = 'browser_switch_tab',
    BROWSER_OPEN_NEW_TAB = 'browser_open_new_tab',
    BROWSER_GET_SELECT_OPTIONS = 'browser_get_select_options',
    BROWSER_SELECT_DROPDOWN_OPTION = 'browser_select_dropdown_option',
    BROWSER_RESTART = 'browser_restart',
    BROWSER_ENTER_TEXT = 'browser_enter_text',
    BROWSER_ENTER_MULTI_TEXTS = 'browser_enter_multi_texts',

    // =========================================================================
    // Todo/Productivity Tools (PascalCase values)
    // =========================================================================
    TODO_WRITE = 'TodoWrite',
    TODO_READ = 'TodoRead',

    // =========================================================================
    // File System Tools (PascalCase values)
    // =========================================================================
    READ = 'Read',
    WRITE = 'Write',
    EDIT = 'Edit',
    LS = 'LS',
    GLOB = 'Glob',
    GREP = 'ASTGrep',
    MULTI_EDIT = 'MultiEdit',
    APPLY_PATCH = 'apply_patch',
    STR_REPLACE_BASED_EDIT = 'str_replace_based_edit_tool',
    LSP = 'lsp',

    // =========================================================================
    // Bash Tools (PascalCase values)
    // =========================================================================
    BASH = 'Bash',
    BASH_INIT = 'BashInit',
    BASH_VIEW = 'BashView',
    BASH_STOP = 'BashStop',
    BASH_KILL = 'BashKill',
    BASH_LIST = 'BashList',
    BASH_WRITE_TO_PROCESS = 'BashWriteToProcess',

    // =========================================================================
    // Task Tool (PascalCase value)
    // =========================================================================
    TASK = 'Task',

    // =========================================================================
    // MCP & Codex Tools
    // =========================================================================
    MCP_TOOL = 'mcp_tool',
    CODEX_EXECUTE = 'codex_execute',
    CODEX_REVIEW = 'codex_review',
    MCP_CODEX_EXECUTE = 'mcp_codex_execute',
    MCP_CODEX_REVIEW = 'mcp_codex_review',
    MCP_CODEX_READ = 'mcp_codex_read',
    MCP_CODEX_WRITE = 'mcp_codex_write',
    CODEX_MCP_CODEX_EXECUTE = 'mcp_codex-as-mcp_codex_execute',
    CODEX_MCP_CODEX_REVIEW = 'mcp_codex-as-mcp_codex_review',
    CLAUDE_CODE = 'mcp_claude_code',
    MCP_FILESYSTEM_READ = 'mcp_filesystem_read',
    MCP_FILESYSTEM_WRITE = 'mcp_filesystem_write',
    MCP_BROWSER_NAVIGATE = 'mcp_browser_navigate',
    MCP_BROWSER_CLICK = 'mcp_browser_click',
    MCP_BROWSER_TYPE = 'mcp_browser_type',
    MCP_BROWSER_SCREENSHOT = 'mcp_browser_screenshot',

    // =========================================================================
    // Document Tools
    // =========================================================================
    DOCUMENT_TEMPLATE_INIT = 'document_template_init',
    DOCUMENT_COMPILE = 'document_compile',
    LATEX_COMPILE = 'latex_compile',

    // =========================================================================
    // Design Tools (Draw.io)
    // =========================================================================
    DESIGN_INIT = 'design_init',
    DESIGN_CREATE = 'design_create',
    DESIGN_EDIT = 'design_edit',
    DESIGN_GET = 'design_get',
    DESIGN_EXPORT = 'design_export',

    // =========================================================================
    // Excalidraw Tools
    // =========================================================================
    EXCALIDRAW_INIT = 'excalidraw_init',
    EXCALIDRAW_CREATE = 'excalidraw_create',
    EXCALIDRAW_UPDATE = 'excalidraw_update',
    EXCALIDRAW_DELETE = 'excalidraw_delete',
    EXCALIDRAW_QUERY = 'excalidraw_query',
    EXCALIDRAW_BATCH_CREATE = 'excalidraw_batch_create',
    EXCALIDRAW_GROUP = 'excalidraw_group',
    EXCALIDRAW_UNGROUP = 'excalidraw_ungroup',
    EXCALIDRAW_ALIGN = 'excalidraw_align',
    EXCALIDRAW_DISTRIBUTE = 'excalidraw_distribute',
    EXCALIDRAW_LOCK = 'excalidraw_lock',
    EXCALIDRAW_UNLOCK = 'excalidraw_unlock',
    EXCALIDRAW_RESOURCE = 'excalidraw_resource',

    // =========================================================================
    // Academic/Research Tools
    // =========================================================================
    PAPER_SEARCH = 'paper_search',
    GET_PAPER_DETAILS = 'get_paper_details',
    SEARCH_AUTHORS = 'search_authors',
    GET_AUTHOR_DETAILS = 'get_author_details',
    GET_AUTHOR_PAPERS = 'get_author_papers',
    SEMANTIC_SCHOLAR_SEARCH = 'semantic_scholar_search',
    ARXIV_SEARCH = 'arxiv_search',
    ARXIV_SEARCH_TOOL = 'arxiv_search_tool',
    PUBMED_CENTRAL = 'pubmed_central',
    PUBMED_SEARCH = 'pubmed_search',
    GOOGLE_SCHOLAR = 'google_scholar',
    SEMANTIC_SCHOLAR = 'semantic_scholar',

    // =========================================================================
    // People & Company Search Tools
    // =========================================================================
    PEOPLE_SEARCH = 'people_search',
    COMPANY_SEARCH = 'company_search',
    MCP_SEARCH = 'mcp_search',

    // =========================================================================
    // Crawl & Retrieval Tools
    // =========================================================================
    CRAWL = 'crawl',
    RETRIEVER = 'retriever',
    HUMAN_FEEDBACK = 'human_feedback',

    // =========================================================================
    // TTS & Voice Tools
    // =========================================================================
    TTS = 'tts',
    VOLCENGINE_TTS = 'volcengine_tts',
    VAPI_VOICE = 'vapi_voice',

    // =========================================================================
    // Vision Tools
    // =========================================================================
    VIEW_IMAGE = 'view_image',
    REALITY_DEFENDER = 'reality_defender',

    // =========================================================================
    // Memory & Summarization Tools
    // =========================================================================
    AGENT_MEMORY = 'agent_memory',
    SUMMARIZATION = 'summarization',
    BACKGROUND_INVESTIGATION = 'background_investigation',

    // =========================================================================
    // Code Execution Tools
    // =========================================================================
    PYTHON_EXECUTE = 'python_execute',
    JAVASCRIPT_EXECUTE = 'javascript_execute',
    CODE_EXECUTE = 'code_execute',

    // =========================================================================
    // Data Tools
    // =========================================================================
    SQL_QUERY = 'sql_query',
    DATAFRAME_OPERATION = 'dataframe_operation',
    PLOT_CHART = 'plot_chart',
    EXPORT_DATA = 'export_data',
    SPREADSHEET = 'spreadsheet',
    UPLOAD_FILE = 'upload_file',

    // =========================================================================
    // Background Middleware Tools
    // =========================================================================
    BACKGROUND_TASK = 'background_task',
    WAIT_FOR_SUBAGENTS = 'wait_for_subagents',
    TASK_PROGRESS = 'task_progress',

    // =========================================================================
    // Persistent Task Middleware Tools
    // =========================================================================
    VIEW_TASKS = 'view_tasks',
    CREATE_TASKS = 'create_tasks',
    UPDATE_TASKS = 'update_tasks',
    DELETE_TASKS = 'delete_tasks',
    CLEAR_ALL_TASKS = 'clear_all_tasks',

    // =========================================================================
    // Sandbox Tools
    // =========================================================================
    SB_SPREADSHEET = 'sb_spreadsheet',
    SB_UPLOAD_FILE = 'sb_upload_file'
}

export type Plan = {
    id: string
    content: string
    status: 'pending' | 'in_progress' | 'completed'
}

export interface FileURLContent {
    type: 'file_url'
    url: string
    mime_type: string
    name: string
    size: number
}

export interface AgentContext {
    agentId: string
    agentType: 'main' | 'subagent'
    agentName?: string
    parentAgentId?: string
    nestingLevel: number
    startTime?: number
    endTime?: number
    status?: 'running' | 'completed' | 'failed'
}

export type ActionStep = {
    type: TOOL
    data: {
        isResult?: boolean
        tool_call_id?: string
        tool_name?: string
        tool_display_name?: string
        agentContext?: AgentContext
        tool_input?: {
            description?: string
            action?: string
            text?: string
            thought?: string
            path?: string
            file_text?: string
            file_path?: string
            command?: string
            url?: string
            query?: string
            queries?: string[]
            file?: string
            instruction?: string
            output_filename?: string
            output_path?: string
            key?: string
            session_id?: string
            seconds?: number
            input?: string
            enter?: boolean
            framework?: string
            project_name?: string
            database_type?: string
            old_string?: string
            new_string?: string
            old_str?: string
            new_str?: string
            project_directory?: string
            commit_message?: string
            todos?: Plan[]
            session_names?: string[]
            session_name?: string
            press_enter?: boolean
            content?: string
            pattern?: string
            include?: string
            name?: string
            tool_name?: string
            prompt?: string
            port?: number
            element?: string
            x?: number
            y?: number
            filename?: string
            presentation_name?: string
            slide_number?: number
            enter_texts?: Array<{
                text: string
                coordinate_x: number
                coordinate_y: number
                press_enter?: boolean
            }>
            coordinate_x_start?: number
            coordinate_y_start?: number
            coordinate_x_end?: number
            coordinate_y_end?: number
            urls?: string[]
            changes?: Record<
                string,
                {
                    add: {
                        content: string
                    }
                    delete: {
                        content: string
                    }
                    update: {
                        unified_diff: string
                    }
                }
            >
        }
        result?:
            | string
            | Record<string, unknown>
            | Record<string, unknown>[]
            | FileURLContent
        query?: string
        content?: string
        path?: string
    }
}

export interface Message {
    id: string
    role: 'user' | 'assistant' | 'system'
    content?: string
    timestamp: number
    action?: ActionStep
    files?: Array<{
        id: string
        file_name: string
        file_size: number
        content_type: string
        created_at: string
    }>
    fileContents?: { [filename: string]: string } // Base64 content of files
    attachments?: Array<AttachmentMeta>
    isHidden?: boolean
    isThinkMessage?: boolean
    agentContext?: AgentContext
    subagentMessages?: Message[] // For grouping subagent messages
}

export type AttachmentType = 'code' | 'xlsx' | 'documents' | 'archive'

export interface AttachmentMeta {
    name: string
    url: string
    file_type: AttachmentType
}

export interface ISession {
    id: string
    workspace_dir: string
    created_at: string
    name: string
    agent_type: string
    is_public?: boolean
}

export interface IEvent {
    id: string
    type: AgentEvent
    content: Record<string, unknown>
    timestamp: string
    workspace_dir: string
}

export interface ToolSettings {
    deep_research: boolean
    pdf: boolean
    media_generation: boolean
    audio_generation: boolean
    browser: boolean
    thinking_tokens: number
    enable_reviewer: boolean
    design_document: boolean
    codex_tools: boolean
    claude_code: boolean
}
export interface ChatToolSettings {
    web_search: boolean
    web_visit: boolean
    image_search: boolean
    code_interpreter: boolean
}
export interface GooglePickerResponse {
    action: string
    docs?: Array<GoogleDocument>
}

export interface GoogleDocument {
    id: string
    name: string
    thumbnailUrl: string
    mimeType: string
}

export interface LLMConfig {
    api_key?: string
    model?: string
    base_url?: string
    max_retries?: string
    temperature?: string
    vertex_region?: string
    vertex_project_id?: string
    api_type?: string
    cot_model?: boolean
    azure_endpoint?: string
    azure_api_version?: string
}

export interface ISetting {
    llm_configs?: {
        [provider: string]: LLMConfig
    }
    search_config?: {
        firecrawl_api_key?: string
        firecrawl_base_url?: string
        serpapi_api_key?: string
        tavily_api_key?: string
        jina_api_key?: string
    }
    media_config?: {
        gcp_project_id?: string
        gcp_location?: string
        gcs_output_bucket?: string
        google_ai_studio_api_key?: string
    }
    audio_config?: {
        openai_api_key: string
        azure_endpoint: string
        azure_api_version: string
    }
    third_party_integration_config?: {
        neon_db_api_key: string
        openai_api_key: string
        vercel_api_key: string
    }
    sandbox_config?: {
        mode: string
        template_id: string
        sandbox_api_key: string
    }
}

export enum BUILD_STEP {
    THINKING = 'thinking',
    PLAN = 'plan',
    BUILD = 'build'
}

export interface IMCPTool {
    name: string
    author: string
    description: string
    logo: string
    url: string
    config: Record<string, unknown>
    isRequireKey?: boolean
}

export enum AGENT_TYPE {
    GENERAL = 'general',
    MEDIA = 'media',
    SLIDE = 'slide',
    WEBSITE_BUILD = 'website_build',
    CODEX = 'codex',
    CLAUDE_CODE = 'claude_code',
    EXCALIDRAW = 'excalidraw',
    DESIGN = 'design',
    DEV = 'dev',
    DATA_SCIENTIST = 'data_scientist',
    QUANT = 'quant',
    DEEP_RESEARCH = 'deep_research'
}

export interface PresentationListResponse {
    session_id?: string
    presentations?: {
        name?: string
        slide_count?: number
        last_updated?: string
        slides?: {
            id: string
            presentation_name?: string
            slide_number?: number
            slide_title?: string
            slide_content?: string
            session_id?: string
            metadata?: Record<string, unknown>
            created_at?: string
            updated_at?: string
        }[]
    }[]
    total?: number
}

export interface UpdateSlideRequest {
    session_id: string
    presentation_name: string
    slide_number: number
    content: string
    title: string
    description?: string
}

export interface UpdateSlideResponse {
    success: boolean
    error?: string
    error_code?: string
}
