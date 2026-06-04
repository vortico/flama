import Markdown from '../Markdown'
import ActionBar from './ActionBar'

interface OutputProps {
  text: string
  onRedo?: () => void
}

export default function Output({ text, onRedo }: OutputProps) {
  return (
    <div className="flex w-full flex-col items-start gap-1">
      <Markdown text={text} />
      <ActionBar align="start" text={text} onRedo={onRedo} alwaysVisible />
    </div>
  )
}
