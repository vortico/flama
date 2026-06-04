import type {
  AssistantMessage,
  Block,
  BlockDelta,
  BlockDescriptor,
  Message,
  Role,
  TextBlock,
} from './types'

export type Action =
  | { type: 'USER_TURN_START'; prompt: string }
  | { type: 'ASSISTANT_TURN_START' }
  | { type: 'BLOCK_START'; index: number; descriptor: BlockDescriptor }
  | { type: 'BLOCK_DELTA'; index: number; delta: BlockDelta }
  | { type: 'STREAM_ERROR'; detail: string }
  | { type: 'STREAM_DONE' }
  | { type: 'DROP_LAST_ASSISTANT' }
  | { type: 'DROP_FROM_LAST_USER' }

export interface State {
  messages: Message[]
  isStreaming: boolean
}

export const INITIAL_STATE: State = { messages: [], isStreaming: false }

function buildBlock(descriptor: BlockDescriptor): Block {
  if (descriptor.type === 'tool') {
    return {
      id: typeof descriptor.id === 'string' && descriptor.id ? descriptor.id : crypto.randomUUID(),
      kind: 'tool',
      name: typeof descriptor.name === 'string' ? descriptor.name : '',
      arguments:
        descriptor.arguments && typeof descriptor.arguments === 'object'
          ? (descriptor.arguments as Record<string, unknown>)
          : {},
    }
  }
  return {
    id: typeof descriptor.id === 'string' && descriptor.id ? descriptor.id : crypto.randomUUID(),
    kind: 'text',
    channel: typeof descriptor.channel === 'string' || descriptor.channel === null ? descriptor.channel : 'output',
    text: '',
  }
}

function applyDelta(block: Block, delta: BlockDelta): Block {
  if (block.kind === 'text' && typeof delta.text === 'string') {
    return { ...block, text: block.text + delta.text }
  }
  if (block.kind === 'tool') {
    const name = typeof delta.name === 'string' && delta.name ? delta.name : block.name
    const args =
      delta.arguments && typeof delta.arguments === 'object' ? delta.arguments : block.arguments
    if (name === block.name && args === block.arguments) return block
    return { ...block, name, arguments: args }
  }
  return block
}

// Wrap a reducer case that mutates the trailing assistant turn. The callback returns either a new turn (replaces the
// previous one) or `void` (no-op, preserves state identity). All immutable splice gymnastics live here.
function withLastAssistantTurn(
  state: State,
  fn: (turn: AssistantMessage) => AssistantMessage | void,
): State {
  const last = state.messages.at(-1)
  if (!last || last.role !== 'assistant') return state
  const next = fn(last) ?? last
  if (next === last) return state
  return { ...state, messages: [...state.messages.slice(0, -1), next] }
}

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'USER_TURN_START': {
      const userTurn: TextBlock = { id: crypto.randomUUID(), kind: 'text', channel: 'output', text: action.prompt }
      return {
        ...state,
        messages: [...state.messages, { id: crypto.randomUUID(), role: 'user', blocks: [userTurn] }],
      }
    }
    case 'ASSISTANT_TURN_START':
      return {
        ...state,
        messages: [...state.messages, { id: crypto.randomUUID(), role: 'assistant', blocks: [] }],
        isStreaming: true,
      }
    case 'BLOCK_START': {
      const { index, descriptor } = action
      // Late blocks may arrive after STREAM_ERROR replaces the assistant turn — drop them rather than mutating the
      // error placeholder.
      return withLastAssistantTurn(state, (turn) => {
        if (turn.error || turn.blocks[index]) return
        const blocks = [...turn.blocks]
        blocks[index] = buildBlock(descriptor)
        return { ...turn, blocks }
      })
    }
    case 'BLOCK_DELTA': {
      const { index, delta } = action
      return withLastAssistantTurn(state, (turn) => {
        if (turn.error) return
        const block = turn.blocks[index]
        if (!block) return
        const next = applyDelta(block, delta)
        if (next === block) return
        const blocks = [...turn.blocks]
        blocks[index] = next
        return { ...turn, blocks }
      })
    }
    case 'STREAM_ERROR': {
      const last = state.messages.at(-1)
      if (!last || last.role !== 'assistant') return { ...state, isStreaming: false }
      return {
        ...state,
        messages: [...state.messages.slice(0, -1), { ...last, error: action.detail }],
        isStreaming: false,
      }
    }
    case 'STREAM_DONE':
      return { ...state, isStreaming: false }
    case 'DROP_LAST_ASSISTANT': {
      const last = state.messages.at(-1)
      if (!last || last.role !== 'assistant') return state
      return { ...state, messages: state.messages.slice(0, -1) }
    }
    case 'DROP_FROM_LAST_USER': {
      const index = state.messages.findLastIndex((m) => m.role === 'user')
      if (index === -1) return state
      return { ...state, messages: state.messages.slice(0, index) }
    }
    default: {
      const _exhaustive: never = action
      void _exhaustive
      return state
    }
  }
}

// Copyable plain text for a single turn: a user turn joins every block; an assistant turn keeps only the `output`
// channel (thoughts and tool calls are internal), mirroring the `toWireHistory` projection.
export function messageText(message: Message): string {
  return (message.blocks as Block[])
    .filter((b): b is TextBlock => b.kind === 'text' && (message.role === 'user' || b.channel === 'output'))
    .map((b) => b.text)
    .join('')
}

// Serialise prior turns into the native `messages` envelope so the model sees the conversation history. Only the
// `output` channel of an assistant turn is replayed: thinking is internal reasoning, and tool blocks would need a
// matching tool-result turn the UI can't synthesise yet.
export function toWireHistory(messages: Message[]): { role: Role; content: string }[] {
  return messages
    .filter((m) => m.role !== 'assistant' || !m.error)
    .map((m) => ({
      role: m.role,
      content: (m.blocks as Block[])
        .filter((b): b is TextBlock => b.kind === 'text' && b.channel === 'output')
        .map((b) => b.text)
        .join(''),
    }))
    .filter((m) => m.content.length > 0)
}
