#!/usr/bin/env bash

function install()
{
  echo "🔥 Install requirements..."
  poetry install "$@"
}

install "$@"