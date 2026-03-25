  Key Findings:

  1. Backend Event Emission - The AgentController in src/ii_agent/controller/agent_controller.py is the brain that emits
   TOOL_CALL, TOOL_RESULT, and AGENT_RESPONSE events through an event stream with subscriber pattern.
  2. WebSocket Transport - Events flow through SocketIOSubscriber which broadcasts to all clients in a session room via
  the chat_event channel.
  3. Frontend Event Processing - The useAppEvents hook (1443 lines) is the CORE that processes all events, creates Redux
   messages with ActionStep data, and manages subagent hierarchy.
  4. The Slideshow System consists of:
    - AgentBuild - The container that shows Browser/Terminal/Code/Slides based on tool type
    - AgentController - The navigation with auto-advance ("Live Update") functionality
    - Together they create the real-time activity feed you see in the Build section
  5. Rendering Components:
    - Action component - Maps 80+ tools to icons, titles, and values
    - MessageContent - Renders user/assistant/think messages
    - Dynamic viewers: Browser, Terminal, CodeEditor, DiffCodeEditor, SearchBrowser

  The document includes complete data flow diagrams and a file reference index for both backend and frontend.

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Ready to code?

 Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 II-Agent Rendering Logic - Comprehensive Investigation & Architecture Documentation

 Executive Summary

 This document provides a complete investigation into how the II-Agent project renders AI messages, tool calls, and the
  Agent Activity Slideshow (the progress indicator in the Build section). The system uses a sophisticated event-driven
 architecture with WebSocket communication, Redux state management, and specialized React components.

 ---
 Table of Contents

 1. #1-high-level-architecture-overview
 2. #2-backend-event-emission-system
 3. #3-websocket-transport-layer
 4. #4-frontend-redux-state-management
 5. #5-frontend-event-processing-useappevents
 6. #6-frontend-rendering-components
 7. #7-the-slideshow-system---agent-activity-progress
 8. #8-complete-data-flow-diagrams
 9. #9-file-reference-index

 ---
 1. High-Level Architecture Overview

 The rendering system follows this flow:

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                         COMPLETE RENDERING PIPELINE                          │
 └─────────────────────────────────────────────────────────────────────────────┘

 BACKEND (Python)                    TRANSPORT                 FRONTEND (React/Redux)
 ┌──────────────────┐               ┌──────────┐              ┌───────────────────┐
 │ AgentController  │               │ Socket.IO│              │ WebSocketContext  │
 │ - run_agent_async│──TOOL_CALL───▶│ Server   │──chat_event─▶│ - handleEvent()   │
 │ - add_tool_result│──TOOL_RESULT─▶│          │              │                   │
 │ - emit events    │──AGENT_RESP──▶│          │              └─────────┬─────────┘
 └──────────────────┘               └──────────┘                        │
                                                                        ▼
                                                               ┌───────────────────┐
                                                               │  useAppEvents     │
                                                               │  - Switch on type │
                                                               │  - Dispatch Redux │
                                                               └─────────┬─────────┘
                                                                         │
                                                                         ▼
                                                               ┌───────────────────┐
                                                               │   Redux Store     │
                                                               │  - messages[]     │
                                                               │  - currentAction  │
                                                               │  - buildStep      │
                                                               └─────────┬─────────┘
                                                                         │
                                     ┌───────────────────────────────────┼───────────────────────────────────┐
                                     │                                   │                                   │
                                     ▼                                   ▼                                   ▼
                            ┌───────────────┐                   ┌───────────────┐                   ┌───────────────┐
                            │ ChatMessage   │                   │ AgentBuild    │                   │AgentController│
                            │ + MessageContent                  │ (Slideshow)   │                   │ (Navigation)  │
                            │ + Action      │                   │ - Browser     │                   │ - Auto-advance│
                            └───────────────┘                   │ - Terminal    │                   │ - Step slider │
                                                                │ - CodeEditor  │                   └───────────────┘
                                                                └───────────────┘

 ---
 2. Backend Event Emission System

 2.1 Core Event Structure

 File: src/ii_agent/core/event.py

 class RealtimeEvent(BaseModel):
     id: UUID = Field(default_factory=uuid4)
     type: EventType                    # TOOL_CALL, TOOL_RESULT, AGENT_RESPONSE, etc.
     session_id: Optional[UUID] = None
     run_id: Optional[UUID] = None
     content: dict[str, Any]            # Event-specific payload
     timestamp: Optional[float] = Field(default_factory=time.time)

 EventType Enum (25+ types):
 - TOOL_CALL - Tool execution request
 - TOOL_RESULT - Tool execution response
 - AGENT_RESPONSE - LLM text response
 - AGENT_THINKING - Extended thinking output
 - COMPLETE - Task completion
 - STATUS_UPDATE - Agent status changes
 - USER_MESSAGE - User input
 - METRICS_UPDATE - Token usage metrics
 - And more...

 2.2 Agent Controller - Event Orchestration

 File: src/ii_agent/controller/agent_controller.py

 This is the brain of event emission. Key methods:

 Tool Call Emission (Lines 273-285):

 await self.event_stream.publish(
     RealtimeEvent(
         type=EventType.TOOL_CALL,
         session_id=self.session_id,
         run_id=self.run_id,
         content={
             "tool_call_id": tool_call.tool_call_id,
             "tool_name": tool_call.tool_name,
             "tool_input": tool_call.tool_input,
             "tool_display_name": tool.display_name,  # Human-readable name
         },
     )
 )

 Tool Result Emission - add_tool_call_result() (Lines 442-506):

 async def add_tool_call_result(
     self, tool_call: ToolCallParameters, tool_result: ToolResult
 ):
     # Format result based on content type (text, image, multi-modal)
     await self.event_stream.publish(
         RealtimeEvent(
             type=EventType.TOOL_RESULT,
             session_id=self.session_id,
             run_id=self.run_id,
             content={
                 "tool_call_id": tool_call.tool_call_id,
                 "tool_name": tool_call.tool_name,
                 "tool_input": tool_call.tool_input,
                 "result": user_display_content,  # The actual output
                 "is_error": is_error,
             },
         )
     )

 Agent Response Emission (Lines 186-193):

 await self.event_stream.publish(
     RealtimeEvent(
         type=EventType.AGENT_RESPONSE,
         session_id=self.session_id,
         run_id=self.run_id,
         content={"text": text_result.text},
     )
 )

 2.3 Event Stream & Subscriber Pattern

 File: src/ii_agent/core/event_stream.py

 The AsyncEventStream manages event distribution:

 async def publish(self, event: RealtimeEvent) -> None:
     # 1. Process through hooks (can modify/filter events)
     processed_event = await self._hook_registry.process_event(event)
     if processed_event is None:
         return  # Event filtered out

     # 2. Notify all subscribers asynchronously
     for subscriber in self._subscribers:
         asyncio.create_task(subscriber.handle_event(processed_event))

 Three Subscriber Types:
 1. SocketIOSubscriber (src/ii_agent/subscribers/socketio_subscriber.py) - Broadcasts to WebSocket
 2. DatabaseSubscriber (src/ii_agent/subscribers/database_subscriber.py) - Persists events
 3. MetricsSubscriber (src/ii_agent/subscribers/metrics_subscriber.py) - Tracks token usage

 ---
 3. WebSocket Transport Layer

 3.1 Socket.IO Server

 File: src/ii_agent/server/socket/socketio.py

 Event Broadcasting:
 async def _emit_chat_event(self, room: str, event_type: str, content: Dict[str, Any]):
     await self.sio.emit(
         "chat_event",                    # Single event channel
         {"type": event_type, "content": content},
         room=room,                       # Room = session_id
     )

 Session Management:
 - Each session ID = Socket.IO room
 - Multiple clients can join same session
 - JWT authentication on connect

 3.2 SocketIO Subscriber - Event-to-WebSocket Bridge

 File: src/ii_agent/subscribers/socketio_subscriber.py

 async def handle_event(self, event: RealtimeEvent) -> None:
     event_data = {
         "type": event.type,
         "content": event.content,
     }
     room = str(event.session_id)
     await self.sio.emit("chat_event", event_data, room=room)

 ---
 4. Frontend Redux State Management

 4.1 Store Configuration

 File: frontend/src/state/store.ts

 11 Redux Slices:
 - messages - Agent and user messages
 - agent - Execution state (buildStep, isCompleted, wsConnectionState)
 - editor - Action data and build step counter
 - ui - Tabs, loading, view mode
 - workspace - URLs and workspace info
 - settings - Tool settings, model selection
 - sessions - Session management
 - files - Uploaded files
 - user - Authentication
 - favorites - Favorited sessions

 4.2 Key Slices for Rendering

 Messages Slice (frontend/src/state/slice/messages.ts):

 interface MessagesState {
     messages: Message[]
     editingMessage?: Message
 }

 // Message structure
 interface Message {
     id: string
     role: 'user' | 'assistant' | 'system'
     content?: string
     timestamp: number
     action?: ActionStep              // Tool call data - CRITICAL for slideshow
     agentContext?: AgentContext      // Which agent (main/subagent)
     isThinkMessage?: boolean         // Extended thinking
 }

 // ActionStep structure - drives the slideshow
 interface ActionStep {
     type: TOOL                       // e.g., TOOL.BROWSER_CLICK
     data: {
         tool_call_id?: string
         tool_name?: string
         tool_display_name?: string
         tool_input?: {...}           // Tool parameters
         result?: string | Record     // Tool output (after TOOL_RESULT)
         isResult?: boolean           // Has result been attached?
     }
 }

 Editor Slice (frontend/src/state/slice/editor.ts):

 interface EditorState {
     currentActionData?: ActionStep   // Currently displayed action in slideshow
     currentBuildStep: number         // Step counter (1, 2, 3...)
     requestAction?: ActionStep       // Action user clicked on
 }

 Agent Slice (frontend/src/state/slice/agent.ts):

 interface AgentState {
     buildStep: BUILD_STEP            // THINKING | PLAN | BUILD
     isCompleted: boolean
     wsConnectionState: WebSocketConnectionState
     resultUrl: string                // Deployment URL
 }

 enum BUILD_STEP {
     THINKING = 'thinking',
     PLAN = 'plan',
     BUILD = 'build'
 }

 ---
 5. Frontend Event Processing (useAppEvents)

 5.1 The Central Event Handler

 File: frontend/src/hooks/use-app-events.tsx (1443 lines)

 This is the CORE of frontend rendering. It receives WebSocket events and updates Redux state.

 Event Processing Flow:

 const handleEvent = useCallback((data: WebSocketEvent, ignoreClickAction?: boolean) => {
     switch (data.type) {
         case AgentEvent.TOOL_CALL:
             // Create message with action, dispatch addMessage
             // Track subagent hierarchy
             // Call handleClickAction to update slideshow
             break;

         case AgentEvent.TOOL_RESULT:
             // Find matching tool call message
             // Attach result to message.action.data.result
             // Dispatch updateMessage
             break;

         case AgentEvent.AGENT_RESPONSE:
             // Create text message, dispatch addMessage
             break;

         case AgentEvent.COMPLETE:
             // Set completed, switch to RESULT tab
             break;
         // ... 20+ more event types
     }
 }, [dispatch])

 5.2 Tool Call Processing (Lines 337-499)

 case AgentEvent.TOOL_CALL: {
     // Detect subagent tools
     const isSubagentTool = [
         TOOL.SUB_AGENT, TOOL.SUB_AGENT_RESEARCHER,
         TOOL.DESIGN_DOCUMENT_AGENT, TOOL.TASK, TOOL.CODEX_AGENT
     ].includes(data.content.tool_name)

     // If subagent: create new agent context, push to stack
     if (isSubagentTool) {
         const newAgentContext: AgentContext = {
             agentId: `${parentId}-${agentName}-${toolCallId}`,
             agentType: 'subagent',
             parentAgentId: parentContext.agentId,
             nestingLevel: parentContext.nestingLevel + 1,
             status: 'running'
         }
         activeAgentsRef.current.set(subagentId, newAgentContext)
         agentStackRef.current.push(subagentId)
     }

     // Create message with action
     const message: Message = {
         id: data.id,
         role: 'assistant',
         action: {
             type: data.content.tool_name as TOOL,
             data: { ...data.content, agentContext }
         },
         timestamp: Date.now(),
         agentContext
     }

     safeDispatch(addMessage(message))

     // Update slideshow view
     if (!ignoreClickAction) {
         handleClickAction(message.action)  // Updates currentActionData
     }
 }

 5.3 Tool Result Processing (Lines 505-844)

 case AgentEvent.TOOL_RESULT: {
     // Find the matching tool call message (search backwards)
     let lastToolCallMessageIndex = -1
     for (let i = messages.length - 1; i >= 0; i--) {
         if (messages[i].action?.type === data.content.tool_name &&
             !messages[i].action?.data?.isResult) {
             lastToolCallMessageIndex = i
             break
         }
     }

     if (lastToolCallMessageIndex !== -1) {
         const lastToolCallMessage = cloneDeep(messages[lastToolCallMessageIndex])

         // Attach result to the action
         lastToolCallMessage.action.data.result = data.content.result
         lastToolCallMessage.action.data.isResult = true

         safeDispatch(updateMessage(lastToolCallMessage))
     }

     // Handle subagent completion if applicable
     if (isSubagentCompletingTool && hasCompletionIndicator) {
         // Mark subagent as completed
         // Update all messages with that agentId
         // Pop from stack
     }
 }

 5.4 handleClickAction - Slideshow Navigation (Lines 1267-1440)

 const handleClickAction = useCallback(
     debounce((data: ActionStep | undefined) => {
         if (!data) return

         // Route to appropriate view based on tool type
         switch (data.type) {
             case TOOL.WEB_SEARCH:
             case TOOL.BROWSER_USE:
             case TOOL.BROWSER_CLICK:
             // ... browser tools
                 dispatch(requestAction(data))           // Set action for display
                 dispatch(setSelectedBuildStep(BUILD_STEP.BUILD))
                 break

             case TOOL.BASH:
             case TOOL.LS:
             case TOOL.GLOB:
                 dispatch(setBuildStep(BUILD_STEP.BUILD))
                 break

             case TOOL.TODO_WRITE:
                 dispatch(setBuildStep(BUILD_STEP.PLAN))
                 break

             case TOOL.REGISTER_DEPLOYMENT:
                 const urls = extractUrls(data.data?.result)
                 dispatch(setResultUrl(urls[0]))
                 dispatch(setBuildStep(BUILD_STEP.BUILD))
                 break
         }
     }, 50),
     [dispatch]
 )

 ---
 6. Frontend Rendering Components

 6.1 Action Component - Tool Activity Renderer

 File: frontend/src/components/agent/action.tsx

 This component transforms raw tool data into the polished UI you see in the chat feed.

 Props:

 interface ActionProps {
     workspaceInfo: string
     type: TOOL                   // The tool type
     value: ActionStep['data']    // Tool call data
     onClick: () => void          // Navigate to Build view
 }

 Icon Mapping (Lines 29-190):

 Maps 80+ tool types to visual icons:
 switch (type) {
     case TOOL.BROWSER_CLICK:
     case TOOL.BROWSER_NAVIGATE:
     case TOOL.BROWSER_USE:
         return <Icon name="browsing" />

     case TOOL.BASH:
     case TOOL.LS:
     case TOOL.GLOB:
         return <Icon name="terminal" />

     case TOOL.READ:
         return <Icon name="read-file" />

     case TOOL.WRITE:
         return <Icon name="create-file" />

     case TOOL.WEB_SEARCH:
         return <Icon name="search-2" />

     case TOOL.IMAGE_GENERATE:
         return <Icon name="gen-image" />
     // ... 70+ more mappings
 }

 Title Generation (Lines 192-428):

 // Tool name → Human-readable title
 case TOOL.BASH: return "Bash"
 case TOOL.WEB_SEARCH: return "Searching"
 case TOOL.BROWSER_NAVIGATE: return "Navigating"
 case TOOL.SLIDE_WRITE: return "Creating Slide"
 case TOOL.IMAGE_GENERATE: return "Generating Image"

 Value Extraction (Lines 430-657):

 // Extract relevant info for display
 case TOOL.READ:
 case TOOL.WRITE:
     return last(value.tool_input?.file_path?.split('/'))  // Just filename

 case TOOL.WEB_SEARCH:
     return value.tool_input?.query  // Search query

 case TOOL.BROWSER_NAVIGATE:
     return value.tool_input?.url  // URL being visited

 Filtering Logic (Lines 659-670):

 Certain tools are hidden from the activity list:
 if ([
     TOOL.COMPLETE,
     TOOL.LIST_HTML_LINKS,
     TOOL.RETURN_CONTROL_TO_USER,
     TOOL.SLIDE_DECK_INIT,
     TOOL.TODO_READ,
     TOOL.TODO_WRITE
 ].includes(type)) {
     return null  // Don't render
 }

 6.2 Message Content Component

 File: frontend/src/components/agent/message-content.tsx

 Renders different message types with role-specific styling:

 // User messages
 {message.role === 'user' && (
     <div className="user-message">
         <Markdown>{message.content}</Markdown>
     </div>
 )}

 // Think messages (collapsible)
 {message.isThinkMessage && (
     <div className="bg-firefly/[0.18]">
         <button onClick={() => toggleThinkMessage(message.id)}>
             {isExpanded ? <ChevronDown /> : <ChevronRight />}
             Thought
         </button>
         {isExpanded && <Markdown>{message.content}</Markdown>}
     </div>
 )}

 // Assistant messages
 {message.role === 'assistant' && !message.isThinkMessage && (
     <Markdown>{message.content}</Markdown>
 )}

 // Action component (tool calls)
 {message.action && (
     <Action
         type={message.action.type}
         value={message.action.data}
         onClick={() => {
             dispatch(setActiveTab(TAB.BUILD))
             handleClickAction(message.action)
         }}
     />
 )}

 6.3 Chat Message Component

 File: frontend/src/components/agent/chat-message.tsx

 Container managing full chat history with subagent grouping:

 // Group messages by agent context
 const groupedMessages = messages.reduce((result, message) => {
     const messageAgentContext = message.agentContext
     const needNewGroup =
         messageAgentContext?.agentId !== currentAgentContext?.agentId

     if (needNewGroup && currentGroup.length > 0) {
         result.push({
             type: currentAgentContext?.agentType === 'subagent'
                 ? 'subagent' : 'main',
             agentContext: currentAgentContext,
             messages: currentGroup
         })
         currentGroup = []
     }
     currentGroup.push(message)
 })

 // Render grouped messages
 {groupedMessages.map(group => (
     group.type === 'subagent'
         ? <SubagentContainer messages={group.messages} />
         : <MainAgentMessages messages={group.messages} />
 ))}

 ---
 7. The "Slideshow" System - Agent Activity Progress

 This is the core feature you asked about - the rectangular box in the Build section that shows tool activities.

 7.1 AgentBuild - The Slideshow Container

 File: frontend/src/components/agent/agent-build.tsx

 This is the main display area in the Build tab that shows tool outputs.

 Redux Connection:

 const currentActionData = useAppSelector(selectCurrentActionData)
 // currentActionData = { type: TOOL, data: { tool_input, result, ... } }

 Tab Determination Logic (Lines 29-131):

 Determines which viewer to show based on tool type:

 const determineTab = () => {
     // BROWSER tab - 35+ browser tools
     if ([
         TOOL.VISIT, TOOL.BROWSER_USE, TOOL.BROWSER_CLICK,
         TOOL.BROWSER_NAVIGATE, TOOL.IMAGE_GENERATE, TOOL.VIDEO_GENERATE,
         // ... 30+ more
     ].includes(currentActionData?.type))
         return 'browser'

     // TERMINAL tab - shell execution tools
     if ([TOOL.BASH, TOOL.BASH_INIT, TOOL.LS, TOOL.GLOB, TOOL.GREP])
         return 'terminal'

     // CODE tab - file editor tools
     if ([TOOL.WRITE, TOOL.EDIT, TOOL.APPLY_PATCH, TOOL.READ])
         return 'code'

     // SLIDE tab - presentation tools
     if ([TOOL.SLIDE_WRITE, TOOL.SLIDE_EDIT, TOOL.SLIDE_APPLY_PATCH])
         return 'slide'

     // SEARCH_BROWSER tab - web search results
     if ([TOOL.WEB_SEARCH, TOOL.WEB_BATCH_SEARCH])
         return 'search_browser'
 }

 Content Rendering (Lines 587-764):

 return (
     <div className="agent-build-container">
         {/* Title Bar */}
         <div className="title-bar">
             <Spinner /> {getHeaderTitle()} {fileName}
         </div>

         {/* Dynamic Content Based on Tab */}
         {tab === 'browser' && (
             <Browser url={browserUrl} screenshot={browserScreenshot} />
         )}

         {tab === 'terminal' && (
             <Terminal result={currentActionData?.data?.result} />
         )}

         {tab === 'code' && !isEditTool && (
             <CodeEditor
                 fileName={fileName}
                 content={fileContent}
                 language={getLanguage(fileName)}
             />
         )}

         {tab === 'code' && isEditTool && (
             <DiffCodeEditor
                 fileName={fileName}
                 oldContent={diffCodeOldContent}
                 newContent={diffCodeNewContent}
             />
         )}

         {tab === 'slide' && (
             <iframe srcDoc={result.content || result?.[0]?.new_content} />
         )}

         {tab === 'search_browser' && (
             <SearchBrowser
                 keyword={tool_input.query}
                 search_results={parseJson(result)}
             />
         )}

         {/* Navigation Controller */}
         <AgentController />
     </div>
 )

 7.2 AgentController - Slideshow Navigation

 File: frontend/src/components/agent/agent-controller.tsx

 This provides the "Live Update" auto-advance functionality.

 Redux Connection:

 const messages = useAppSelector(selectMessages)
 const currentBuildStep = useAppSelector(selectCurrentBuildStep)

 // Filter to get only action-bearing messages
 const actions = messages?.filter(m =>
     m.action &&
     m.action.type !== TOOL.TODO_WRITE &&
     m.action.type !== TOOL.TODO_READ &&
     m.action.type !== TOOL.COMPLETE
 )

 const totalBuildSteps = actions?.length || 0

 Auto-Advance Logic (Lines 47-51):

 useEffect(() => {
     // When new messages arrive and Live Update is on, jump to latest
     if (isLiveUpdate && totalBuildSteps > 0) {
         dispatch(setCurrentBuildStep(totalBuildSteps))
     }
 }, [totalBuildSteps, isLiveUpdate, dispatch])

 Step Sync (Lines 54-59):

 useEffect(() => {
     // When step changes, update currentActionData in Redux
     if (step > 0 && step <= totalBuildSteps && actions) {
         const actionData = actions[step - 1]?.action
         dispatch(setCurrentActionData(actionData))
     }
 }, [step, totalBuildSteps, actions, dispatch])

 UI Controls (Lines 75-139):

 ┌─────────────────────────────────────────────┐
 │  [◄]     Step 3 / 15     [►]                │
 │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
 │                          [Live Update ●]    │
 └─────────────────────────────────────────────┘

 - ◄/► buttons: Manual step navigation (disables auto-advance)
 - Slider: Scrub through history
 - Live Update: Toggle auto-advance to latest step

 7.3 How the Slideshow Works - Step by Step

 1. Tool Call Event Arrives:
   - Backend emits TOOL_CALL event via WebSocket
   - useAppEvents receives event
   - Creates Message with action: { type: TOOL, data: {...} }
   - Dispatches addMessage(message)
   - Calls handleClickAction(message.action)
 2. handleClickAction Updates Slideshow:
   - Dispatches requestAction(action) → sets editor.requestAction
   - Dispatches setSelectedBuildStep(BUILD_STEP.BUILD)
   - UI switches to Build tab
 3. AgentController Auto-Advances:
   - totalBuildSteps increases (new action in messages)
   - If isLiveUpdate, dispatches setCurrentBuildStep(totalBuildSteps)
   - Effect syncs currentActionData from the action at that step
 4. AgentBuild Re-Renders:
   - selectCurrentActionData returns the new action
   - determineTab() calculates which viewer to show
   - Content extraction functions get tool_input and result
   - Appropriate viewer component renders (Browser, Terminal, Code, etc.)
 5. Tool Result Arrives:
   - TOOL_RESULT event updates the message's action.data.result
   - AgentBuild re-renders with the result data
   - Browser shows screenshot, Terminal shows output, Code shows content

 ---
 8. Complete Data Flow Diagrams

 8.1 Tool Call → Slideshow Update

 Backend: agent_controller.py
     │
     ├── execute_tool()
     │
     └── event_stream.publish(TOOL_CALL event)
         │
         ▼
 SocketIOSubscriber
     │
     └── sio.emit("chat_event", {type: "tool_call", content: {...}})
         │
         ▼
 Frontend: WebSocketContext
     │
     └── socket.on("chat_event", handleEventRef.current)
         │
         ▼
 useAppEvents.handleEvent()
     │
     ├── case AgentEvent.TOOL_CALL:
     │   │
     │   ├── Create Message with action: { type: TOOL, data: {...} }
     │   │
     │   ├── safeDispatch(addMessage(message))
     │   │   │
     │   │   └── Redux: state.messages.messages.push(message)
     │   │
     │   └── handleClickAction(message.action)
     │       │
     │       ├── dispatch(requestAction(action))
     │       │   │
     │       │   └── Redux: state.editor.requestAction = action
     │       │
     │       └── dispatch(setSelectedBuildStep(BUILD_STEP.BUILD))
         │
         ▼
 AgentController Component
     │
     ├── actions = messages.filter(m => m.action)  // New action detected
     │
     ├── totalBuildSteps = actions.length  // Increases
     │
     └── useEffect: if (isLiveUpdate) setCurrentBuildStep(totalBuildSteps)
         │
         └── dispatch(setCurrentBuildStep(totalBuildSteps))
             │
             ▼
 AgentController: Step Sync Effect
     │
     └── dispatch(setCurrentActionData(actions[step - 1]?.action))
         │
         └── Redux: state.editor.currentActionData = action
             │
             ▼
 AgentBuild Component
     │
     ├── currentActionData = useAppSelector(selectCurrentActionData)
     │
     ├── tab = determineTab(currentActionData.type)
     │
     └── Render appropriate viewer:
         ├── Browser (screenshot/URL)
         ├── Terminal (command output)
         ├── CodeEditor (file content)
         ├── DiffCodeEditor (edits)
         ├── SearchBrowser (search results)
         └── Slide (HTML presentation)

 8.2 Message Structure Through Pipeline

 BACKEND EVENT:
 {
     type: "tool_call",
     content: {
         tool_call_id: "call_abc123",
         tool_name: "browser_click",
         tool_input: { selector: ".button", x: 100, y: 200 },
         tool_display_name: "Clicking Element"
     }
 }
     │
     ▼
 REDUX MESSAGE:
 {
     id: "1706000000000",
     role: "assistant",
     action: {
         type: TOOL.BROWSER_CLICK,
         data: {
             tool_call_id: "call_abc123",
             tool_name: "browser_click",
             tool_input: { selector: ".button", x: 100, y: 200 },
             tool_display_name: "Clicking Element",
             agentContext: { agentId: "main-agent", agentType: "main" }
         }
     },
     timestamp: 1706000000000,
     agentContext: { agentId: "main-agent", agentType: "main" }
 }
     │
     ▼ (After TOOL_RESULT event)

 REDUX MESSAGE (Updated):
 {
     ...same as above,
     action: {
         ...same as above,
         data: {
             ...same as above,
             result: "iVBORw0KGgoAAAAN...",  // Base64 screenshot
             isResult: true
         }
     }
 }
     │
     ▼
 RENDERED IN UI:
 ┌─ Chat Feed ─────────────────────────────┐
 │ [🌐] Clicking Element  .button          │
 └─────────────────────────────────────────┘
       │
       │ onClick
       ▼
 ┌─ Build View (Slideshow) ────────────────┐
 │ ● ● ●  Clicking: .button                │
 ├─────────────────────────────────────────┤
 │                                         │
 │     [Screenshot of clicked element]     │
 │                                         │
 ├─────────────────────────────────────────┤
 │ [◄]  Step 5 / 12  [►]   [Live Update ●] │
 └─────────────────────────────────────────┘

 ---
 9. File Reference Index

 Backend Files
 ┌─────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────┐
 │                        File                         │                           Purpose                           │
 ├─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
 │ src/ii_agent/core/event.py                          │ RealtimeEvent model, EventType enum                         │
 ├─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
 │ src/ii_agent/core/event_stream.py                   │ AsyncEventStream, hook registry, subscriber management      │
 ├─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
 │ src/ii_agent/core/event_hooks.py                    │ EventHook base class, EventHookRegistry                     │
 ├─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
 │ src/ii_agent/controller/agent_controller.py         │ Main orchestration, event emission (TOOL_CALL, TOOL_RESULT) │
 ├─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
 │ src/ii_agent/server/socket/socketio.py              │ Socket.IO server, session management                        │
 ├─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
 │ src/ii_agent/subscribers/socketio_subscriber.py     │ Broadcasts events to WebSocket clients                      │
 ├─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
 │ src/ii_agent/subscribers/database_subscriber.py     │ Persists events to database                                 │
 ├─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
 │ src/ii_agent/subscribers/metrics_subscriber.py      │ Tracks token usage and credits                              │
 ├─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
 │ src/ii_agent/server/socket/command/query_handler.py │ Handles user query events                                   │
 ├─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
 │ src/ii_agent/server/socket/chat_session.py          │ Chat session context and hook registration                  │
 └─────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────┘
 Frontend Files
 ┌──────────────────────────────────────────────────────┬──────────────────────────────────────────────────────┐
 │                         File                         │                       Purpose                        │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/state/store.ts                          │ Redux store configuration                            │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/state/slice/messages.ts                 │ Messages slice (addMessage, updateMessage)           │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/state/slice/editor.ts                   │ Editor slice (currentActionData, currentBuildStep)   │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/state/slice/agent.ts                    │ Agent slice (buildStep, isCompleted)                 │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/state/slice/ui.ts                       │ UI slice (activeTab, isLoading)                      │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/contexts/websocket-context.tsx          │ Socket.IO client, event routing                      │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/hooks/use-app-events.tsx                │ CORE - Event processing, Redux dispatch (1443 lines) │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/hooks/use-session-manager.tsx           │ Session replay, historical events                    │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/hooks/use-question-handlers.tsx         │ Query submission, pending query handling             │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/components/agent/action.tsx             │ Tool activity renderer (icons, titles, values)       │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/components/agent/agent-build.tsx        │ SLIDESHOW CONTAINER - Dynamic content viewer         │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/components/agent/agent-controller.tsx   │ SLIDESHOW NAVIGATION - Auto-advance, scrubbing       │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/components/agent/message-content.tsx    │ Message rendering (user, assistant, think)           │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/components/agent/chat-message.tsx       │ Chat history container, subagent grouping            │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/components/agent/browser.tsx            │ Browser content display (URL, screenshot)            │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/components/agent/search-browser.tsx     │ Web search results display                           │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/components/terminal.tsx                 │ xterm.js terminal emulator                           │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/components/agent/subagent-container.tsx │ Collapsible subagent messages                        │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/components/agent/agent-result.tsx       │ Final result display (deployment, slides)            │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/components/agent/slides-result.tsx      │ Presentation viewer with PDF export                  │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ frontend/src/typings/agent.ts                        │ TypeScript types (Message, ActionStep, TOOL enum)    │
 └──────────────────────────────────────────────────────┴──────────────────────────────────────────────────────┘
 ---
 Summary

 The II-Agent rendering system is a sophisticated event-driven architecture:

 1. Backend emits structured RealtimeEvent objects through AgentController
 2. Subscribers broadcast events to WebSocket clients and persist to database
 3. Frontend receives events via Socket.IO and processes in useAppEvents
 4. Redux stores messages with embedded ActionStep data for tool calls
 5. Components render based on Redux selectors:
   - Action component shows tool activities in chat feed
   - AgentBuild shows detailed tool output in slideshow format
   - AgentController manages auto-advance and manual navigation

 The slideshow effect is achieved by:
 - Filtering messages to get only those with action property
 - Auto-advancing currentBuildStep when new actions arrive
 - Syncing currentActionData from the action at that step
 - Dynamically rendering the appropriate viewer (Browser/Terminal/Code/etc.)

 This architecture allows for real-time progress visualization with full history scrubbing capability.




