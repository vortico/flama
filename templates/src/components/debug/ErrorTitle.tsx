import React from 'react'

export interface ErrorTitleProps {
  error: string
  method: string
  path: string
  description?: string
}

export default function ErrorTitle({ error, method, path, description }: ErrorTitleProps) {
  return (
    <>
      <div className="text-2xl">
        <span className="font-bold text-brand-500">{error}</span> raised at <span className="font-bold">{method}</span>{' '}
        <span className="font-mono">{path}</span>
      </div>
      {description && <div className="text-xl font-medium">{description}</div>}
    </>
  )
}
