.PHONY: setup data xlsx analyze demo detect test lint guardrails all

PY := PYTHONPATH=src python3

setup:
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

data:
	$(PY) -m adops_triage.generate_dataset --n 640 --seed 20260823

xlsx: data
	$(PY) -m adops_triage.export_xlsx

analyze: data
	$(PY) -m adops_triage.analysis.baseline > /dev/null && echo "✔ reports/baseline.json"

demo:
	$(PY) -m adops_triage.agents.demo

detect:
	$(PY) -m adops_triage.detectors.demo

test:
	$(PY) -m pytest tests -q

lint:
	ruff check src tools && ruff format --check src tools

guardrails:
	python3 tools/check_probes_readonly.py src/adops_triage/probes
	python3 tools/check_playbook_refs.py --spec specs/playbook_registry.yaml --src src
	python3 tools/check_taxonomy_drift.py --spec specs/taxonomy.yaml --src src

all: data xlsx analyze guardrails test
