PYTHON ?= python3

.PHONY: ci frontend lint compile check migrations test

ci: lint compile check migrations test

frontend:
	npm ci --ignore-scripts --no-audit --no-fund
	npm run build:assets

lint:
	$(PYTHON) -m ruff check .

compile:
	$(PYTHON) -m compileall -q Mizzac

check:
	cd Mizzac && $(PYTHON) manage.py check --settings=Mizzac.settings_test

migrations:
	cd Mizzac && $(PYTHON) manage.py makemigrations --check --dry-run --settings=Mizzac.settings_test

test:
	$(PYTHON) -m pytest --cov --cov-report=term-missing
