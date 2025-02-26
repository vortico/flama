import type { Lines } from './types'

interface LineNumberProps {
  type: Lines['type']
  lines?: number
  token?: string
  selectedLine?: number
}

export default function LineNumbers({ type, lines, token, selectedLine }: LineNumberProps) {
  return (
    <div
      className="border-primary-500 bg-primary-900 hidden h-fit min-h-full w-fit flex-none border-r py-1 select-none md:sticky md:left-0 md:block"
      aria-hidden="true"
    >
      {Array.from(Array(lines).keys()).map((line) => (
        <div
          key={`line-number-${line + 1}`}
          className={`px-2 text-right font-mono text-xs leading-5 ${line + 1 === selectedLine ? 'text-flama-500 font-semibold' : 'text-primary-500'}`}
        >
          {type === 'token' ? token : line + 1}
        </div>
      ))}
    </div>
  )
}
