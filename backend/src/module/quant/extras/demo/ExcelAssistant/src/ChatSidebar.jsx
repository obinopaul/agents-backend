import React, { useState, useRef, useEffect } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import './ChatSidebar.css'

marked.setOptions({
  breaks: true,
  gfm: true,
})

function renderAssistantContent(markdownText) {
  const rawHtml = marked.parse(markdownText || '')
  return DOMPurify.sanitize(rawHtml)
}

function ChatSidebar({ isOpen, onToggle, onSendMessage, isLoading }) {
  const [inputValue, setInputValue] = useState('')
  const [messages, setMessages] = useState([])
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isOpen])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!inputValue.trim() || isLoading) return

    const userMessage = inputValue.trim()
    setInputValue('')

    // Add user message to chat
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])

    try {
      // Call the parent handler to process with agent
      const result = await onSendMessage(userMessage, messages)
      
      if (result.success) {
        // Add assistant response
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: result.response,
        }])
      } else {
        // Add error message
        setMessages(prev => [...prev, {
          role: 'error',
          content: result.error || 'An error occurred',
        }])
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'error',
        content: error.message || 'Failed to communicate with agent',
      }])
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const clearChat = () => {
    setMessages([])
  }

  const renderMessageContent = (msg) => {
    if (msg.role === 'assistant') {
      const safeHtml = renderAssistantContent(msg.content)
      return (
        <div
          className="message-content markdown"
          dangerouslySetInnerHTML={{ __html: safeHtml }}
        />
      )
    }

    return (
      <div className="message-content">
        {msg.content}
      </div>
    )
  }

  return (
    <>
      {/* Toggle button */}
      <button 
        className={`sidebar-toggle ${isOpen ? 'open' : ''}`}
        onClick={onToggle}
        title={isOpen ? 'Close AI Assistant' : 'Open AI Assistant'}
      >
        {isOpen ? (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
          </svg>
        )}
      </button>

      {/* Sidebar */}
      <div className={`chat-sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4M12 8h.01" />
            </svg>
            <span>AI Assistant</span>
          </div>
          <button className="clear-chat-btn" onClick={clearChat} title="Clear chat">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
            </svg>
          </button>
        </div>

        <div className="messages-container">
          {messages.length === 0 ? (
            <div className="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
              </svg>
              <p>Ask me to help with your spreadsheet!</p>
              <span className="hint">Examples:</span>
              <ul className="examples">
                <li>"Sum A1:A5 and put the result in B1"</li>
                <li>"Add a formula to calculate averages"</li>
              </ul>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`message ${msg.role}`}>
                <div className="message-header">
                  {msg.role === 'user' ? 'You' : msg.role === 'assistant' ? 'AI Assistant' : 'Error'}
                </div>
                {renderMessageContent(msg)}
              </div>
            ))
          )}
          {isLoading && (
            <div className="message assistant loading">
              <div className="message-header">AI Assistant</div>
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="input-container" onSubmit={handleSubmit}>
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me to modify your spreadsheet..."
            disabled={isLoading}
            rows={2}
          />
          <button 
            type="submit" 
            disabled={!inputValue.trim() || isLoading}
            title="Send message"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        </form>
      </div>
    </>
  )
}

export default ChatSidebar
