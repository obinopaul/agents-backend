import { createSelector, createSlice, PayloadAction } from '@reduxjs/toolkit'
import { TOOL } from '@/typings/agent'

// ─── Tool Category Mapping ──────────────────────────────────────────────────
// Maps TOOL enum values to high-level categories for the Signal Rail stats.
// Categories match the design spec: read, write, bash, browse, generate, search, deploy, agent, other

type ToolCategory = 'read' | 'write' | 'bash' | 'browse' | 'generate' | 'search' | 'deploy' | 'agent' | 'other'

const TOOL_CATEGORY_MAP: Partial<Record<TOOL, ToolCategory>> = {
    // Read
    [TOOL.READ]: 'read',
    [TOOL.GLOB]: 'read',
    [TOOL.LS]: 'read',
    [TOOL.GREP]: 'read',
    [TOOL.LSP]: 'read',
    [TOOL.PDF_TEXT_EXTRACT]: 'read',
    [TOOL.VIEW_IMAGE]: 'read',
    [TOOL.READ_REMOTE_IMAGE]: 'read',
    [TOOL.MCP_FILESYSTEM_READ]: 'read',
    [TOOL.MCP_CODEX_READ]: 'read',
    [TOOL.TODO_READ]: 'read',

    // Write
    [TOOL.WRITE]: 'write',
    [TOOL.EDIT]: 'write',
    [TOOL.MULTI_EDIT]: 'write',
    [TOOL.APPLY_PATCH]: 'write',
    [TOOL.STR_REPLACE_BASED_EDIT]: 'write',
    [TOOL.MCP_FILESYSTEM_WRITE]: 'write',
    [TOOL.MCP_CODEX_WRITE]: 'write',
    [TOOL.TODO_WRITE]: 'write',
    [TOOL.SLIDE_WRITE]: 'write',
    [TOOL.SLIDE_EDIT]: 'write',
    [TOOL.SLIDE_APPLY_PATCH]: 'write',

    // Bash / Shell
    [TOOL.BASH]: 'bash',
    [TOOL.BASH_INIT]: 'bash',
    [TOOL.BASH_VIEW]: 'bash',
    [TOOL.BASH_STOP]: 'bash',
    [TOOL.BASH_KILL]: 'bash',
    [TOOL.BASH_LIST]: 'bash',
    [TOOL.BASH_WRITE_TO_PROCESS]: 'bash',
    [TOOL.SHELL_EXEC]: 'bash',
    [TOOL.SHELL_KILL_PROCESS]: 'bash',
    [TOOL.SHELL_VIEW]: 'bash',
    [TOOL.SHELL_WRITE_TO_PROCESS]: 'bash',
    [TOOL.SHELL_WAIT]: 'bash',
    [TOOL.PYTHON_EXECUTE]: 'bash',
    [TOOL.JAVASCRIPT_EXECUTE]: 'bash',
    [TOOL.CODE_EXECUTE]: 'bash',

    // Browse
    [TOOL.VISIT]: 'browse',
    [TOOL.VISIT_COMPRESS]: 'browse',
    [TOOL.BROWSER_USE]: 'browse',
    [TOOL.BROWSER_CLICK]: 'browse',
    [TOOL.BROWSER_CLOSE]: 'browse',
    [TOOL.BROWSER_CONSOLE_MESSAGES]: 'browse',
    [TOOL.BROWSER_DRAG]: 'browse',
    [TOOL.BROWSER_EVALUATE]: 'browse',
    [TOOL.BROWSER_HANDLE_DIALOG]: 'browse',
    [TOOL.BROWSER_HOVER]: 'browse',
    [TOOL.BROWSER_NAVIGATE]: 'browse',
    [TOOL.BROWSER_NETWORK_REQUESTS]: 'browse',
    [TOOL.BROWSER_PRESS_KEY]: 'browse',
    [TOOL.BROWSER_SELECT_OPTION]: 'browse',
    [TOOL.BROWSER_SNAPSHOT]: 'browse',
    [TOOL.BROWSER_TAKE_SCREENSHOT]: 'browse',
    [TOOL.BROWSER_TYPE]: 'browse',
    [TOOL.BROWSER_WAIT_FOR]: 'browse',
    [TOOL.BROWSER_TAB_CLOSE]: 'browse',
    [TOOL.BROWSER_TAB_LIST]: 'browse',
    [TOOL.BROWSER_TAB_NEW]: 'browse',
    [TOOL.BROWSER_TAB_SELECT]: 'browse',
    [TOOL.BROWSER_MOUSE_CLICK_XY]: 'browse',
    [TOOL.BROWSER_MOUSE_DRAG_XY]: 'browse',
    [TOOL.BROWSER_MOUSE_MOVE_XY]: 'browse',
    [TOOL.BROWSER_NAVIGATION]: 'browse',
    [TOOL.BROWSER_WAIT]: 'browse',
    [TOOL.BROWSER_VIEW_INTERACTIVE_ELEMENTS]: 'browse',
    [TOOL.BROWSER_SCROLL_DOWN]: 'browse',
    [TOOL.BROWSER_SCROLL_UP]: 'browse',
    [TOOL.BROWSER_SWITCH_TAB]: 'browse',
    [TOOL.BROWSER_OPEN_NEW_TAB]: 'browse',
    [TOOL.BROWSER_GET_SELECT_OPTIONS]: 'browse',
    [TOOL.BROWSER_SELECT_DROPDOWN_OPTION]: 'browse',
    [TOOL.BROWSER_RESTART]: 'browse',
    [TOOL.BROWSER_ENTER_TEXT]: 'browse',
    [TOOL.BROWSER_ENTER_MULTI_TEXTS]: 'browse',
    [TOOL.MCP_BROWSER_NAVIGATE]: 'browse',
    [TOOL.MCP_BROWSER_CLICK]: 'browse',
    [TOOL.MCP_BROWSER_TYPE]: 'browse',
    [TOOL.MCP_BROWSER_SCREENSHOT]: 'browse',
    [TOOL.CRAWL]: 'browse',

    // Generate
    [TOOL.IMAGE_GENERATE]: 'generate',
    [TOOL.VIDEO_GENERATE]: 'generate',
    [TOOL.LONG_VIDEO_GENERATE]: 'generate',
    [TOOL.LONG_VIDEO_GENERATE_FROM_IMAGE]: 'generate',
    [TOOL.AUDIO_TRANSCRIBE]: 'generate',
    [TOOL.GENERATE_AUDIO_RESPONSE]: 'generate',
    [TOOL.DISPLAY_IMAGE]: 'generate',
    [TOOL.DESIGN_CREATE]: 'generate',
    [TOOL.DESIGN_EDIT]: 'generate',
    [TOOL.EXCALIDRAW_CREATE]: 'generate',
    [TOOL.EXCALIDRAW_BATCH_CREATE]: 'generate',
    [TOOL.DOCUMENT_COMPILE]: 'generate',
    [TOOL.LATEX_COMPILE]: 'generate',

    // Search
    [TOOL.WEB_SEARCH]: 'search',
    [TOOL.WEB_BATCH_SEARCH]: 'search',
    [TOOL.IMAGE_SEARCH]: 'search',
    [TOOL.TAVILY_SEARCH]: 'search',
    [TOOL.PAPER_SEARCH]: 'search',
    [TOOL.GET_PAPER_DETAILS]: 'search',
    [TOOL.SEARCH_AUTHORS]: 'search',
    [TOOL.GET_AUTHOR_DETAILS]: 'search',
    [TOOL.GET_AUTHOR_PAPERS]: 'search',
    [TOOL.SEMANTIC_SCHOLAR_SEARCH]: 'search',
    [TOOL.ARXIV_SEARCH]: 'search',
    [TOOL.ARXIV_SEARCH_TOOL]: 'search',
    [TOOL.PUBMED_CENTRAL]: 'search',
    [TOOL.PUBMED_SEARCH]: 'search',
    [TOOL.GOOGLE_SCHOLAR]: 'search',
    [TOOL.SEMANTIC_SCHOLAR]: 'search',
    [TOOL.PEOPLE_SEARCH]: 'search',
    [TOOL.COMPANY_SEARCH]: 'search',
    [TOOL.MCP_SEARCH]: 'search',

    // Deploy
    [TOOL.STATIC_DEPLOY]: 'deploy',
    [TOOL.REGISTER_DEPLOYMENT]: 'deploy',
    [TOOL.REGISTER_PORT]: 'deploy',

    // Agent
    [TOOL.SUB_AGENT]: 'agent',
    [TOOL.SUB_AGENT_RESEARCHER]: 'agent',
    [TOOL.DESIGN_DOCUMENT_AGENT]: 'agent',
    [TOOL.CODEX_AGENT]: 'agent',
    [TOOL.CODEX_DELEGATE]: 'agent',
    [TOOL.BROWSER_SUBAGENT]: 'agent',
    [TOOL.DEEP_RESEARCH]: 'agent',
    [TOOL.REVIEWER_AGENT]: 'agent',
    [TOOL.CLAUDE_CODE]: 'agent',
    [TOOL.CODEX_EXECUTE]: 'agent',
    [TOOL.CODEX_REVIEW]: 'agent',
    [TOOL.MCP_CODEX_EXECUTE]: 'agent',
    [TOOL.MCP_CODEX_REVIEW]: 'agent',
    [TOOL.CODEX_MCP_CODEX_EXECUTE]: 'agent',
    [TOOL.CODEX_MCP_CODEX_REVIEW]: 'agent',
}

