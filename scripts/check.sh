#!/usr/bin/env bash

NO_FORMAT="\033[0m"
F_ITALIC="\e[3m"
F_BOLD="\033[1m"
C_YELLOW1="\033[38;5;226m"
C_SPRINGGREEN2="\033[38;5;47m"
C_RED1="\033[38;5;196m"

POETRY_INSTALLER="/tmp/poetry_install.py"
POETRY_URL="https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py"

install_poetry()
{
  curl $POETRY_URL --output $POETRY_INSTALLER
  python $POETRY_INSTALLER -y
  rm $POETRY_INSTALLER
}

install_poetry_question()
{
  printf "%b" "\n⚠️ ${C_YELLOW1} Poetry is not available:${NO_FORMAT}\n";
  while true; do
    read -p "- Do you wish to install this program? (Y/N) -> " yn
    case $yn in
        [Yy]* )
          install_poetry;
          break;;
        [Nn]* )
          printf "%b" "\n🚨 ${F_BOLD}${C_RED1}Poetry won't be installed.${NO_FORMAT}"
          printf "%b" "\n${C_YELLOW1}WARNING: ${F_ITALIC}The development team recommends the installation of Poetry for the packaging and management of dependencies.${NO_FORMAT}\n" | fold -w 99
          exit;;
        [q]* )
          printf "\n"
          exit;;
        * ) printf "%b" "\nPlease answer yes (Y) or no (N).\n";;
    esac
  done
}

echo "🔥 Checking dependencies..."
if ! (command -v poetry &> /dev/null)
then
  install_poetry_question
else
  printf "%b" "✅ ${C_SPRINGGREEN2}Poetry is installed:${NO_FORMAT} $(poetry --version))\n"
fi