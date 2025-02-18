import ReactDOM from 'react-dom/client'

import { Error, Request } from '@/data/debug'
import { EnvironmentTable, ErrorTitle, ErrorTraceback, Footer, Menu, RequestTable, Section } from '@/ui/components'

import '@/ui/styles/tailwind.css'

function Page() {
  const error = new Error()
  const request = new Request()

  return (
    <div>
      <Menu />
      <div className="mt-[calc(3.5rem+1px)] h-[calc(100vh-6.5rem-2px)] overflow-auto">
        <header>
          <Section id="error" border={false}>
            <ErrorTitle
              error={error.error}
              path={request.path}
              method={request.method}
              description={error.description}
            />
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
      </div>
      <Footer />
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('app')!).render(<Page />)
