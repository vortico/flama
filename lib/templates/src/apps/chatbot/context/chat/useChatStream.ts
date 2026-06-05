import { useCallback, useEffect, useRef } from 'react'

import { parseEvent, SSE_EVENTS } from './parseEvent'
import type { Action } from './reducer'

export interface ChatRequestBody {
  messages: { role: 'system' | 'user' | 'assistant'; content: string }[]
  transport: 'conversation'
  chat_template_kwargs?: Record<string, unknown>
  params?: Record<string, unknown>
}

interface UseChatStreamOptions {
  streamUrl: string
  onAction: (action: Action) => void
}

// Owns the network lifecycle for one streaming turn: handshake POST, EventSource creation, event-name dispatch via the
// codec, and cancellation through an AbortController. The hook itself is stateless from React's perspective — it never
// triggers a re-render — so consumers can drop refs and Promise rendezvous in favour of `send`/`cancel`.
export function useChatStream({ streamUrl, onAction }: UseChatStreamOptions) {
  const controllerRef = useRef<AbortController | null>(null)
  // Keep a fresh reference to the dispatch function without re-creating `send`. Avoids re-running consumers' effects
  // when the underlying reducer's dispatch is stable (it always is) but the component identity changes.
  const onActionRef = useRef(onAction)
  useEffect(() => {
    onActionRef.current = onAction
  })

  const cancel = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
  }, [])

  const send = useCallback(
    async (body: ChatRequestBody) => {
      cancel()
      const ac = new AbortController()
      controllerRef.current = ac
      try {
        const create = await fetch(streamUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: ac.signal,
        })
        if (!create.ok) throw new Error(`HTTP ${create.status}`)
        const created = (await create.json()) as { id?: string }
        if (!created.id) throw new Error('Stream id missing in response')

        const sse = new EventSource(`${streamUrl.replace(/\/$/, '')}/${created.id}/`)
        ac.signal.addEventListener('abort', () => sse.close(), { once: true })

        // Bridge the EventSource into a single Promise: it resolves on terminal frames (`message.stop` / `error`) or
        // on cancel, and rejects on transport-level failures. The reducer is the only side effect via `onActionRef`.
        await new Promise<void>((resolve, reject) => {
          const dispatch = (name: string) => (ev: MessageEvent) => {
            const action = parseEvent(name, typeof ev.data === 'string' ? ev.data : '')
            if (action) onActionRef.current(action)
            if (action?.type === 'STREAM_DONE' || action?.type === 'STREAM_ERROR') resolve()
          }
          SSE_EVENTS.forEach((n) => sse.addEventListener(n, dispatch(n)))
          sse.onerror = () => reject(new Error('SSE connection error'))
          ac.signal.addEventListener('abort', () => resolve(), { once: true })
        }).finally(() => sse.close())
      } catch (e) {
        // Abort is the user-cancel path: silent. Anything else surfaces as a reducer-visible STREAM_ERROR.
        if (ac.signal.aborted) return
        onActionRef.current({
          type: 'STREAM_ERROR',
          detail: `Error: ${e instanceof Error ? e.message : 'Unknown error'}`,
        })
      } finally {
        if (controllerRef.current === ac) controllerRef.current = null
      }
    },
    [streamUrl, cancel],
  )

  useEffect(() => () => controllerRef.current?.abort(), [])

  return { send, cancel }
}
