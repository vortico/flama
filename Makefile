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
