PYTHON ?= python3.12
APP := Mainstream Toolkit/web_platform
PY := .venv/bin/python

.PHONY: setup build check test run worker
setup:
	$(PYTHON) -m venv .venv
	$(PY) -m pip install -r "$(APP)/requirements.txt"
	cd "$(APP)/frontend" && npm ci
	@test -f "$(APP)/.env" || cp "$(APP)/.env.example" "$(APP)/.env"
	$(MAKE) build
	$(PY) "$(APP)/manage.py" migrate
build:
	cd "$(APP)/frontend" && npm run build
	$(PY) "$(APP)/manage.py" collectstatic --noinput
check:
	$(PY) "$(APP)/manage.py" check
	$(PY) "$(APP)/manage.py" makemigrations --check --dry-run
test: build
	$(PY) "$(APP)/manage.py" test studio --noinput
	cd "$(APP)/frontend" && npm test
run:
	$(PY) "$(APP)/manage.py" runserver 127.0.0.1:8000
worker:
	$(PY) "$(APP)/manage.py" sync_memberships --loop
