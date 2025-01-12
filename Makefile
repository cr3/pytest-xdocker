VENV := .venv

PYTHON := poetry run python
TOUCH := $(PYTHON) -c 'import sys; from pathlib import Path; Path(sys.argv[1]).touch()'

poetry.lock: pyproject.toml
	poetry lock

# Build venv with python deps.
$(VENV): environment.yml
	@echo Installing Poetry environment
	@poetry install
	@$(TOUCH) $@

# Convenience target to build venv
.PHONY: setup
setup: $(VENV)

.PHONY: check
check: $(VENV)
	@echo Checking Poetry lock: Running poetry check --lock
	@poetry check --lock
	@echo Linting code: Running pre-commit
	@poetry run pre-commit run -a

.PHONY: test
test: $(VENV)
	@echo Testing code: Running pytest
	@poetry run coverage run -p -m pytest

.PHONY: coverage
coverage: $(VENV)
	@echo Testing covarage: Running coverage
	@poetry run coverage combine
	@poetry run coverage html --skip-covered --skip-empty
	@poetry run coverage report

.PHONY: docs
docs: $(VENV)
	@echo Building docs: Running sphinx-build
	@poetry run sphinx-build -W -d build/doctrees docs build/html

.PHONY: build
build:
	@echo Creating wheel file
	@poetry build

.PHONY: publish
publish:
	@poetry config pypi-token.pypi $(PYPI_TOKEN)
	@echo Publishing: Dry run
	@poetry publish --dry-run
	@echo Publishing
	@poetry publish

.PHONY: clean
clean:
	@echo Cleaning ignored files
	@git clean -Xfd

.DEFAULT_GOAL := test
