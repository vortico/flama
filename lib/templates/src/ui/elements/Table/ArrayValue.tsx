import Value from './Value'

export interface ArrayValueProps {
  array: (string | number | boolean)[]
}

export default function ArrayValue({ array }: ArrayValueProps) {
  return (
    <ul>
      {array.map((value, i) => (
        <li key={i}>
          <Value value={value} />
        </li>
      ))}
    </ul>
  )
}
