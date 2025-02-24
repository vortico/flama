import { VorticoIcon } from '../icons'

export default function Vortico() {
  return (
    <div className="flex items-center justify-start gap-1" aria-label="Vortico logo">
      <VorticoIcon className="h-10 w-10" />
      <span className="text-vortico text-2xl leading-10">Vortico</span>
    </div>
  )
}
