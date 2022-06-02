#!/usr/bin/env bash

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

run_lint "${@:2}"