# Rendering Logic Investigation Report

## 1. Executive Overview

This document serves as a comprehensive investigation into the rendering logic of the Intelligent Internet Agent (II Agent). It specifically focuses on the mechanisms behind the **Agent Activity Slideshow** viewed in the frontend Build section, as well as the rendering of chat messages and tool executions.

The investigation covers the end-to-end data flow, starting from the backend execution in `agent_controller.py`, where tool results are structured and emitted as `RealtimeEvents`. It follows this data through the WebSocket transport layer to the frontend, where it triggers updates in the Redux store.

On the frontend, we analyze the specific components responsible for visualizing this data:
*   **`action.tsx`**: The core component that transforms raw tool data into the polished, icon-rich list of activities seen in the chat feed. It handles the mapping of technical tool names to human-readable titles and icons.
*   **`agent-build.tsx`**: The container for the "slideshow" view, dynamically rendering the appropriate content (Browser, Terminal, Code, etc.) for the active step. It serves as the main display area in the Build tab.
*   **`agent-controller.tsx`**: The navigation implementation that provides the "Live Update" auto-advance functionality, creating the user experience of a real-time activity feed.
*   **`message-content.tsx`**: The component responsible for rendering the chat stream, which utilizes `action.tsx` to display tool inputs and outputs inline with the conversation.

