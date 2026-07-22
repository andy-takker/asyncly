PROJECT_NAME = asyncly
PYTHON_VERSION := 3.10
TEST_FOLDER_NAME = tests

.PHONY: develop develop-ci lint-ci test-ci test-minimum-ci build-ci \
	docs-install docs-serve docs-build docs-deploy clean_dev

develop: clean_dev
	python$(PYTHON_VERSION) -m venv .venv
	.venv/bin/pip install -U pip uv
	.venv/bin/uv sync --all-groups --all-extras
	.venv/bin/pre-commit install

develop-ci:
	uv sync --locked --all-groups --all-extras

lint-ci:
	uv run ruff format --check asyncly tests examples tools
	uv run ruff check asyncly tests examples tools
	uv run mypy asyncly --config-file pyproject.toml

test-ci:
	uv run pytest --cov=asyncly --cov-report=xml

test-minimum-ci:
	uv pip install --python .venv/bin/python -r requirements/lowest-direct.txt
	uv run --no-sync pytest tests

build-ci:
	uv build --clear
	uvx --from twine==6.2.0 twine check dist/*.whl dist/*.tar.gz
	uv run python -m tools.release artifacts \
		--version "$$(uv version --short)" \
		--directory dist \
		--output dist/SHA256SUMS.json

docs-install: ##@Docs Sync docs deps and all extras
	uv sync --all-extras --group docs

docs-serve: ##@Docs Live-preview the documentation site
	.venv/bin/mkdocs serve

docs-build:
	uv run mkdocs build --strict

docs-deploy: ##@Docs Deploy current version with mike
	uv run mike deploy --push --update-aliases dev latest

clean_dev:
	rm -rf .venv
