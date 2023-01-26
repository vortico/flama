import React, { useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import '@/styles/schemas/docs.css'

interface DocsPageProps {
  specUrl: string
  baseUrl: string
}

function DocsPage({ specUrl, baseUrl }: DocsPageProps) {
  useEffect(() => {
    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = 'https://unpkg.com/@stoplight/elements/web-components.min.js'

    const style = document.createElement('link')
    style.rel = 'stylesheet'
    style.href = 'https://unpkg.com/@stoplight/elements/styles.min.css'

    const elements = document.createElement('elements-api')
    elements.setAttribute('apiDescriptionUrl', specUrl)
    elements.setAttribute(
      'logo',
      'https://raw.githubusercontent.com/vortico/flama-site/master/public/favicon/icon-512x512.png'
    )
    elements.setAttribute('basePath', baseUrl)

    document.head.appendChild(script)
    document.head.appendChild(style)
    document.getElementById('app')?.appendChild(elements)

    return () => {
      document.getElementById('app')?.removeChild(elements)
      document.head.removeChild(style)
      document.head.removeChild(script)
    }
  }, [])

  return <></>
}

createRoot(document.getElementById('app')!).render(<DocsPage specUrl="||@ schema_url @||" baseUrl="||@ docs_url @||" />)
