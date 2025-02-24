export default class Environment {
  pythonVersion: string
  python: string
  platform: string
  path: string[]

  constructor() {
    this.pythonVersion = '||@ environment.python_version|safe @||'
    this.python = '||@ environment.python|safe @||'
    this.platform = '||@ environment.platform|safe @||'
    this.path = JSON.parse('||@ environment.path|safe_json @||') as string[]
  }
}
