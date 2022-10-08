import Window, { WindowProps } from '@/components/Window'
import CodeBlock, { CodeBlockProps } from '@/components/CodeBlock'
import React, { useEffect, useRef } from 'react'

export interface CodeWindowProps extends WindowProps, CodeBlockProps {
  autoScroll?: boolean
}

export default function CodeWindow({
  title,
  code,
  language,
  lineNumbers,
  copyButton,
  selectedLine,
  autoScroll = false,
  className,
}: CodeWindowProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const scrollTargetRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (autoScroll && scrollContainerRef.current && scrollTargetRef.current)
      scrollContainerRef.current.scrollTo({
        top:
          scrollTargetRef.current.offsetTop -
          scrollContainerRef.current.clientHeight / 2,
        left: 0,
        behavior: 'smooth',
      })
  })

  return (
    <Window title={title} contentRef={scrollContainerRef}>
      <div className={className}>
        <CodeBlock
          code={code}
          language={language}
          lineNumbers={lineNumbers}
          copyButton={copyButton}
          selectedLine={selectedLine}
          selectedLineRef={scrollTargetRef}
        />
      </div>
    </Window>
  )
}
