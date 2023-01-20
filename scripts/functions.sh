POETRY_INSTALLER="/tmp/poetry_install.py"
POETRY_URL="https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py"

NO_FORMAT="\033[0m"
F_ITALIC="\e[3m"
F_BOLD="\033[1m"
C_RED1="\033[38;5;196m"
C_YELLOW1="\033[38;5;226m"
C_SPRINGGREEN2="\033[38;5;47m"

FOLDERS="dist flama.egg-info pip-wheel-metadata site test-results .coverage .pytest_cache .mypy_cache flama/templates"

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

install_pkg()
{
  echo "🔥 Install python requirements..."
  poetry install --with dev,schemas,ml "$@"
  cd templates
  echo "🔥 Install js requirements..."
  npm i
  echo "🔥 Build templates..."
  npm run build
  cd ..
}

build_pkg()
{
  local arg="$1"
  if [ -z "$arg" ]; then
    cd templates
    echo "🔥 Install js requirements..."
    npm i
    echo "🔥 Build templates..."
    npm run build
    cd ..
    echo "🔥 Build package:"
    poetry build
  elif [[ "$arg" == "-c" || "$arg" == "--clean" ]]; then
    clean_folder
    echo "🔥 Build package:"
    poetry build
  else
    printf "%b" "🚨 ${C_RED1}Unknown argument:${NO_FORMAT} ${arg}\n"
  fi
}

publish_pkg()
{
    username=$PYPI_USERNAME
    password=$PYPI_PASSWORD

    if [[ (-z "$PYPI_USERNAME") || (-z "$PYPI_PASSWORD") ]] ; then
      printf "%b" "🆘 Error: Environment variables ${C_RED1}PYPI_USERNAME${NO_FORMAT} or ${C_RED1}PYPI_PASSWORD${NO_FORMAT} (or both) not found\n"
      return;
    else
        poetry config http-basic.pypi "$username" "$password"
    fi

    local arg="$1"
    if [ "$arg" == "--build" ]; then
      clean_folder
      build_pkg
    fi

    poetry publish --skip-existing
}

run_black()
{
  echo "• Run Black code formatting:"
  poetry run black "$@"
  echo "↳ Black done"
}

run_ruff()
{
  echo "• Run Ruff code analysis:"
  poetry run ruff "$@"
  echo "↳ Ruff done"
}

run_test()
{
  echo "🧪 Run tests:"
  poetry run pytest -n auto
}

run_isort()
{
  echo "poetry run isort $@"
  echo "• Run Isort imports formatting:"
  poetry run isort "$@"
  echo "↳ Isort done"
}

run_mypy()
{
  echo "• Run MyPy code formatting:"
  poetry run mypy "$@"
  echo "↳ MyPy done"
}

run_lint()
{
  echo "🧹 Code lint using multiple tools:"
  run_black --check .
  run_isort --check .
  run_ruff .
  run_mypy .
}

run_version()
{
  echo "⬆️ Upgrade version:"
  poetry version "$@"
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
  printf "%b" "✅ ${C_SPRINGGREEN2}Poetry is installed:${NO_FORMAT} $(poetry --version)\n"
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
