#!/usr/bin/env bash

NO_FORMAT="\033[0m"
F_ITALIC="\e[3m"
F_BOLD="\033[1m"
C_YELLOW1="\033[38;5;226m"
C_SPRINGGREEN2="\033[38;5;47m"
C_RED1="\033[38;5;196m"

POETRY_INSTALLER="/tmp/poetry_install.py"
POETRY_URL="https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py"
FOLDERS="dist flama.egg-info pip-wheel-metadata site test-results .coverage .pytest_cache"

clean_folder()
{
  echo "🔥 Clean directory..."
  for folder in $FOLDERS; do
    if [[ ! -d $folder ]]
    then
      printf "%b" "${C_YELLOW1}- Folder not found${NO_FORMAT}: $folder\n"
    else
      printf "%b" "🧹 ${C_SPRINGGREEN2}Deleting folder${NO_FORMAT}: $folder\n"
      rm -r "$folder" 2> /dev/null
    fi
  done
}

install_poetry()
{
  curl $POETRY_URL --output $POETRY_INSTALLER
  python $POETRY_INSTALLER -y
  rm $POETRY_INSTALLER
}

install_poetry_menu()
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

install_success_message()
{
  printf "%b" "✅ ${C_SPRINGGREEN2}Poetry is installed:${NO_FORMAT} $(poetry --version))\n"
}

check_poetry()
{
  echo "🔥 Check dependencies:"
  if ! (command -v poetry &> /dev/null)
  then
    install_poetry_menu
  else
    install_success_message
  fi
}

build_pkg()
{
  echo "🔥 Build package:"
  local arg="$1"
  if [ -z "$arg" ]; then
    poetry build
  elif [[ "$arg" == "-c" || "$arg" == "--clean" ]]; then
    sh "${PWD}/scripts/clean.sh"
    poetry build
  else
    printf "%b" "🚨 ${C_RED1}Unknown argument:${NO_FORMAT} ${arg}\n"
  fi
}

run_black()
{
  echo "• Run Black code formatting:"
  poetry run black "$@"
}

run_flake8()
{
  echo "• Run Flake8 code analysis:"
  poetry run flake8 "$@"
}

run_isort()
{
  echo "• Run Isort imports formatting:"
  poetry run isort "$@"
}

run_lint()
{
  echo "🧹 Code lint using multiple tools:"
  run_black "."
  run_flake8
  run_isort "."
}

run_test()
{
  echo "🧪 Run tests:"
  poetry run tests "$@"
}

run_docs()
{
  echo "📝 Build docs:"
  poetry run mkdocs "$@"
}

run_version()
{
  echo "⬆️ Upgrade version:"
  poetry version "$@"
}


install_pkg()
{
  echo "🔥 Install requirements..."
  poetry install "$@"
}

publish_pkg()
{
    username=$PYPI_USERNAME
    password=$PYPI_PASSWORD

    if [[ (-z "$PYPI_USERNAME") || (-z "$PYPI_PASSWORD") ]] ; then
      printf "%b" "🆘 Error: Environment variables ${C_RED1}PYPI_USERNAME${NO_FORMAT} or ${C_RED1}PYPI_PASSWORD${NO_FORMAT} (or both) are not set\n"
      return;
    else
        poetry config http-basic.pypi "$username" "$password"
    fi

    local arg="$1"
    if [ "$arg" == "--build" ]; then
      build_pkg --clean
    fi

    poetry publish
}

if [[ -n $1 ]]; then command=$1
else command=""
fi

if [[ $command == "check" ]]; then
    check_poetry "${@:2}"
elif [[ $command == "clean" ]]; then
    clean_folder "${@:2}"
elif [[ $command == "install" ]]; then
    install_pkg "${@:2}"
elif [[ $command == "build" ]]; then
    build_pkg "${@:2}"
elif [[ $command == "black" ]]; then
    run_black "${@:2}"
elif [[ $command == "flake8" ]]; then
    run_flake8 "${@:2}"
elif [[ $command == "isort" ]]; then
    run_isort "${@:2}"
elif [[ $command == "lint" ]]; then
    run_lint "${@:2}"
elif [[ $command == "test" ]]; then
    run_test "${@:2}"
elif [[ $command == "docs" ]]; then
    run_docs "${@:2}"
elif [[ $command == "version" ]]; then
    run_version "${@:2}"
elif [[ $command == "publish" ]]; then
    publish_pkg "${@:2}"
else
    printf "%b" "\nPoetry command not implemented yet.\n"
fi
