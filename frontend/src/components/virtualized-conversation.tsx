
import { Virtuoso, type VirtuosoHandle } from 'react-virtuoso'
import { useEffect, useRef, useState } from 'react'
import { type ChatMessage } from '@/utils/chat-events'
import ChatMessageContent from './chat-message-content'
import { GroupedPart } from '@/utils/chat-events'
import { Button } from './ui/button'
import { ArrowDown } from 'lucide-react'

interface VirtualizedConversationProps {
  messages: ChatMessage[]
  groupMessageParts: (messages: ChatMessage[]) => GroupedPart[]
  isStreaming?: boolean
  isWaitingForNextEvent?: boolean
  className?: string
  footer?: React.ReactNode
}

export function VirtualizedConversation({
  messages,
  groupMessageParts,
  isStreaming,
  isWaitingForNextEvent,
  className,
  footer
}: VirtualizedConversationProps) {
  const virtuosoRef = useRef<VirtuosoHandle>(null)
  const [atBottom, setAtBottom] = useState(true)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const isUserScrolling = useRef(false)

  // Group messages for rendering
  // We re-calculate this when messages change. ideally this should be memoized in parent or here
  const groupedParts = groupMessageParts(messages)

  // Auto-scroll effect
  useEffect(() => {
    // If we are at the bottom or a new streaming event comes in, forces scroll
    if (atBottom || isStreaming) {
      // Use a macrotask/timeout to let DOM render first
      setTimeout(() => {
        virtuosoRef.current?.scrollToIndex({
          index: groupedParts.length - 1,
          align: 'end',
          behavior: 'smooth'
        })
      }, 50)
    }
  }, [groupedParts.length, isStreaming, atBottom])

  return (
    <div className={`h-full w-full relative ${className || ''}`}>
      <Virtuoso
        ref={virtuosoRef}
        style={{ height: '100%', width: '100%' }}
        data={groupedParts}
        atBottomStateChange={(bottom) => {
          setAtBottom(bottom)
          setShowScrollButton(!bottom)
          isUserScrolling.current = !bottom
        }}
        initialTopMostItemIndex={groupedParts.length - 1} 
        followOutput={atBottom ? "smooth" : "auto"}
        components={{
          Footer: () => <>{footer}</>
        }}
        itemContent={(index, group) => (
          <div className="px-4 py-2">
            <ChatMessageContent
              group={group}
              isStreaming={isStreaming && index === groupedParts.length - 1}
              isWaitingForNextEvent={
                isWaitingForNextEvent && index === groupedParts.length - 1
              }
            />
          </div>
        )}
      />
      
      {showScrollButton && (
        <Button
          onClick={() => {
            virtuosoRef.current?.scrollToIndex({
              index: groupedParts.length - 1,
              align: 'end',
              behavior: 'smooth'
            })
          }}
          size="icon"
          className="absolute bottom-4 right-4 rounded-full shadow-lg z-50 h-10 w-10 animate-in fade-in zoom-in duration-200"
        >
          <ArrowDown className="h-5 w-5" />
        </Button>
      )}
    </div>
  )
}
