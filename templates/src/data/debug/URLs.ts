interface Endpoint {
  endpoint: string
  file: string
  line: number
  module: string
  name?: string
  path: string
}

interface App {
  name?: string
  path: string
  apps: App[]
  endpoints: Endpoint[]
}

export default class URLs {
  name?: string
  path: string
  apps: App[]
  endpoints: Endpoint[]

  constructor() {
    this.name = '||@ app.name @||'
    this.path = '||@ app.path @||'
    this.apps = JSON.parse('||@ app.apps|safe_json @||') as App[]
    this.endpoints = JSON.parse('||@ app.endpoints|safe_json @||') as Endpoint[]
  }
}
