# AG-UI Protocol Frontend Integration

> Complete guide for frontend developers to integrate AG-UI Protocol events for tool calls, reasoning, and multimodal messages.

---

## Quick Start

### 1. Connect to SSE Stream

```typescript
async function connectToStream(
  endpoint: '/agent/chat/stream' | '/agent/agent/stream',
  token: string,
  messages: Message[],
  threadId: string
): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream'
    },
    body: JSON.stringify({
      messages,
      thread_id: threadId
    })
  });
  
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.body!.getReader();
}
```

### 2. Parse SSE Events

```typescript
function parseSSE(chunk: string): Array<{ event: string; data: any }> {
  const events: Array<{ event: string; data: any }> = [];
  const blocks = chunk.split('\n\n').filter(Boolean);
  
  for (const block of blocks) {
    const lines = block.split('\n');
    let eventType = '';
    let eventData = '';
    
    for (const line of lines) {
      if (line.startsWith('event: ')) eventType = line.slice(7);
      if (line.startsWith('data: ')) eventData = line.slice(6);
    }
    
    if (eventType && eventData) {
      try {
        events.push({ event: eventType, data: JSON.parse(eventData) });
      } catch (e) {
        console.warn('Failed to parse SSE data:', eventData);
      }
    }
  }
  
  return events;
}
```

### 3. Handle Events

```typescript
async function streamChat(token: string, messages: Message[], threadId: string) {
  const reader = await connectToStream('/agent/chat/stream', token, messages, threadId);
  const decoder = new TextDecoder();
  let buffer = '';
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    
    // Find complete events
    const lastNewline = buffer.lastIndexOf('\n\n');
    if (lastNewline === -1) continue;
    
    const completeChunk = buffer.slice(0, lastNewline + 2);
    buffer = buffer.slice(lastNewline + 2);
    
    const events = parseSSE(completeChunk);
    for (const { event, data } of events) {
      handleAGUIEvent(event, data);
    }
  }
}
```

---

## Event Types Reference

### Tool Call Events

| Event | When | Payload |
|-------|------|---------|
| `tool_call_start` | Tool execution begins | `{ toolCallId, toolCallName }` |
| `tool_call_args` | Arguments streaming | `{ toolCallId, delta }` |
| `tool_call_end` | Arguments complete | `{ toolCallId }` |
| `tool_result` | Tool returns result | `{ toolCallId, content, role: "tool" }` |

### Reasoning Events

| Event | When | Payload |
|-------|------|---------|
| `reasoning_start` | Reasoning session begins | `{ messageId }` |
| `reasoning_message_start` | Message begins | `{ messageId, role }` |
| `reasoning_message_content` | Content streaming | `{ messageId, delta }` |
| `reasoning_message_end` | Message ends | `{ messageId }` |
| `reasoning_end` | Session ends | `{ messageId }` |

### Other Events

| Event | When | Payload |
|-------|------|---------|
| `message` | Text content | `{ content, thread_id }` |
| `status` | Status update | `{ type, message }` |
| `error` | Error occurred | `{ type, message, code }` |

---

## React Implementation

### Types

```typescript
// types/agui.ts
export interface ToolCall {
  id: string;
  name: string;
  args: string;
  result?: string;
  status: 'pending' | 'running' | 'complete' | 'error';
}

export interface ReasoningSession {
  id: string;
  content: string;
  status: 'active' | 'complete';
}

export interface StreamState {
  response: string;
  toolCalls: ToolCall[];
  reasoning: ReasoningSession | null;
  isStreaming: boolean;
  error: string | null;
}

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string | ContentBlock[];
}

export interface ContentBlock {
  type: 'text' | 'image';
  text?: string;
  url?: string;
  data?: string;
  mime_type?: string;
}
```

### useAGUIStream Hook

