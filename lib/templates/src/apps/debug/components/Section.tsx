import React from 'react'

export interface SectionProps extends React.ComponentProps<'section'> {
  title?: string
  border?: boolean
  gradient?: boolean
}

export default function Section({
  title,
  border = true,
  gradient = true,
  className = '',
  children,
  ...props
}: SectionProps) {
  return (
    <section className={`my-14 ${border ? 'border-flama-500/50 border-t' : ''} ${className}`} {...props}>
      <div className={`${gradient ? 'from-flama-500/10 bg-linear-to-b' : ''}`}>
        {title && (
          <div className="max-w-8xl mx-auto px-4 py-8 sm:px-6 sm:py-10 md:px-8 md:py-12">
            <h2 className="text-primary-700 text-2xl font-semibold">{title}</h2>
          </div>
        )}
      </div>
      <div className="max-w-8xl mx-auto px-4 sm:px-6 md:px-8">{children}</div>
    </section>
  )
}
