import { useEffect, useId, useState } from 'react'
import { Window } from '@vortico/ui/elements'

type MermaidApi = (typeof import('mermaid'))['default']

let mermaidPromise: Promise<MermaidApi> | undefined

// Mermaid is loaded on demand and initialised once. The diagram renders on the dark surface of
// `Window`, so a single fixed theme is used and no light/dark switching is needed. The colouring is
// inverted relative to the surface — light primary node/section fills with dark text and flama
// accents — so that any light pastel `fill` the model emits (without a matching text colour) still
// keeps its labels and titles readable instead of vanishing on a dark block.
async function loadMermaid(): Promise<MermaidApi> {
  if (mermaidPromise === undefined) {
    mermaidPromise = import('mermaid').then(({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'base',
        themeVariables: {
          darkMode: false,
          fontFamily: 'var(--font-mono)',
          fontSize: '14px',
          background: '#28292f', // primary-900 — Window surface stays dark behind
          primaryColor: '#e6e7ea', // primary-100 — light node fill
          mainBkg: '#e6e7ea',
          primaryBorderColor: '#e25822', // flama-500 — primary accent
          nodeBorder: '#e25822',
          primaryTextColor: '#1f1f24', // primary-950 — dark text
          nodeTextColor: '#1f1f24',
          textColor: '#1f1f24',
          lineColor: '#a5a6b1', // primary-300 — visible on the dark surface
          secondaryColor: '#fba292', // flama-100
          secondaryBorderColor: '#e25822',
          secondaryTextColor: '#1f1f24',
          tertiaryColor: '#c6c7cd', // primary-200
          tertiaryBorderColor: '#656775', // primary-500
          tertiaryTextColor: '#1f1f24',
          clusterBkg: '#c6c7cd', // primary-200 — light section
          clusterBorder: '#656775', // primary-500
          titleColor: '#1f1f24', // dark section title
          edgeLabelBackground: '#e6e7ea', // light chip for edge labels
        },
      })
      return mermaid
    })
  }
  return mermaidPromise
}

interface MermaidProps {
  chart: string
}

export default function Mermaid({ chart }: MermaidProps) {
  const id = `mermaid-${useId().replace(/[^a-zA-Z0-9-]/g, '')}`
  const [svg, setSvg] = useState('')

  useEffect(() => {
    let cancelled = false

    // Debounce so a diagram streamed token-by-token is only rendered once it settles, and keep the
    // last good SVG on screen while the in-progress source is still invalid.
    const handle = setTimeout(() => {
      void (async () => {
        const mermaid = await loadMermaid()
        if (cancelled || (await mermaid.parse(chart, { suppressErrors: true })) === false) {
          return
        }

        try {
          const { svg: rendered } = await mermaid.render(id, chart)
          if (!cancelled) {
            setSvg(rendered)
          }
        } catch {
          // A late render failure keeps the previous SVG / raw-source fallback rather than throwing.
        }
      })()
    }, 150)

    return () => {
      cancelled = true
      clearTimeout(handle)
    }
  }, [chart, id])

  return (
    <Window title="Diagram">
      <div className="flex justify-center p-4 [&_svg]:h-auto [&_svg]:max-w-full">
        {svg ? (
          <div dangerouslySetInnerHTML={{ __html: svg }} />
        ) : (
          <pre className="text-primary-300 text-xs whitespace-pre-wrap">{chart}</pre>
        )}
      </div>
    </Window>
  )
}
