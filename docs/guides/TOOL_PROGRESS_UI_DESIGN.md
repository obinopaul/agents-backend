# Tool Execution Progress — Production Design Specification

> **Design Philosophy: "Signal Flow"** — Inspired by electronic circuit diagrams and recording studio signal chain meters. Progress is communicated through spatial density and signal intensity, not through generic spinners or status badges. The tool execution state is a living signal — flowing through the interface like current through a board.

---

## 1. Existing Architecture Analysis

### What Already Exists (and is excellent)

The current build panel is a **simulator-style viewport** — a rectangular panel with macOS-style traffic light dots (red/yellow/green), a dynamic title bar, and content that swaps contextually:

| Component | Visual Identity | Strength |
|-----------|----------------|----------|
| **Build Panel** (`agent-build.tsx`) | macOS window chrome, `sky-blue` title bar, content area swaps between CodeEditor / Terminal / Browser / DiffEditor / iframes | Unique — looks like a real IDE window embedded in the chat |
| **Action Cards** (`action.tsx`) | Dark pill cards (`bg-firefly dark:bg-[#000000]/50`), icon + title + value, expand on click, `animate-fadeIn` entrance | Clean, contextual, shows exactly what tool is doing |
| **Task Plan** (`agent-task.tsx`) | Vertical checklist with `firefly/sky-blue` fill, progress bar at bottom | Good for macro progress (what tasks remain) |
| **Step Navigation** (`agent-step.tsx`) | Plan → Build → Result horizontal stepper with circular icons | Clear state machine at high level |
| **SubAgent Container** (`subagent-container.tsx`) | Framer Motion card, gradient header, indeterminate shimmer progress bar, collapsible | Effective for nested agent flows |

### What's Missing

The gap is between the **macro** level (Plan/Build/Result stepper, task checklist) and the **micro** level (individual Action cards + Build Panel content). There's no **meso** layer — nothing that shows:

1. **Execution rhythm** — how fast are tools firing, are we in a burst or a lull?
2. **Tool chain context** — what sequence of tools led here, how many remain in this thought cycle?
3. **Operational state during latency** — when a single tool takes 5-15 seconds, the UI goes silent (the Build Panel shows old content, the Action card sits static)
4. **Quantitative progress** — how much work has been done in this build phase (file operations count, search queries made, terminal commands run)

---

## 2. Design: The Signal Rail

### Concept

A thin, persistent **horizontal signal rail** that lives directly *above* the Build Panel (inside the same white/black container card). It replaces the dead space between the traffic-light chrome bar and the content viewport.

It is NOT a progress bar. It is a **signal meter** — a dense, information-rich strip that shows the execution pulse in real time.

```
┌─────────────────────────────────────────────────────────┐
│ ● ● ●        ⚡ Reading main.py                        │  ← Title bar (existing)
├─────────────────────────────────────────────────────────┤
│ ▓▓▓▓▓▓▓▓▓░░░░  12 ops  ·  read 4  ·  write 2  ·  bash 3  ·  3.2s │  ← SIGNAL RAIL (new)
├─────────────────────────────────────────────────────────┤
│                                                         │
│           [ Code Editor / Terminal / Browser ]           │  ← Content viewport (existing)
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Signal Rail Anatomy

The rail is **32px tall**, sits in a `bg-firefly/5 dark:bg-sky-blue/5` band, and contains:

#### 2a. Segment Meter (left side)

A horizontal bar of **discrete segments**, one per tool call in the current build phase. Each segment is a tiny rectangle (4-6px wide, 12px tall) that fills with color based on status:

| Segment State | Color | Visual |
|---------------|-------|--------|
| Completed | `firefly dark:sky-blue` (solid) | `▓` |
| Active (executing) | `sky-blue-2` with pulse animation | `█` breathing |
| Pending (queued by agent) | `firefly/20 dark:sky-blue/20` | `░` |

This creates a **waveform-like visualization** — you see at a glance how many tools have executed, which one is active, and the overall density of the build phase. It fills from left→right as tools complete.

```css
/* Segment styling */
.signal-segment {
  width: 5px;
  height: 12px;
  border-radius: 1px;
  transition: background-color 200ms ease-out;
}

