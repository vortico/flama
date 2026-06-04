import { IconAlertOctagonFilled } from '@tabler/icons-react'
import { bgColorForTransparent, borderColor, mainShadow, shadowColor, textColor, textSize } from '@vortico/ui/styles'

export interface ErrorProps {
  text: string
}

export default function Error({ text }: ErrorProps) {
  return (
    <div
      className={`flex max-w-full min-w-0 items-start gap-2 border p-2 ${textSize['sm']} ${bgColorForTransparent['flama']} ${borderColor['flama']} ${mainShadow} ${shadowColor['flama']}`}
    >
      <IconAlertOctagonFilled size={18} className={`shrink-0 ${textColor['flama']}`} />
      <span className="select-text">{text}</span>
    </div>
  )
}
