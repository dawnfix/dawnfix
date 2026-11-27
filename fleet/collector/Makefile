PY ?= python3.12
VENV := .venv

.PHONY: install test clean fixture

install:
	uv venv --python $(PY) $(VENV)
	uv pip install --python $(VENV)/bin/python -e ../../core -e '.[dev]'

test:
	$(VENV)/bin/pytest -q

# Rewrites ../fixtures/summary.json from the stubbed collection in tests/test_fixture.py.
fixture:
	FLEET_WRITE_FIXTURE=1 $(VENV)/bin/pytest -q tests/test_fixture.py

clean:
	rm -rf $(VENV) .pytest_cache src/*.egg-info
