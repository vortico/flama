import React from 'react'

export class Environment {
  pythonVersion: string
  python: string
  platform: string
  path: string[]

  constructor() {
    this.pythonVersion = '||@ environment.python_version @||'
    this.python = '||@ environment.python @||'
    this.platform = '||@ environment.platform @||'
    this.path = JSON.parse('||@ environment.path|safe_json @||') as string[]
  }
}

interface EnvironmentTableProps extends React.ComponentProps<'table'> {
  environment: Environment
}

export default function EnvironmentTable({ environment, ...props }: EnvironmentTableProps) {
  const { pythonVersion, python, platform, path } = environment

  return (
    <table className="w-full table-fixed border-b-2 border-t-2 border-primary-400" {...props}>
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
