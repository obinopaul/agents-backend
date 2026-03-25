'use client'

import { useEffect, useRef, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Icon } from '../ui/icon'
import {
    useAppSelector,
    selectToolProgressSegments,
    selectActiveCategories,
    selectTotalToolsCalled,
    selectCurrentToolStartTime,
    selectToolProgressIsActive,
} from '@/state'
import type { ToolSegment } from '@/state/slice/toolProgress'


// ─── Category Icon Map ──────────────────────────────────────────────────────
// Miniature icons (10px) inline with stat text, reusing existing icon names

const CATEGORY_ICONS: Record<string, string> = {
    read: 'read-file',
    write: 'create-file',
    bash: 'terminal',
    browse: 'browsing',
    generate: 'gen-image',
    search: 'search-2',
    deploy: 'deploy',
    agent: 'bot',
    other: 'setting',
}

const CATEGORY_LABELS: Record<string, string> = {
    read: 'read',
    write: 'write',
    bash: 'bash',
    browse: 'browse',
    generate: 'gen',
    search: 'search',
    deploy: 'deploy',
    agent: 'agent',
    other: 'other',
}


// ─── Segment Component ──────────────────────────────────────────────────────

interface SegmentProps {
    segment: ToolSegment
    index: number
}

const Segment = ({ segment, index }: SegmentProps) => {
    return (
        <motion.div
            initial={{ scaleY: 0, opacity: 0 }}
            animate={{ scaleY: 1, opacity: 1 }}
            transition={{
                duration: 0.2,
                delay: index * 0.02, // Stagger on initial render
                ease: 'easeOut',
            }}
            className={cn(
                'w-[5px] h-3 rounded-[1px] transition-colors duration-200 origin-bottom',
                segment.status === 'completed' && 'bg-firefly dark:bg-sky-blue',
                segment.status === 'active' && 'bg-sky-blue-2 animate-pulse'
            )}
            title={`${segment.displayName} — ${segment.status === 'completed' && segment.durationMs ? `${(segment.durationMs / 1000).toFixed(1)}s` : 'executing...'}`}
        />
    )
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


// ─── Signal Rail Component ──────────────────────────────────────────────────

interface SignalRailProps {
    className?: string
}

const SignalRail = ({ className }: SignalRailProps) => {
    const segments = useAppSelector(selectToolProgressSegments)
    const activeCategories = useAppSelector(selectActiveCategories)
    const totalToolsCalled = useAppSelector(selectTotalToolsCalled)
    const currentToolStartTime = useAppSelector(selectCurrentToolStartTime)
    const isActive = useAppSelector(selectToolProgressIsActive)

    const elapsed = useElapsedTimer(currentToolStartTime)

    // Only render when there are segments to show
    const shouldShow = segments.length > 0

    // Scroll container ref for auto-scrolling the segment meter
    const segmentContainerRef = useRef<HTMLDivElement>(null)

    // Auto-scroll to the rightmost segment when new ones appear
    useEffect(() => {
        if (segmentContainerRef.current && segments.length > 0) {
            segmentContainerRef.current.scrollLeft =
                segmentContainerRef.current.scrollWidth
        }
    }, [segments.length])

    // Memoize the stats display
    const statsDisplay = useMemo(() => {
        if (activeCategories.length === 0) return null

        return activeCategories.map(({ category, count }) => (
            <div
                key={category}
                className="flex items-center gap-[3px] shrink-0"
            >
                <Icon
                    name={CATEGORY_ICONS[category] || 'setting'}
                    className="size-[10px] fill-current opacity-60"
                />
                <span>{CATEGORY_LABELS[category]}</span>
                <span className="font-semibold">{count}</span>
            </div>
        ))
    }, [activeCategories])

    return (
        <AnimatePresence>
            {shouldShow && (
                <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 32, opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25, ease: 'easeOut' }}
                    className={cn(
                        'w-full overflow-hidden',
                        'bg-firefly/5 dark:bg-sky-blue/5',
                        'border-t border-firefly/10 dark:border-sky-blue/10',
                        className
                    )}
                >
                    <div className="flex items-center justify-between h-8 px-3 gap-3">
                        {/* Left: Segment Meter */}
                        <div
                            ref={segmentContainerRef}
                            className="flex items-center gap-[2px] overflow-x-auto scrollbar-none min-w-0 flex-shrink"
                        >
                            {segments.map((segment, i) => (
                                <Segment
                                    key={segment.id}
                                    segment={segment}
                                    index={i}
                                />
                            ))}
                        </div>

                        {/* Right: Execution Stats */}
                        <div
                            className={cn(
                                'flex items-center gap-2 shrink-0',
                                'text-[11px] font-medium tracking-wide',
                                'text-firefly/70 dark:text-sky-blue/70',
                                '[font-variant-numeric:tabular-nums]'
                            )}
                        >
                            {/* Total ops count */}
                            <span className="font-semibold shrink-0">
                                {totalToolsCalled} ops
                            </span>

                            {/* Category breakdown — show separator + categories */}
                            {activeCategories.length > 0 && (
                                <>
                                    <span className="text-pewter">·</span>
                                    {statsDisplay}
                                </>
                            )}

                            {/* Elapsed timer for current tool */}
                            {isActive && currentToolStartTime && (
                                <>
                                    <span className="text-pewter">·</span>
                                    <span className="text-sky-blue-4 font-mono shrink-0">
                                        {elapsed}
                                    </span>
                                </>
                            )}
                        </div>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    )
}

export default SignalRail
