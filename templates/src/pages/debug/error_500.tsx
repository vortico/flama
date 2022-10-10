import Environment from '@/components/debug/Environment'
import Request from '@/components/debug/Request'
import Traceback from '@/components/debug/Traceback'
import FlamaLogo from '@/components/FlamaLogo'
import '@/styles/main.css'
import React from 'react'
import { createRoot } from 'react-dom/client'

interface ErrorTitleProps {
  error: string
  method: string
  path: string
  description: string
}

function ErrorTitle({ error, method, path, description }: ErrorTitleProps) {
  return (
    <>
      <div className="text-2xl">
        <span className="font-bold text-brand-500">{error}</span> raised at{' '}
        <span className="font-bold">{method}</span>{' '}
        <span className="font-mono">{path}</span>
      </div>
      <div className="text-xl font-medium">{description}</div>
    </>
  )
}

function ServerErrorPage() {
  const error = {
    error: '||@ error.error @||',
    description: '||@ error.description @||',
    traceback: JSON.parse('||@ error.traceback|safe_json @||'),
  }

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
              <h2 className="text-2xl font-semibold text-primary-700">
                Traceback
              </h2>
              <div className="mt-10 w-full">
                <Traceback traceback={error.traceback} />
              </div>
            </div>
          </div>
        </section>
        <section id="request">
          <div className="mt-16 border-t border-brand-500/50 bg-gradient-to-b from-brand-500/10 py-8">
            <div className="mx-auto max-w-8xl px-10">
              <h2 className="text-2xl font-semibold text-primary-700">
                Request
              </h2>
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
              <h2 className="w-full text-2xl font-semibold text-primary-700">
                Environment
              </h2>
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