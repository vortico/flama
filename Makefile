all: check

check:
	@$(shell) ./scripts/check.sh

.PHONY: clean
clean:
	@$(shell) ./scripts/clean.sh
