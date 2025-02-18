import { Environment } from '@/data/debug'
import { TableArrayValue as ArrayValue, TableRow as Row, Table, TableValue as Value } from '@/ui/elements'

export default function EnvironmentTable() {
  const { pythonVersion, python, platform, path } = new Environment()

  return (
    <Table>
      <Row header="Python version">
        <Value value={pythonVersion} />
      </Row>
      <Row header="Python">
        <Value value={python} />
      </Row>
      <Row header="Platform">
        <Value value={platform} />
      </Row>
      <Row header="Path">
        <ArrayValue array={path} />
      </Row>
    </Table>
  )
}
