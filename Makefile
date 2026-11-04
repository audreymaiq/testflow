PYTHON ?= python3.11
PIP = backend/.venv/bin/pip
MANAGE = backend/.venv/bin/python backend/manage.py

.PHONY: setup dev services migrate api worker web check

setup:
	$(PYTHON) -m venv backend/.venv
	$(PIP) install -r backend/requirements-dev.txt
	$(PIP) install -e contracts
	cd frontend && npm ci
	$(PYTHON) design/build_tokens.py
	$(PYTHON) scripts/init_env.py

services:
	docker compose -f compose.dev.yml up -d --wait

migrate:
	$(MANAGE) migrate

api:
	$(MANAGE) runserver

worker:
	cd backend && .venv/bin/celery -A config worker -l info

web:
	cd frontend && npm run dev

dev: services migrate
	$(MAKE) -j3 api worker web

check:
	$(PYTHON) design/palette.py
	backend/.venv/bin/ruff check backend contracts
	backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/apps backend/config contracts/testflow_contracts
	cd backend && .venv/bin/lint-imports --config .importlinter
	backend/.venv/bin/pytest backend
	cd frontend && npm run check
	cd frontend && npm run build
