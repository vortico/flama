import React from 'react'

export interface RowProps extends React.ComponentProps<'tr'> {
  header: string
}

export default function Row({ header, children, ...props }: RowProps) {
  return (
    <tr {...props}>
      <th className="border-primary-300 w-40 border px-4 py-1">
        <span className="text-flama">{header}</span>
      </th>
      <td className="border-primary-300 border px-4 py-1">{children}</td>
    </tr>
  )
}
