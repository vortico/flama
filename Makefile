CHDIR_SHELL := $(SHELL)
define chdir
	$(eval _D=$(firstword $(1) $(@D)))
	$(info $(MAKE): cd $(_D)) $(eval SHELL = cd $(_D); $(CHDIR_SHELL))
endef

all: check

check:
	@$(shell) ./scripts/check.sh

.PHONY: clean
clean:
	@$(shell) ./scripts/clean.sh

install:
	@$(shell) ./scripts/install.sh

build:
	@$(shell) ./scripts/build.sh

lint:
	@$(shell) ./scripts/lint.sh

docs:
	@$(shell) ./scripts/docs.sh

test:
	$(call chdir,$(PWD))
	./scripts/test.sh

publish:
	@$(shell) ./scripts/publish.sh

version:
	@$(shell) ./scripts/version.sh

isort:
	@$(shell) ./scripts/isort.sh

black:
	@$(shell) ./scripts/black.sh

flake8:
	@$(shell) ./scripts/flake8.sh
