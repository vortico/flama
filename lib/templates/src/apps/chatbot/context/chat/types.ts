export type Role = 'user' | 'assistant'

export interface TextBlock {
  id: string
  kind: 'text'
  channel: string | null
  text: string
}

export interface ToolBlock {
  id: string
  kind: 'tool'
  name: string
  arguments: Record<string, unknown>
}

export type Block = TextBlock | ToolBlock

export interface UserMessage {
  id: string
  role: 'user'
  blocks: TextBlock[]
}

export interface AssistantMessage {
  id: string
  role: 'assistant'
  blocks: Block[]
  error?: string
}

export type Message = UserMessage | AssistantMessage

export interface BlockDescriptor {
  type?: 'text' | 'tool'
  channel?: string | null
  id?: string
  name?: string
  arguments?: Record<string, unknown>
}

// Wire-level delta frame (SSE `block.delta`). The server tags deltas as `text.delta` / `tool.delta`, but the reducer
// discriminates on the target block's already-known `kind` instead, so `type` is carried for completeness only and the
// payload fields are read by presence.
export interface BlockDelta {
  type?: 'text.delta' | 'tool.delta'
  text?: string
  name?: string
  arguments?: Record<string, unknown>
}
