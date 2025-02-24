import { html } from '@/ui/lib/codecs'

export interface ValueProps {
  value: string | number | boolean
}

export default function Value({ value }: ValueProps) {
  return <span>{html.decode(String(value))}</span>
}
