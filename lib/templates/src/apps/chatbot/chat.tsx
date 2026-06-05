import ReactDOM from 'react-dom/client'

import { Footer, Menu } from '@/ui/components'

import { ChatApp } from './components'
import { Chat } from './data'

import 'katex/dist/katex.min.css'
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

const container = document.getElementById('app')
if (container) {
  ReactDOM.createRoot(container).render(<Page />)
}
