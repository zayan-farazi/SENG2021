.PHONY: all ci check lint format fix test coverage dev

PYTHON := ./.venv/bin/python
RUFF := $(PYTHON) -m ruff
PYTEST := $(PYTHON) -m pytest
UVICORN := $(PYTHON) -m uvicorn

all: $(PYTHON) fix check test

$(PYTHON):
	uv sync --group dev

ci: $(PYTHON) check test

check: $(PYTHON) lint

lint: $(PYTHON)
	$(RUFF) check .
	$(RUFF) format --check .

format: $(PYTHON)
	$(RUFF) format .

fix: $(PYTHON)
	$(RUFF) check --fix .
	$(RUFF) format .

test: $(PYTHON)
	$(PYTEST) -q

coverage: $(PYTHON)
	$(PYTEST) --cov=app --cov-report=term-missing

dev: $(PYTHON)
	PYTHONPATH=. $(UVICORN) app.main:app --reload
