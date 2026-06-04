import ReactDOM from 'react-dom/client'

import { Footer, Menu } from '@/ui/components'

import { ChatApp } from './components'
import { Chat } from './data'

import '@/ui/styles/base.css'

function Page() {
  const chat = new Chat()

  return (
    <div className="flex h-screen flex-col">
      <Menu />
      <div className="mt-14.25 flex flex-1 flex-col overflow-hidden">
        <ChatApp streamUrl={chat.streamUrl} />
      </div>
      <Footer />
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('app')!).render(<Page />)
