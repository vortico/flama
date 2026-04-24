import ReactDOM from 'react-dom/client'

import { Chat } from '@/data/chatbot'
import { ChatApp, Footer, Menu } from '@/ui/components'

import '@/ui/styles/chatbot.css'

function Page() {
  const chat = new Chat()

  return (
    <div className="flex h-screen flex-col">
      <Menu />
      <div className="mt-[calc(3.5rem+1px)] flex flex-1 flex-col overflow-hidden">
        <ChatApp streamUrl={chat.streamUrl} />
      </div>
      <Footer />
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('app')!).render(<Page />)
