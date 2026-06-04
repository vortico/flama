import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'

import { IconBrain, IconChevronDown, IconChevronRight } from '@tabler/icons-react'
import { bgColorForTransparent, borderColor, mainShadow, shadowColor, textSize } from '@vortico/ui/styles'
import { AnimatePresence, motion } from 'motion/react'

import Markdown from '../Markdown'

interface CollapseButtonProps {
  channel: string
  state: [boolean, Dispatch<SetStateAction<boolean>>]
}

function CollapseButton({ channel, state: [expanded, setExpanded] }: CollapseButtonProps) {
  const chevron = expanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />

  return (
    <button
      type="button"
      onClick={() => setExpanded((v) => !v)}
      className="flex w-full items-center justify-start gap-2"
    >
      <IconBrain size={14} />
      <span className="flex-1 text-left">{`${expanded ? 'Hide' : 'Show'} ${channel ?? 'thinking'}`}</span>
      {chevron}
    </button>
  )
}

interface ThoughtProps {
  channel: string | null
  text: string
  isActive: boolean
}

export default function Thought({ channel, text, isActive }: ThoughtProps) {
  const [expanded, setExpanded] = useState(true)
  const wasActiveRef = useRef(isActive)

  useEffect(() => {
    if (wasActiveRef.current && !isActive) setExpanded(false)
    wasActiveRef.current = isActive
  }, [isActive])

  return (
    <div
      className={`max-w-full min-w-0 border p-2 ${textSize['sm']} ${bgColorForTransparent['primary-light']} ${borderColor['primary-light']} ${mainShadow} ${shadowColor['primary-light']}`}
    >
      <CollapseButton channel={channel ?? 'thinking'} state={[expanded, setExpanded]} />
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'tween', duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="pt-2 italic select-text">
              <Markdown text={text} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
