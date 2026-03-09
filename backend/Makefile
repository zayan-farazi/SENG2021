.PHONY: all ci check lint format fix test coverage

PYTHON := ./.venv/bin/python
RUFF := $(PYTHON) -m ruff
PYTEST := $(PYTHON) -m pytest

all: fix check test

ci: check test

check: lint

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) format .

fix:
	$(RUFF) check --fix .
	$(RUFF) format .

test:
	$(PYTEST) -q

coverage:
	$(PYTEST) --cov=app --cov-report=term-missing
