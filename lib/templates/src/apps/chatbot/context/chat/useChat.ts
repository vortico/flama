import { useCallback, useReducer } from 'react'

import { INITIAL_STATE, messageText, reducer, toWireHistory } from './reducer'
import type { ChatRequestBody } from './useChatStream'
import { useChatStream } from './useChatStream'

interface UseChatOptions {
  streamUrl: string
}

// Composes the chat reducer with the streaming transport. Exposes a tight surface: the rendered `messages` list, the
// `isStreaming` flag, and `submit` / `cancel` actions. Wire details (history serialisation, the assistant turn-start
// dance, the terminal STREAM_DONE epilogue) live here so views never see them.
export function useChat({ streamUrl }: UseChatOptions) {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE)
  const { send, cancel } = useChatStream({ streamUrl, onAction: dispatch })

  // `enable_thinking` is consumed by reasoning-aware chat templates (e.g. Gemma 4) and silently ignored by the rest,
  // so the chat UI opts in unconditionally — the dedicated `ThoughtBubble` collapse-on-next-channel UX is only
  // meaningful when the model actually emits a thought channel.
  const requestBody = useCallback(
    (history: { role: 'user' | 'assistant'; content: string }[]): ChatRequestBody => ({
      messages: history,
      transport: 'conversation',
      chat_template_kwargs: { enable_thinking: true },
      params: {},
    }),
    [],
  )

  const submit = useCallback(
    async (prompt: string) => {
      const trimmed = prompt.trim()
      if (!trimmed || state.isStreaming) return

      const history = toWireHistory(state.messages)
      history.push({ role: 'user', content: trimmed })

      dispatch({ type: 'USER_TURN_START', prompt: trimmed })
      dispatch({ type: 'ASSISTANT_TURN_START' })

      await send(requestBody(history))

      dispatch({ type: 'STREAM_DONE' })
    },
    [state.isStreaming, state.messages, send, requestBody],
  )

  // Drop the trailing assistant turn and re-ask the model for the unchanged prior input.
  const regenerate = useCallback(async () => {
    if (state.isStreaming) return
    if (state.messages.at(-1)?.role !== 'assistant') return

    const history = toWireHistory(state.messages.slice(0, -1))
    if (history.length === 0) return

    dispatch({ type: 'DROP_LAST_ASSISTANT' })
    dispatch({ type: 'ASSISTANT_TURN_START' })

    await send(requestBody(history))

    dispatch({ type: 'STREAM_DONE' })
  }, [state.isStreaming, state.messages, send, requestBody])

  // Remove the last user turn (and anything after it) and return its text so the caller can refill the prompt input.
  const editLast = useCallback((): string | undefined => {
    if (state.isStreaming) return undefined

    const index = state.messages.findLastIndex((m) => m.role === 'user')
    if (index === -1) return undefined

    const text = messageText(state.messages[index])
    dispatch({ type: 'DROP_FROM_LAST_USER' })
    return text
  }, [state.isStreaming, state.messages])

  return {
    messages: state.messages,
    isStreaming: state.isStreaming,
    submit,
    cancel,
    regenerate,
    editLast,
  }
}
