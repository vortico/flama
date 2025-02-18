import CodeWindow from '@/components/CodeWindow'
import React, { useEffect, useMemo, useRef, useState } from 'react'

interface Frame {
  filename: string
  function: string
  line: number
  vendor: boolean
  code: string
}

export class Error {
  error: string
  description: string
  traceback: Frame[]

  constructor() {
    this.error = '||@ error.error @||'
    this.description = '||@ error.description @||'
    this.traceback = JSON.parse('||@ error.traceback|safe_json @||') as Frame[]
  }
}

interface TracebackListItemProps {
  frame: Frame
  isActive: boolean
}

function TracebackListItem({ frame, isActive }: TracebackListItemProps) {
  const filename =
    frame.filename.length > 35 && frame.filename.split('/').length > 2
      ? frame.filename.split('/', 1).concat(['...', frame.filename.split('/').slice(-1)[0]])
      : frame.filename.split('/')

  return (
    <div
      className={`-ml-px flex h-12 w-full cursor-pointer items-center justify-start gap-4 border-l-4 border-transparent pl-4 ${isActive ? 'border-brand-400 bg-brand-50' : 'hover:border-primary-400 hover:bg-primary-200'
        }`}
    >
      <div className={`text-5xl ${frame.vendor ? 'text-brand-400' : 'text-primary-500'}`}>&#8226;</div>
      <div
        className={`overflow-hidden font-mono text-sm text-primary-600 ${isActive ? 'border-current font-semibold' : 'hover:text-primary-800'
          }`}
      >
        <div>
          {filename.map((value, i) => (
            <React.Fragment key={`filename-${i}`}>
              {i > 0 && <span>/</span>}
              <span className={i === 0 && frame.vendor ? 'text-brand-500' : ''}>{value}</span>
            </React.Fragment>
          ))}
          <span>:</span>
          <span>{frame.line}</span>
        </div>
        <div className="truncate">
          <span className="italic">{frame.function}</span>
        </div>
      </div>
    </div>
  )
}

interface TracebackListProps {
  traceback: Frame[]
  selected: number

  setSelected(i: number): void
}

function TracebackList({ traceback, selected, setSelected }: TracebackListProps) {
  const itemRef = useRef<HTMLLIElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (itemRef.current && listRef.current)
      listRef.current.scrollTo({
        top: itemRef.current.offsetTop - listRef.current.clientHeight / 2,
        left: 0,
        behavior: 'smooth',
      })
  }, [itemRef, listRef])

  return (
    <div ref={listRef} className="h-full overflow-scroll">
      <ul className="space-y-2 border-l border-primary-300">
        {traceback.map((frame, i) => (
          <li ref={selected === i ? itemRef : undefined} key={`traceback-frame-${i}`} onClick={() => setSelected(i)}>
            <TracebackListItem frame={frame} isActive={selected === i} />
          </li>
        ))}
      </ul>
    </div>
  )
}

interface ErrorTracebackProps extends React.ComponentProps<'div'> {
  error: Error
}

export default function ErrorTraceback({ error, ...props }: ErrorTracebackProps) {
  const { traceback } = error
  const [selected, setSelected] = useState(traceback.length - 1)

  const code = useMemo(
    () => new DOMParser().parseFromString(traceback[selected].code, 'text/html').body.textContent || '',
    [selected, traceback]
  )

  return (
    <div className="flex gap-10" {...props}>
      <div className="h-[776px] flex-auto basis-1/3 overflow-hidden">
        <TracebackList traceback={traceback} selected={selected} setSelected={setSelected} />
      </div>
      <div className="h-[776px] flex-auto basis-2/3 overflow-hidden">
        <CodeWindow
          title={traceback[selected].filename}
          code={code}
          language="python"
          lineNumbers={true}
          copyButton={true}
          selectedLine={traceback[selected].line}
          autoScroll={true}
        />
      </div>
    </div>
  )
}
