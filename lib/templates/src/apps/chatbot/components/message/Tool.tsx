import { useState, type Dispatch, type SetStateAction } from 'react'

import { IconChevronDown, IconChevronRight, IconTool } from '@tabler/icons-react'
import { Code } from '@vortico/ui/elements'
import { bgColorForTransparent, borderColor, mainShadow, shadowColor, textSize } from '@vortico/ui/styles'
import { AnimatePresence, motion } from 'motion/react'

interface CollapseButtonProps {
  tool: string
  state: [boolean, Dispatch<SetStateAction<boolean>>]
}

function CollapseButton({ tool, state: [expanded, setExpanded] }: CollapseButtonProps) {
  const chevron = expanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />

  return (
    <button
      type="button"
      onClick={() => setExpanded((v) => !v)}
      className="flex w-full items-center justify-start gap-2"
    >
      <IconTool size={14} />
      <span className="flex-1 text-left">
        {`${expanded ? 'Hide' : 'Show'} tool call: `} <code className="font-mono">{tool || '...'}</code>
      </span>
      {chevron}
    </button>
  )
}

interface ToolArgumentProps {
  argument: [string, string | object | null | unknown]
}

function ToolArgument({ argument: [key, value] }: ToolArgumentProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-primary-500 font-medium">{key}:</span>
      {value === null ? (
        <span className="font-mono">null</span>
      ) : typeof value === 'string' && value.includes('\n') ? (
        <Code code={value} />
      ) : value !== null && typeof value === 'object' ? (
        <Code code={JSON.stringify(value, null, 2)} language="json" />
      ) : (
        <span className="font-mono">String(value)</span>
      )}
    </div>
  )
}

interface ToolProps {
  id: string
  name: string
  arguments: Record<string, unknown>
}

export default function Tool({ id, name, arguments: args }: ToolProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className={`max-w-full min-w-0 border p-2 ${textSize['sm']} ${bgColorForTransparent['primary-light']} ${borderColor['primary-light']} ${mainShadow} ${shadowColor['primary-light']}`}
    >
      <CollapseButton tool={name} state={[expanded, setExpanded]} />
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'tween', duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-2 pt-2">
              <div className="flex gap-2">
                <span className="text-primary-500 font-medium">id:</span>
                <span className="font-mono">{id}</span>
              </div>
              {Object.entries(args).map(([key, value]) => (
                <ToolArgument key={key} argument={[key, value]} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
