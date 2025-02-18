import EnvironmentTable, { Environment } from '@/components/debug/EnvironmentTable'
import ErrorTitle from '@/components/debug/ErrorTitle'
import ErrorTraceback, { Error } from '@/components/debug/ErrorTraceback'
import RequestTable, { Request } from '@/components/debug/RequestTable'
import FlamaLogo from '@/components/FlamaLogo'

import '@/styles/main.css'

import React from 'react'

import ReactDOM from 'react-dom/client'

function ServerErrorPage() {
  const error = new Error()
  const request = new Request()
  const environment = new Environment()

  return (
    <>
      <header>
        <div className="mx-auto flex max-w-8xl items-center justify-between gap-x-20 px-10 py-4">
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
            <div className="mx-auto max-w-8xl px-10">
              <h2 className="text-2xl font-semibold text-primary-700">Traceback</h2>
              <div className="mt-10 w-full">
                <ErrorTraceback error={error} />
              </div>
            </div>
          </div>
        </section>
        <section id="request">
          <div className="mt-16 border-t border-brand-500/50 bg-gradient-to-b from-brand-500/10 py-8">
            <div className="mx-auto max-w-8xl px-10">
              <h2 className="text-2xl font-semibold text-primary-700">Request</h2>
            </div>
          </div>
          <div className="mx-auto mt-10 w-full max-w-8xl px-10">
            <RequestTable request={request} />
          </div>
        </section>
        <section id="environment">
          <div className="mt-16 border-t border-brand-500/50 bg-gradient-to-b from-brand-500/10 py-8">
            <div className="mx-auto max-w-8xl px-10">
              <h2 className="w-full text-2xl font-semibold text-primary-700">Environment</h2>
            </div>
          </div>
          <div className="mx-auto my-10 w-full max-w-8xl px-10">
            <EnvironmentTable environment={environment} />
          </div>
        </section>
      </main>
    </>
  )
}

ReactDOM.createRoot(document.getElementById('app')!).render(<ServerErrorPage />)
