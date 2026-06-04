import { mainBgColor } from '@vortico/ui/styles'

import { ChatProvider } from '../context/chat'
import { Conversation } from './conversation'
import PromptInput from './PromptInput'

function ChatLayout() {
  return (
    <div className="relative flex h-full flex-col">
      <Conversation />
      {/* Composer: an absolute bottom bar (fade + solid container) overlapping the bottom of the Conversation. Its right
          edge is inset by the scrollbar width (8px, @vortico/ui's fixed scrollbar) so the fade never paints over it. */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-2 z-10">
        <div className="from-primary-50 h-32 bg-linear-to-t to-transparent" />
        <div className={`${mainBgColor}`}>
          <div className="pointer-events-auto mx-auto max-w-5xl px-4 pb-2 sm:px-6 md:px-8">
            <div className="mx-auto w-full sm:w-4/5">
              <PromptInput />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

interface ChatAppProps {
  streamUrl: string
}

export default function ChatApp({ streamUrl }: ChatAppProps) {
  return (
    <ChatProvider streamUrl={streamUrl}>
      <ChatLayout />
    </ChatProvider>
  )
}
