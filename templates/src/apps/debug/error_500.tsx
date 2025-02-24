import ReactDOM from 'react-dom/client'

import { Error, Request } from '@/data/debug'
import { EnvironmentTable, ErrorTitle, ErrorTraceback, RequestTable } from '@/ui/components'
import { FlamaLogo } from '@/ui/logos'

import '@/styles/main.css'

function Page() {
  const error = new Error()
  const request = new Request()

  return (
    <>
      <header>
        <div className="max-w-8xl mx-auto flex items-center justify-between gap-x-20 px-10 py-4">
          <div>
            <ErrorTitle
              error={error.error}
              path={request.path}
              method={request.method}
              description={error.description}
            />
          </div>
          <div>
            <FlamaLogo />
          </div>
        </div>
      </header>
      <main>
        <section id="traceback">
          <div className="mt-10 py-8">
            <div className="max-w-8xl mx-auto px-10">
              <h2 className="text-primary-700 text-2xl font-semibold">Traceback</h2>
              <div className="mt-10 w-full">
                <ErrorTraceback />
              </div>
            </div>
          </div>
        </section>
        <section id="request">
          <div className="border-flama-500/50 from-flama-500/10 mt-16 border-t bg-linear-to-b py-8">
            <div className="max-w-8xl mx-auto px-10">
              <h2 className="text-primary-700 text-2xl font-semibold">Request</h2>
            </div>
          </div>
          <div className="max-w-8xl mx-auto mt-10 w-full px-10">
            <RequestTable />
          </div>
        </section>
        <section id="environment">
          <div className="border-flama-500/50 from-flama-500/10 mt-16 border-t bg-linear-to-b py-8">
            <div className="max-w-8xl mx-auto px-10">
              <h2 className="text-primary-700 w-full text-2xl font-semibold">Environment</h2>
            </div>
          </div>
          <div className="max-w-8xl mx-auto my-10 w-full px-10">
            <EnvironmentTable />
          </div>
        </section>
      </main>
    </>
  )
}

ReactDOM.createRoot(document.getElementById('app')!).render(<Page />)