.signal-segment--completed {
  @apply bg-firefly dark:bg-sky-blue;
}

.signal-segment--active {
  @apply bg-sky-blue-2;
  animation: breathing-fill 1.5s ease-in-out infinite;
}

.signal-segment--pending {
  @apply bg-firefly/20 dark:bg-sky-blue/20;
}
```

The segments appear with `animate-scaleIn` (existing in `animations.css`) as each new tool call arrives. When a tool completes, its segment transitions from breathing to solid. This creates a cascading fill effect — like a VU meter or an equalizer bar.

#### 2b. Execution Stats (right side)

Small monospace-style counters showing real-time operational metrics. Typography: `text-[11px] font-medium tracking-wide` using the system sans-serif stack (already defined in `global.css`).

```
12 ops  ·  read 4  ·  write 2  ·  bash 3  ·  3.2s
```

Counters use `tabular-nums` for stable layout. Each category uses the **same icon set** from `action.tsx` (the `step_icon` switch) but rendered at 10px, inline with text — so `read` shows the same `read-file` icon at miniature scale, `write` shows `create-file`, etc.

The `·` separators use `text-pewter` (from the design system #919eae) — the existing muted color.

The timer (`3.2s`) counts up from when the current tool started executing, using `requestAnimationFrame` for smooth updates. It resets per tool and uses `text-sky-blue-4` (#87e7ff) to differentiate it from the counts.

---

## 3. Design: The Pulse Indicator

### Concept

Replace the static `loading` spinner in the Build Panel title bar with a dynamic **pulse ring** that communicates execution intensity.

Currently the title bar shows:
```tsx
<Icon name="loading" className="animate-spin fill-black size-[18px]" />
```

Replace with a **concentric ring indicator**:

```tsx
<div className="relative size-[18px] flex items-center justify-center">
  {/* Outer ring — slow rotation, represents the build phase */}
  <div className="absolute inset-0 rounded-full border-2 border-firefly/30 dark:border-sky-blue/30" />
  
  {/* Inner ring — speed varies with tool execution cadence */}
  <motion.div 
    className="absolute inset-[2px] rounded-full border-2 border-t-transparent border-sky-blue-2"
    animate={{ rotate: 360 }}
    transition={{ 
      duration: pulseSpeed,  // 0.6s during execution, 2.5s during idle
      repeat: Infinity, 
      ease: "linear" 
    }}
  />
  
  {/* Center dot — solid when executing, breathing when idle */}
  <div className={cn(
    "size-1.5 rounded-full",
    isToolExecuting 
      ? "bg-sky-blue-2" 
      : "bg-firefly/40 dark:bg-sky-blue/40 animate-pulse"
  )} />
