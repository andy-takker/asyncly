PROJECT_NAME = asyncly
PYTHON_VERSION := 3.10
TEST_FOLDER_NAME = tests

develop: clean_dev
	python$(PYTHON_VERSION) -m venv .venv
	.venv/bin/pip install -U pip uv
	.venv/bin/uv sync --all-groups --all-extras
	.venv/bin/pre-commit install

develop-ci:
	python -m pip install -U pip uv
	uv sync --all-groups --all-extras

lint-ci: ruff-ci mypy-ci  ##@Linting Run all linters in CI

test-ci:  ##@Test Run all tests in CI
	.venv/bin/pytest ./$(TEST_FOLDER_NAME) --cov=./$(PROJECT_NAME) --cov-report=xml

ruff-ci: ##@Linting Run ruff
	.venv/bin/ruff check ./$(PROJECT_NAME)

mypy-ci: ##@Linting Run mypy
	.venv/bin/mypy ./$(PROJECT_NAME) --config-file ./pyproject.toml

rst-ci: ##@Linting Run rst-lint
	rst-lint --encoding utf-8 README.rst

build-ci: ##@Build Build distribution
	uv build

clean_dev:
	rm -rf .venv