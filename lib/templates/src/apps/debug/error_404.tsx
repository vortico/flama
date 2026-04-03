import ReactDOM from 'react-dom/client'

import { Request } from '@/data/debug'
import { EnvironmentTable, ErrorTitle, Footer, Menu, RequestTable, Section, URLTree } from '@/ui/components'

import '@/ui/styles/tailwind.css'

function Page() {
  const request = new Request()

  return (
    <div>
      <Menu />
      <div className="mt-[calc(3.5rem+1px)] h-[calc(100vh-6.5rem-2px)] overflow-auto">
        <header>
          <Section id="error" border={false}>
            <ErrorTitle error="Not Found" path={request.path} method={request.method} />
          </Section>
        </header>
        <main>
          <Section id="url-tree" title="Application URLs">
            <URLTree />
          </Section>
          <Section id="request" title="Request">
            <RequestTable />
          </Section>
          <Section id="environment" title="Environment">
            <EnvironmentTable />
          </Section>
        </main>
      </div>
      <Footer />
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('app')!).render(<Page />)
