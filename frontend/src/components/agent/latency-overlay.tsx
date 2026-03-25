'use client'

import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Icon } from '../ui/icon'
import { TOOL } from '@/typings/agent'
import {
    useAppSelector,
    selectCurrentToolName,
    selectCurrentToolDisplayName,
    selectCurrentToolStartTime,
    selectToolProgressIsActive,
} from '@/state'

// ─── Latency Threshold ─────────────────────────────────────────────────────

const LATENCY_THRESHOLD_MS = 8000

// ─── Tool-Specific Contextual Messages ──────────────────────────────────────

function getContextualMessage(toolName: string | null, displayName: string | null): string {
    if (!toolName) return 'Processing...'

    switch (toolName) {
        // Bash / Shell
        case TOOL.BASH:
        case TOOL.BASH_INIT:
        case TOOL.SHELL_EXEC:
            return 'Executing command...'

        // Write / Edit
        case TOOL.WRITE:
        case TOOL.EDIT:
        case TOOL.MULTI_EDIT:
        case TOOL.APPLY_PATCH:
        case TOOL.STR_REPLACE_BASED_EDIT:
            return 'Writing file...'

        // Read
        case TOOL.READ:
        case TOOL.GLOB:
        case TOOL.LS:
        case TOOL.GREP:
            return 'Reading file...'

        // Web / Search
        case TOOL.WEB_SEARCH:
        case TOOL.WEB_BATCH_SEARCH:
        case TOOL.TAVILY_SEARCH:
            return 'Searching the web...'

        // Browser
        case TOOL.VISIT:
        case TOOL.VISIT_COMPRESS:
        case TOOL.BROWSER_USE:
        case TOOL.BROWSER_NAVIGATE:
            return 'Loading page...'

        // Media
        case TOOL.IMAGE_GENERATE:
            return 'Generating image...'
        case TOOL.VIDEO_GENERATE:
        case TOOL.LONG_VIDEO_GENERATE:
        case TOOL.LONG_VIDEO_GENERATE_FROM_IMAGE:
            return 'Generating video...'

        // Research / Agent
        case TOOL.DEEP_RESEARCH:
            return 'Deep research in progress...'
        case TOOL.SUB_AGENT:
        case TOOL.SUB_AGENT_RESEARCHER:
        case TOOL.DESIGN_DOCUMENT_AGENT:
            return 'Sub-agent working...'

        // Deploy
        case TOOL.STATIC_DEPLOY:
        case TOOL.REGISTER_DEPLOYMENT:
            return 'Deploying...'

        // Code execution
        case TOOL.PYTHON_EXECUTE:
        case TOOL.JAVASCRIPT_EXECUTE:
        case TOOL.CODE_EXECUTE:
            return 'Executing code...'

        default:
            // MCP tools or unknown — use display name if available
            if (displayName) {
                return `Running ${displayName}...`
            }
            return 'Processing...'
    }
}

// ─── Tool Icon Resolver ─────────────────────────────────────────────────────

function getToolIconName(toolName: string | null): string {
    if (!toolName) return 'loading'

    const lower = toolName.toLowerCase()

    if (lower.startsWith('bash') || lower.startsWith('shell_')) return 'terminal'
    if (toolName === TOOL.READ) return 'read-file'
    if (toolName === TOOL.WRITE) return 'create-file'
    if (toolName === TOOL.EDIT || toolName === TOOL.MULTI_EDIT) return 'edit-file'
    if (lower.includes('search')) return 'search-2'
    if (lower.startsWith('browser_') || toolName === TOOL.VISIT || toolName === TOOL.VISIT_COMPRESS) return 'browsing'
    if (toolName === TOOL.IMAGE_GENERATE) return 'gen-image'
    if (toolName === TOOL.STATIC_DEPLOY || toolName === TOOL.REGISTER_DEPLOYMENT) return 'deploy'
    if (lower.startsWith('sub_agent') || lower.startsWith('codex') || toolName === TOOL.DEEP_RESEARCH) return 'bot'

    return 'loading'
}


