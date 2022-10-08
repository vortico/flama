import FlamaIcon from '@/components/FlamaIcon'
import React from 'react'

export default function FlamaLogo() {
  return (
    <a
      className="flex items-center justify-start gap-2 text-brand-500"
      aria-label="Flama logo"
      href="https://flama.dev"
    >
      <FlamaIcon className="h-5 w-5 lg:h-6 lg:w-6" />
      <span className="text-xl lg:text-2xl">Flama</span>
    </a>
  )
}
