.PHONY: install dev lint test build publish clean

install:
	pip install .

dev:
	pip install -e ".[dev]"

lint:
	ruff check src/
	ruff format --check src/

format:
	ruff check --fix src/
	ruff format src/

test:
	pytest tests/ -v

build: clean
	python -m build

publish: build
	twine upload dist/*

clean:
	rm -rf dist/ build/ src/*.egg-info