// ─── Elapsed Timer Hook ─────────────────────────────────────────────────────

function useElapsedTimer(startTime: number | null): string {
    const [elapsed, setElapsed] = useState('0.0s')
    const rafRef = useRef<number | null>(null)

    useEffect(() => {
        if (!startTime) {
            setElapsed('0.0s')
            return
        }

        const tick = () => {
            const seconds = (Date.now() - startTime) / 1000
            setElapsed(`${seconds.toFixed(1)}s`)
            rafRef.current = requestAnimationFrame(tick)
        }

        rafRef.current = requestAnimationFrame(tick)

        return () => {
            if (rafRef.current !== null) {
                cancelAnimationFrame(rafRef.current)
            }
        }
    }, [startTime])

    return elapsed
}


// ─── LatencyOverlay Component ───────────────────────────────────────────────

interface LatencyOverlayProps {
    className?: string
}

const LatencyOverlay = ({ className }: LatencyOverlayProps) => {
    const currentToolName = useAppSelector(selectCurrentToolName)
    const currentToolDisplayName = useAppSelector(selectCurrentToolDisplayName)
    const currentToolStartTime = useAppSelector(selectCurrentToolStartTime)
    const isActive = useAppSelector(selectToolProgressIsActive)

    const [isLongRunning, setIsLongRunning] = useState(false)
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    const elapsed = useElapsedTimer(
        isLongRunning ? currentToolStartTime : null
    )

    // Set up the 8-second latency threshold timer
    useEffect(() => {
        // Clear any existing timer
        if (timerRef.current) {
            clearTimeout(timerRef.current)
            timerRef.current = null
        }

        // Reset when tool changes or becomes inactive
        setIsLongRunning(false)

        if (!currentToolStartTime || !isActive || !currentToolName) {
            return
        }

        // Check if already past threshold (e.g., on component mount during long operation)
        const timeSinceStart = Date.now() - currentToolStartTime
        if (timeSinceStart >= LATENCY_THRESHOLD_MS) {
            setIsLongRunning(true)
            return
        }

        // Set timer for remaining time until threshold
        const remaining = LATENCY_THRESHOLD_MS - timeSinceStart
        timerRef.current = setTimeout(() => {
            setIsLongRunning(true)
        }, remaining)

        return () => {
            if (timerRef.current) {
                clearTimeout(timerRef.current)
                timerRef.current = null
            }
        }
    }, [currentToolStartTime, isActive, currentToolName])

    const contextualMessage = getContextualMessage(currentToolName, currentToolDisplayName)
    const iconName = getToolIconName(currentToolName)

    return (
        <AnimatePresence>
            {isLongRunning && isActive && currentToolName && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.6 }}
                    className={cn(
                        'absolute inset-0 z-10',
                        'backdrop-blur-[2px] bg-black/20 dark:bg-black/40',
                        'flex flex-col items-center justify-center gap-3',
                        className
                    )}
                >
                    {/* Tool-specific contextual message */}
                    <div
                        className={cn(
                            'flex items-center gap-2 px-4 py-2',
                            'bg-firefly/80 dark:bg-charcoal/80',
                            'rounded-lg backdrop-blur-md',
                            'border border-sky-blue/20'
                        )}
                    >
                        <Icon
                            name={iconName}
                            className="size-4 fill-white"
                        />
                        <span className="text-white text-sm font-medium">
                            {contextualMessage}
                        </span>
                    </div>

                    {/* Elapsed time with terminal cursor blink */}
                    <div className="flex items-center gap-1.5 text-sky-blue-4 text-xs font-mono">
                        <span className="[font-variant-numeric:tabular-nums]">
                            {elapsed}
                        </span>
                        <span className="animate-pulse">│</span>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    )
}

export default LatencyOverlay
