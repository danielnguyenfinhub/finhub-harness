.PHONY: help install test lint typecheck format package clean

help:
	@echo "Common targets:"
	@echo "  install     Create .venv and install in editable mode with dev extras"
	@echo "  test        Run pytest"
	@echo "  lint        Run ruff check + black --check (same as CI)"
	@echo "  typecheck   Run mypy --strict src"
	@echo "  format      Apply ruff --fix + black"
	@echo "  package     Build plugin packages (scripts/package-plugin.sh)"
	@echo "  clean       Remove caches and build artifacts (keeps .venv)"

install:
	python -m venv .venv
	.venv/bin/pip install -e '.[dev]'

test:
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/ruff check src tests
	.venv/bin/black --check src tests

typecheck:
	.venv/bin/mypy --strict src

format:
	.venv/bin/ruff check --fix src tests
	.venv/bin/black src tests

package:
	bash scripts/package-plugin.sh

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist
