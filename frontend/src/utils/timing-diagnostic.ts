/**
 * Frontend Timing Diagnostic
 * ===========================
 * Instruments the prompt-to-first-output pipeline to identify latency bottlenecks.
 *
 * Usage (browser console):
 *   window.__timingDiag.enable()   — Start recording
 *   window.__timingDiag.disable()  — Stop recording
 *   window.__timingDiag.report()   — Print latest timing report
 *   window.__timingDiag.history()  — Print all recorded sessions
 *   window.__timingDiag.clear()    — Clear history
 *
 * The diagnostic hooks into the global event system via monkey-patching.
 * It measures:
 *   T0: User presses Enter (submit)
 *   T1: WebSocket `query` command sent to server
 *   T2: First WebSocket event received from server (any type)
 *   T3: First content event (AGENT_THINKING, AGENT_RESPONSE, or TOOL_CALL)
 *   T4: BUILD_STEP transitions from THINKING → BUILD (content becomes visible)
 *   T5: First complete response (COMPLETE event)
 */

export interface TimingRecord {
    sessionId: string
    timestamp: string

    // Core milestones (ms since T0)
    t0_submit: number               // User pressed Enter
    t1_querySent: number | null      // query command emitted via socket
    t2_firstEvent: number | null     // First server event received
    t3_firstContent: number | null   // First content-bearing event
    t4_viewTransition: number | null // BUILD_STEP changed from THINKING to BUILD
    t5_complete: number | null       // COMPLETE event received

    // Derived durations (ms)
    submitToQuerySent: number | null
    queryToFirstEvent: number | null
    firstEventToContent: number | null
    contentToVisible: number | null
    submitToFirstVisible: number | null
    submitToComplete: number | null

    // Event log
    events: Array<{
        type: string
        elapsed: number  // ms since T0
        detail?: string
    }>

    // First event type
    firstEventType: string | null
    firstContentType: string | null
}

class TimingDiagnostic {
    private enabled = false
    private currentSession: TimingRecord | null = null
    private sessions: TimingRecord[] = []
    private t0: number = 0

    enable() {
        this.enabled = true
        console.log(
            '%c[TimingDiag] ✓ Enabled — submit a prompt to start recording',
            'color: #22c55e; font-weight: bold'
        )
    }

    disable() {
        this.enabled = false
        if (this.currentSession) {
            this.finalize()
        }
        console.log(
            '%c[TimingDiag] ✗ Disabled',
            'color: #ef4444; font-weight: bold'
        )
    }

    isEnabled() {
        return this.enabled
    }

    /**
     * Called when the user presses Enter to submit a prompt
     */
    markSubmit(question?: string) {
        if (!this.enabled) return

        // Finalize any previous session
        if (this.currentSession) {
            this.finalize()
        }

        this.t0 = performance.now()
        this.currentSession = {
            sessionId: `diag-${Date.now()}`,
            timestamp: new Date().toISOString(),
            t0_submit: 0,
            t1_querySent: null,
            t2_firstEvent: null,
            t3_firstContent: null,
            t4_viewTransition: null,
            t5_complete: null,
            submitToQuerySent: null,
            queryToFirstEvent: null,
            firstEventToContent: null,
            contentToVisible: null,
            submitToFirstVisible: null,
            submitToComplete: null,
            events: [{
                type: 'SUBMIT',
                elapsed: 0,
                detail: question?.substring(0, 80)
            }],
            firstEventType: null,
            firstContentType: null
        }

        console.log(
            '%c[TimingDiag] ⏱ T0: Prompt submitted',
            'color: #3b82f6; font-weight: bold',
            question?.substring(0, 60)
        )
    }

    /**
     * Called when the WebSocket "query" command is actually emitted
     */
    markQuerySent() {
        if (!this.enabled || !this.currentSession) return

        const elapsed = performance.now() - this.t0
        this.currentSession.t1_querySent = elapsed
        this.currentSession.submitToQuerySent = elapsed
        this.currentSession.events.push({
            type: 'QUERY_SENT',
            elapsed
        })

        console.log(
            `%c[TimingDiag] ⏱ T1: Query sent to server (+${elapsed.toFixed(0)}ms)`,
            'color: #8b5cf6; font-weight: bold'
        )
    }

