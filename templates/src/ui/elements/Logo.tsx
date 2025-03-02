import { FlamaIcon, VorticoIcon } from '@/ui/icons'
import type { Color, Size } from '@/ui/types'

const iconSize: Record<Size, string> = {
  xs: 'h-4 w-4 md:h-5 md:w-5',
  sm: 'h-5 w-5 md:h-6 md:w-6',
  md: 'h-6 w-6 md:h-7 md:w-7',
  lg: 'h-7 w-7 md:h-8 md:w-8',
  xl: 'h-8 w-8 md:h-9 md:w-9',
  '2xl': 'h-9 w-9 md:h-10 md:w-10',
}

const textSize: Record<Size, string> = {
  xs: 'text-xs leading-4 md:text-sm md:leading-5',
  sm: 'text-sm leading-5 md:text-base md:leading-6',
  md: 'text-base leading-6 md:text-lg md:leading-7',
  lg: 'text-lg leading-7 md:text-xl md:leading-8',
  xl: 'text-xl leading-8 md:text-2xl md:leading-9',
  '2xl': 'text-2xl leading-9 md:text-3xl md:leading-10',
}

const colors: Record<Color, string> = {
  vortico: 'text-vortico-500',
  bosque: 'text-bosque-500',
  bruma: 'text-bruma-500',
  ciclon: 'text-ciclon-500',
  flama: 'text-flama-500',
  primary: 'text-primary-500',
  'vortico-light': 'text-vortico-200',
  'bosque-light': 'text-bosque-200',
  'bruma-light': 'text-bruma-200',
  'ciclon-light': 'text-ciclon-200',
  'flama-light': 'text-flama-200',
  'primary-light': 'text-primary-200',
  'vortico-dark': 'text-vortico-800',
  'bosque-dark': 'text-bosque-800',
  'bruma-dark': 'text-bruma-800',
  'ciclon-dark': 'text-ciclon-800',
  'flama-dark': 'text-flama-800',
  'primary-dark': 'text-primary-800',
}

const logos: Record<Logo, { text: string; icon: React.ReactElement }> = {
  flama: { text: 'Flama', icon: <FlamaIcon /> },
  vortico: { text: 'Vortico', icon: <VorticoIcon /> },
}

export type Logo = 'flama' | 'vortico'

export interface LogoProps {
  logo: Logo
  color?: Color
  size?: Size
}

export default function Logo({ logo, color, size = 'md' }: LogoProps) {
  const { text, icon } = logos[logo]
  const colorClasses = color ? colors[color] : ''

  return (
    <div className="flex items-center justify-center gap-1" aria-label={`${text} logo`}>
      <div className={`${iconSize[size]} ${colorClasses}`}>{icon}</div>
      <span className={`text-brand ${textSize[size]} ${colorClasses}`}>{text}</span>
    </div>
  )
}