```typescript
// hooks/useAGUIStream.ts
import { useState, useCallback, useRef } from 'react';
import type { ToolCall, ReasoningSession, Message, StreamState } from '../types/agui';

export function useAGUIStream(token: string) {
  const [state, setState] = useState<StreamState>({
    response: '',
    toolCalls: [],
    reasoning: null,
    isStreaming: false,
    error: null
  });
  
  const abortRef = useRef<AbortController | null>(null);
  
  const handleEvent = useCallback((eventType: string, data: any) => {
    setState(prev => {
      switch (eventType) {
        // Tool Call Events
        case 'tool_call_start':
          return {
            ...prev,
            toolCalls: [...prev.toolCalls, {
              id: data.toolCallId,
              name: data.toolCallName,
              args: '',
              status: 'running' as const
            }]
          };
          
        case 'tool_call_args':
          return {
            ...prev,
            toolCalls: prev.toolCalls.map(tc =>
              tc.id === data.toolCallId
                ? { ...tc, args: tc.args + (data.delta || '') }
                : tc
            )
          };
          
        case 'tool_call_end':
          return {
            ...prev,
            toolCalls: prev.toolCalls.map(tc =>
              tc.id === data.toolCallId
                ? { ...tc, status: 'complete' as const }
                : tc
            )
          };
          
        case 'tool_result':
          return {
            ...prev,
            toolCalls: prev.toolCalls.map(tc =>
              tc.id === data.toolCallId
                ? { ...tc, result: data.content }
                : tc
            )
          };
          
        // Reasoning Events
        case 'reasoning_start':
          return {
            ...prev,
            reasoning: {
              id: data.messageId,
              content: '',
              status: 'active' as const
            }
          };
          
        case 'reasoning_message_content':
          if (!prev.reasoning) return prev;
          return {
            ...prev,
            reasoning: {
              ...prev.reasoning,
              content: prev.reasoning.content + (data.delta || '')
            }
          };
          
        case 'reasoning_end':
          if (!prev.reasoning) return prev;
          return {
            ...prev,
            reasoning: {
              ...prev.reasoning,
              status: 'complete' as const
            }
          };
          
        // Message Events
        case 'message':
          return {
            ...prev,
            response: prev.response + (data.content || '')
          };
          
        case 'error':
          return {
            ...prev,
            error: data.message || 'Unknown error',
            isStreaming: false
          };
          
        case 'status':
          if (data.type === 'complete') {
            return { ...prev, isStreaming: false };
          }
          return prev;
          
        default:
          return prev;
      }
    });
  }, []);
  
  const sendMessage = useCallback(async (
    messages: Message[],
    threadId: string,
    options?: {
      endpoint?: '/agent/chat/stream' | '/agent/agent/stream';
      enableDeepThinking?: boolean;
    }
  ) => {
    const endpoint = options?.endpoint ?? '/agent/chat/stream';
    
    // Abort any existing stream
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    
    // Reset state
    setState({
      response: '',
      toolCalls: [],
      reasoning: null,
      isStreaming: true,
      error: null
    });
    
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify({
          messages,
          thread_id: threadId,
          enable_deep_thinking: options?.enableDeepThinking
        }),
        signal: abortRef.current.signal
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }
      
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');
      
      const decoder = new TextDecoder();
      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        // Parse complete events
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';
        
        for (const eventBlock of events) {
          if (!eventBlock.trim()) continue;
          
          const lines = eventBlock.split('\n');
          let eventType = '';
          let eventData = '';
          
          for (const line of lines) {
            if (line.startsWith('event: ')) eventType = line.slice(7);
            if (line.startsWith('data: ')) eventData = line.slice(6);
          }
          
          if (eventType && eventData) {
            try {
              handleEvent(eventType, JSON.parse(eventData));
            } catch (e) {
              console.error('Failed to parse event:', eventData);
            }
          }
        }
      }
      
      setState(prev => ({ ...prev, isStreaming: false }));
    } catch (error: any) {
      if (error.name === 'AbortError') return;
      setState(prev => ({
        ...prev,
        error: error.message,
        isStreaming: false
      }));
    }
  }, [token, handleEvent]);
  
  const stop = useCallback(() => {
    abortRef.current?.abort();
    setState(prev => ({ ...prev, isStreaming: false }));
  }, []);
  
  return {
    ...state,
    sendMessage,
    stop
  };
}
```

### ToolCallDisplay Component

```tsx
// components/ToolCallDisplay.tsx
import React from 'react';
import type { ToolCall } from '../types/agui';

interface ToolCallDisplayProps {
  toolCall: ToolCall;
}

export function ToolCallDisplay({ toolCall }: ToolCallDisplayProps) {
  return (
    <div className="tool-call-card">
      <div className="tool-call-header">
        <span className="tool-icon">🔧</span>
        <span className="tool-name">{toolCall.name}</span>
        <span className={`status status-${toolCall.status}`}>
          {toolCall.status === 'running' ? '⏳ Running...' : '✅ Complete'}
        </span>
      </div>
      
      {toolCall.args && (
        <div className="tool-args">
          <strong>Arguments:</strong>
          <pre>{JSON.stringify(JSON.parse(toolCall.args), null, 2)}</pre>
        </div>
      )}
      
      {toolCall.result && (
        <div className="tool-result">
          <strong>Result:</strong>
          <pre>{toolCall.result}</pre>
        </div>
      )}
    </div>
  );
}
```

