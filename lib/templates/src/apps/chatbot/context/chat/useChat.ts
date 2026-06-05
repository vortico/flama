import { useCallback, useReducer } from 'react'

import { INITIAL_STATE, messageText, reducer, toWireHistory } from './reducer'
import type { ChatRequestBody } from './useChatStream'
import { useChatStream } from './useChatStream'

interface UseChatOptions {
  streamUrl: string
}

// Prepended to every request so the model formats answers for this UI's renderer (GitHub-flavoured
// Markdown, Shiki code, KaTeX math via `$`/`$$`, and Mermaid). The backend is stateless, so the system
// turn must travel with each turn's history rather than being set once.
const SYSTEM_PROMPT = `You are a helpful assistant in a chat interface that renders GitHub-flavored Markdown: tables, fenced code, LaTeX math, and Mermaid diagrams. Use them to make answers clear and well-structured.

- Code: fenced blocks with a language tag, e.g. \`\`\`python.
- Math: LaTeX with $...$ inline and $$...$$ for display. Do not use \\( \\) or \\[ \\].
- Tables: use GitHub-flavored Markdown tables for tabular data.
- Diagrams: use \`\`\`mermaid blocks with valid Mermaid only — never ASCII art. Follow these rules strictly:
  - ALWAYS wrap EVERY node label in double quotes, even simple ones. Correct: A["Encoder"] --> B["Encoder Output (Keys/Values)"]. Wrong: A[Encoder] --> B[Encoder Output (Keys/Values)]. An unquoted label is invalid and breaks the whole diagram.
  - Begin with a diagram type, e.g. "graph TD" or "sequenceDiagram".
  - Write one statement per line and do not use semicolons.
  - Do not add comments (no % or %%) inside the diagram.
  - Never set colors or styles: do not use style, classDef, fill, or stroke. The interface themes diagrams automatically.
  - Keep diagrams simple: use common types (flowchart, sequenceDiagram, classDiagram) and short alphanumeric node ids.`

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
      messages: [{ role: 'system', content: SYSTEM_PROMPT }, ...history],
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
