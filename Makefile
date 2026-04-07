benchmark: ## Generates benchmark comparison report
	@./scripts/benchmark

build: ## Builds the package
	@./scripts/build

check: ## Checks the dependencies of the project and install those missing
	@./scripts/check

clean: ## Removes artifact folders and files which are cached
	@./scripts/clean

docker_push: ## Push docker images to registry
	@./scripts/docker_push .

format: ## Runs code formatting
	@./scripts/format .

install: ## Installs the package, JS requirements, and build templates needed
	@./scripts/install

lint: ## Runs code linting
	@./scripts/lint .

lint-fix: ## Runs code linting with autofixing
	@./scripts/lint --fix .

performance: ## Runs performance tests
	@./scripts/performance

publish: ## Publishes the package to PyPI
	@./scripts/publish

test: ## Runs all tests of the repository
	@./scripts/test

typecheck: ## Runs static types checking
	@./scripts/typecheck

version: ## Gets the current version of the package
	@./scripts/version

.PHONY: help benchmark build check clean docker_push format install lint lint-fix performance publish test typecheck version
.DEFAULT_GOAL := help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
