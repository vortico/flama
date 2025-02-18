import getHighlighter, { theme, tokenStyle } from '@/ui/lib/highlighter'

export default function HighlightCode({
  code,
  language,
  selectedLine,
}: {
  code: string
  language: string
  selectedLine?: number
}) {
  const tokens = getHighlighter().codeToTokens(code, { lang: language, theme })

  const isInline = tokens?.tokens.length === 1

  return (
    <code>
      {tokens?.tokens.map((line, i) => (
        <span
          key={i}
          className={`${isInline ? 'inline' : 'block w-full px-2 text-sm'} ${
            selectedLine === i + 1 ? 'bg-flama-500/25' : ''
          }`}
        >
          {line.length === 0 ? (
            <br />
          ) : (
            line.map((token, j) => (
              <span key={j} style={tokenStyle(token)}>
                {token.content}
              </span>
            ))
          )}
        </span>
      ))}
    </code>
  )
}
