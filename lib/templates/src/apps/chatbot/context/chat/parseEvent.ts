import type { Action } from './reducer'
import type { BlockDelta, BlockDescriptor } from './types'

type Data = Record<string, unknown>

// Wire-event -> Action codec. Adding a new event means adding a row here; consumers (reducer, transport) don't change.
// Note: the wire `message.start` frame is intentionally unhandled — the assistant turn is opened client-side in
// `useChat` (ASSISTANT_TURN_START) before the stream is read.
const HANDLERS: Record<string, (data: Data) => Action | null> = {
  'block.start': (d) =>
    typeof d.index === 'number' && d.index >= 0
      ? { type: 'BLOCK_START', index: d.index, descriptor: (d.block ?? {}) as BlockDescriptor }
      : null,
  'block.delta': (d) =>
    typeof d.index === 'number' && d.index >= 0
      ? { type: 'BLOCK_DELTA', index: d.index, delta: (d.delta ?? {}) as BlockDelta }
      : null,
  'message.stop': () => ({ type: 'STREAM_DONE' }),
  error: (d) => ({ type: 'STREAM_ERROR', detail: `Error: ${typeof d.detail === 'string' ? d.detail : 'Stream error'}` }),
}

export const SSE_EVENTS = Object.keys(HANDLERS)

export function parseEvent(name: string, raw: string): Action | null {
  const handler = HANDLERS[name]
  if (!handler) return null
  let data: Data = {}
  if (raw) {
    try {
      const parsed = JSON.parse(raw)
      if (parsed && typeof parsed === 'object') data = parsed as Data
    } catch {
      // Malformed frame: fall through with empty payload so the handler can still produce a default Action.
    }
  }
  return handler(data)
}
