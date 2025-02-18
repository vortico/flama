import React, { ReactElement, useCallback, useState } from 'react'

import { IconBook, IconBrandGithub, IconMenu2, IconScript, IconX } from '@tabler/icons-react'
import { createPortal } from 'react-dom'

import { Logo } from '@/ui/elements'

interface NavItem {
  href: string
  title: string
  icon: ReactElement
  label: string
}

function Nav({ onClick, ...props }: Omit<React.ComponentProps<'ul'>, 'onClick'> & { onClick?: () => void }) {
  const entries: NavItem[] = [
    { href: 'https://flama.dev/docs/', title: 'Docs', icon: <IconBook />, label: 'Flama docs' },
    { href: 'https://flama.dev/blog/', title: 'Blog', icon: <IconScript />, label: 'Flama blog' },
  ]

  return (
    <nav>
      <ul {...props}>
        {entries.map(({ href, title, icon, label }, i) => (
          <li key={i} onClick={onClick}>
            <a href={href} aria-label={label}>
              <div className="flex h-12 cursor-pointer items-center justify-start gap-2">
                <div className="text-primary-400 hover:text-flama-500 h-6 w-6 transition-colors duration-200 md:hidden">
                  {icon}
                </div>
                <div className="text-primary-400 hover:text-flama-500 text-md font-medium transition-colors duration-200">
                  {title}
                </div>
              </div>
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}

interface SocialItem {
  href: string
  title: string
  icon: ReactElement
  label: string
}

function Social({ ...props }: React.ComponentProps<'ul'>) {
  const entries: SocialItem[] = [
    { href: 'https://github.com/vortico/flama', title: 'GitHub', icon: <IconBrandGithub />, label: 'Flama on GitHub' },
  ]

  return (
    <div>
      <ul {...props}>
        {entries.map(({ href, title, icon, label }, i) => (
          <li key={i}>
            <a href={href} aria-label={label}>
              <div className="flex h-12 cursor-pointer items-center justify-start gap-2">
                <div className="text-primary-400 hover:text-flama-500 h-6 w-6 transition-colors duration-200">
                  {icon}
                </div>
                <div className="text-primary-400 hover:text-flama-500 text-md font-medium transition-colors duration-200 md:hidden">
                  {title}
                </div>
              </div>
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

function FloatMenu({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="bg-primary-100 fixed inset-x-0 top-0 z-50 h-screen w-screen overflow-auto"
      aria-modal="true"
      role="dialog"
    >
      <div className="border-flama-500 flex h-14 w-full items-center justify-between border-b px-4 sm:px-6 md:px-8">
        <a href="https://flama.dev" className="block cursor-pointer" aria-label="Flama website">
          <Logo logo="flama" color="flama" size="lg" />
        </a>
        <button className="h-6 w-6" onClick={onClose} aria-label="Close menu">
          <IconX className="text-primary-400 hover:text-flama-500 h-full w-full transition-colors duration-200" />
        </button>
      </div>
      <div className="w-full px-4 sm:px-6 md:px-8">
        <Nav className="flex flex-col items-start justify-start" onClick={onClose} />
        <Social className="flex flex-col items-start justify-start gap-8" />
      </div>
    </div>
  )
}

function FixedMenu({ onOpen }: { onOpen: () => void }) {
  return (
    <>
      <div className="flex h-14 w-full items-center justify-between">
        <a href="https://flama.dev" className="block cursor-pointer" aria-label="Flama website">
          <Logo logo="flama" color="flama" size="lg" />
        </a>
        <div className="hidden items-center justify-between gap-8 md:flex">
          <Nav className="flex items-center justify-start gap-8" />
          <Social className="flex items-center justify-start gap-8" />
        </div>
        <button className="block h-6 w-6 cursor-pointer md:hidden" onClick={onOpen} aria-label="Open menu">
          <IconMenu2 className="h-full w-full" />
        </button>
      </div>
    </>
  )
}

export default function Menu() {
  const [isOpen, setIsOpen] = useState<boolean>(false)

  const onOpen = useCallback(() => setIsOpen(true), [setIsOpen])
  const onClose = useCallback(() => setIsOpen(false), [setIsOpen])

  return (
    <div className="border-flama-500 bg-primary-100 fixed inset-x-0 top-0 z-10 mx-auto border-b">
      <div className="divide-flama-500/50 mx-auto w-full divide-y px-4 sm:px-6 md:px-8">
        <FixedMenu onOpen={onOpen} />
      </div>

      {isOpen && createPortal(<FloatMenu onClose={onClose} />, document.body)}
    </div>
  )
}
