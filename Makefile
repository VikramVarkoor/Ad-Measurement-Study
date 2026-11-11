# Ad Measurement Study — one command rebuilds everything.
#
#   make data     download the public datasets into data/raw/ (idempotent)
#   make report   rebuild every table, figure, the workbook and the deck
#   make test     run the known-answer test suite
#   make all      data + report + test

PY := .venv/bin/python

.PHONY: all data report test audit kpis lift uplift meta ecommerce excel deck dashboards venv

all: data report test

venv:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

data:
	$(PY) -m src.download

audit:
	$(PY) -m src.audit

kpis:
	$(PY) -m src.kpis

lift:
	$(PY) -m src.lift

uplift:
	$(PY) -m src.uplift

meta:
	$(PY) -m src.run_meta

ecommerce:
	$(PY) -m src.ecommerce

excel:
	$(PY) -m src.make_excel

deck:
	$(PY) -m src.make_deck

dashboards:
	$(PY) -m src.export_dashboards

report: audit kpis lift uplift meta ecommerce excel deck dashboards

test:
	$(PY) -m pytest tests/ -q
