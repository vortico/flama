import { ApiReferenceReact } from '@scalar/api-reference-react'

import { Docs as DocsData } from '@/data/schemas'

import '@/ui/styles/docs.css'
import '@scalar/api-reference-react/style.css'

export default function Docs() {
  const docs = new DocsData()

  return (
    <ApiReferenceReact
      configuration={{
        isEditable: false,
        spec: { url: docs.url },
        showSidebar: true,
        hideModels: false,
        hideDownloadButton: false,
        hideTestRequestButton: false,
        hideSearch: false,
        darkMode: false,
        forceDarkModeState: 'light',
        hideDarkModeToggle: true,
        searchHotKey: 'k',
        withDefaultFonts: false,
        defaultOpenAllTags: false,
        tagsSorter: 'alpha',
        operationsSorter: 'alpha',
        theme: 'none',
        hideClientButton: true,
      }}
    />
  )
}
