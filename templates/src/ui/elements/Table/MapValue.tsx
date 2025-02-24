import Value from './Value'

export interface MapValueProps {
  map: Map<string, string | number | boolean>
}

export default function MapValue({ map }: MapValueProps) {
  return (
    <ul>
      {Array.from(map).map(([key, value], i) => (
        <li key={i}>
          <span className="font-semibold">{`${key}:`}</span>
          <span className="ml-1">
            <Value value={value} />
          </span>
        </li>
      ))}
    </ul>
  )
}
