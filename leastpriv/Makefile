PY ?= python3.12
VENV := .venv

.PHONY: install test clean

install:
	uv venv --python $(PY) $(VENV)
	uv pip install --python $(VENV)/bin/python -e ../core -e '.[dev]'

test:
	$(VENV)/bin/pytest -q

clean:
	rm -rf $(VENV) .pytest_cache src/*.egg-info
