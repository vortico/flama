export interface ErrorTitleProps {
  error: string
  method: string
  path: string
  description?: string
}

export default function ErrorTitle({ error, method, path, description }: ErrorTitleProps) {
  return (
    <>
      <h1 className="text-2xl">
        <span className="text-flama-500 font-bold">{error}</span>
        <span className="pl-2">raised at</span>
        <span className="pl-2 font-bold">{method}</span>
        <span className="pl-2 font-mono">{path}</span>
      </h1>
      {description && <h2 className="text-xl font-medium">{description}</h2>}
    </>
  )
}
