.PHONY: sync dev load-environment test coverage shell

sync:
	uv sync
	@echo Activate the virtual environment: source .venv/bin/activate.fish

dev:
	uv sync --extra dev

load-environment:
	@echo Activate the virtual environment: source .venv/bin/activate.fish

test:
	uv run python -m unittest discover

coverage: dev
	uv run coverage run -m unittest discover
	uv run coverage report

shell:
	uv run python
