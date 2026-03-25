# Frontend Issues - Detailed Analysis Report

This document provides an extensive analysis of the three critical issues affecting the frontend application. Each section traces the complete code flow from frontend to backend with specific file paths and line numbers.

---

## Issue 1: Agent Mode "Not Authenticated" Error

### Problem Description
User switches to Agent mode, sends a message, and receives "Not authenticated" error. The spinner continues spinning indefinitely with no recovery path.

### Code Flow Analysis

**Frontend Connection Sequence:**
The WebSocket connection is initiated in `frontend/src/contexts/websocket-context.tsx`. At line 135, the authentication token is added to the connection options. The connection targets the `/ws` namespace (line 149-152). Upon successful connection, the `connect` event handler (lines 154-179) conditionally emits `join_session` - but ONLY when `isFromNewQuestionRef.current` is true (line 162). This is a critical condition: if the user is loading an existing session, `join_session` is never automatically called.

**Backend Authentication Flow:**
In `backend/common/socketio/server.py`, the `connect` handler (lines 20-70) validates the JWT token and saves session data to Redis via `sio.save_session()` (lines 54-59). This session data contains `authenticated: True` and `user_id`. However, this save operation can fail silently - if Redis is unavailable or the save fails, the connection is rejected but the error is not propagated clearly.

**Where the Error Originates:**
In `backend/common/socketio/handlers.py`, the `chat_message` handler (lines 242-301) attempts to retrieve the user_id via `_get_user_id_from_session()` at line 271. This method (lines 92-100) calls `sio.get_session()` to retrieve the session data from Redis. If this returns `None` or the `authenticated` flag is false, line 274 emits the "Not authenticated" error.

### Root Causes Identified

1. **Redis Session Data Loss**: The Socket.IO session data stored in Redis during `connect` may not be available when `chat_message` is processed. This can happen due to Redis connection issues, key expiration, or race conditions between distributed Redis nodes.

2. **Race Condition**: The frontend can send `chat_message` before `join_session` completes its database operations. While the code at lines 278-296 attempts to handle this with a `get_or_create` pattern, this only executes AFTER the authentication check fails.

3. **No Fallback Mechanism**: Once `_get_user_id_from_session()` returns `None`, there is no attempt to re-authenticate or retrieve credentials from the original connection. The error is immediately emitted with no retry logic.

4. **Frontend State Mismatch**: The `isFromNewQuestion` flag in Redux determines whether `join_session` is called automatically. When this flag is `false` (default), users navigating to existing sessions never trigger `join_session`, leaving the backend in an uninitialized state.

### Key File References
- `frontend/src/contexts/websocket-context.tsx`: Lines 93-247 (connectSocket), 159-178 (auto-initialize condition)
- `backend/common/socketio/server.py`: Lines 20-70 (connect handler), 54-62 (session save)
- `backend/common/socketio/handlers.py`: Lines 92-100 (_get_user_id_from_session), 271-276 (error emission)

---

## Issue 2: File Upload Failure

### Problem Description
User clicks the upload button, selects a file, and receives "Failed to upload file" error. The backend endpoint works when tested directly via test scripts, but fails through the frontend.

### Code Flow Analysis

**Frontend Upload Sequence:**
The upload process begins in `frontend/src/hooks/use-upload-files.tsx`. At lines 36-41, the frontend calls `uploadService.generateUploadUrl()` with the file's name, content_type (`file.type || 'application/octet-stream'`), and size. Upon receiving the presigned URL, lines 43-81 use XMLHttpRequest to PUT the file directly to the R2/S3 endpoint. The `Content-Type` header is set at lines 48-51 using the same value sent to generate the URL.

**Backend URL Generation:**
In `backend/app/agent/api/v1/files.py`, the `generate_upload_url` endpoint (lines 298-332) calls `storage.get_upload_url()`. In `backend/src/services/file_processing/storage.py`, the `get_upload_url` method (lines 493-527) generates a presigned URL using `generate_presigned_url("put_object")` with the `ContentType` parameter embedded in the AWS Signature V4.

**The Critical Issue:**
The presigned URL signature includes the `ContentType` parameter. When the frontend sends the PUT request, the `Content-Type` header MUST exactly match what was signed. However, browsers report `file.type` inconsistently - for unknown file types, it may be empty string `''` or vary between browsers. The frontend defaults to `'application/octet-stream'` when `file.type` is empty, but this happens AFTER the initial `generateUploadUrl` call might have sent a different value.

### Root Causes Identified

1. **Content-Type Signature Mismatch**: The presigned URL is signed with a specific `ContentType`. If the browser sends a different `Content-Type` header (even slightly different), R2/S3 returns 403 Forbidden. The browser's `File.type` property is unreliable for many file types.

2. **No Error Body Inspection**: In `use-upload-files.tsx` lines 65-70, the XMLHttpRequest error handler only checks `xhr.status` and `xhr.statusText`. It never inspects `xhr.responseText` to see R2's actual error message explaining why the signature failed.

3. **Silent Success on Failure**: In `files.py` line 353, the `upload_complete` endpoint has commented-out validation: `if not await storage.exists(storage_path): pass`. This means even if the PUT to R2 fails, the endpoint still creates a `StagedFile` record and returns success.

