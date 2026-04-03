import React, { useEffect, useMemo, useRef, useState } from 'react'

import { IconCircleFilled } from '@tabler/icons-react'

import { Error } from '@/data/debug'
import { Code, Window } from '@/ui/elements'
import { html } from '@/ui/lib/codecs'

type TFrame = Error['traceback'][number]

function TracebackListItem({ frame, isActive }: { frame: TFrame; isActive: boolean }) {
  const filename =
    frame.filename.length > 35 && frame.filename.split('/').length > 2
      ? frame.filename.split('/', 1).concat(['...', frame.filename.split('/').slice(-1)[0]])
      : frame.filename.split('/')

  return (
    <div
      className={`border-primary-300 shadow-primary-300 -mt-px border shadow-md transition duration-200 ${isActive ? 'bg-primary-200' : 'bg-primary-100 hover:bg-flama-300 hover:shadow-flama-300 hover:shadow-lg'}`}
    >
      <div
        className={`flex h-12 w-full cursor-pointer items-center justify-start transition duration-200 ${
          isActive
            ? 'border-primary-300 border-l-4'
            : 'hover:border-flama-500 border-primary-100 pl-1 hover:border-l-4 hover:pl-0'
        }`}
      >
        <div
          className={`flex h-8 w-8 items-center justify-center pl-1 ${frame.vendor ? 'text-flama-400' : 'text-primary-500'}`}
        >
          <IconCircleFilled className="h-2 w-2" />
        </div>
        <div
          className={`text-primary-600 overflow-hidden font-mono text-xs ${
            isActive ? 'border-current font-semibold' : 'hover:text-primary-800'
          }`}
        >
          <div>
            {filename.map((value, i) => (
              <React.Fragment key={`filename-${i}`}>
                {i > 0 && <span>/</span>}
                <span className={i === 0 && frame.vendor ? 'text-flama-500' : ''}>{value}</span>
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
    </div>
  )
}

function TracebackList({
  traceback,
  selected,
  setSelected,
}: {
  traceback: TFrame[]
  selected: number
  setSelected(i: number): void
}) {
  const itemRef = useRef<HTMLLIElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  useEffect(() => {
    if (itemRef.current && listRef.current)
      listRef.current.scrollTo({
        top: itemRef.current.offsetTop - listRef.current.clientHeight / 2,
        left: 0,
        behavior: 'smooth',
      })
  }, [itemRef, listRef])

  return (
    <ul ref={listRef} className="mt-px h-full w-full overflow-y-scroll py-6 pr-3 pl-2">
      {traceback.map((frame, i) => (
        <li ref={selected === i ? itemRef : undefined} key={`traceback-frame-${i}`} onClick={() => setSelected(i)}>
          <TracebackListItem frame={frame} isActive={selected === i} />
        </li>
      ))}
    </ul>
  )
}

export default function ErrorTraceback() {
  const { traceback } = new Error()
  const [selected, setSelected] = useState(traceback.length - 1)

  const code = useMemo(() => html.decode(traceback[selected].code), [selected, traceback])

  return (
    <div className="flex flex-col gap-8 lg:flex-row">
      <div className="h-[672px] max-h-[calc(85vh)] w-full flex-none overflow-hidden lg:w-xs">
        <TracebackList traceback={traceback} selected={selected} setSelected={setSelected} />
      </div>
      <div className="h-[672px] max-h-[calc(85vh)] flex-auto overflow-hidden">
        <Window title={traceback[selected].filename}>
          <Code code={code} language="python" lines={{ type: 'number' }} selectedLine={traceback[selected].line} />
        </Window>
      </div>
    </div>
  )
}
