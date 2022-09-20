import React, { useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import '../../css/schemas/docs.css'

function DocsPage ({ specUrl, baseUrl }) {
  useEffect(() => {
    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = 'https://unpkg.com/@stoplight/elements/web-components.min.js'

    const style = document.createElement('link')
    style.rel = 'stylesheet'
    style.href = 'https://unpkg.com/@stoplight/elements/styles.min.css'

    const elements = document.createElement('elements-api')
    elements.setAttribute('apiDescriptionUrl', specUrl)
    elements.setAttribute('logo', 'https://raw.githubusercontent.com/perdy/flama-site/master/public/favicon/icon-512x512.png')
    elements.setAttribute('basePath', baseUrl)

    document.head.appendChild(script)
    document.head.appendChild(style)
    document.getElementById('app').appendChild(elements)

    return () => {
      document.getElementById('app').removeChild(elements)
      document.head.removeChild(style)
      document.head.removeChild(script)
    }
  }, [])
}

createRoot(document.getElementById('app')).render(
  <DocsPage specUrl="${{ schema_url }}" baseUrl="${{ docs_url }}"/>
)
