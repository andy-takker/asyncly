PROJECT_NAME = asyncly

develop: clean_dev
	python3.10 -m venv .venv
	.venv/bin/pip install -U pip poetry
	.venv/bin/poetry config virtualenvs.create false
	.venv/bin/poetry install --all-extras
	.venv/bin/pre-commit install

develop-ci:
	pip install -U pip poetry
	poetry config virtualenvs.create false
	poetry install --all-extras

lint-ci: ruff-ci mypy-ci  ##@Linting Run all linters in CI

ruff-ci: ##@Linting Run ruff
	ruff check ./$(PROJECT_NAME)

mypy-ci: ##@Linting Run mypy
	mypy ./$(PROJECT_NAME) --config-file ./pyproject.toml

rst-ci: ##@Linting Run rst-lint
	rst-lint --encoding utf-8 README.rst

clean_dev:
	rm -rf .venv