import { useCallback, useEffect, type ChangeEvent, type KeyboardEvent } from 'react'

import { IconPlayerStopFilled, IconSend } from '@tabler/icons-react'
import { BorderBox, RippleBox } from '@vortico/ui/containers'
import { TextArea } from '@vortico/ui/inputs'
import {
  bgHoverColor,
  iconRoundedSize,
  iconSize,
  mainBgColor,
  mainShadow,
  shadowColor,
  textColor,
} from '@vortico/ui/styles'

import { useChatContext } from '../context/chat'

function SendButton({ isStreaming, onClick }: { isStreaming: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={isStreaming ? 'Stop' : 'Send'}
      className={`inline-flex shrink-0 cursor-pointer transition ${textColor['flama']} ${bgHoverColor['flama']}`}
    >
      <RippleBox from="center" color="flama" className={`flex items-center justify-center ${iconRoundedSize['xl']}`}>
        {isStreaming ? <IconPlayerStopFilled size={iconSize['xl']} /> : <IconSend size={iconSize['xl']} />}
      </RippleBox>
    </button>
  )
}

export default function PromptInput() {
  const { input, setInput, submit, cancel, isStreaming, inputRef } = useChatContext()

  useEffect(() => {
    if (!inputRef.current) return
    inputRef.current.style.height = 'auto'
    inputRef.current.style.height = `${inputRef.current.scrollHeight}px`
  }, [inputRef, input])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        if (!isStreaming) submit()
      }
    },
    [submit, isStreaming],
  )
  const handleChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => setInput(e.target.value), [setInput])
  const handleClick = useCallback(() => (isStreaming ? cancel() : submit()), [isStreaming, cancel, submit])

  return (
    <BorderBox
      color="flama"
      loading={isStreaming}
      className={`mx-auto flex max-h-48 min-h-10 w-full items-center justify-between gap-2 ${mainShadow} ${shadowColor['flama']} ${mainBgColor}`}
    >
      <div className="max-h-47.5 flex-1 overflow-y-auto">
        <TextArea
          ref={inputRef}
          name="prompt"
          color="flama"
          size="md"
          rows={1}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          inline
        />
      </div>
      <SendButton isStreaming={isStreaming} onClick={handleClick} />
    </BorderBox>
  )
}