### ReasoningDisplay Component

```tsx
// components/ReasoningDisplay.tsx
import React from 'react';
import type { ReasoningSession } from '../types/agui';

interface ReasoningDisplayProps {
  reasoning: ReasoningSession;
}

export function ReasoningDisplay({ reasoning }: ReasoningDisplayProps) {
  return (
    <div className="reasoning-panel">
      <div className="reasoning-header">
        <span className="reasoning-icon">💭</span>
        <span>Thinking...</span>
        {reasoning.status === 'complete' && (
          <span className="status-complete">✓ Done</span>
        )}
      </div>
      
      <div className="reasoning-content">
        {reasoning.content}
        {reasoning.status === 'active' && (
          <span className="cursor">▊</span>
        )}
      </div>
    </div>
  );
}
```

### ChatWindow Component

```tsx
// components/ChatWindow.tsx
import React, { useState } from 'react';
import { useAGUIStream } from '../hooks/useAGUIStream';
import { ToolCallDisplay } from './ToolCallDisplay';
import { ReasoningDisplay } from './ReasoningDisplay';
import type { Message } from '../types/agui';

interface ChatWindowProps {
  token: string;
  threadId: string;
}

export function ChatWindow({ token, threadId }: ChatWindowProps) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  
  const {
    response,
    toolCalls,
    reasoning,
    isStreaming,
    error,
    sendMessage,
    stop
  } = useAGUIStream(token);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    
    const userMessage: Message = { role: 'user', content: input };
    const newMessages = [...messages, userMessage];
    
    setMessages(newMessages);
    setInput('');
    
    await sendMessage(newMessages, threadId, {
      endpoint: '/agent/chat/stream',
      enableDeepThinking: true
    });
  };
  
  return (
    <div className="chat-window">
      {/* Messages */}
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message message-${msg.role}`}>
            {typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)}
          </div>
        ))}
        
        {/* Streaming Response */}
        {(response || isStreaming) && (
          <div className="message message-assistant">
            {/* Reasoning Panel */}
            {reasoning && (
              <ReasoningDisplay reasoning={reasoning} />
            )}
            
            {/* Tool Calls */}
            {toolCalls.map(tc => (
              <ToolCallDisplay key={tc.id} toolCall={tc} />
            ))}
            
            {/* Response Text */}
            <div className="response-text">
              {response}
              {isStreaming && <span className="cursor">▊</span>}
            </div>
          </div>
        )}
        
        {/* Error */}
        {error && (
          <div className="error-message">
            ⚠️ Error: {error}
          </div>
        )}
      </div>
      
      {/* Input */}
      <form onSubmit={handleSubmit} className="input-form">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Type a message..."
          disabled={isStreaming}
        />
        {isStreaming ? (
          <button type="button" onClick={stop}>Stop</button>
        ) : (
          <button type="submit">Send</button>
        )}
      </form>
    </div>
  );
}
```

---

## Sending Multimodal Messages

### Image from URL

```typescript
const message: Message = {
  role: 'user',
  content: [
    { type: 'text', text: 'What do you see in this image?' },
    { type: 'image', url: 'https://example.com/photo.jpg' }
  ]
};

await sendMessage([message], threadId);
```

### Image from Base64

```typescript
// Convert file to base64
async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Remove data URL prefix
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// Send image message
async function sendImageMessage(file: File) {
  const base64 = await fileToBase64(file);
  
  const message: Message = {
    role: 'user',
    content: [
      { type: 'text', text: 'Describe this image' },
      { type: 'image', data: base64, mime_type: file.type }
    ]
  };
  
  await sendMessage([message], threadId);
}
```

### Image Upload Component

```tsx
// components/ImageUpload.tsx
import React, { useRef } from 'react';

interface ImageUploadProps {
  onImageSelect: (base64: string, mimeType: string) => void;
}

