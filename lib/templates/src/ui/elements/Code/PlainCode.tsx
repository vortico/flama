export default function PlainCode({ code, selectedLine }: { code: string; selectedLine?: number }) {
  const lines = code.split('\n')

  const isInline = lines.length === 1

  return (
    <code>
      {lines.map((line, i) => (
        <span
          key={i}
          className={`line ${isInline ? 'inline' : 'block w-full px-2'} ${
            selectedLine === i + 1 ? 'bg-flama-700' : ''
          }`}
        >
          {line.length === 0 ? (
            <br />
          ) : (
            line.split(' ').map((token, j) => (
              <span key={j} className="token">
                {token}
              </span>
            ))
          )}
        </span>
      ))}
    </code>
  )
}
