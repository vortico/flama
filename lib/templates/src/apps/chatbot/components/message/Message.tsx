import { useChatContext } from '../../context/chat'
import type {
  AssistantMessage as AssistantMessageType,
  Message as MessageType,
  UserMessage as UserMessageType,
} from '../../context/chat'
import Error from './Error'
import Loading from './Loading'
import Output from './Output'
import Thought from './Thought'
import Tool from './Tool'
import User from './User'

interface AssistantMessageProps {
  message: AssistantMessageType
  isLastAssistant: boolean
}

function AssistantMessage({ message, isLastAssistant }: AssistantMessageProps) {
  const { isStreaming, regenerate } = useChatContext()
  const isActive = isStreaming && isLastAssistant

  if (message.blocks.length === 0 && !message.error) return isActive ? <Loading /> : null

  const lastIndex = message.blocks.length - 1
  // Redo hangs off the last output bubble of the last (completed) assistant turn.
  const lastOutputId = message.blocks.filter((b) => b.kind === 'text' && b.channel === 'output').at(-1)?.id
  const canRedo = isLastAssistant && !isStreaming

  return (
    <div className="flex max-w-full flex-col items-start justify-start gap-2">
      {message.error ? (
        <Error text={message.error} />
      ) : (
        message.blocks.map((block, i) =>
          block.kind === 'tool' ? (
            <Tool key={block.id} id={block.id} name={block.name} arguments={block.arguments} />
          ) : block.channel === 'output' ? (
            <Output
              key={block.id}
              text={block.text}
              onRedo={canRedo && block.id === lastOutputId ? regenerate : undefined}
            />
          ) : (
            <Thought key={block.id} channel={block.channel} text={block.text} isActive={i === lastIndex} />
          ),
        )
      )}
    </div>
  )
}

interface UserMessageProps {
  message: UserMessageType
  isLastUser: boolean
}

function UserMessage({ message, isLastUser }: UserMessageProps) {
  const { isStreaming, editLast } = useChatContext()
  const lastBlockId = message.blocks.at(-1)?.id
  const canEdit = isLastUser && !isStreaming

  return (
    <div className="flex max-w-full flex-col items-end justify-start gap-2">
      {message.blocks.map((block) => (
        <User key={block.id} text={block.text} onEdit={canEdit && block.id === lastBlockId ? editLast : undefined} />
      ))}
    </div>
  )
}

interface MessageProps {
  message: MessageType
  isLastUser?: boolean
  isLastAssistant?: boolean
}

export default function Message({ message, isLastUser = false, isLastAssistant = false }: MessageProps) {
  return message.role === 'assistant' ? (
    <AssistantMessage message={message} isLastAssistant={isLastAssistant} />
  ) : (
    <UserMessage message={message} isLastUser={isLastUser} />
  )
}
