#!/usr/bin/env bash

install_pkg()
{
  echo "🔥 Install requirements..."
  poetry install "$@"
}

install_pkg "${@:2}"