This report details the exact file paths, component hierarchies, and code logic that drive these visual experiences, providing a complete map of the rendering architecture from the backend execution to the pixels on the screen.

---

## 2. Detailed Investigation Report

### 2.1 Executive Summary

The "slideshow" effect is achieved through a coordinated system where:
1.  **Chat Stream**: Acts as the "playlist" of activities (`Action` components).
2.  **Build View**: Acts as the "screen" showing the detailed state (`AgentBuild`) of the current activity.
3.  **Controller**: Automatically advances the view (`AgentController`) as new events arrive.

**Key Files Identified:**
-   **Frontend (The Visuals)**:
    -   `frontend/src/components/agent/action.tsx`: The "proper rendering" logic that converts raw tool names into user-friendly UI (Icons + Titles).
    -   `frontend/src/components/agent/agent-build.tsx`: The main container that renders the *content* (Browser/Code/Terminal) for the active step.
    -   `frontend/src/components/agent/agent-controller.tsx`: The navigation bar (step scrubber) that drives the "slideshow".
    -   `frontend/src/components/agent/message-content.tsx`: Renders the list of activities in the chat feed.
-   **Backend (The Source)**:
    -   `src/ii_agent/controller/agent_controller.py`: The Python orchestration layer that structures and emits the `TOOL_CALL` and `TOOL_RESULT` events.

