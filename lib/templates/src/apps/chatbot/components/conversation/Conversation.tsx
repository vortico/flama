import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

import { useChatContext } from '../../context/chat'
import EmptyChatInfo from '../EmptyChatInfo'
import { Message } from '../message'
import ScrollDownButton from './ScrollDownButton'

// Gap (px) left above the pinned prompt; must match the `scroll-mt-*` on the last user message wrapper below.
const TOP_GAP_PX = 24
// Show the jump-to-latest button only when the last message sits at least this far below the viewport bottom.
const AT_BOTTOM_TOLERANCE_PX = 100

function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

// Owns the scrollable transcript and its Gemini-style scroll model: when a new turn starts the latest user prompt is
// pinned to the top of the viewport and a reserved bottom spacer guarantees there's room to do so even before the
// answer arrives; the spacer shrinks once the turn is idle. There is no bottom-following — the prompt stays anchored
// and the user scrolls down manually via the floating jump-to-latest button. The pin trigger is `pinToken` (bumped per
// submit/regenerate), so re-asking the same prompt re-pins it. The composer bar that overlaps the bottom of this area
// is an absolute sibling rendered by ChatApp.
export default function Conversation() {
  const { messages, isStreaming, pinToken } = useChatContext()
  const lastUserId = messages.findLast((m) => m.role === 'user')?.id
  const last = messages.at(-1)
  const lastAssistantId = last?.role === 'assistant' ? last.id : undefined

  const containerRef = useRef<HTMLDivElement | null>(null)
  const contentRef = useRef<HTMLDivElement | null>(null)
  const spacerRef = useRef<HTMLDivElement | null>(null)
  const [isAtBottom, setIsAtBottom] = useState(true)

  const lastUserEl = useCallback(
    () => (lastUserId ? (contentRef.current?.querySelector<HTMLElement>(`[data-mid="${lastUserId}"]`) ?? null) : null),
    [lastUserId],
  )

  // Drive button visibility off the real message content, not the scroll container: the reserved spacer is a sibling
  // of `content`, so it's excluded here. The flag reflects "is there message content below the fold", independent of
  // the reserved empty space (which would otherwise keep the button visible for the whole of a short streamed turn).
  const refreshAtBottom = useCallback(() => {
    const container = containerRef.current
    const content = contentRef.current
    if (!container || !content) return
    const hidden = content.getBoundingClientRect().bottom - container.getBoundingClientRect().bottom
    setIsAtBottom(hidden < AT_BOTTOM_TOLERANCE_PX)
  }, [])

  // Size the reserved bottom space so the latest prompt can reach the top, and refresh the at-bottom flag. Driven
  // imperatively (the spacer is a sibling of the observed content, so writing its height can't re-trigger the
  // ResizeObserver) and synchronously so the pin scroll below has room on the same frame.
  const measure = useCallback(() => {
    const container = containerRef.current
    const content = contentRef.current
    const spacer = spacerRef.current
    if (!container || !content || !spacer) return
    const user = lastUserEl()
    if (!user) {
      spacer.style.height = '0px'
    } else {
      const belowPromptTop = content.getBoundingClientRect().bottom - user.getBoundingClientRect().top
      // While the turn is generating, reserve a full viewport below the prompt so it stays pinned at the top even as
      // content below it grows or collapses (e.g. the thinking frame folding away). Sizing to the exact fit instead
      // leaves the scroll at its maximum, where a collapse clamps it and drags the prompt down. Once idle, trim to the
      // exact fit; that preserves the pinned position, so there's no jump.
      const reserved = isStreaming
        ? container.clientHeight - TOP_GAP_PX
        : container.clientHeight - belowPromptTop - TOP_GAP_PX
      spacer.style.height = `${Math.max(0, reserved)}px`
    }
    refreshAtBottom()
  }, [lastUserEl, isStreaming, refreshAtBottom])

  // Re-measure on content growth (streaming) and viewport resize.
  useEffect(() => {
    const container = containerRef.current
    const content = contentRef.current
    if (!container || !content) return
    const observer = new ResizeObserver(() => measure())
    observer.observe(container)
    observer.observe(content)
    return () => observer.disconnect()
  }, [measure])

  // Track manual scrolling for the jump-to-latest button.
  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    container.addEventListener('scroll', refreshAtBottom, { passive: true })
    return () => container.removeEventListener('scroll', refreshAtBottom)
  }, [refreshAtBottom])

  // Pin the latest prompt to the top on each new turn. Reserve the space first (synchronously, via `measure`) so the
  // scroll target is reachable on this same frame.
  useLayoutEffect(() => {
    measure()
    const user = lastUserEl()
    if (!user) return
    user.scrollIntoView({ block: 'start', behavior: prefersReducedMotion() ? 'auto' : 'smooth' })
    // Re-pin only when a new turn is requested (pinToken), not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pinToken])

  // Jump to the bottom. When idle the spacer has been trimmed to a fit, so the true end of the scroll range lands the
  // latest message just above the composer. While a turn is streaming the spacer reserves a full viewport of room, so
  // scrolling to the raw bottom would drop into that blank space — target the real content bottom instead.
  const scrollToBottom = useCallback(() => {
    const container = containerRef.current
    const content = contentRef.current
    if (!container || !content) return
    const top = isStreaming
      ? container.scrollTop + content.getBoundingClientRect().bottom - container.getBoundingClientRect().bottom
      : container.scrollHeight
    container.scrollTo({ top, behavior: prefersReducedMotion() ? 'auto' : 'smooth' })
  }, [isStreaming])

  return (
    <div className="relative min-h-0 flex-1">
      <div
        ref={containerRef}
        className="h-full overflow-y-auto [overflow-anchor:none] [scrollbar-gutter:stable] [scrollbar-width:thin]"
      >
        <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6 md:px-8">
          <div ref={contentRef} className="flex flex-col gap-4 pb-40">
            {messages.length === 0 ? (
              <div className="py-32">
                <EmptyChatInfo />
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  data-mid={message.id}
                  className={message.id === lastUserId ? 'scroll-mt-6' : undefined}
                >
                  <Message
                    message={message}
                    isLastUser={message.id === lastUserId}
                    isLastAssistant={message.id === lastAssistantId}
                  />
                </div>
              ))
            )}
          </div>
          {/* Reserved space (sized above) so the latest prompt can sit at the top of the viewport. */}
          <div ref={spacerRef} aria-hidden="true" />
        </div>
      </div>
      {/* Floating jump-to-latest overlay, centered above the composer. The composer (rendered by ChatApp) is an absolute
          sibling bar overlapping this area's bottom; the bottom offset clears its resting height. */}
      <div className="absolute bottom-24 left-1/2 z-20 -translate-x-1/2">
        <ScrollDownButton visible={!isAtBottom} onClick={scrollToBottom} />
      </div>
    </div>
  )
}
