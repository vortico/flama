#!/usr/bin/env bash

run_test()
{
  echo "🧪 Run tests:"
  pytest --ignore=flama --cov=flama tests
}

run_test "${@:2}"