---

### 2.2 Frontend Rendering Architecture

#### 2.2.1 The "Core" Activity Renderer
**File**: `frontend/src/components/agent/action.tsx`

This component is responsible for the "proper rendering" of tool activities you observed. It transforms raw backend signals into a polished UI.

-   **Icon Logic**: Maps tool types (e.g., `TOOL.BROWSER_CLICK`, `TOOL.CODEX_EXECUTE`) to specific Lucide icons (lines 29-190).
-   **Title Logic**: Converts technical tool names into human-readable strings like "Clicking Element" or "Deep Researching" (lines 192-428).
-   **Description Logic**: Extracts relevant metadata (files, URLs, commands) to show a brief summary of the action (lines 430-657).

#### 2.2.2 The "Slideshow" Container (Build View)
**File**: `frontend/src/components/agent/agent-build.tsx`

This is the main "square box" in the Build section. It dynamically changes its content based on the *currently selected step*.

-   **State Connection**: Listens to `selectCurrentActionData` from the Redux store.
-   **Dynamic Rendering**:
    -   **Browser Tools**: Renders `<Browser />` (showing screenshots/URLs).
    -   **Terminal Tools**: Renders `<Terminal />` (showing command output).
    -   **Code Tools**: Renders `<CodeEditor />` or `<DiffCodeEditor />`.
    -   **Slides**: Renders an `<iframe>` with the generated slide HTML (line 733).
