import React, { useCallback, useState } from 'react'
import { CheckIcon, DocumentDuplicateIcon } from '@heroicons/react/24/outline'

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
      className={`absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded bg-primary-500/30 opacity-0 ring-1 ring-inset backdrop-blur transition-opacity duration-500 group-hover:opacity-100 ${
        copied ? 'ring-brand-500/50' : 'ring-primary-500/50'
      }`}
    >
      <button onClick={onCopy} aria-label="Copy to Clipboard">
        {copied ? (
          <CheckIcon className="h-6 w-6 text-brand-500" />
        ) : (
          <DocumentDuplicateIcon className="h-6 w-6 text-primary-500" />
        )}
      </button>
    </div>
  )
}
