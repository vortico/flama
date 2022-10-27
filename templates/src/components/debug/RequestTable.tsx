import React from 'react'

export class Request {
  path: string
  method: string
  clientHost: string
  clientPort: number
  pathParams: Map<string, string>
  queryParams: Map<string, string>
  headers: Map<string, string>
  cookies: Map<string, string>

  constructor() {
    this.path = '||@ request.path @||'
    this.method = '||@ request.method @||'
    this.clientHost = '||@ request.client.host @||'
    this.clientPort = parseInt('||@ request.client.port @||')
    this.pathParams = new Map<string, string>(
      Object.entries(JSON.parse('||@ request.params.path|safe_json @||') as object)
    )
    this.queryParams = new Map<string, string>(
      Object.entries(JSON.parse('||@ request.params.query|safe_json @||') as object)
    )
    this.headers = new Map<string, string>(Object.entries(JSON.parse('||@ request.headers|safe_json @||') as object))
    this.cookies = new Map<string, string>(Object.entries(JSON.parse('||@ request.cookies|safe_json @||') as object))
  }
}

export interface RequestTableProps extends React.ComponentProps<'table'> {
  request: Request
}

export default function RequestTable({ request, ...props }: RequestTableProps) {
  const { path, method, pathParams, queryParams, headers, cookies, clientHost, clientPort } = request

  return (
    <table className="w-full table-fixed border-b-2 border-t-2 border-primary-400" {...props}>
      <tbody className="text-left">
        <tr className="border-b border-primary-400">
          <th className="w-48 p-2">Path</th>
          <td className="p-2">{path}</td>
        </tr>
        <tr className="border-b border-primary-400">
          <th className="p-2">Method</th>
          <td className="p-2">{method}</td>
        </tr>
        <tr className="border-b border-primary-400">
          <th className="p-2">Query params</th>
          <td className="p-2">
            <ul>
              {Object.entries(queryParams).map(([key, value], i) => (
                <li key={`request-queryparams-${i}`}>
                  <span className="font-semibold">{`${key} :`}</span>
                  <span>{value}</span>
                </li>
              ))}
            </ul>
          </td>
        </tr>
        <tr className="border-b border-primary-400">
          <th className="p-2">Path params</th>
          <td className="p-2">
            <ul>
              {Object.entries(pathParams).map(([key, value], i) => (
                <li key={`request-pathparams-${i}`}>
                  <span className="font-semibold">{`${key} :`}</span>
                  <span>{value}</span>
                </li>
              ))}
            </ul>
          </td>
        </tr>
        <tr className="border-b border-primary-400">
          <th className="p-2">Headers</th>
          <td className="p-2">
            <ul>
              {Object.entries(headers).map(([key, value], i) => (
                <li key={`request-headers-${i}`}>
                  <span className="font-semibold">{`${key} :`}</span>
                  <span>{value}</span>
                </li>
              ))}
            </ul>
          </td>
        </tr>
        <tr className="border-b border-primary-400">
          <th className="p-2">Cookies</th>
          <td className="p-2">
            <ul>
              {Object.entries(cookies).map(([key, value], i) => (
                <li key={`request-cookies-${i}`}>
                  <span className="font-semibold">{`${key} :`}</span>
                  <span>{value}</span>
                </li>
              ))}
            </ul>
          </td>
        </tr>
        {clientHost && (
          <tr className="border-b border-primary-400">
            <th className="p-2">Client host</th>
            <td className="p-2">{clientHost}</td>
          </tr>
        )}
        {clientPort && (
          <tr className="border-b border-primary-400">
            <th className="p-2">Client port</th>
            <td className="p-2">{clientPort}</td>
          </tr>
        )}
      </tbody>
    </table>
  )
}
