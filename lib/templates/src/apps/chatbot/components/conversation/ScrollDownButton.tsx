import { IconChevronDown } from '@tabler/icons-react'
import { RippleBox } from '@vortico/ui/containers'
import {
  bgHoverColor,
  borderColor,
  iconRoundedSize,
  iconSize,
  mainBgColor,
  mainShadow,
  shadowColor,
  textColor,
} from '@vortico/ui/styles'

// Square jump-to-latest control. Intentionally not @vortico/ui's IconButton, whose circular hover/ripple clash with the
// squared bordered box around it.
function JumpButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Jump to latest"
      className={`inline-flex cursor-pointer transition ${textColor['flama']} ${bgHoverColor['flama']}`}
    >
      <RippleBox from="center" color="flama" className={`flex items-center justify-center ${iconRoundedSize['lg']}`}>
        <IconChevronDown size={iconSize['lg']} />
      </RippleBox>
    </button>
  )
}

export default function ScrollDownButton({ visible, onClick }: { visible: boolean; onClick: () => void }) {
  if (!visible) return null

  return (
    <div className={`border ${mainBgColor} ${borderColor['flama']} ${mainShadow} ${shadowColor['flama']}`}>
      <JumpButton onClick={onClick} />
    </div>
  )
}
