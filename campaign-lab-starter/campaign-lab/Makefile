.PHONY: setup data lint test all

setup:
	uv sync
	uv run pre-commit install

data:
	uv run campaign-generate

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest

all: lint data test
