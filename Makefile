benchmark: ## Generates benchmark comparison report
	@./scripts/benchmark

build: ## Builds the package with prebuilt templates fetched from the latest published wheel
	@./scripts/build --fetch-templates $(ARGS)

build-from-source: ## Builds the package, building templates from source (core-team; needs Artifact Registry access)
	@./scripts/build --build-templates $(ARGS)

build-templates: ## Builds only the templates from source, without the core package (core-team; needs Artifact Registry access)
	@./scripts/build --no-build-core --build-templates $(ARGS)

check: ## Checks the dependencies of the project and install those missing
	@./scripts/check

clean: ## Removes artifact folders and files which are cached
	@./scripts/clean

docker_push: ## Push docker images to registry
	@./scripts/docker_push .

fetch-templates: ## Fetches prebuilt templates from the latest published wheel
	@./scripts/fetch_templates

format: ## Runs code formatting
	@./scripts/format .

install: ## Installs the package and dependencies with prebuilt templates fetched from the latest published wheel
	@./scripts/install --fetch-templates $(ARGS)

install-from-source: ## Installs the package, building templates from source (core-team; needs Artifact Registry access)
	@./scripts/install --build-templates $(ARGS)

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

.PHONY: help benchmark build build-from-source build-templates check clean docker_push fetch-templates format install install-from-source lint lint-fix performance publish test typecheck version
.DEFAULT_GOAL := help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
