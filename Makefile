all: check

.PHONY: check
check:
	./scripts/check

.PHONY: clean
clean:
	./scripts/clean

.PHONY: install
install:
	./scripts/install

.PHONY: build
build:
	./scripts/build

.PHONY: lint
lint:
	./scripts/lint

.PHONY: docs
docs:
	./scripts/docs

.PHONY: tests
test:
	./scripts/test

.PHONY: publish
publish:
	./scripts/publish

.PHONY: version
version:
	./scripts/version

.PHONY: isort
isort:
	./scripts/isort

.PHONY: black
black:
	./scripts/black

.PHONY: flake8
flake8:
	./scripts/flake8