</div>
```

The key insight: **spin speed reflects execution cadence**. When tools are firing rapidly (< 2s apart), the inner ring spins fast (0.6s rotation). When there's a latency gap (> 5s), it slows to 2.5s. This creates a subconscious signal — the user feels the execution rhythm without needing to read any text.

The transition between speeds uses framer-motion's `transition.duration` dynamic change — it interpolates smoothly.

---

## 4. Design: Action Card Micro-State

### Enriching Existing Action Cards

The existing Action cards in `action.tsx` are excellent. But they currently have no concept of "in progress" vs "completed" — every card looks the same once rendered.

Add a **left-edge indicator** — a 3px vertical bar on the left side of the card:

```tsx
// Inside action.tsx return, add before the content div:
<div className={cn(
  "absolute left-0 top-2 bottom-2 w-[3px] rounded-full transition-colors duration-300",
  isCurrentlyExecuting && "bg-sky-blue-2 animate-pulse",
  isCompleted && "bg-sky-blue dark:bg-sky-blue",
  !isCurrentlyExecuting && !isCompleted && "bg-transparent"
)} />
```

This is minimal and surgical — it doesn't change the existing card layout at all. But when you scan the chat timeline, you can instantly distinguish:
- **Breathing cyan bar** = this tool is executing right now
- **Solid bar** = completed
- **No bar** = historical/static

The active card also gets a subtle `ring-1 ring-sky-blue-2/30` to create a soft glow boundary, matching the existing `shadow-sm` but making it directional.

---

## 5. Design: Latency Awareness Overlay

### When a Tool Takes > 8 Seconds

Instead of showing nothing (current behavior), the Build Panel viewport gains a **frosted overlay** with contextual information:

```tsx
{isLongRunningTool && (
  <motion.div 
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    transition={{ duration: 0.6 }}
    className="absolute inset-0 z-10 backdrop-blur-[2px] bg-black/20 dark:bg-black/40 
               flex flex-col items-center justify-center gap-3"
  >
    {/* Tool-specific contextual message */}
    <div className="flex items-center gap-2 px-4 py-2 bg-firefly/80 dark:bg-charcoal/80 
                    rounded-lg backdrop-blur-md border border-sky-blue/20">
      {currentToolIcon}  {/* Same icon from action.tsx step_icon */}
      <span className="text-white text-sm font-medium">
        {contextualMessage}
      </span>
    </div>
    
    {/* Elapsed time with tick animation */}
    <div className="flex items-center gap-1.5 text-sky-blue-4 text-xs font-mono">
      <span className="tabular-nums">{elapsedTime}</span>
      <span className="animate-pulse">│</span>  {/* Terminal cursor blink */}
    </div>
  </motion.div>
)}
```

Contextual messages are tool-specific:
- `TOOL.BASH` → "Executing command..."
- `TOOL.WRITE` → "Writing file..."
- `TOOL.WEB_SEARCH` → "Searching the web..."
- `TOOL.IMAGE_GENERATE` → "Generating image..."
- `TOOL.DEEP_RESEARCH` → "Deep research in progress..."
- MCP tools → "Running {tool_display_name}..."

The overlay uses `backdrop-blur-[2px]` — just barely frosted, so the underlying CodeEditor/Terminal content is still visible but pushed to background. This communicates "yes, content is being processed" without a hard modal.

The cursor blink (`│`) is a nod to the terminal aesthetic that already exists in the app.

---

## 6. Backend Changes Required

### 6a. New Socket Event: `tool_execution_stats`

Emit alongside existing events from `stream_buffer.py`:

```python
# In StreamBuffer, when processing TOOL_CALL events
tool_stats = {
    "type": "tool_execution_stats",
    "data": {
        "total_tools_called": self._tool_count,
        "tools_by_category": self._tool_category_counts,  # {"read": 4, "write": 2, ...}
        "current_tool_index": self._current_tool_index,
        "current_tool_start_time": time.time(),
        "current_tool_name": tool_name,
        "build_phase_start_time": self._build_phase_start
    }
}
```

Categories are derived from the existing TOOL enum mappings (same categories used in `agent-build.tsx`'s `tab` switch):
- `read`: READ, GLOB, LS, GREP
- `write`: WRITE, EDIT, MULTI_EDIT, APPLY_PATCH, STR_REPLACE_BASED_EDIT
- `bash`: BASH, BASH_INIT, BASH_VIEW, BASH_STOP, BASH_KILL, SHELL_EXEC
- `browse`: VISIT, BROWSER_*, WEB_SEARCH, WEB_BATCH_SEARCH
- `generate`: IMAGE_GENERATE, VIDEO_GENERATE, AUDIO_TRANSCRIBE
- `search`: TAVILY_SEARCH, ARXIV_SEARCH, PAPER_SEARCH, etc.
- `deploy`: STATIC_DEPLOY, REGISTER_DEPLOYMENT
- `agent`: SUB_AGENT_*, CODEX_*, CLAUDE_CODE, DEEP_RESEARCH
- `other`: MCP_TOOL, TASK, SEQUENTIAL_THINKING

### 6b. Tool Timing Metadata

Add `started_at` and `completed_at` timestamps to each `TOOL_CALL` / `TOOL_RESULT` event pair:

```python
# When emitting TOOL_CALL
event_data["started_at"] = time.time()

