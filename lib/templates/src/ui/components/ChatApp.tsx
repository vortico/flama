import { KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react'

import { IconSend2 } from '@tabler/icons-react'
import { IconButton, TextArea } from '@vortico/ui/inputs'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

function parseSSE(chunk: string): string[] {
  const tokens: string[] = []
  for (const line of chunk.split('\n')) {
    if (line.startsWith('data: ')) {
      const raw = line.slice(6).trim()
      if (raw) {
        try {
          tokens.push(JSON.parse(raw) as string)
        } catch {
          tokens.push(raw)
        }
      }
    }
  }
  return tokens
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm/6 ${
          isUser
            ? 'bg-flama-500/15 text-primary-700'
            : 'bg-primary-200/30 text-primary-700'
        }`}
      >
        {message.content || (
          <span className="text-primary-400 inline-flex items-center gap-1">
            <span className="bg-primary-400 inline-block h-1.5 w-1.5 animate-pulse rounded-full" />
            <span className="bg-primary-400 inline-block h-1.5 w-1.5 animate-pulse rounded-full [animation-delay:0.2s]" />
            <span className="bg-primary-400 inline-block h-1.5 w-1.5 animate-pulse rounded-full [animation-delay:0.4s]" />
          </span>
        )}
      </div>
    </div>
  )
}

export default function ChatApp({ streamUrl }: { streamUrl: string }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = useCallback(async () => {
    const prompt = input.trim()
    if (!prompt || isStreaming) return

    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: prompt }])
    setIsStreaming(true)

    const assistantIndex = messages.length + 1
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    try {
      const response = await fetch(streamUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, params: {} }),
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''

        for (const block of lines) {
          const tokens = parseSSE(block)
          if (tokens.length > 0) {
            setMessages((prev) => {
              const updated = [...prev]
              updated[assistantIndex] = {
                ...updated[assistantIndex],
                content: updated[assistantIndex].content + tokens.join(''),
              }
              return updated
            })
          }
        }
      }

      if (buffer.trim()) {
        const tokens = parseSSE(buffer)
        if (tokens.length > 0) {
          setMessages((prev) => {
            const updated = [...prev]
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              content: updated[assistantIndex].content + tokens.join(''),
            }
            return updated
          })
        }
      }
    } catch (error) {
      setMessages((prev) => {
        const updated = [...prev]
        updated[assistantIndex] = {
          ...updated[assistantIndex],
          content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        }
        return updated
      })
    } finally {
      setIsStreaming(false)
      textareaRef.current?.focus()
    }
  }, [input, isStreaming, messages.length, streamUrl])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  return (
    <div className="flex h-screen flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 md:px-8">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {messages.length === 0 && (
            <div className="text-primary-400 flex flex-1 flex-col items-center justify-center gap-2 pt-32">
              <svg className="text-flama-400 h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
                />
              </svg>
              <p className="text-lg font-medium">How can I help you today?</p>
              <p className="text-sm">Send a message to start the conversation.</p>
            </div>
          )}
          {messages.map((message, i) => (
            <MessageBubble key={i} message={message} />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="border-primary-200 bg-primary-100 border-t px-4 py-3 sm:px-6 md:px-8">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <div className="flex-1">
            <TextArea
              ref={textareaRef}
              name="prompt"
              color="flama"
              size="md"
              label="Message"
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
            />
          </div>
          <div className="pb-px">
            <IconButton
              icon={<IconSend2 />}
              color="flama"
              size="lg"
              onClick={handleSubmit}
              disabled={isStreaming || !input.trim()}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
