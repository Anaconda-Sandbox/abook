.DEFAULT_GOAL := help
ENV_NAME ?= ./env
CONDA    ?= conda

PYTHON ?= $(CONDA) run --no-capture-output -p $(ENV_NAME) python
PIP := $(PYTHON) -m pip
PROJECT := agentbook
DIST_DIR := dist
BUILD_DIR := build

PRE_COMMIT ?= $(PYTHON) -m pre_commit
RUFF       ?= $(PYTHON) -m ruff
MYPY       ?= $(PYTHON) -m mypy
PYTEST     ?= $(PYTHON) -m pytest

MYPY_SRCS ?= src
RUFF_SRCS ?= src tests
MYPY_ARGS ?=

.PHONY: help which-python setup clean-setup activate install-dev uninstall \
        clean clean-artifacts clean-cache \
        test test-coverage \
        ruff fix ruff-fix format lint \
        pre-commit pre-commit-install pre-commit-update pre-commit-all pre-commit-clean \
        mypy mypy-clean

which-python: ## Show Python executable being used
	@echo "PYTHON      = $(PYTHON)"
	@$(PYTHON) -c "import sys; print('sys.executable =', sys.executable)"
	@echo "CONDA_PREFIX= '$(CONDA_PREFIX)'"

setup: ## Create or update the dev conda env from environment-dev.yml
	@echo "Setting up Conda env: $(ENV_NAME)"
	@if [ -d "$(ENV_NAME)" ]; then \
		echo "Environment exists. Updating…"; \
		$(CONDA) env update -p $(ENV_NAME) -f environment-dev.yml --prune; \
	else \
		echo "Environment not found. Creating…"; \
		$(CONDA) env create -p $(ENV_NAME) -f environment-dev.yml; \
	fi
	@echo "Installing package in editable mode…"
	$(PYTHON) -m pip install --no-deps -e .
	@echo "Done. Activate with: conda activate $(ENV_NAME)"

clean-setup: ## Remove the dev conda env and all build artifacts (fresh start)
	@echo "Removing Conda env: $(ENV_NAME) (if present)…"
	-$(CONDA) env remove -p $(ENV_NAME) -y >/dev/null 2>&1 || true
	@$(MAKE) clean
	@echo "Clean reset complete."

activate: ## Show activation command (must be run manually)
	@echo "To activate the development environment, run:"
	@echo "  conda activate $(ENV_NAME)"

install-dev: ## Install package in development mode (no-deps; use make setup for full env)
	$(PIP) install --no-deps -e .

uninstall: ## Uninstall the package from the current Python environment
	$(PIP) uninstall -y $(PROJECT)

clean-artifacts: ## Remove build artifacts and __pycache__
	rm -rf $(DIST_DIR) $(BUILD_DIR) *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-cache: ## Clean pytest, mypy, ruff caches
	rm -rf .pytest_cache .mypy_cache .ruff_cache .tox

clean: clean-artifacts clean-cache ## Clean all build artifacts and caches

test: ## Run tests with pytest
	$(PYTEST) -s -vvv $(ARGS)

test-coverage: ## Run tests with coverage report
	$(PYTEST) --cov=agentbook --cov-report=html --cov-report=term $(ARGS)

ruff: ## Run Ruff checks (no changes)
	$(RUFF) check $(RUFF_SRCS) $(ARGS)

fix: ## Run Ruff with --fix (auto-fix issues, no formatting)
	$(RUFF) check --fix $(RUFF_SRCS) $(ARGS)

ruff-fix: ## Run Ruff with --fix then format
	$(RUFF) check --fix $(RUFF_SRCS) $(ARGS)
	$(RUFF) format $(RUFF_SRCS)

format: ## Apply code formatting only
	$(RUFF) format $(RUFF_SRCS)

lint: ## Run static checks (Ruff)
	$(RUFF) check $(RUFF_SRCS)

pre-commit-install: ## Install pre-commit git hooks
	$(PRE_COMMIT) install

pre-commit-update: ## Update pre-commit hooks to latest revisions
	$(PRE_COMMIT) autoupdate

pre-commit: ## Run pre-commit on staged files
	$(PRE_COMMIT) run

pre-commit-all: ## Run pre-commit on all files
	$(PRE_COMMIT) run --all-files

pre-commit-clean: ## Clear pre-commit cache
	$(PRE_COMMIT) clean

mypy: ## Run static type checks (mypy)
	$(MYPY) $(MYPY_ARGS) $(MYPY_SRCS)

mypy-clean: ## Remove mypy cache
	rm -rf .mypy_cache

help: ## List all options in the Makefile
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_.-]+:.*## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
