import type { Language } from 'prism-react-renderer'
import Highlight, { defaultProps } from 'prism-react-renderer'
import ClipboardButton from '@/components/ClipboardButton'
import React, { MutableRefObject } from 'react'

interface LineNumbersProps {
  lines: number
  token?: string
}

function LineNumbers({ lines, token }: LineNumbersProps) {
  return (
    <div
      className="hidden flex-none select-none py-4 pl-4 text-right text-primary-500 md:block"
      aria-hidden="true"
    >
      {Array.from(Array(lines).keys()).map((line) => (
        <div key={`line-number-${line + 1}`} className="line-number">
          {token ? token : line + 1}
        </div>
      ))}
    </div>
  )
}

interface CodeWrapperProps extends React.ComponentProps<'pre'> {
  lines: number
  token?: string | boolean
  code: string
  copyButton?: boolean
}

function CodeWrapper({
  lines,
  token,
  code,
  copyButton,
  children,
  className,
}: CodeWrapperProps) {
  return (
    <pre
      className={`group relative flex h-fit w-full overflow-hidden whitespace-pre text-left text-sm leading-6 ${className}`}
    >
      {token && (
        <LineNumbers
          lines={lines}
          token={typeof token === 'string' ? token : undefined}
        />
      )}
      <code className="relative block h-fit w-fit flex-auto overflow-auto p-4 text-primary-200">
        {children}
      </code>
      {copyButton && <ClipboardButton code={code} />}
    </pre>
  )
}

export interface CodeBlockProps {
  code: string
  language?: Language
  lineNumbers?: string | boolean
  copyButton?: boolean
  selectedLine?: number
  selectedLineRef?: MutableRefObject<HTMLDivElement | null>
}

export default function CodeBlock({
  code,
  language,
  selectedLine,
  selectedLineRef,
  lineNumbers = true,
  copyButton = true,
}: CodeBlockProps) {
  const { theme, ...props } = defaultProps

  return language ? (
    <Highlight {...props} code={code} language={language}>
      {({ className, tokens, getLineProps, getTokenProps }) => (
        <CodeWrapper
          lines={tokens.length}
          token={lineNumbers}
          code={code}
          copyButton={copyButton}
          className={className}
        >
          {tokens.map((line, i) => {
            const {
              className: lineClassName,
              key: lineKey,
              ...lineProps
            } = getLineProps({
              line,
              key: i,
            })
            return (
              <div
                key={lineKey}
                ref={selectedLine === i + 1 ? selectedLineRef : undefined}
                className={`${lineClassName} ${
                  selectedLine === i + 1 ? 'token-line-selected' : ''
                }`}
                {...lineProps}
              >
                {line.map((token, j) => {
                  const { key: tokenKey, ...tokenProps } = getTokenProps({
                    token,
                    key: j,
                  })
                  return <span key={tokenKey} {...tokenProps} />
                })}
              </div>
            )
          })}
        </CodeWrapper>
      )}
    </Highlight>
  ) : (
    <CodeWrapper
      lines={code.split('\n').length}
      token={lineNumbers}
      code={code}
      copyButton={copyButton}
    >
      {code}
    </CodeWrapper>
  )
}
