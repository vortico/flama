all: check

check: ## Checks the dependencies of the project and install those missing
	@./scripts/check

clean: ## Removes artifact folders and files which are cached
	@./scripts/clean

install: ## Installs the package, JS requirements, and build templates needed
	@./scripts/install

build: ## Builds the package, and templates needed
	@./scripts/build

lint: ## Runs a linting pipeline: black, isort, ruff, and mypy
	@./scripts/lint

lint-fix: ## Runs a linting pipeline with auto fixing: black, isort, ruff, and mypy
	@./scripts/lint --fix

test: ## Runs all tests of the repository
	@./scripts/test

publish: ## Publishes the package in PiPy if user and passwords are correct
	@./scripts/publish

version: ## Gets the current version of the package
	@./scripts/version

isort: ## Runs isort on Flama
	@./scripts/isort .

black: ## Runs black on Flama
	@./scripts/black .

ruff: ## Runs ruff on Flama
	@./scripts/ruff .

pyright: ## Runs pyright on Flama
	@./scripts/pyright

docker_push: ## Push docker images to registry
	@./scripts/docker_push .

.PHONY: help check clean install build lint tests publish version isort black ruff pyright docker_push
.DEFAULT_GOAL := help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
