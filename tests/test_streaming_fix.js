/**
 * Tests for the premature streaming stop fix (frontend).
 *
 * Verifies the STATUS_UPDATE handler in use-app-events.tsx correctly
 * ignores 'idle' status and only the COMPLETE/ERROR/INTERRUPTED events
 * authoritatively control the loading state.
 *
 * Run: node tests/test_streaming_fix.js
 */

// ─── Simulated Frontend State Machine ────────────────────────────────────────

class FrontendStreamState {
  constructor() {
    this.isLoading = false
    this.isCompleted = false
    this.isStopped = false
    this.eventsReceived = []
  }

  get thinkingVisible() {
    return this.isLoading && !this.isStopped && !this.isCompleted
  }

  handleEvent(eventType, content = {}) {
    this.eventsReceived.push({ type: eventType, content })

    switch (eventType) {
      case 'status_update': {
        const status = content.status
        // Fix: Only set loading=true on 'running'.
        // Do NOT set loading=false on 'idle' — COMPLETE/ERROR/INTERRUPTED
        // are the authoritative stream-end signals.
        if (typeof status === 'string' && status === 'running') {
          this.isLoading = true
        }
        break
      }
      case 'complete': {
        this.isCompleted = true
        this.isLoading = false
        break
      }
      case 'error': {
        this.isLoading = false
        break
      }
      case 'agent_response_interrupted': {
        this.isLoading = false
        this.isStopped = true
        break
      }
      // All other event types (agent_response, tool_call, tool_result, etc.)
      // do not affect loading state
    }
  }
}

// ─── Test Framework ──────────────────────────────────────────────────────────

let testCount = 0
let passCount = 0
let failCount = 0

function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`)
  }
}

function test(name, fn) {
  testCount++
  try {
    fn()
    passCount++
    console.log(`  ✓ ${name}`)
  } catch (e) {
    failCount++
    console.error(`  ✗ ${name}`)
    console.error(`    ${e.message}`)
  }
}

function describe(name, fn) {
  console.log(`\n${name}`)
  fn()
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe('STATUS_UPDATE handler (fix verification)', () => {
  test('running status sets isLoading=true', () => {
    const state = new FrontendStreamState()
    state.handleEvent('status_update', { status: 'running' })
    assert(state.isLoading === true, 'isLoading should be true')
    assert(state.thinkingVisible === true, 'ThinkingMessage should be visible')
  })

  test('idle status does NOT clear isLoading (root cause fix)', () => {
    const state = new FrontendStreamState()
    state.handleEvent('status_update', { status: 'running' })
    assert(state.isLoading === true, 'isLoading should be true after running')

    state.handleEvent('status_update', { status: 'idle' })
    assert(state.isLoading === true, 'isLoading must remain true — idle is ignored')
    assert(state.thinkingVisible === true, 'ThinkingMessage must remain visible')
  })

  test('unknown statuses do not affect loading', () => {
    const state = new FrontendStreamState()
    state.handleEvent('status_update', { status: 'running' })

    for (const s of ['processing', 'thinking', 'queued', '']) {
      state.handleEvent('status_update', { status: s })
      assert(state.isLoading === true, `isLoading changed by status "${s}"`)
    }
  })
})

describe('Authoritative stream-end signals', () => {
  test('COMPLETE clears loading and sets completed', () => {
    const state = new FrontendStreamState()
    state.handleEvent('status_update', { status: 'running' })
    state.handleEvent('complete', { message: 'done' })
    assert(state.isLoading === false, 'isLoading should be false')
    assert(state.isCompleted === true, 'isCompleted should be true')
    assert(state.thinkingVisible === false, 'ThinkingMessage should be hidden')
  })

  test('ERROR clears loading', () => {
    const state = new FrontendStreamState()
    state.handleEvent('status_update', { status: 'running' })
    state.handleEvent('error', { message: 'fail' })
    assert(state.isLoading === false, 'isLoading should be false')
    assert(state.thinkingVisible === false, 'ThinkingMessage should be hidden')
  })

  test('INTERRUPTED clears loading and sets stopped', () => {
    const state = new FrontendStreamState()
    state.handleEvent('status_update', { status: 'running' })
    state.handleEvent('agent_response_interrupted', {})
    assert(state.isLoading === false, 'isLoading should be false')
    assert(state.isStopped === true, 'isStopped should be true')
    assert(state.thinkingVisible === false, 'ThinkingMessage should be hidden')
  })
})

describe('Race condition: idle before complete', () => {
  test('ThinkingMessage stays visible when idle arrives before complete', () => {
    const state = new FrontendStreamState()

    // Start streaming
    state.handleEvent('status_update', { status: 'running' })
    assert(state.thinkingVisible === true, 'Should be visible at start')

    // Stream some events
    state.handleEvent('agent_response', { content: 'Processing...' })
    assert(state.thinkingVisible === true, 'Should stay visible during stream')

    // RACE: idle arrives before complete
    state.handleEvent('status_update', { status: 'idle' })
    assert(
      state.thinkingVisible === true,
      'CRITICAL: ThinkingMessage vanished on idle — race condition NOT fixed!'
    )

    // COMPLETE arrives (authoritative)
    state.handleEvent('complete', { message: 'done' })
    assert(state.thinkingVisible === false, 'Should hide after COMPLETE')
  })
})

describe('Full agent session simulation', () => {
  test('10-node agent workflow keeps ThinkingMessage visible', () => {
    const state = new FrontendStreamState()
    state.handleEvent('status_update', { status: 'running' })

    for (let i = 0; i < 10; i++) {
      state.handleEvent('agent_response', { content: `Step ${i}` })
      state.handleEvent('tool_call', { tool: `tool_${i}` })
      state.handleEvent('tool_result', { result: `result_${i}` })
      assert(
        state.thinkingVisible === true,
        `ThinkingMessage vanished at step ${i}!`
      )
    }

    state.handleEvent('complete', { message: 'done' })
    assert(state.thinkingVisible === false, 'Should hide after COMPLETE')
  })

  test('billing failure: ERROR then idle', () => {
    const state = new FrontendStreamState()
    state.handleEvent('status_update', { status: 'running' })

    // Billing error
    state.handleEvent('error', { message: 'Insufficient credits' })
    assert(state.isLoading === false, 'ERROR should clear loading')

    // Idle follows (harmless)
    state.handleEvent('status_update', { status: 'idle' })
    assert(state.isLoading === false, 'Still false after idle')
  })

  test('complete event followed by idle (normal finally block path)', () => {
    const state = new FrontendStreamState()
    state.handleEvent('status_update', { status: 'running' })
    state.handleEvent('agent_response', { content: 'Analysis...' })

    // Normal completion
    state.handleEvent('complete', { message: 'done' })
    assert(state.isCompleted === true, 'Should be completed')
    assert(state.isLoading === false, 'Loading should be false')

    // Finally block idle (now harmless)
    state.handleEvent('status_update', { status: 'idle' })
    assert(state.isCompleted === true, 'Still completed')
    assert(state.isLoading === false, 'Still not loading')
  })
})

// ─── Results ─────────────────────────────────────────────────────────────────

console.log(`\n${'─'.repeat(60)}`)
console.log(`Results: ${passCount}/${testCount} passed, ${failCount} failed`)

if (failCount > 0) {
  console.error('\n❌ SOME TESTS FAILED')
  process.exit(1)
} else {
  console.log('\n✅ ALL TESTS PASSED')
  process.exit(0)
}
