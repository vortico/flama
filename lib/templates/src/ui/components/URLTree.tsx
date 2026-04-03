import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { IconChevronRight, IconCircleFilled } from '@tabler/icons-react'

import { URLs } from '@/data/debug'

type TApp = URLs['apps'][number]
type TEndpoint = URLs['endpoints'][number]

function Tooltip({ data }: { data: Map<string, string | number | undefined> }) {
  return (
    <div className="bg-primary-800 text-primary-200 after:border-b-primary-800 absolute -bottom-2 left-1/2 z-20 hidden -translate-x-1/2 translate-y-full rounded-lg p-3 text-left text-sm group-hover:block after:absolute after:bottom-[100%] after:left-1/2 after:-translate-x-1/2 after:border-8 after:border-x-transparent after:border-t-transparent after:content-['']">
      <ul>
        {Array.from(data.entries())
          .sort((a, b) => a[0].localeCompare(b[0]))
          .filter((x) => x[1])
          .map(([k, v], i) => (
            <li key={i}>
              <span className="text-flama-400 capitalize">{k}:</span> <span>{v}</span>
            </li>
          ))}
      </ul>
    </div>
  )
}

function Endpoint({ endpoint: e }: { endpoint: TEndpoint }) {
  const { endpoint, file, line, module, name, path } = e
  return (
    <div className="group border-primary-300 bg-primary-100 shadow-primary-300 relative -mt-px border leading-8 shadow-md">
      <div className="hover:border-flama-500 hover:bg-flama-300 -ml-px flex cursor-pointer border-l-4 border-transparent transition-colors duration-200">
        <div className="text-primary-500 flex h-8 w-8 items-center justify-center">
          <IconCircleFilled className="h-2 w-2" />
        </div>
        <div>{path}</div>
      </div>
      <Tooltip data={new Map(Object.entries({ endpoint, file, line, module, name, path }))} />
    </div>
  )
}

function App({ app }: { app: TApp }) {
  const { name, path, apps, endpoints } = app
  const [isOpen, setIsOpen] = useState<boolean>(false)
  const contentRef = useRef<HTMLDivElement>(null)

  const countItems = useCallback(
    (apps: TApp[], endpoints: TEndpoint[]): number =>
      endpoints.length + apps.reduce((y, x) => y + 1 + countItems(x.apps, x.endpoints), 0),
    [],
  )

  const urlsLength = useMemo(() => countItems(apps, endpoints), [countItems, apps, endpoints])

  useEffect(() => {
    if (contentRef.current) contentRef.current.style.maxHeight = `${isOpen ? urlsLength * 34 : 0}px`
  }, [isOpen, contentRef, urlsLength])

  return (
    <div>
      <div className="group border-primary-300 bg-primary-200 shadow-primary-300 relative -mt-px border leading-8 shadow-md">
        <div
          className="hover:border-flama-500 hover:bg-flama-300 -ml-px flex cursor-pointer items-center border-l-4 border-transparent transition-colors duration-200"
          onClick={() => setIsOpen(!isOpen)}
        >
          <div className={`flex h-8 w-8 items-center justify-center transition-transform ${isOpen ? 'rotate-90' : ''}`}>
            <IconChevronRight className="h-4 w-4" />
          </div>
          <div>{path}</div>
        </div>
        <Tooltip data={new Map(Object.entries({ name, path }))} />
      </div>
      <div
        ref={contentRef}
        className={`ml-1 max-h-0 pl-4 transition-all ${
          isOpen ? 'overflow-visible opacity-100' : 'overflow-hidden opacity-0'
        }`}
      >
        <AppURLs apps={apps} endpoints={endpoints} />
      </div>
    </div>
  )
}

function AppURLs({ apps, endpoints }: { apps: URLs['apps']; endpoints: URLs['endpoints'] }) {
  const urls = [
    ...apps.map((item) => ({
      key: item.path,
      node: (
        <li key={item.path}>
          <App key={item.path} app={item} />
        </li>
      ),
    })),
    ...endpoints.map((item) => ({
      key: item.path,
      node: (
        <li key={item.path}>
          <Endpoint key={item.path} endpoint={item} />
        </li>
      ),
    })),
  ].sort((a, b) => a.key.localeCompare(b.key))

  return <ul>{urls.map(({ node }) => node)}</ul>
}

export default function URLTree() {
  const { apps, endpoints } = new URLs()

  return (
    <div>
      <AppURLs apps={apps} endpoints={endpoints} />
    </div>
  )
}
