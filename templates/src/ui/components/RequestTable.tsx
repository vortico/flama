import { Request } from '@/data/debug'
import { TableMapValue as MapValue, TableRow as Row, Table, TableValue as Value } from '@/ui/elements'

export default function RequestTable() {
  const { path, method, pathParams, queryParams, headers, cookies, clientHost, clientPort } = new Request()

  return (
    <Table>
      <Row header="Path">
        <Value value={path} />
      </Row>
      <Row header="Method">
        <Value value={method} />
      </Row>
      <Row header="Query parameters">
        <MapValue map={queryParams} />
      </Row>
      <Row header="Path parameters">
        <MapValue map={pathParams} />
      </Row>
      <Row header="Headers">
        <MapValue map={headers} />
      </Row>
      <Row header="Cookies">
        <MapValue map={cookies} />
      </Row>
      {clientHost && (
        <Row header="Client host">
          <Value value={clientHost} />
        </Row>
      )}
      {clientPort && (
        <Row header="Client port">
          <Value value={String(clientPort)} />
        </Row>
      )}
    </Table>
  )
}
