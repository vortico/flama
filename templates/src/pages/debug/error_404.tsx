import Environment from '@/components/debug/Environment'
import Request from '@/components/debug/Request'
import FlamaLogo from '@/components/FlamaLogo'
import '@/styles/main.css'
import React from 'react'
import { createRoot } from 'react-dom/client'
import URLTree from '@/components/debug/URLTree'
import ErrorTitle from '@/components/debug/ErrorTitle'

function ServerErrorPage() {
  const urls = JSON.parse('||@ urls|safe_json @||')

  const request = {
    path: '||@ request.path @||',
    method: '||@ request.method @||',
    clientHost: '||@ request.client.host @||',
    clientPort: '||@ request.client.port @||',
    pathParams: JSON.parse('||@ request.params.path|safe_json @||'),
    queryParams: JSON.parse('||@ request.params.query|safe_json @||'),
    headers: JSON.parse('||@ request.headers|safe_json @||'),
    cookies: JSON.parse('||@ request.cookies|safe_json @||'),
  }

  const environment = {
    pythonVersion: '||@ environment.python_version @||',
    python: '||@ environment.python @||',
    platform: '||@ environment.platform @||',
    path: JSON.parse('||@ environment.path|safe_json @||'),
  }

  return (
    <>
      <header>
        <div className="mx-auto flex max-w-8xl items-center justify-between gap-x-20 px-10 py-4">
          <div>
            <ErrorTitle error="Not Found" path={request.path} method={request.method} />
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
              <h2 className="text-2xl font-semibold text-primary-700">Application URLs</h2>
              <div className="mt-10 w-full">
                <URLTree urls={urls} />
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
            <Request
              path={request.path}
              method={request.method}
              clientHost={request.clientHost}
              clientPort={request.clientPort}
              queryParams={request.queryParams}
              pathParams={request.pathParams}
              headers={request.headers}
              cookies={request.cookies}
            />
          </div>
        </section>
        <section id="environment">
          <div className="mt-16 border-t border-brand-500/50 bg-gradient-to-b from-brand-500/10 py-8">
            <div className="mx-auto max-w-8xl px-10">
              <h2 className="w-full text-2xl font-semibold text-primary-700">Environment</h2>
            </div>
          </div>
          <div className="mx-auto my-10 w-full max-w-8xl px-10">
            <Environment
              pythonVersion={environment.pythonVersion}
              python={environment.python}
              platform={environment.platform}
              path={environment.path}
            />
          </div>
        </section>
      </main>
    </>
  )
}

createRoot(document.getElementById('app')!).render(<ServerErrorPage />)
