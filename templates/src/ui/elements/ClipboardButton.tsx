import { useCallback, useState } from 'react'

import { IconCheck, IconClipboardCopy } from '@tabler/icons-react'

export interface ClipboardButtonProps {
  code: string
}

export default function ClipboardButton({ code }: ClipboardButtonProps) {
  const [copied, setCopied] = useState<boolean>(false)

  const onCopy = useCallback(async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 3000)
  }, [code, setCopied])

  return (
    <div
      className={`bg-primary-500/30 absolute top-4 right-4 flex h-8 w-8 items-center justify-center rounded opacity-0 ring-1 backdrop-blur transition-opacity duration-500 ring-inset group-hover:opacity-100 ${
        copied ? 'ring-brand-500/50' : 'ring-primary-500/50'
      }`}
    >
      <button onClick={onCopy} aria-label="Copy to Clipboard">
        {copied ? (
          <IconCheck className="text-brand-500 h-6 w-6" />
        ) : (
          <IconClipboardCopy className="text-primary-500 h-6 w-6" />
        )}
      </button>
    </div>
  )
}
