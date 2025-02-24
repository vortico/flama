export interface ErrorTitleProps {
  error: string
  method: string
  path: string
  description?: string
}

export default function ErrorTitle({ error, method, path, description }: ErrorTitleProps) {
  return (
    <>
      <div className="text-2xl">
        <span className="text-flama-500 font-bold">{error}</span> raised at <span className="font-bold">{method}</span>{' '}
        <span className="font-mono">{path}</span>
      </div>
      {description && <div className="text-xl font-medium">{description}</div>}
    </>
  )
}