export function ImageUpload({ onImageSelect }: ImageUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  
  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(',')[1];
      onImageSelect(base64, file.type);
    };
    reader.readAsDataURL(file);
  };
  
  return (
    <div className="image-upload">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        onChange={handleChange}
        style={{ display: 'none' }}
      />
      <button onClick={() => inputRef.current?.click()}>
        📷 Upload Image
      </button>
    </div>
  );
}
```

---

## CSS Styling

```css
/* styles/agui.css */

.chat-window {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.message {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 8px;
}

.message-user {
  background: #e3f2fd;
  margin-left: 20%;
}

.message-assistant {
  background: #f5f5f5;
  margin-right: 20%;
}

/* Tool Call Card */
.tool-call-card {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  margin: 0.5rem 0;
  overflow: hidden;
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: #f9f9f9;
  border-bottom: 1px solid #ddd;
}

.tool-icon {
  font-size: 1.2em;
}

.tool-name {
  font-weight: 600;
}

.status {
  margin-left: auto;
  font-size: 0.875rem;
}

.status-running {
  color: #1976d2;
}

.status-complete {
  color: #388e3c;
}

.tool-args, .tool-result {
  padding: 0.5rem 1rem;
}

.tool-args pre, .tool-result pre {
  background: #f5f5f5;
  padding: 0.5rem;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 0.875rem;
}

/* Reasoning Panel */
.reasoning-panel {
  background: linear-gradient(135deg, #e8f5e9 0%, #f1f8e9 100%);
  border: 1px solid #c8e6c9;
  border-radius: 8px;
  margin: 0.5rem 0;
  padding: 0.75rem 1rem;
}

.reasoning-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  color: #2e7d32;
  font-weight: 500;
}

.reasoning-icon {
  font-size: 1.2em;
}

.reasoning-content {
  font-style: italic;
  color: #1b5e20;
  white-space: pre-wrap;
}

/* Cursor animation */
.cursor {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

/* Input form */
.input-form {
  display: flex;
  gap: 0.5rem;
  padding: 1rem;
  border-top: 1px solid #ddd;
}

.input-form input {
  flex: 1;
  padding: 0.75rem 1rem;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 1rem;
}

.input-form button {
  padding: 0.75rem 1.5rem;
  background: #1976d2;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
}

.input-form button:hover {
  background: #1565c0;
}

/* Error message */
.error-message {
  background: #ffebee;
  border: 1px solid #ef9a9a;
  color: #c62828;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin: 0.5rem 0;
}
```

---

## Testing Your Integration

Use the test endpoint to verify events are working:

```typescript
// Simple test
async function testAGUIEvents() {
  const response = await fetch('/agent/chat/stream', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      messages: [{ role: 'user', content: 'Search for weather in Tokyo' }],
      thread_id: 'test-thread'
    })
  });
  
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  const events: string[] = [];
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const text = decoder.decode(value);
    console.log('Received:', text);
    
    // Extract event types
    const matches = text.matchAll(/event: (\w+)/g);
    for (const match of matches) {
      events.push(match[1]);
    }
  }
  
  console.log('Events received:', events);
  
  // Verify tool events
  const expectedToolEvents = ['tool_call_start', 'tool_call_args', 'tool_call_end', 'tool_result'];
  for (const evt of expectedToolEvents) {
    if (events.includes(evt)) {
      console.log(`✅ ${evt}`);
    } else {
      console.log(`❌ ${evt} missing`);
    }
  }
}
```

---

## Troubleshooting

### No Events Received

1. Check authentication token is valid
2. Verify endpoint URL is correct
3. Check network tab for errors
4. Ensure Content-Type is `application/json`

### Tool Events Not Showing

1. Use a prompt that triggers tool usage (e.g., "search for...")
2. Ensure agent has tools configured
3. Check if `toolCallId` is null (may need retry)

### Reasoning Events Not Showing

1. Enable deep thinking: `enable_deep_thinking: true`
2. Model must support reasoning (Claude extended thinking, o1, etc.)
3. Use prompts requiring step-by-step analysis

### Base64 Image Errors

1. Ensure base64 string has no data URL prefix
2. Include correct `mime_type` (e.g., `image/jpeg`)
3. Verify base64 encoding is valid

---

## Related Documentation

- [AG-UI Protocol Overview](../agui-protocol.md)
- [AG-UI Protocol API Contract](../api-contracts/agui-protocol.md)
- [Agent API](./agent-api.md)
- [Chat API](./chat-api.md)
- [Authentication](./authentication.md)
