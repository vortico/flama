import { FlamaIcon } from '../icons'

export default function Flama() {
  return (
    <div className="flex items-center justify-start gap-1" aria-label="Flama logo">
      <FlamaIcon className="h-10 w-10" />
      <span className="text-flama text-2xl leading-10">Flama</span>
    </div>
  )
}
