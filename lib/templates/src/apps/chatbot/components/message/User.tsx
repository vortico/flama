import { bgColorForTransparent, borderColor, mainShadow, shadowColor, textSize } from '@vortico/ui/styles'

import Markdown from '../Markdown'
import ActionBar from './ActionBar'

interface UserProps {
  text: string
  onEdit?: () => void
}

export default function User({ text, onEdit }: UserProps) {
  return (
    <div className="group/msg flex w-full flex-col items-end gap-1">
      <div
        className={`max-w-full min-w-0 border p-2 ${textSize['md']} ${bgColorForTransparent['flama']} ${borderColor['flama']} ${mainShadow} ${shadowColor['flama']}`}
      >
        <Markdown text={text} />
      </div>
      <ActionBar align="end" text={text} onEdit={onEdit} />
    </div>
  )
}
