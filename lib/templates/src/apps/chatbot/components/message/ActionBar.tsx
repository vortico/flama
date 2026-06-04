import { useCallback, useState } from 'react'

import { IconCheck, IconCopy, IconPencil, IconRefresh } from '@tabler/icons-react'
import { IconButton } from '@vortico/ui/inputs'

interface ActionBarProps {
  text?: string
  onEdit?: () => void
  onRedo?: () => void
  align: 'start' | 'end'
  alwaysVisible?: boolean
}

// Action toolbar rendered beneath a bubble. Copy is available whenever there is text; edit/redo render only when the
// corresponding handler is provided. By default the bar fades in on hover via the bubble's `group/msg`; pass
// `alwaysVisible` to keep it shown (used by assistant output).
export default function ActionBar({ text, onEdit, onRedo, align, alwaysVisible = false }: ActionBarProps) {
  const [copied, setCopied] = useState<boolean>(false)

  const onCopy = useCallback(async () => {
    if (!text) return
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [text])

  if (!text && !onEdit && !onRedo) return null

  return (
    <div
      className={`flex items-center gap-1 ${align === 'end' ? 'justify-end' : 'justify-start'} ${
        alwaysVisible ? '' : 'opacity-0 transition-opacity duration-200 group-hover/msg:opacity-100'
      }`}
    >
      {onEdit && (
        <IconButton icon={<IconPencil />} color="primary" size="sm" aria-label="Edit message" onClick={onEdit} />
      )}
      {onRedo && (
        <IconButton
          icon={<IconRefresh />}
          color="primary"
          size="sm"
          aria-label="Regenerate response"
          onClick={onRedo}
        />
      )}
      {text && (
        <IconButton
          icon={copied ? <IconCheck /> : <IconCopy />}
          color="primary"
          size="sm"
          aria-label="Copy to clipboard"
          onClick={() => void onCopy()}
        />
      )}
    </div>
  )
}
