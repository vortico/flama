import React, { RefObject, useCallback, useEffect, useRef, useState } from 'react'

import { IconCircleDotFilled, IconCirclePlusFilled, IconCircleXFilled } from '@tabler/icons-react'

export interface WindowProps extends React.ComponentProps<'div'> {
  title?: string
  autoScroll?: RefObject<HTMLDivElement | null>
}

export default function Window({ title, autoScroll, className, children }: WindowProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'open' | 'closed' | 'full'>('open')

  const onMinimize = useCallback(() => setState(state === 'open' ? 'closed' : 'open'), [state, setState])
  const onMaximize = useCallback(() => setState('full'), [setState])
  const onClose = useCallback(() => setState('closed'), [setState])

  useEffect(() => {
    if (containerRef.current && autoScroll?.current)
      containerRef.current.scrollTo({
        top: autoScroll.current.offsetTop - containerRef.current.clientHeight / 2,
        left: 0,
        behavior: 'smooth',
      })
  }, [autoScroll, containerRef])

  return (
    <div
      className={
        state === 'full' ? 'fixed inset-0 z-50 h-screen w-screen overflow-hidden' : 'relative h-full w-full p-2'
      }
      {...(state === 'full' && { 'aria-modal': true, role: 'dialog' })}
    >
      {state === 'full' && (
        <div className="bg-primary-950/30 fixed inset-0 backdrop-blur-sm" aria-hidden={true} onClick={onMinimize} />
      )}
      <div
        className={`bg-primary-900 shadow-primary-300 border-primary-300 h-full overflow-hidden border shadow-md ${
          state === 'closed'
            ? 'relative max-h-[32px]'
            : state === 'full'
              ? 'fixed inset-x-4 inset-y-[5vh] max-h-[calc(85vh+2rem+3px)] sm:inset-x-6 md:inset-x-8'
              : state === 'open'
                ? 'relative max-h-full'
                : ''
        } ${className || ''}`}
      >
        <div className="border-primary-300 bg-primary-900 mb-px flex h-8 w-full flex-none items-center justify-between border-b px-4">
          <span className="text-primary-200 font-alternative truncate text-sm leading-8 font-semibold">{title}</span>
          <div className="flex items-center justify-end gap-x-2">
            <button className="h-4 w-4 cursor-pointer" onClick={onMinimize} aria-label="Minimize Window">
              <IconCircleDotFilled className="text-primary-300 hover:text-ciclon h-full w-full transition-colors duration-200" />
            </button>
            <button className="h-4 w-4 cursor-pointer" onClick={onMaximize} aria-label="Maximize Window">
              <IconCirclePlusFilled className="text-primary-300 hover:text-bosque h-full w-full transition-colors duration-200" />
            </button>
            <button className="h-4 w-4 cursor-pointer" onClick={onClose} aria-label="Close Window">
              <IconCircleXFilled className="text-primary-300 hover:text-flama h-full w-full transition-colors duration-200" />
            </button>
          </div>
        </div>
        <div
          ref={containerRef}
          className={`bg-primary-900 h-full w-full ${
            state === 'closed'
              ? 'max-h-0'
              : state === 'full'
                ? 'max-h-[calc(100%-2rem-1px)]'
                : state === 'open'
                  ? 'max-h-[calc(100%-2rem-1px)]'
                  : ''
          }`}
        >
          {children}
        </div>
      </div>
    </div>
  )
}
