import ReactDOM from 'react-dom/client'

import { Footer, Menu } from '@/ui/components'

import { Docs } from './components'

import '@/ui/styles/base.css'
import './styles/docs.css'
import '@scalar/api-reference-react/style.css'

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
