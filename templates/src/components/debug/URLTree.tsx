import { ChevronRightIcon } from '@heroicons/react/20/solid'
import React, { useEffect, useMemo, useRef, useState } from 'react'

type URL = {
  endpoint: string
  file: string
  line: number
  module: string
  name?: string
  path: string
}

type App = {
  name?: string
  path: string
  urls: Array<URL | App>
}

export class RootApp {
  name?: string
  path: string
  urls: Array<URL | App>

  constructor() {
    this.name = '||@ app.name @||'
    this.path = '||@ app.path @||'
    this.urls = JSON.parse('||@ app.urls|safe_json @||') as Array<URL | App>
  }
}

interface TooltipProps {
  data: Map<string, string | number | undefined>
}

function Tooltip({ data }: TooltipProps) {
  return (
    <div
      className="absolute left-1/2 -bottom-2 z-20 hidden -translate-x-1/2 translate-y-full rounded-lg
    bg-primary-800 p-3 text-left text-sm text-primary-200 after:absolute after:left-1/2 after:bottom-[100%]
    after:-translate-x-1/2 after:border-8 after:border-x-transparent after:border-t-transparent after:border-b-primary-800
    after:content-[''] group-hover:block"
    >
      <ul>
        {Array.from(data.entries())
          .sort((a, b) => a[0].localeCompare(b[0]))
          .filter((x) => x[1])
          .map(([k, v], i) => (
            <li key={i}>
              <span className="capitalize text-brand-300">{k}:</span> <span>{v}</span>
            </li>
          ))}
      </ul>
    </div>
  )
}

function isApp(item: URL | App): item is App {
  return 'urls' in item
}

interface URLProps {
  url: URL
}

function URL({ url }: URLProps) {
  const { endpoint, file, line, module, name, path } = url
  return (
    <div className="group relative border-l border-primary-400 bg-primary-100 leading-8 shadow-lg">
      <div className="-ml-px flex cursor-pointer border-l-4 border-transparent hover:border-brand-400 hover:bg-brand-100">
        <div className="h-8 w-8 text-center text-2xl text-primary-500">&#8226;</div>
        <div>{path}</div>
      </div>
      <Tooltip data={new Map(Object.entries({ endpoint, file, line, module, name, path }))} />
    </div>
  )
}

interface AppProps {
  app: App
}

function App({ app }: AppProps) {
  const { name, path, urls } = app
  const [isOpen, setIsOpen] = useState<boolean>(false)
  const contentRef = useRef<HTMLDivElement>(null)

  const countItems = (items: Array<App | URL>): number =>
    items.reduce((y, x) => y + (isApp(x) ? 1 + countItems(x.urls) : 1), 0)

  const urlsLength = useMemo(() => countItems(urls), [])

  useEffect(() => {
    if (contentRef.current) contentRef.current.style.maxHeight = `${isOpen ? urlsLength * 32 : 0}px`
  }, [isOpen, contentRef])

  return (
    <div>
      <div className="group relative border-l border-primary-400 bg-primary-200 leading-8 shadow-lg">
        <div
          className="-ml-px flex cursor-pointer items-center border-l-4 border-transparent hover:border-brand-400 hover:bg-brand-100"
          onClick={() => setIsOpen(!isOpen)}
        >
          <div className={`transition-transform ${isOpen ? 'rotate-90' : ''}`}>
            <ChevronRightIcon className="h-6 w-8" />
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
        <URLList urls={urls} />
      </div>
    </div>
  )
}

interface URLListProps {
  urls: Array<URL | App>
}

function URLList({ urls }: URLListProps) {
  return (
    <ul>
      {urls
        .sort((a, b) => a.path.localeCompare(b.path))
        .map((item) => (
          <li key={item.path}>
            {isApp(item) ? <App key={item.path} app={item} /> : <URL key={item.path} url={item} />}
          </li>
        ))}
    </ul>
  )
}

export interface URLTreeProps {
  root: RootApp
}

export default function URLTree({ root }: URLTreeProps) {
  const { urls } = root

  return (
    <div className="relative">
      <URLList urls={urls} />
    </div>
  )
}
