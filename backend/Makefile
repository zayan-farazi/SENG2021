.PHONY: all ci check lint format fix test test-unit test-integration coverage report dev

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

test-unit: $(PYTHON)
	$(PYTEST) -q tests/unit

test-integration: $(PYTHON)
	$(PYTEST) -q tests/integration

coverage: $(PYTHON)
	$(PYTEST) --cov=app --cov-report=term-missing

report: $(PYTHON)
	mkdir -p reports
	PYTHONPATH=. $(PYTEST) tests/unit tests/integration \
		--cov=app \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml \
		--junitxml=reports/results.xml \
		--html=reports/report.html \
		--self-contained-html

dev: $(PYTHON)
	PYTHONPATH=. $(UVICORN) app.main:app --reload
