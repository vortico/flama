import ReactDOM from 'react-dom/client'

import { Error, Request } from '@/data/debug'
import { EnvironmentTable, ErrorTitle, ErrorTraceback, Footer, Menu, RequestTable, Section } from '@/ui/components'

import '@/styles/debug/error_500.css'

function Page() {
  const error = new Error()
  const request = new Request()

  return (
    <div className="min-h-screen">
      <Menu />
      <header>
        <Section id="error" border={false} className="mt-28">
          <ErrorTitle error={error.error} path={request.path} method={request.method} description={error.description} />
        </Section>
      </header>
      <main>
        <Section id="traceback" title="Traceback">
          <ErrorTraceback />
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
