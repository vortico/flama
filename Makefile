all: check

.PHONY: check
check:
	./scripts/check.sh

.PHONY: clean
clean:
	./scripts/clean.sh

.PHONY: install
install:
	./scripts/install.sh

.PHONY: build
build:
	./scripts/build.sh

.PHONY: lint
lint:
	./scripts/lint.sh

.PHONY: docs
docs:
	./scripts/docs.sh

.PHONY: tests
tests:
	./scripts/test.sh

.PHONY: publish
publish:
	./scripts/publish.sh

.PHONY: version
version:
	./scripts/version.sh

.PHONY: isort
isort:
	./scripts/isort.sh

.PHONY: black
black:
	./scripts/black.sh

.PHONY: flake8
flake8:
	./scripts/flake8.sh
