import React from 'react'

export default function Table({ children }: Omit<React.ComponentProps<'table'>, 'className'>) {
  return (
    <table className="border-primary-300 w-full table-fixed border-collapse border">
      <tbody className="text-left">{children}</tbody>
    </table>
  )
}