    /**
     * Called on ANY WebSocket event from the server
     */
    markEvent(eventType: string, detail?: string) {
        if (!this.enabled || !this.currentSession) return

        const elapsed = performance.now() - this.t0
        this.currentSession.events.push({
            type: eventType,
            elapsed,
            detail
        })

        // First event of any type
        if (this.currentSession.t2_firstEvent === null) {
            this.currentSession.t2_firstEvent = elapsed
            this.currentSession.firstEventType = eventType
            if (this.currentSession.t1_querySent !== null) {
                this.currentSession.queryToFirstEvent =
                    elapsed - this.currentSession.t1_querySent
            }
            console.log(
                `%c[TimingDiag] ⏱ T2: First event "${eventType}" (+${elapsed.toFixed(0)}ms)`,
                'color: #f59e0b; font-weight: bold'
            )
        }

        // First content-bearing event
        const contentEvents = [
            'agent_thinking', 'agent_response', 'tool_call',
            'AGENT_THINKING', 'AGENT_RESPONSE', 'TOOL_CALL'
        ]
        if (
            this.currentSession.t3_firstContent === null &&
            contentEvents.includes(eventType)
        ) {
            this.currentSession.t3_firstContent = elapsed
            this.currentSession.firstContentType = eventType
            if (this.currentSession.t2_firstEvent !== null) {
                this.currentSession.firstEventToContent =
                    elapsed - this.currentSession.t2_firstEvent
            }
            console.log(
                `%c[TimingDiag] ⏱ T3: First content "${eventType}" (+${elapsed.toFixed(0)}ms)`,
                'color: #10b981; font-weight: bold'
            )
        }

        // COMPLETE event
        if (
            (eventType === 'complete' || eventType === 'COMPLETE') &&
            this.currentSession.t5_complete === null
        ) {
            this.currentSession.t5_complete = elapsed
            this.currentSession.submitToComplete = elapsed
            console.log(
                `%c[TimingDiag] ⏱ T5: Complete (+${elapsed.toFixed(0)}ms)`,
                'color: #06b6d4; font-weight: bold'
            )
            this.finalize()
        }
    }

    /**
     * Called when BUILD_STEP transitions from THINKING to BUILD
     */
    markViewTransition() {
        if (!this.enabled || !this.currentSession) return

        const elapsed = performance.now() - this.t0
        if (this.currentSession.t4_viewTransition === null) {
            this.currentSession.t4_viewTransition = elapsed
            if (this.currentSession.t3_firstContent !== null) {
                this.currentSession.contentToVisible =
                    elapsed - this.currentSession.t3_firstContent
            }
            this.currentSession.submitToFirstVisible = elapsed
            this.currentSession.events.push({
                type: 'VIEW_TRANSITION',
                elapsed,
                detail: 'THINKING → BUILD'
            })
            console.log(
                `%c[TimingDiag] ⏱ T4: View transition THINKING→BUILD (+${elapsed.toFixed(0)}ms)`,
                'color: #ec4899; font-weight: bold'
            )
        }
    }

    /**
     * Finalize the current session and add it to history
     */
    private finalize() {
        if (!this.currentSession) return

        this.sessions.push({ ...this.currentSession })
        this.printReport(this.currentSession)
        this.currentSession = null
    }

