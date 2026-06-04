import { IconMessageDots } from '@tabler/icons-react'
import { mainTextContrast, textColor } from '@vortico/ui/styles'

export default function EmptyChatInfo() {
  return (
    <div className={`flex flex-1 flex-col items-center justify-center gap-2 ${mainTextContrast}`}>
      <div className={`${textColor['flama']}`}>
        <IconMessageDots width={48} height={48} stroke="currentColor" strokeWidth={2} />
      </div>
      <p className="text-lg font-medium">How can I help you today?</p>
      <p className="text-sm">Send a message to start the conversation.</p>
    </div>
  )
}
