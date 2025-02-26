import React, { useEffect, useRef } from 'react'

import { ClipboardButton } from '@/ui/elements'

import LineNumbers from './LineNumbers'
import type { Lines } from './types'

const LINE_HEIGHT = 20

interface CodeBlockProps {
  code: string
  lines?: Lines
  copyButton?: boolean
  children: React.ReactNode
  selectedLine?: number
  className?: string
}

export default function CodeBlock({
  lines = { type: 'number' },
  copyButton = true,
  code,
  selectedLine,
  className,
  children,
}: CodeBlockProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (ref.current && selectedLine) {
      ref.current.scrollTo({
        top: selectedLine * LINE_HEIGHT - ref.current.clientHeight * 0.5,
        left: 0,
        behavior: 'smooth',
      })
    }
  }, [ref, selectedLine])

  return (
    <div
      className={`bg-primary-900 relative flex h-full min-h-full w-full overflow-auto whitespace-pre ${className || ''}`}
      ref={ref}
    >
      {lines && (
        <LineNumbers
          lines={code.split('\n').length - 1}
          type={lines.type}
          token={lines.token}
          selectedLine={selectedLine}
        />
      )}
      <pre className="bg-primary-900 h-fit min-h-full w-fit flex-auto py-1">{children}</pre>
      {copyButton && <ClipboardButton code={code} />}
    </div>
  )
}