/**
 * Resolves a tool name (possibly dynamic/MCP) to a category.
 * Falls back to 'other' for unknown tools.
 */
export function getToolCategory(toolName: string | TOOL): ToolCategory {
    // Direct enum lookup
    const direct = TOOL_CATEGORY_MAP[toolName as TOOL]
    if (direct) return direct

    // Handle dynamic MCP tool names (e.g., "mcp_github_create_issue" → "other")
    // and sub_agent variants (e.g., "sub_agent_planner" → "agent")
    const lower = toolName.toLowerCase()
    if (lower.startsWith('sub_agent') || lower.startsWith('codex')) return 'agent'
    if (lower.startsWith('browser_') || lower.startsWith('mcp_browser')) return 'browse'
    if (lower.startsWith('shell_') || lower.startsWith('bash')) return 'bash'
    if (lower.includes('search')) return 'search'
    if (lower.startsWith('mcp_')) return 'other'

    return 'other'
}


// ─── Segment Model ─────────────────────────────────────────────────────────
// Each segment in the Signal Rail corresponds to one tool call in the current build phase.

export interface ToolSegment {
    id: string                     // tool_call_id
    toolName: string               // normalized TOOL enum value
    displayName: string            // human-readable name
    category: ToolCategory
    status: 'active' | 'completed' // active = executing, completed = result received
    startTime: number              // Date.now() timestamp
    endTime: number | null         // null while active
    durationMs: number | null      // computed on completion
}


