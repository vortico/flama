import React from 'react'

interface EnvironmentProps {
  pythonVersion: string
  python: string
  platform: string
  path: string[]
}

export default function Environment({
  pythonVersion,
  python,
  platform,
  path,
}: EnvironmentProps) {
  return (
    <table className="w-full table-fixed border-b-2 border-t-2 border-primary-400">
      <tbody className="text-left">
        <tr className="border-b border-primary-400">
          <th className="w-48 p-2">Python version</th>
          <td className="p-2">{pythonVersion}</td>
        </tr>
        <tr className="border-b border-primary-400">
          <th className="p-2">Python</th>
          <td className="p-2">{python}</td>
        </tr>
        <tr className="border-b border-primary-400">
          <th className="p-2">Platform</th>
          <td className="p-2">{platform}</td>
        </tr>
        <tr className="border-b border-primary-400">
          <th className="p-2">Path</th>
          <td className="p-2">
            <ul>
              {path.map((item, i) => (
                <li key={`environment-path-${i}`}>{item}</li>
              ))}
            </ul>
          </td>
        </tr>
      </tbody>
    </table>
  )
}
