PYTHON ?= python3
PRESET ?= native
JOBS ?= 2
.NOTPARALLEL:

.PHONY: help deps configure build test package universal source clean
help:
	@$(PYTHON) scripts/build.py --help

deps configure build test package universal source clean:
	$(PYTHON) scripts/build.py $@ --preset $(PRESET) --jobs $(JOBS)
