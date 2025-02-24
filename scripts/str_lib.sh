NO_FORMAT="\033[0m"
F_ITALIC="\e[3m"
F_BOLD="\033[1m"
C_RED1="\033[38;5;196m"
C_SPRINGGREEN2="\033[38;5;47m"
C_YELLOW1="\033[38;5;226m"

message() {
  case $1 in
  info) printf "🔥 %b\n" "$2" ;;
  success) printf "✅ ${C_SPRINGGREEN2}%b${NO_FORMAT}\n" "$2" ;;
  warning) printf "⚠️ ${F_ITALIC}${C_YELLOW1}%b${NO_FORMAT}\n" "$2" >&2 ;;
  error) printf "🚨 ${F_BOLD}${C_RED1}%b${NO_FORMAT}\n" "$2" >&2 ;;
  *) printf "%b\n" "$1" ;;
  esac
}
