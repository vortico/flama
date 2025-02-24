export default class Request {
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
      Object.entries(JSON.parse('||@ request.params.path|safe_json @||') as object),
    )
    this.queryParams = new Map<string, string>(
      Object.entries(JSON.parse('||@ request.params.query|safe_json @||') as object),
    )
    this.headers = new Map<string, string>(Object.entries(JSON.parse('||@ request.headers|safe_json @||') as object))
    this.cookies = new Map<string, string>(Object.entries(JSON.parse('||@ request.cookies|safe_json @||') as object))
  }
}