// ─── State Shape ────────────────────────────────────────────────────────────

interface ToolProgressState {
    /** All tool segments in the current build phase, ordered chronologically */
    segments: ToolSegment[]

    /** Category-wise counters */
    toolsByCategory: Record<ToolCategory, number>

    /** Total tools called in this build phase */
    totalToolsCalled: number

    /** Index of the currently active tool (0-based), -1 if none */
    currentToolIndex: number

    /** Name of the currently executing tool */
    currentToolName: string | null

    /** Display name of the currently executing tool */
    currentToolDisplayName: string | null

    /** Timestamp when the currently active tool started */
    currentToolStartTime: number | null

    /** Timestamp when the build phase started (first tool call) */
    buildPhaseStartTime: number | null

    /** Rolling window of recent tool durations (last 5) for cadence calculation */
    recentToolDurations: number[]

    /** Whether the build is currently active (tools are or were recently executing) */
    isActive: boolean
}

const initialState: ToolProgressState = {
    segments: [],
    toolsByCategory: {
        read: 0,
        write: 0,
        bash: 0,
        browse: 0,
        generate: 0,
        search: 0,
        deploy: 0,
        agent: 0,
        other: 0,
    },
    totalToolsCalled: 0,
    currentToolIndex: -1,
    currentToolName: null,
    currentToolDisplayName: null,
    currentToolStartTime: null,
    buildPhaseStartTime: null,
    recentToolDurations: [],
    isActive: false,
}


// ─── Slice ──────────────────────────────────────────────────────────────────

