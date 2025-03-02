import ReactDOM from 'react-dom/client'

import { Request } from '@/data/debug'
import { EnvironmentTable, ErrorTitle, Footer, Menu, RequestTable, Section, URLTree } from '@/ui/components'

import '@/styles/debug/error_404.css'

function Page() {
  const request = new Request()

  return (
    <div className="min-h-screen">
      <Menu />
      <header>
        <Section id="error" border={false} className="mt-28">
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
      <Footer />
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('app')!).render(<Page />)