# When emitting TOOL_RESULT  
event_data["completed_at"] = time.time()
event_data["duration_ms"] = int((time.time() - started_at) * 1000)
```

This enables the frontend to calculate tool duration without its own timers, and to show historical timing in the Action cards.

---

## 7. Frontend State Changes

### 7a. New State Slice: `toolProgress`

```typescript
// state/slice/toolProgress.ts
interface ToolProgressState {
  totalToolsCalled: number
  toolsByCategory: Record<string, number>
  currentToolIndex: number
  currentToolStartTime: number | null
  currentToolName: string | null
  buildPhaseStartTime: number | null
  recentToolDurations: number[]  // Last 5 tool durations for cadence calc
}

const initialState: ToolProgressState = {
  totalToolsCalled: 0,
  toolsByCategory: {},
  currentToolIndex: 0,
  currentToolStartTime: null,
  currentToolName: null,
  buildPhaseStartTime: null,
  recentToolDurations: []
}
```

### 7b. Selectors

```typescript
export const selectToolExecutionCadence = createSelector(
  [selectRecentToolDurations],
  (durations) => {
    if (durations.length < 2) return 'slow'
    const avgDuration = durations.reduce((a, b) => a + b, 0) / durations.length
    if (avgDuration < 2000) return 'fast'    // < 2s avg → fast spin
    if (avgDuration < 5000) return 'normal'  // 2-5s avg → normal
    return 'slow'                            // > 5s avg → slow spin
  }
)

export const selectIsLongRunningTool = createSelector(
  [selectCurrentToolStartTime],
  (startTime) => {
    if (!startTime) return false
    return Date.now() - startTime > 8000
  }
)
```

---

## 8. Component Hierarchy

```
AgentBuild (existing — modified)
├── TitleBar (existing — replace spinner with PulseIndicator)
│   └── PulseIndicator (new)
├── SignalRail (new — 32px band between title and content)
│   ├── SegmentMeter (new — left side, waveform segments)
│   └── ExecutionStats (new — right side, operation counters)
├── ContentViewport (existing)
│   ├── CodeEditor / Terminal / Browser / etc (existing)
│   └── LatencyOverlay (new — conditional, appears after 8s)
└── AgentController (existing)
```

---

## 9. Implementation Phases

### Phase 1: Signal Rail + Execution Stats (Backend + Frontend)
**Files to modify:**
- `backend/app/agent/stream_buffer.py` — Add tool counting and `tool_execution_stats` event
- `frontend/src/state/slice/toolProgress.ts` — New state slice
- `frontend/src/components/agent/signal-rail.tsx` — New component
- `frontend/src/components/agent/agent-build.tsx` — Insert SignalRail between title bar and content

**Estimated effort:** 2-3 days

### Phase 2: Pulse Indicator + Action Card Enhancement
**Files to modify:**
- `frontend/src/components/agent/pulse-indicator.tsx` — New component
- `frontend/src/components/agent/agent-build.tsx` — Replace `<Icon name="loading" />` with `<PulseIndicator />`
- `frontend/src/components/agent/action.tsx` — Add left-edge indicator, pass `isCurrentlyExecuting` prop

**Estimated effort:** 1-2 days

### Phase 3: Latency Overlay
**Files to modify:**
- `frontend/src/components/agent/latency-overlay.tsx` — New component
- `frontend/src/components/agent/agent-build.tsx` — Add overlay inside content viewport

**Estimated effort:** 1 day

### Phase 4: Tool Timing Metadata
**Files to modify:**
- `backend/src/graph/nodes.py` — Add timing metadata to tool events
- `frontend/src/components/agent/action.tsx` — Display duration badge in completed cards

**Estimated effort:** 1 day

---

## 10. Color Palette Reference

All colors used in this design are drawn from the existing design system in `global.css`:

| Token | Hex | Usage in this design |
|-------|-----|---------------------|
| `firefly` | `#0f2b33` | Completed segments (light mode), stat text |
| `sky-blue` | `#bee6f0` | Completed segments (dark mode), ring borders |
| `sky-blue-2` | `#a6ffff` | Active segment pulse, active card edge, center dot |
| `sky-blue-4` | `#87e7ff` | Timer text, elapsed time display |
| `charcoal` | `#181e1c` | Overlay background |
| `pewter` | `#919eae` | Separator dots `·` in stats |
| `mist` | `#d5dce0` | Subtle borders, light mode segment backgrounds |