    /**
     * Print a formatted timing report
     */
    private printReport(record: TimingRecord) {
        const bar = (ms: number | null, label: string, max = 10000) => {
            if (ms === null) return `  ${label}: — (not recorded)`
            const blocks = Math.min(Math.round(ms / (max / 40)), 40)
            const bar = '█'.repeat(blocks) + '░'.repeat(40 - blocks)
            return `  ${label}: ${bar} ${ms.toFixed(0)}ms`
        }

        console.log(
            '\n%c╔══════════════════════════════════════════════════╗\n' +
            '║          TIMING DIAGNOSTIC REPORT                ║\n' +
            '╚══════════════════════════════════════════════════╝',
            'color: #3b82f6; font-weight: bold'
        )
        console.log(`  Session: ${record.sessionId}`)
        console.log(`  Time: ${record.timestamp}`)
        console.log('')
        console.log('%c  ── Pipeline Milestones ──', 'color: #8b5cf6; font-weight: bold')
        console.log(`  T0  Submit:           0ms`)
        console.log(`  T1  Query sent:       ${record.t1_querySent?.toFixed(0) ?? '—'}ms`)
        console.log(`  T2  First event:      ${record.t2_firstEvent?.toFixed(0) ?? '—'}ms  (${record.firstEventType ?? '—'})`)
        console.log(`  T3  First content:    ${record.t3_firstContent?.toFixed(0) ?? '—'}ms  (${record.firstContentType ?? '—'})`)
        console.log(`  T4  View visible:     ${record.t4_viewTransition?.toFixed(0) ?? '—'}ms`)
        console.log(`  T5  Complete:         ${record.t5_complete?.toFixed(0) ?? '—'}ms`)
        console.log('')
        console.log('%c  ── Latency Breakdown ──', 'color: #f59e0b; font-weight: bold')
        console.log(bar(record.submitToQuerySent, 'Submit → Query sent '))
        console.log(bar(record.queryToFirstEvent, 'Query  → First event'))
        console.log(bar(record.firstEventToContent, 'Event  → Content    '))
        console.log(bar(record.contentToVisible, 'Content → Visible   '))
        console.log(bar(record.submitToFirstVisible, 'Submit → Visible    '))
        console.log(bar(record.submitToComplete, 'Submit → Complete   '))
        console.log('')

        // Flag bottlenecks
        const bottlenecks: string[] = []
        if ((record.submitToQuerySent ?? 0) > 500) {
            bottlenecks.push(
                `⚠️ Submit→QuerySent is ${record.submitToQuerySent?.toFixed(0)}ms — ` +
                'possible delay in session creation or WebSocket reconnect'
            )
        }
        if ((record.queryToFirstEvent ?? 0) > 3000) {
            bottlenecks.push(
                `⚠️ QuerySent→FirstEvent is ${record.queryToFirstEvent?.toFixed(0)}ms — ` +
                'backend startup latency (sandbox init, MCP, Codex, port setup)'
            )
        }
        if ((record.firstEventToContent ?? 0) > 5000) {
            bottlenecks.push(
                `⚠️ FirstEvent→Content is ${record.firstEventToContent?.toFixed(0)}ms — ` +
                'backend agent initialization before LLM streaming starts'
            )
        }
        if ((record.contentToVisible ?? 0) > 200) {
            bottlenecks.push(
                `⚠️ Content→Visible is ${record.contentToVisible?.toFixed(0)}ms — ` +
                'BUILD_STEP view transition delay'
            )
        }
        if (record.t4_viewTransition === null && record.t3_firstContent !== null) {
            bottlenecks.push(
                '🔴 Content arrived but view never transitioned from THINKING → BUILD! ' +
                'User sees "I\'m thinking..." animation but content is hidden behind it.'
            )
        }

        if (bottlenecks.length > 0) {
            console.log('%c  ── Bottlenecks ──', 'color: #ef4444; font-weight: bold')
            bottlenecks.forEach(b => console.log(`  ${b}`))
        } else {
            console.log(
                '%c  ✓ No major bottlenecks detected',
                'color: #22c55e; font-weight: bold'
            )
        }

        console.log('')
        console.log(`  Events received: ${record.events.length}`)
        console.table(record.events)
    }

    /**
     * Print latest report
     */
    report() {
        if (this.currentSession) {
            this.printReport(this.currentSession)
        } else if (this.sessions.length > 0) {
            this.printReport(this.sessions[this.sessions.length - 1])
        } else {
            console.log('[TimingDiag] No sessions recorded yet.')
        }
    }

    /**
     * Print all recorded sessions summary
     */
    history() {
        if (this.sessions.length === 0) {
            console.log('[TimingDiag] No sessions recorded.')
            return
        }
        console.table(
            this.sessions.map((s, i) => ({
                '#': i + 1,
                timestamp: s.timestamp,
                'submit→visible': s.submitToFirstVisible
                    ? `${s.submitToFirstVisible.toFixed(0)}ms`
                    : '—',
                'submit→complete': s.submitToComplete
                    ? `${s.submitToComplete.toFixed(0)}ms`
                    : '—',
                firstContent: s.firstContentType ?? '—',
                events: s.events.length
            }))
        )
    }

    /**
     * Clear all recorded sessions
     */
    clear() {
        this.sessions = []
        this.currentSession = null
        console.log('[TimingDiag] History cleared.')
    }
}

// Singleton instance
export const timingDiag = new TimingDiagnostic()

// Expose on window for console access
if (typeof window !== 'undefined') {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(window as any).__timingDiag = timingDiag
}