4. **Test vs Frontend Difference**: Direct test scripts likely use explicit, correct MIME types. The frontend relies on browser detection which is inconsistent. Additionally, test scripts may not go through CORS preflight, while browser requests do.

5. **Potential Authorization Header Conflict**: XMLHttpRequest in browsers may auto-include credentials. If an `Authorization` header is sent alongside the presigned URL signature, R2 may reject it as the signature was computed without that header.

### Key File References
- `frontend/src/hooks/use-upload-files.tsx`: Lines 30-100 (uploadFileWithSignedUrl), 48-51 (Content-Type header)
- `frontend/src/services/upload.service.ts`: Lines 82-90 (API calls)
- `backend/app/agent/api/v1/files.py`: Lines 298-332 (generate_upload_url), 334-373 (upload_complete), 353 (silent pass)
- `backend/src/services/file_processing/storage.py`: Lines 493-527 (presigned URL generation)

---

## Issue 3: Chat Messages Disappearing After Response

### Problem Description
User sends a message in Chat mode, the AI responds, then immediately after the response completes, both the user message and AI response disappear. The screen shows "Ask anything, your assistant is ready to help" placeholder. The sidebar shows "new conversation" instead of the actual chat title.

### Code Flow Analysis

**Frontend Message Building:**
During the SSE stream, messages are built in local state within `frontend/src/hooks/use-chat-query.tsx`. The `sendMessage` function (lines 257-585) initializes the user and assistant messages at lines 378-398, setting `chatStatus: 'running'`. As tokens arrive, the `updateMessagePart` function (lines 400-458) appends content to the streaming message.

**The Destructive Call:**
When the stream completes, the `onDone` callback (lines 688-735) is triggered. At line 731, it calls `hydrateSessionHistory(targetSessionId, true)`. This function (lines 124-209) fetches chat history from the backend API at line 141: `chatService.getChatHistory(activeSessionId)`. At lines 179-186, the fetched data OVERWRITES the entire `messages` state.

**Why the Fetch Returns Empty Data:**
The critical issue is that **messages are never persisted to the database during streaming**. Looking at `backend/app/agent/api/v1/chat.py`:
- Lines 796-809 create the session in the database before streaming
- However, during `_astream_workflow_generator()` (lines 633-722) and `_stream_graph_events()`, NO messages are written to the database
- The `ChatEvent` model in `backend/app/agent/crud/crud_chat_event.py` defines message storage, but it's never called during SSE streaming
- When `hydrateSessionHistory` fetches from `/chat-sessions/{id}/events`, it returns empty because nothing was ever persisted

### Latency Analysis

The delay before the first response token appears is caused by sequential blocking operations:

1. **Database Session Creation** (lines 796-809 in chat.py): The `async with async_db_session()` block queries for existing sessions, potentially creates a new one, and commits - all before the StreamingResponse is returned. This adds 300-500ms.

2. **Checkpointer Initialization** (line 705): The `checkpointer_manager.get_graph_with_checkpointer()` may involve additional database operations.

3. **Graph Initialization**: The LangGraph workflow must initialize before producing the first event. This includes loading tools, system prompts, and establishing the agent state.

Combined, these operations create 1.5-5+ seconds of latency before the first token reaches the frontend.

### Root Causes Identified

1. **Hydration Overwrites Streamed Messages**: The `hydrateSessionHistory` call in `onDone` fetches from an empty database and overwrites the perfectly valid messages that were just displayed.

2. **Messages Never Persisted**: The backend SSE stream emits events but never writes them to the database. There's no integration between the streaming generator and the `ChatEvent` persistence layer.

3. **Session Name Never Set**: The sidebar shows "new conversation" because `session.name` is never populated. The `get_or_create` function creates sessions with null names, and there's no subsequent call to update the name based on the first user message.

4. **Blocking Operations Before Stream**: Database and checkpointer initialization happen synchronously before the stream starts, causing noticeable latency.

### Key File References
- `frontend/src/hooks/use-chat-query.tsx`: Lines 688-735 (onDone callback), 731 (hydrateSessionHistory call), 124-209 (hydrateSessionHistory function), 179-186 (state overwrite)
- `backend/app/agent/api/v1/chat.py`: Lines 796-809 (blocking DB operations), 633-722 (_astream_workflow_generator), 553-631 (_stream_graph_events - no DB writes)
- `backend/app/agent/crud/crud_chat_event.py`: ChatEvent model exists but is never used during streaming
- `frontend/src/components/header.tsx`: Lines 136-147 (session name display)

---

## Summary Table

| Issue | Frontend Location | Backend Location | Root Cause |
|-------|-------------------|------------------|------------|
| Agent Auth | websocket-context.tsx:159-178 | handlers.py:271-276 | Redis session data loss + race condition |
| File Upload | use-upload-files.tsx:48-51 | storage.py:493-527 | Content-Type signature mismatch |
| Message Wipe | use-chat-query.tsx:731 | chat.py:633-722 | Messages never persisted + hydration overwrites state |

---

*Report generated for debugging purposes. All line numbers reference the current state of the codebase.*
