'use client'

import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import {
    useAppSelector,
    selectToolExecutionCadence,
    selectCurrentToolName,
    selectToolProgressIsActive,
} from '@/state'

/**
 * PulseIndicator — A dynamic concentric ring that replaces the static loading spinner
 * in the Build Panel title bar.
 *
 * Spin speed reflects execution cadence:
 * - fast (< 2s avg between tools): 0.6s rotation
 * - normal (2-5s avg): 1.5s rotation
 * - slow (> 5s avg or idle): 2.5s rotation
 *
 * Center dot: solid sky-blue-2 when executing, breathing pulse when idle.
 */

const CADENCE_SPEEDS: Record<'fast' | 'normal' | 'slow', number> = {
    fast: 0.6,
    normal: 1.5,
    slow: 2.5,
}

interface PulseIndicatorProps {
    className?: string
}

const PulseIndicator = ({ className }: PulseIndicatorProps) => {
    const cadence = useAppSelector(selectToolExecutionCadence)
    const currentToolName = useAppSelector(selectCurrentToolName)
    const isActive = useAppSelector(selectToolProgressIsActive)

    const isToolExecuting = Boolean(currentToolName && isActive)

    const spinDuration = useMemo(
        () => CADENCE_SPEEDS[cadence],
        [cadence]
    )

    return (
        <div className={cn('relative size-[18px] flex items-center justify-center', className)}>
            {/* Outer ring — static border, represents the build phase */}
            <div
                className={cn(
                    'absolute inset-0 rounded-full border-[1.5px]',
                    isToolExecuting
                        ? 'border-firefly/40 dark:border-sky-blue/40'
                        : 'border-firefly/20 dark:border-sky-blue/20'
                )}
            />

            {/* Inner ring — rotation speed varies with tool execution cadence */}
            <motion.div
                className={cn(
                    'absolute inset-[2px] rounded-full border-[1.5px] border-t-transparent',
                    isToolExecuting
                        ? 'border-sky-blue-2'
                        : 'border-firefly/30 dark:border-sky-blue/30'
                )}
                animate={{ rotate: 360 }}
                transition={{
                    duration: spinDuration,
                    repeat: Infinity,
                    ease: 'linear',
                }}
            />

            {/* Center dot — solid when executing, breathing when idle */}
            <div
                className={cn(
                    'size-1.5 rounded-full transition-colors duration-300',
                    isToolExecuting
                        ? 'bg-sky-blue-2'
                        : 'bg-firefly/40 dark:bg-sky-blue/40 animate-pulse'
                )}
            />
        </div>
    )
}

export default PulseIndicator
