VENV := .venv

RUN := uv run
PYTHON := $(RUN) python
TOUCH := $(PYTHON) -c 'import sys; from pathlib import Path; Path(sys.argv[1]).touch()'

uv.lock: pyproject.toml
	uv lock

# Build venv and install python deps.
$(VENV):
	@echo "==> Installing environment..."
	@uv sync --frozen --all-extras
	@$(TOUCH) $@

# Convenience target to build venv
.PHONY: setup
setup: $(VENV)

.PHONY: check
check: $(VENV)
	@echo "==> Checking uv lock..."
	@uv lock --check
	@echo "==> Linting Python code..."
	@$(RUN) ruff check .

.PHONY: test
test: $(VENV)
	@echo "==> Testing Python code..."
	@$(RUN) coverage run -p -m pytest

.PHONY: coverage
coverage: $(VENV)
	@echo "==> Checking coverage..."
	@$(RUN) coverage combine
	@$(RUN) coverage html --skip-covered --skip-empty
	@$(RUN) coverage report

.PHONY: docs
docs: $(VENV)
	@echo "==> Building docs..."
	@$(RUN) sphinx-build -W -d build/doctrees docs build/html

.PHONY: clean
clean:
	@echo "==> Cleaning ignored files..."
	@git clean -Xfd

.DEFAULT_GOAL := test
