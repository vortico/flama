import React from 'react'

interface CodeInlineProps {
  className?: string
  children: React.ReactNode
}

export default function CodeInline({ className, children }: CodeInlineProps) {
  return <span className={className}>{children}</span>
}