const toolProgressSlice = createSlice({
    name: 'toolProgress',
    initialState,
    reducers: {
        /**
         * Called when a TOOL_CALL event arrives from the socket.
         * Creates a new segment and updates counters.
         */
        recordToolCall: (
            state,
            action: PayloadAction<{
                toolCallId: string
                toolName: string
                toolDisplayName: string
            }>
        ) => {
            const { toolCallId, toolName, toolDisplayName } = action.payload
            const category = getToolCategory(toolName)
            const now = Date.now()

            // If there's a currently active segment, mark it completed
            // (handles edge case where tool_result was missed)
            const activeIdx = state.segments.findIndex(s => s.status === 'active')
            if (activeIdx !== -1) {
                const seg = state.segments[activeIdx]
                seg.status = 'completed'
                seg.endTime = now
                seg.durationMs = now - seg.startTime
                // Add to recent durations
                state.recentToolDurations.push(seg.durationMs)
                if (state.recentToolDurations.length > 5) {
                    state.recentToolDurations.shift()
                }
            }

            // Create new segment
            const segment: ToolSegment = {
                id: toolCallId,
                toolName,
                displayName: toolDisplayName,
                category,
                status: 'active',
                startTime: now,
                endTime: null,
                durationMs: null,
            }

            state.segments.push(segment)
            state.totalToolsCalled += 1
            state.toolsByCategory[category] = (state.toolsByCategory[category] || 0) + 1
            state.currentToolIndex = state.segments.length - 1
            state.currentToolName = toolName
            state.currentToolDisplayName = toolDisplayName
            state.currentToolStartTime = now
            state.isActive = true

            // Set build phase start on first tool
            if (!state.buildPhaseStartTime) {
                state.buildPhaseStartTime = now
            }
        },

        /**
         * Called when a TOOL_RESULT event arrives from the socket.
         * Marks the matching segment as completed.
         */
        recordToolResult: (
            state,
            action: PayloadAction<{
                toolName: string
            }>
        ) => {
            const { toolName } = action.payload
            const now = Date.now()

            // Find the last active segment matching this tool name
            // (match by toolName since tool_result doesn't always have tool_call_id)
            let targetIdx = -1
            for (let i = state.segments.length - 1; i >= 0; i--) {
                if (state.segments[i].status === 'active' && state.segments[i].toolName === toolName) {
                    targetIdx = i
                    break
                }
            }

            // If no match by name, mark any active segment as completed
            if (targetIdx === -1) {
                targetIdx = state.segments.findIndex(s => s.status === 'active')
            }

            if (targetIdx !== -1) {
                const seg = state.segments[targetIdx]
                seg.status = 'completed'
                seg.endTime = now
                seg.durationMs = now - seg.startTime

                // Add to recent durations
                state.recentToolDurations.push(seg.durationMs)
                if (state.recentToolDurations.length > 5) {
                    state.recentToolDurations.shift()
                }
            }

            // Clear current tool tracking since it completed
            // (next tool_call will set these again)
            state.currentToolName = null
            state.currentToolDisplayName = null
            state.currentToolStartTime = null
        },

        /**
         * Reset all progress state. Called on COMPLETE event or new query.
         */
        resetToolProgress: (state) => {
            Object.assign(state, initialState)
        },

        /**
         * Mark the build phase as inactive (tools stopped flowing, but don't clear history yet).
         * The SignalRail stays visible showing completed segments until explicit reset.
         */
        deactivateToolProgress: (state) => {
            state.isActive = false
            state.currentToolName = null
            state.currentToolDisplayName = null
            state.currentToolStartTime = null
        },
    },
})


// ─── Exports ────────────────────────────────────────────────────────────────

export const {
    recordToolCall,
    recordToolResult,
    resetToolProgress,
    deactivateToolProgress,
} = toolProgressSlice.actions

export const toolProgressReducer = toolProgressSlice.reducer


// ─── Selectors ──────────────────────────────────────────────────────────────

interface RootStateWithToolProgress {
    toolProgress: ToolProgressState
}

export const selectToolProgressSegments = (state: RootStateWithToolProgress) =>
    state.toolProgress.segments

export const selectToolsByCategory = (state: RootStateWithToolProgress) =>
    state.toolProgress.toolsByCategory

export const selectTotalToolsCalled = (state: RootStateWithToolProgress) =>
    state.toolProgress.totalToolsCalled

export const selectCurrentToolIndex = (state: RootStateWithToolProgress) =>
    state.toolProgress.currentToolIndex

export const selectCurrentToolName = (state: RootStateWithToolProgress) =>
    state.toolProgress.currentToolName

export const selectCurrentToolDisplayName = (state: RootStateWithToolProgress) =>
    state.toolProgress.currentToolDisplayName

export const selectCurrentToolStartTime = (state: RootStateWithToolProgress) =>
    state.toolProgress.currentToolStartTime

export const selectBuildPhaseStartTime = (state: RootStateWithToolProgress) =>
    state.toolProgress.buildPhaseStartTime

export const selectToolProgressIsActive = (state: RootStateWithToolProgress) =>
    state.toolProgress.isActive

export const selectRecentToolDurations = (state: RootStateWithToolProgress) =>
    state.toolProgress.recentToolDurations

/**
 * Computes execution cadence from recent tool durations.
 * Used by PulseIndicator to adjust spin speed.
 */
export const selectToolExecutionCadence = createSelector(
    [selectRecentToolDurations],
    (durations): 'fast' | 'normal' | 'slow' => {
        if (durations.length < 2) return 'slow'
        const avgDuration = durations.reduce((a, b) => a + b, 0) / durations.length
        if (avgDuration < 2000) return 'fast'
        if (avgDuration < 5000) return 'normal'
        return 'slow'
    }
)

/**
 * Returns non-zero category entries for display in the Signal Rail stats.
 */
export const selectActiveCategories = createSelector(
    [selectToolsByCategory],
    (categories) => {
        return Object.entries(categories)
            .filter(([, count]) => count > 0)
            .map(([category, count]) => ({ category: category as ToolCategory, count }))
    }
)
