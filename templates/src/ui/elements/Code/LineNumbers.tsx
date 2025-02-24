import type { Lines } from './types'

interface LineNumberProps {
  type: Lines['type']
  lines?: number
  token?: string
}

export default function LineNumbers({ type, lines, token }: LineNumberProps) {
  return (
    <div
      className="border-primary-500 bg-primary-900 hidden h-fit w-fit flex-none border-r px-2 py-1 select-none md:sticky md:left-0 md:block"
      aria-hidden="true"
    >
      {Array.from(Array(lines).keys()).map((line) => (
        <div key={`line-number-${line + 1}`} className="text-primary-500 text-right font-mono text-xs leading-5">
          {type === 'token' ? token : line + 1}
        </div>
      ))}
    </div>
  )
}
