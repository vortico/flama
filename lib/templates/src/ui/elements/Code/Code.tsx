import CodeBlock from './CodeBlock'
import CodeInline from './CodeInline'
import HighlightCode from './HighlightCode'
import PlainCode from './PlainCode'
import type { Lines } from './types'

export interface CodeProps {
  code: string
  language?: string
  lines?: Lines
  copyButton?: boolean
  selectedLine?: number
  className?: string
}

export default function Code({ code, language, lines, copyButton = true, selectedLine, className }: CodeProps) {
  const isInline = lines === undefined && code.split('\n').length === 1

  const renderedCode = language ? (
    <HighlightCode code={code} language={language} selectedLine={selectedLine} />
  ) : (
    <PlainCode code={code} selectedLine={selectedLine} />
  )

  return isInline ? (
    <CodeInline className={className}>{renderedCode}</CodeInline>
  ) : (
    <CodeBlock code={code} lines={lines} copyButton={copyButton} className={className} selectedLine={selectedLine}>
      {renderedCode}
    </CodeBlock>
  )
}
