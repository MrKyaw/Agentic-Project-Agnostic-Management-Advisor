PYTHON ?= python3
PROJECT := project_advisor
PROJECT_JSON ?= project.json

.PHONY: help install test coverage coverage-html demo json cli-check clean

help:
	@echo "make install        Install dev tooling (pytest, pytest-cov)"
	@echo "make test           Run the test suite"
	@echo "make coverage       Run tests with 100% line+branch gate"
	@echo "make coverage-html  Generate htmlcov/index.html"
	@echo "make demo           Render the built-in executive plan"
	@echo "make json           Emit the demo plan as stable JSON"
	@echo "make cli-check      Verify --help and --demo work from the repo root"
	@echo "make clean          Remove caches and coverage artefacts"

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

coverage:
	$(PYTHON) -m pytest --cov=$(PROJECT) --cov-branch --cov-report=term-missing

coverage-html:
	$(PYTHON) -m pytest --cov=$(PROJECT) --cov-branch --cov-report=html
	@echo "Open htmlcov/index.html"

demo:
	$(PYTHON) -m project_advisor --demo

json:
	$(PYTHON) -m project_advisor --demo --json

cli-check:
	$(PYTHON) -m project_advisor --help > /dev/null
	$(PYTHON) -m project_advisor --demo > /dev/null
	@echo "CLI OK"

clean:
	rm -rf .pytest_cache .coverage .coverage.* htmlcov coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