No new colors introduced. No new fonts. No purple gradients. No centered layouts. No Inter font.

---

## 11. Animation Reference

All animations used are from the existing `animations.css` or framer-motion (already a dependency):

| Animation | Source | Usage |
|-----------|--------|-------|
| `animate-scaleIn` | `animations.css` | Segment appearance |
| `animate-pulse` | `animations.css` | Active segment breathing |
| `breathing-fill` | `global.css` | Active segment (reuses existing `animate-breathing-fill`) |
| `motion.div animate` | framer-motion | Ring rotation, overlay entrance, content transitions |
| `tabular-nums` | CSS font-feature | Stable stat counter layout |

No new animation libraries. No Lottie. No canvas-based rendering.

---

## 12. What This Design Does NOT Do

- Does **not** replace the Build Panel viewport or Action cards
- Does **not** add a sidebar, modal, or pop-up
- Does **not** introduce new icon libraries or icon styles
- Does **not** change the Plan → Build → Result stepper
- Does **not** add a timeline/list of all tools (the chat already does this via Action cards)
- Does **not** use generic progress indicators (no circular spinners, no percentage bars, no check-circle icons)

---

## 13. Design Rationale

**Why a signal meter instead of a progress bar?**
A progress bar implies known total work. Agent tool execution is open-ended — we don't know how many tools will be called. A segment meter grows organically, showing what *has happened* rather than predicting what *will happen*.

**Why tool-category counters instead of a single "12 tools" count?**
The existing Action cards already show each individual tool. Repeating that list is redundant. Category counters add a new dimension — letting the user see at a glance "this build is write-heavy" or "lots of web searches happening" without scrolling through the chat.

**Why vary the pulse ring speed?**
Users reported the app feeling "stuck" during latency. A uniform spinner provides no information about whether execution is fast or slow. By varying the ring speed with actual execution cadence, we create an ambient signal that communicates throughput without requiring the user to read anything.

**Why a frosted overlay instead of a loading skeleton?**
The Build Panel already shows rich content (code, terminals, browsers). A skeleton would destroy that context. A subtle frost keeps the content visible while signaling "still processing" — the same pattern used in iOS during background processing.

---

## 14. Implementation Status

**Status: IMPLEMENTED** (all phases completed)

### Files Created
| File | Purpose |
|------|---------|
| `frontend/src/state/slice/toolProgress.ts` | Redux slice with segments, category counts, timing, cadence selectors |
| `frontend/src/components/agent/pulse-indicator.tsx` | Dynamic concentric ring (replaces static spinner) |
| `frontend/src/components/agent/signal-rail.tsx` | 32px signal meter band with segments + execution stats |
| `frontend/src/components/agent/latency-overlay.tsx` | Frosted overlay after 8s with contextual message |

### Files Modified
| File | Change |
|------|--------|
| `backend/app/agent/stream_buffer.py` | Added tool counting, timing metadata, `_categorize_tool()`, `tool_stats` in `tool_call` event |
| `frontend/src/state/reducer.ts` | Added `toolProgress: toolProgressReducer` |
| `frontend/src/state/index.ts` | Added `export * from './slice/toolProgress'` |
| `frontend/src/hooks/use-app-events.tsx` | Wired `recordToolCall` in TOOL_CALL, `recordToolResult` in TOOL_RESULT, `resetToolProgress` in COMPLETE/reset |
| `frontend/src/components/agent/agent-build.tsx` | Replaced spinner with PulseIndicator, inserted SignalRail + LatencyOverlay |
| `frontend/src/components/agent/action.tsx` | Added left-edge state indicator bar (3px, active pulse / completed solid) |
