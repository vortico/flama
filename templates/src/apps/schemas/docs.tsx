import ReactDOM from 'react-dom/client'

import { Docs, Footer, Menu } from '@/ui/components'

import '@/ui/styles/tailwind.css'

function Page() {
  return (
    <div>
      <Menu />
      <main>
        <Docs />
      </main>
      <Footer />
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('app')!).render(<Page />)