-   **Header Logic**: Generates the dynamic status text at the top (e.g., "Searching: 'query'") similar to `action.tsx` but specialized for the active header (lines 269-364).

#### 2.2.3 The Controller (Navigation)
**File**: `frontend/src/components/agent/agent-controller.tsx`

This component manages the "Live Update" behavior, effectively turning the sequence of tools into a slideshow.

-   **Auto-Advance**: A `useEffect` hook (lines 47-51) detects new messages and automatically updates the `currentBuildStep` to the latest one (`totalBuildSteps`), creating the real-time "slideshow" effect.
-   **Scrubbing**: The slider and arrow buttons allow the user to manually review the history of agent activities.

---

### 2.3 Backend "Rendering" (Event Construction)

The backend is responsible for structuring the data that the frontend renders.

#### 2.3.1 Tool Call & Result Orchestration
**File**: `src/ii_agent/controller/agent_controller.py`

This is the brain of the operation. It runs the agent loop and emits the events that populate the frontend.

-   **Emission Mechanism**: The `add_tool_call_result` method (line 442) is critical.
    -   It takes the raw execution result.
    -   It constructs a `RealtimeEvent` of type `EventType.TOOL_RESULT`.
    -   **Payload**: It structures the content dictionary:
        ```python
        content={
            "tool_call_id": tool_call.tool_call_id,
            "tool_name": tool_call.tool_name,
            "tool_input": tool_call.tool_input,
            "result": user_display_content,  # Used by frontend to show output
            "is_error": is_error,
        }
        ```
    -   This structured payload provides all the necessary fields (`tool_name` for icons, `tool_input` for descriptions, `result` for the main view) that `action.tsx` and `agent-build.tsx` rely on.

---

### 2.4 Summary of Data Flow for Activity Slideshow

1.  **Backend Execution**: `AgentController` (Python) executes a tool (e.g., `browser_use`).
2.  **Event Emission**: `add_tool_call_result` emits a `TOOL_RESULT` event via Socket.IO.
3.  **Frontend State**: `useAppEvents` hook receives the event and updates the Redux `messages` store.
4.  **List Rendering**: `MessageContent` sees the new message and uses `Action` component to render the "Activity" row in the chat.
5.  **Slideshow Update**: `AgentController` (React) detects the new step and updates `currentBuildStep`.
6.  **Main View Update**: `AgentBuild` reads the new step data and switches its main view (e.g., updates the Browser component with the new screenshot).
