import { createContext, useCallback, useContext, useRef, useState, type ReactNode, type RefObject } from 'react'

import type { Message } from './types'
import { useChat } from './useChat'

interface ChatContextValue {
  messages: Message[]
  isStreaming: boolean
  input: string
  setInput: (value: string) => void
  submit: () => void
  cancel: () => void
  regenerate: () => void
  editLast: () => void
  inputRef: RefObject<HTMLTextAreaElement | null>
  pinToken: number
}

const ChatContext = createContext<ChatContextValue | null>(null)

interface ChatProviderProps {
  streamUrl: string
  children: ReactNode
}

// Single source of truth for the chat view tree: composes the transport/reducer (`useChat`) with the prompt input
// state so leaf views consume context instead of receiving drilled props. The scroll/pin-to-top model lives in
// `Conversation`; this provider only emits `pinToken` as the signal to re-pin.
export function ChatProvider({ streamUrl, children }: ChatProviderProps) {
  const {
    messages,
    isStreaming,
    submit: sendPrompt,
    cancel,
    regenerate: regenerateTurn,
    editLast: dropLastUserTurn,
  } = useChat({ streamUrl })

  // Bumped once per submit/regenerate so `Conversation` re-pins the latest prompt to the top (a new prompt or a
  // re-ask of the same prompt).
  const [pinToken, setPinToken] = useState<number>(0)

  const [input, setInput] = useState<string>('')
  const inputRef = useRef<HTMLTextAreaElement | null>(null)

  const submit = useCallback(() => {
    const prompt = input.trim()
    if (!prompt) return
    setInput('')
    inputRef.current?.focus()
    setPinToken((token) => token + 1)
    void sendPrompt(prompt)
  }, [input, sendPrompt])

  const regenerate = useCallback(() => {
    setPinToken((token) => token + 1)
    void regenerateTurn().then(() => inputRef.current?.focus())
  }, [regenerateTurn])

  // Pull the last user turn back into the prompt input for editing, then resubmit through the normal flow.
  const editLast = useCallback(() => {
    const text = dropLastUserTurn()
    if (text === undefined) return
    setInput(text)
    inputRef.current?.focus()
  }, [dropLastUserTurn])

  const value: ChatContextValue = {
    messages,
    isStreaming,
    input,
    setInput,
    submit,
    cancel,
    regenerate,
    editLast,
    inputRef,
    pinToken,
  }

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

export function useChatContext(): ChatContextValue {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChatContext must be used within a ChatProvider')
  return ctx
}
