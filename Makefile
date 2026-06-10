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

build-ci: ##@Build Build distribution
	uv build

docs-install: ##@Docs Sync docs deps and all extras
	uv sync --all-extras --group docs

docs-serve: ##@Docs Live-preview the documentation site
	.venv/bin/mkdocs serve

docs-build: ##@Docs Strict build (links / nav / autodoc check)
	.venv/bin/mkdocs build --strict

docs-deploy: ##@Docs Deploy current version with mike
	uv run mike deploy --push --update-aliases dev latest

clean_dev:
	rm -rf .venv