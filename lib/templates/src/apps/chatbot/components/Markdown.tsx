import type { ComponentProps } from 'react'
import { Code, Window } from '@vortico/ui/elements'
import type { CodeLanguage } from '@vortico/ui/elements'
import rehypeKatex from 'rehype-katex'
import ReactMarkdown, { type Components, type ExtraProps } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'

const CodeOverride = ({ className, children }: ComponentProps<'code'> & ExtraProps) => {
  const language = /language-(\w+)/.exec(className ?? '')?.[1]?.toLowerCase()

  // Math (inline `$x$` and display `$$x$$`) is emitted as `language-math` and already turned into
  // `.katex` spans by `rehype-katex` upstream, so the children are passed through untouched instead
  // of being treated as a fenced code block.
  if (language === 'math') {
    return <>{children}</>
  }

  const value = String(children).replace(/\n$/, '')
  const isBlock = value.includes('\n') || (className?.includes('language-') ?? false)
  if (isBlock) {
    return (
      <Window title={language ?? ''}>
        <div className="p-2">
          <Code code={value} language={language as CodeLanguage | undefined} inline={false} size="xs" />
        </div>
      </Window>
    )
  }
  return <Code code={value} inline={true} size="xs" />
}

const STATIC_OVERRIDES: Components = {
  pre: ({ children }) => <>{children}</>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-flama-500 underline">
      {children}
    </a>
  ),
  p: ({ children }) => <p className="my-1 w-full first:mt-0 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="my-1 w-full list-outside list-disc ps-5 first:mt-0 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="my-1 w-full list-outside list-decimal ps-5 first:mt-0 last:mb-0">{children}</ol>,
  h1: ({ children }) => <h1 className="my-2 w-full text-lg font-bold first:mt-0 last:mb-0">{children}</h1>,
  h2: ({ children }) => <h2 className="my-2 w-full text-base font-bold first:mt-0 last:mb-0">{children}</h2>,
  h3: ({ children }) => <h3 className="my-2 w-full text-base font-semibold first:mt-0 last:mb-0">{children}</h3>,
  h4: ({ children }) => <h4 className="my-2 w-full text-sm font-semibold first:mt-0 last:mb-0">{children}</h4>,
  h5: ({ children }) => <h5 className="my-2 w-full text-sm font-medium first:mt-0 last:mb-0">{children}</h5>,
  h6: ({ children }) => <h6 className="my-2 w-full text-xs font-medium first:mt-0 last:mb-0">{children}</h6>,
  blockquote: ({ children }) => (
    <blockquote className="border-primary-300 my-1 border-l-2 pl-3 italic">{children}</blockquote>
  ),
  hr: () => <div className="border-primary-300 my-2 w-full border-t" />,
  code: CodeOverride,
}

interface MarkdownProps {
  text: string
}

export default function Markdown({ text }: MarkdownProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[[rehypeKatex, { throwOnError: false }]]}
      components={STATIC_OVERRIDES}
    >
      {text}
    </ReactMarkdown>
  )
}
