interface Frame {
  filename: string
  function: string
  line: number
  vendor: boolean
  code: string
}

export default class Error {
  error: string
  description: string
  traceback: Frame[]

  constructor() {
    this.error = '||@ error.error @||'
    this.description = '||@ error.description @||'
    this.traceback = JSON.parse('||@ error.traceback|safe_json @||') as Frame[]
  }
}
