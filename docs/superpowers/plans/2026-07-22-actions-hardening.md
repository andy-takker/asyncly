# Asyncly CI, Release, and Changelog Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden Asyncly's CI and release supply chain, add one stable required check, and automate Keep a Changelog releases from Towncrier fragments.

**Architecture:** A top-level CI orchestrator calls focused reusable workflows and collapses their results into `CI required`. A manual release-preparation workflow assembles fragments into a reviewable release PR, while a tag-only workflow rebuilds and verifies the exact tagged source once before provenance, PyPI, Sigstore, GitHub Release, and Mike deployment. Repository-local Python helpers own parsing and artifact validation so YAML remains orchestration rather than application code.

**Tech Stack:** GitHub Actions, uv 0.11.31, Python 3.10-3.14, Towncrier 25.8, actionlint 1.7.12, zizmor 1.28, MkDocs/Mike, PyPI trusted publishing, Sigstore, GitHub artifact attestations, pytest, Ruff, mypy.

---

## Fixed references and file map

Use these immutable action revisions throughout the plan:

```text
actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1          # v7.0.1
astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9        # v9.0.0
actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a  # v7.0.1
actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
actions/attest-build-provenance@0f67c3f4856b2e3261c31976d6725780e5e4c373 # v4.1.1
sigstore/gh-action-sigstore-python@5b79a39c381910c090341a2c9b0bf022c8b387e1 # v3.4.0
softprops/action-gh-release@3d0d9888cb7fd7b750713d6e236d1fcb99157228 # v3.0.2
zizmorcore/zizmor-action@6599ee8b7a49aef6a770f63d261d214911a7ce02 # v0.6.0
```

The implementation changes these units:

```text
pyproject.toml                         Towncrier dependency/config and Python 3.14 classifier
uv.lock                                locked dependency update
CHANGELOG.md                           Towncrier insertion marker
changes/                               reviewable changelog fragments and contributor guide
tools/release.py                       testable release/version/artifact helpers
tests/tools/test_release.py            helper unit tests
requirements/lowest-direct.txt         declared minimum direct dependencies
Makefile                               local/CI quality, test, docs, and package commands
.github/actions/setup-project/         shared uv/Python/cache setup
.github/workflows/ci.yaml              PR/master/merge-group orchestrator and stable status
.github/workflows/_check.yaml          workflow and Python static checks
.github/workflows/_test.yaml           supported-Python and minimum-dependency tests
.github/workflows/_docs.yaml           strict documentation build
.github/workflows/_build.yaml          distribution verification and upload
.github/workflows/prepare-release.yaml Towncrier dry-run/release-PR automation
.github/workflows/release.yaml         tag-only validation and orchestration
.github/workflows/_publish.yaml        provenance, idempotent PyPI, Sigstore, GitHub Release
.github/workflows/docs.yaml            hardened Mike deployment
.github/dependabot.yml                 action updates and changelog exemption
.github/rulesets/*.json                reproducible branch/tag ruleset payloads
docs/guide/contributing.md             fragment and release-maintainer workflow
mkdocs.yml                              contributor guide navigation
```

Delete `.github/workflows/feature.yaml` after `ci.yaml` is in place. Keep the reusable-workflow split; do not migrate to release-please or GitHub Pages artifacts.

### Task 1: Establish Towncrier fragments

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `CHANGELOG.md`
- Create: `changes/README.md`
- Create: `changes/template.md`
- Create: `changes/+actions-hardening.changed.md`

- [ ] **Step 1: Record the failing Towncrier command**

Run:

```bash
rtk uv run towncrier build --draft --version 0.9.1 --date 2026-07-22
```

Expected: non-zero exit because Towncrier is not installed/configured.

- [ ] **Step 2: Add the dependency and ordered fragment configuration**

Add `"towncrier>=25.8.0,<26"` to the `dev` dependency group. Append this exact configuration to `pyproject.toml`:

```toml
[tool.towncrier]
directory = "changes"
filename = "CHANGELOG.md"
template = "changes/template.md"
start_string = "<!-- towncrier release notes start -->\n"
title_format = "## [{version}] - {project_date}"
issue_format = "[#{issue}](https://github.com/andy-takker/asyncly/issues/{issue})"
issue_pattern = "\\d+"
orphan_prefix = "+"
ignore = []

[[tool.towncrier.type]]
directory = "added"
name = "Added"
showcontent = true

[[tool.towncrier.type]]
directory = "changed"
name = "Changed"
showcontent = true

[[tool.towncrier.type]]
directory = "breaking"
name = "Changed (breaking)"
showcontent = true

[[tool.towncrier.type]]
directory = "fixed"
name = "Fixed"
showcontent = true

[[tool.towncrier.type]]
directory = "deprecated"
name = "Deprecated"
showcontent = true

[[tool.towncrier.type]]
directory = "security"
name = "Security"
showcontent = true

[[tool.towncrier.type]]
directory = "docs"
name = "Documentation"
showcontent = true
```

Immediately below `## [Unreleased]` in `CHANGELOG.md`, add:

```markdown
<!-- towncrier release notes start -->
```

- [ ] **Step 3: Add the deterministic Markdown template**

Create `changes/template.md` with:

```jinja
{% for section, categories in sections.items() %}
{% for category, entries in categories.items() if entries %}
### {{ definitions[category]["name"] }}

{% for text, issues in entries.items() -%}
- {{ text }}{% if issues %} ({{ issues | join(", ") }}){% endif %}
{% endfor %}

{% endfor %}
{% endfor %}
```

Create `changes/README.md` with the filename grammar, the seven types, examples, and the rule that only maintainers may use `skip-changelog`. Include these commands verbatim:

````markdown
Create a fragment as `changes/<pr-number>.<type>.md`, for example
`changes/42.fixed.md`. Before a pull request has a number, use an orphan name
such as `changes/+short-description.changed.md`.

Preview the next section:

```bash
uv run towncrier build --draft --version 0.9.1
```

Validate the current branch:

```bash
uv run towncrier check --compare-with origin/master
```
````

Create `changes/+actions-hardening.changed.md`:

```markdown
Hardened CI and release automation with immutable Actions, complete quality
gates, artifact provenance, protected release tags, and automated changelog
assembly.
```

- [ ] **Step 4: Update and verify the lockfile**

Run:

```bash
rtk uv lock
rtk uv sync --locked --all-groups --all-extras
rtk uv run towncrier build --draft --version 0.9.1 --date 2026-07-22
rtk uv run towncrier check --compare-with master
```

Expected: the draft contains `## [0.9.1] - 2026-07-22`, `### Changed`, and the hardening fragment; the check reports the fragment.

- [ ] **Step 5: Commit the changelog foundation**

```bash
rtk git add pyproject.toml uv.lock CHANGELOG.md changes
rtk git commit -m "build: add Towncrier changelog fragments"
```

### Task 2: Specify the release helper behavior test-first

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/release.py`
- Create: `tests/tools/__init__.py`
- Create: `tests/tools/test_release.py`

- [ ] **Step 1: Create tests for stable versions and comparison links**

Create empty `tools/__init__.py` and `tests/tools/__init__.py`. Create `tests/tools/test_release.py` starting with:

```python
import json
from pathlib import Path

import pytest

from tools.release import (
    ReleaseError,
    artifact_manifest,
    extract_release_notes,
    lock_version,
    project_version,
    stable_version,
    update_comparison_links,
    validate_next_version,
)


def test_stable_version_accepts_semver() -> None:
    assert stable_version("1.20.3") == (1, 20, 3)


@pytest.mark.parametrize("value", ["1.2", "v1.2.3", "1.2.3rc1", "01.2.3"])
def test_stable_version_rejects_non_release_values(value: str) -> None:
    with pytest.raises(ReleaseError, match="stable X.Y.Z"):
        stable_version(value)


def test_validate_next_version_requires_increase() -> None:
    validate_next_version("0.10.0", "0.9.0")
    with pytest.raises(ReleaseError, match="greater than 0.9.0"):
        validate_next_version("0.9.0", "0.9.0")


def test_update_comparison_links() -> None:
    source = """[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.9.0...HEAD
[0.9.0]: https://github.com/andy-takker/asyncly/compare/0.8.0...0.9.0
"""
    assert update_comparison_links(source, previous="0.9.0", version="0.10.0") == """[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.10.0...HEAD
[0.10.0]: https://github.com/andy-takker/asyncly/compare/0.9.0...0.10.0
[0.9.0]: https://github.com/andy-takker/asyncly/compare/0.8.0...0.9.0
"""
```

- [ ] **Step 2: Add tests for metadata, release notes, and artifacts**

Append:

```python
def test_read_versions(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "asyncly"\nversion = "0.10.0"\n')
    lock = tmp_path / "uv.lock"
    lock.write_text('version = 1\n[[package]]\nname = "asyncly"\nversion = "0.10.0"\n')
    assert project_version(pyproject) == "0.10.0"
    assert lock_version(lock) == "0.10.0"


def test_extract_release_notes() -> None:
    changelog = """## [Unreleased]

<!-- towncrier release notes start -->

## [0.10.0] - 2026-08-01

### Added
- Retry budgets.

## [0.9.0] - 2026-07-22
"""
    assert extract_release_notes(changelog, "0.10.0") == """### Added
- Retry budgets.
"""


def test_artifact_manifest_hashes_exact_pair(tmp_path: Path) -> None:
    wheel = tmp_path / "asyncly-0.10.0-py3-none-any.whl"
    sdist = tmp_path / "asyncly-0.10.0.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    manifest = artifact_manifest(tmp_path, "0.10.0")
    assert [item["filename"] for item in manifest] == [wheel.name, sdist.name]
    assert all(len(item["sha256"]) == 64 for item in manifest)


def test_manifest_is_json_serializable(tmp_path: Path) -> None:
    (tmp_path / "asyncly-0.10.0-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / "asyncly-0.10.0.tar.gz").write_bytes(b"sdist")
    json.dumps(artifact_manifest(tmp_path, "0.10.0"))
```

- [ ] **Step 3: Run the tests to prove the helper is missing**

```bash
rtk uv run pytest tests/tools/test_release.py -q
```

Expected: collection fails because the named functions are not defined.

### Task 3: Implement the release helper CLI

**Files:**
- Modify: `tools/release.py`
- Modify: `tests/tools/test_release.py`

- [ ] **Step 1: Implement the pure helper functions**

Implement these interfaces in `tools/release.py`:

```python
import argparse
import hashlib
import json
import re
import sys
from email.parser import Parser
from pathlib import Path
from tarfile import open as open_tar
from zipfile import ZipFile

import toml

_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_COMPARE_ROOT = "https://github.com/andy-takker/asyncly/compare"


class ReleaseError(ValueError):
    pass


def stable_version(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value)
    if match is None:
        raise ReleaseError(f"version {value!r} must be stable X.Y.Z SemVer")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def validate_next_version(version: str, previous: str) -> None:
    if stable_version(version) <= stable_version(previous):
        raise ReleaseError(f"version {version} must be greater than {previous}")


def project_version(path: Path) -> str:
    return str(toml.load(path)["project"]["version"])


def lock_version(path: Path) -> str:
    packages = toml.load(path)["package"]
    matches = [item for item in packages if item.get("name") == "asyncly"]
    if len(matches) != 1:
        raise ReleaseError("uv.lock must contain exactly one asyncly package")
    return str(matches[0]["version"])


def update_comparison_links(text: str, *, previous: str, version: str) -> str:
    old = f"[Unreleased]: {_COMPARE_ROOT}/{previous}...HEAD\n"
    if text.count(old) != 1:
        raise ReleaseError(f"missing unique Unreleased link for {previous}")
    release_link = f"[{version}]: {_COMPARE_ROOT}/{previous}...{version}\n"
    if f"[{version}]:" in text:
        raise ReleaseError(f"comparison link for {version} already exists")
    return text.replace(
        old,
        f"[Unreleased]: {_COMPARE_ROOT}/{version}...HEAD\n{release_link}",
        1,
    )


def extract_release_notes(text: str, version: str) -> str:
    stable_version(version)
    heading = re.compile(rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}\n", re.M)
    match = heading.search(text)
    if match is None:
        raise ReleaseError(f"missing changelog section for {version}")
    next_heading = re.search(r"^## \[", text[match.end():], re.M)
    end = match.end() + next_heading.start() if next_heading else len(text)
    notes = text[match.end():end].strip()
    if not notes:
        raise ReleaseError(f"empty changelog section for {version}")
    return notes + "\n"


def artifact_manifest(directory: Path, version: str) -> list[dict[str, str]]:
    stable_version(version)
    names = [
        f"asyncly-{version}-py3-none-any.whl",
        f"asyncly-{version}.tar.gz",
    ]
    unexpected = sorted(
        path.name for path in directory.iterdir()
        if path.is_file() and path.name not in {*names, "SHA256SUMS.json"}
    )
    if unexpected:
        raise ReleaseError(f"unexpected distribution files: {unexpected}")
    result = []
    for name in names:
        path = directory / name
        if not path.is_file():
            raise ReleaseError(f"missing distribution: {name}")
        result.append({"filename": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return result


def verify_wheel(directory: Path, version: str) -> None:
    wheel = directory / f"asyncly-{version}-py3-none-any.whl"
    with ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ReleaseError("wheel must contain exactly one METADATA file")
        metadata = Parser().parsestr(archive.read(metadata_names[0]).decode())
        if metadata["Name"] != "asyncly" or metadata["Version"] != version:
            raise ReleaseError("wheel name/version metadata mismatch")
        if metadata["Requires-Python"] != "<4,>=3.10":
            raise ReleaseError("wheel Requires-Python metadata mismatch")
        required = {"asyncly/client/retry.py", "asyncly/srvmocker/responses/faults.py"}
        missing = sorted(required - set(archive.namelist()))
        if missing:
            raise ReleaseError(f"wheel missing public files: {missing}")


def verify_sdist(directory: Path, version: str) -> None:
    sdist = directory / f"asyncly-{version}.tar.gz"
    prefix = f"asyncly-{version}/"
    required = {
        prefix + "pyproject.toml",
        prefix + "asyncly/client/retry.py",
        prefix + "asyncly/srvmocker/responses/faults.py",
    }
    with open_tar(sdist, "r:gz") as archive:
        missing = sorted(required - set(archive.getnames()))
    if missing:
        raise ReleaseError(f"sdist missing public files: {missing}")
```

Format the long expressions to Ruff's 88-column style during implementation; do not suppress Ruff for the helper.

- [ ] **Step 2: Add exact CLI commands**

Implement `main(argv: list[str] | None = None) -> int` with these subcommands:

```text
validate-next --version VERSION --pyproject pyproject.toml
update-links --version VERSION --previous PREVIOUS --changelog CHANGELOG.md
validate-release --version VERSION --pyproject pyproject.toml --lockfile uv.lock --changelog CHANGELOG.md
notes --version VERSION --changelog CHANGELOG.md --output release-notes.md
artifacts --version VERSION --directory dist --output dist/SHA256SUMS.json
```

Behavior must be exact:

```python
def validate_release(version: str, pyproject: Path, lockfile: Path, changelog: Path) -> None:
    stable_version(version)
    if project_version(pyproject) != version:
        raise ReleaseError("tag does not match pyproject version")
    if lock_version(lockfile) != version:
        raise ReleaseError("tag does not match uv.lock version")
    extract_release_notes(changelog.read_text(), version)
```

`update-links` rewrites the file only after `update_comparison_links` succeeds. `notes` writes `extract_release_notes`. `artifacts` calls `verify_wheel`, serializes `artifact_manifest(..., indent=2, sort_keys=True)`, and adds a final newline. Implement the dispatcher with this structure:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    validate_next = commands.add_parser("validate-next")
    validate_next.add_argument("--version", required=True)
    validate_next.add_argument("--pyproject", type=Path, required=True)

    update_links = commands.add_parser("update-links")
    update_links.add_argument("--version", required=True)
    update_links.add_argument("--previous", required=True)
    update_links.add_argument("--changelog", type=Path, required=True)

    validate = commands.add_parser("validate-release")
    validate.add_argument("--version", required=True)
    validate.add_argument("--pyproject", type=Path, required=True)
    validate.add_argument("--lockfile", type=Path, required=True)
    validate.add_argument("--changelog", type=Path, required=True)

    notes = commands.add_parser("notes")
    notes.add_argument("--version", required=True)
    notes.add_argument("--changelog", type=Path, required=True)
    notes.add_argument("--output", type=Path, required=True)

    artifacts = commands.add_parser("artifacts")
    artifacts.add_argument("--version", required=True)
    artifacts.add_argument("--directory", type=Path, required=True)
    artifacts.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "validate-next":
            validate_next_version(args.version, project_version(args.pyproject))
        elif args.command == "update-links":
            source = args.changelog.read_text()
            args.changelog.write_text(
                update_comparison_links(
                    source,
                    previous=args.previous,
                    version=args.version,
                )
            )
        elif args.command == "validate-release":
            validate_release(
                args.version,
                args.pyproject,
                args.lockfile,
                args.changelog,
            )
        elif args.command == "notes":
            args.output.write_text(
                extract_release_notes(args.changelog.read_text(), args.version)
            )
        elif args.command == "artifacts":
            verify_wheel(args.directory, args.version)
            verify_sdist(args.directory, args.version)
            args.output.write_text(
                json.dumps(
                    artifact_manifest(args.directory, args.version),
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
    except ReleaseError as exc:
        print(f"release validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Add CLI tests**

Import `main` and append:

```python
def test_main_updates_links(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.9.0...HEAD\n"
    )
    result = main(
        [
            "update-links",
            "--version",
            "0.10.0",
            "--previous",
            "0.9.0",
            "--changelog",
            str(changelog),
        ]
    )
    assert result == 0
    assert "[0.10.0]:" in changelog.read_text()


def test_main_reports_release_mismatch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "asyncly"\nversion = "0.9.0"\n')
    lockfile = tmp_path / "uv.lock"
    lockfile.write_text(
        'version = 1\n[[package]]\nname = "asyncly"\nversion = "0.10.0"\n'
    )
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## [0.10.0] - 2026-08-01\n\n### Added\n- Item.\n")
    result = main(
        [
            "validate-release",
            "--version",
            "0.10.0",
            "--pyproject",
            str(pyproject),
            "--lockfile",
            str(lockfile),
            "--changelog",
            str(changelog),
        ]
    )
    assert result == 1
    assert capsys.readouterr().err.startswith("release validation failed:")
```

- [ ] **Step 4: Run focused and static verification**

```bash
rtk uv run pytest tests/tools/test_release.py -q
rtk uv run ruff format tools tests/tools
rtk uv run ruff check tools tests/tools
```

Expected: all helper tests pass and Ruff is clean.

- [ ] **Step 5: Commit the helper**

```bash
rtk git add tools tests/tools
rtk git commit -m "build: add tested release helpers"
```

### Task 4: Make local commands match CI

**Files:**
- Modify: `Makefile`
- Create: `requirements/lowest-direct.txt`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Add the minimum direct dependency set**

Create `requirements/lowest-direct.txt`:

```text
aiohttp==3.13.3
msgspec==0.19.0
opentelemetry-sdk==1.37.0
orjson==3.10.6
prometheus-client==0.22.1
pydantic==2.8.2
```

- [ ] **Step 2: Replace CI targets with uv-backed complete gates**

Keep developer environment targets, but replace the CI targets with:

```make
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

docs-build:
	uv run mkdocs build --strict
```

Declare the targets phony. Do not retain `.venv/bin/...` in CI targets.

- [ ] **Step 3: Verify Python 3.14 before declaring support**

```bash
rtk uv python install 3.14
rtk uv sync --python 3.14 --locked --all-groups --all-extras
rtk uv run --python 3.14 pytest tests -q
```

Expected: the core suite passes on Python 3.14. Then add this classifier to `pyproject.toml`:

```toml
"Programming Language :: Python :: 3.14",
```

Run `rtk uv lock` because project metadata changed.

- [ ] **Step 4: Verify every local target**

```bash
rtk make lint-ci
rtk make test-ci
rtk make docs-build
rtk make build-ci
```

Expected: all targets pass; `dist/SHA256SUMS.json` lists exactly the 0.9.0 wheel and sdist.

- [ ] **Step 5: Commit the local gates**

```bash
rtk git add Makefile requirements/lowest-direct.txt pyproject.toml uv.lock
rtk git commit -m "ci: align local and hosted quality gates"
```

### Task 5: Add the shared project setup action

**Files:**
- Create: `.github/actions/setup-project/action.yml`

- [ ] **Step 1: Create the complete composite action**

```yaml
name: Set up Asyncly
description: Install uv, the requested Python, and locked project dependencies

inputs:
  python-version:
    description: Python version to install
    required: true

runs:
  using: composite
  steps:
    - name: Install uv and Python
      uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
      with:
        version: "0.11.31"
        python-version: ${{ inputs.python-version }}
        enable-cache: true
        cache-python: true
        activate-environment: true

    - name: Sync locked dependencies
      shell: bash
      run: uv sync --locked --all-groups --all-extras
```

- [ ] **Step 2: Validate the local action syntax**

```bash
rtk docker run --rm \
  -v "$PWD:/repo" -w /repo \
  rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667
```

Expected: actionlint exits zero.

- [ ] **Step 3: Commit the composite action**

```bash
rtk git add .github/actions/setup-project/action.yml
rtk git commit -m "ci: centralize uv project setup"
```

### Task 6: Rebuild the reusable quality workflows

**Files:**
- Modify: `.github/workflows/_check.yaml`
- Modify: `.github/workflows/_test.yaml`
- Create: `.github/workflows/_docs.yaml`
- Modify: `.github/workflows/_build.yaml`

- [ ] **Step 1: Replace `_check.yaml`**

Use two jobs on `ubuntu-24.04`, each with `timeout-minutes: 10` and `permissions: contents: read`. Both check out with the pinned checkout SHA. The workflow-security job runs:

```yaml
- name: Run actionlint
  run: >-
    docker run --rm
    -v "${GITHUB_WORKSPACE}:/repo"
    -w /repo
    rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667

- name: Run zizmor
  uses: zizmorcore/zizmor-action@6599ee8b7a49aef6a770f63d261d214911a7ce02 # v0.6.0
  with:
    version: "1.28.0"
    advanced-security: false
    annotations: true
    persona: pedantic
```

The Python-quality job uses `.github/actions/setup-project` with Python 3.10 and runs `make lint-ci`.

- [ ] **Step 2: Replace `_test.yaml`**

Define a matrix job with `fail-fast: false`, Python `['3.10', '3.11', '3.12', '3.13', '3.14']`, `ubuntu-24.04`, `timeout-minutes: 15`, checkout, shared setup, and `make test-ci`.

Add `minimum-direct-dependencies`, Python 3.10, with the same checkout/setup followed by `make test-minimum-ci`. Do not upload five duplicate coverage artifacts.

- [ ] **Step 3: Add `_docs.yaml`**

Create a callable workflow containing one `strict-docs` job on `ubuntu-24.04`, timeout 10 minutes, checkout, shared setup on Python 3.10, and `make docs-build`.

- [ ] **Step 4: Replace `_build.yaml`**

The single package job uses `ubuntu-24.04`, timeout 15 minutes, checkout, shared setup, and `make build-ci`. Then smoke-install the wheel outside the checkout:

```yaml
- name: Export package version
  run: echo "PACKAGE_VERSION=$(uv version --short)" >> "${GITHUB_ENV}"

- name: Smoke-test the built wheel
  shell: bash
  run: |
    cd "${RUNNER_TEMP}"
    uv run --isolated --no-project \
      --with "${GITHUB_WORKSPACE}/dist/asyncly-${GITHUB_REF_NAME#v}-py3-none-any.whl" \
      python -c 'from importlib.metadata import version; from asyncly import RetryPolicy; from asyncly.srvmocker import DisconnectResponse, RecordedRequest; print(version("asyncly"), RetryPolicy.__name__, DisconnectResponse.__name__, RecordedRequest.__name__)'
```

Do not derive the package version from a branch name. Upload `dist/` as `python-package-dist` with the pinned upload-artifact action and `if-no-files-found: error`.

- [ ] **Step 5: Run actionlint and commit**

```bash
rtk docker run --rm -v "$PWD:/repo" -w /repo \
  rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667
rtk git add .github/workflows/_check.yaml .github/workflows/_test.yaml \
  .github/workflows/_docs.yaml .github/workflows/_build.yaml
rtk git commit -m "ci: complete reusable quality workflows"
```

### Task 7: Introduce the CI orchestrator and changelog gate

**Files:**
- Delete: `.github/workflows/feature.yaml`
- Create: `.github/workflows/ci.yaml`

- [ ] **Step 1: Create `ci.yaml` triggers and permissions**

Start with:

```yaml
name: CI

on:
  pull_request:
    branches: [master]
    types: [opened, synchronize, reopened, labeled, unlabeled]
  merge_group:
  push:
    branches: [master]
  workflow_dispatch:

permissions:
  contents: read
  pull-requests: read

concurrency:
  group: ci-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true
```

Call `_check.yaml`, `_test.yaml`, `_docs.yaml`, and `_build.yaml` as jobs named `check`, `test`, `docs`, and `build`, with dependencies `check -> test`, while docs and build may start after check. Reusable calls must not request write permissions.

- [ ] **Step 2: Add the PR-only Towncrier gate**

Add a `changelog` job that runs only when the event is a pull request and neither `skip-changelog` nor `release` appears in `github.event.pull_request.labels.*.name`. It checks out with `fetch-depth: 0`, uses the shared setup action, and runs:

```yaml
changelog:
  if: >-
    github.event_name == 'pull_request' &&
    !contains(github.event.pull_request.labels.*.name, 'skip-changelog') &&
    !contains(github.event.pull_request.labels.*.name, 'release')
  runs-on: ubuntu-24.04
  timeout-minutes: 5
  steps:
    - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      with:
        fetch-depth: 0
    - uses: ./.github/actions/setup-project
      with:
        python-version: "3.10"
    - name: Require a changelog fragment
      run: uv run towncrier check --compare-with origin/master
```

No commit-message escape hatch is allowed.

- [ ] **Step 3: Add the stable aggregate job**

Use this exact final job:

```yaml
  required:
    name: CI required
    if: always()
    needs: [check, test, docs, build, changelog]
    runs-on: ubuntu-24.04
    timeout-minutes: 2
    steps:
      - name: Verify required jobs
        env:
          CHECK_RESULT: ${{ needs.check.result }}
          TEST_RESULT: ${{ needs.test.result }}
          DOCS_RESULT: ${{ needs.docs.result }}
          BUILD_RESULT: ${{ needs.build.result }}
          CHANGELOG_RESULT: ${{ needs.changelog.result }}
        run: |
          python - <<'PY'
          import os
          allowed = {"success", "skipped"}
          names = ("CHECK", "TEST", "DOCS", "BUILD", "CHANGELOG")
          failed = {name: os.environ[f"{name}_RESULT"] for name in names if os.environ[f"{name}_RESULT"] not in allowed}
          if failed:
              raise SystemExit(f"required jobs failed: {failed}")
          PY
```

- [ ] **Step 4: Remove the old orchestrator and verify**

```bash
rtk git rm .github/workflows/feature.yaml
rtk docker run --rm -v "$PWD:/repo" -w /repo \
  rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667
```

Expected: actionlint passes and only `ci.yaml` owns branch/PR CI.

- [ ] **Step 5: Commit**

```bash
rtk git add .github/workflows/ci.yaml
rtk git commit -m "ci: add pull request pipeline with stable required check"
```

### Task 8: Add dry-run and release-PR preparation

**Files:**
- Create: `.github/workflows/prepare-release.yaml`

- [ ] **Step 1: Define safe manual inputs and permissions**

Use `workflow_dispatch` inputs `version` (required string) and `dry_run` (required boolean, default true). Set `permissions: {}` and a non-cancelling `prepare-release` concurrency group. The one job uses `ubuntu-24.04`, timeout 15 minutes, and only:

```yaml
permissions:
  actions: write
  contents: write
  issues: write
  pull-requests: write
```

Checkout `master` with `fetch-depth: 0`, then use shared setup on Python 3.10.

- [ ] **Step 2: Validate and generate release files**

Pass workflow inputs through environment variables, never direct shell interpolation:

```yaml
env:
  RELEASE_VERSION: ${{ inputs.version }}
```

Run these steps in order:

```bash
git fetch origin master --tags
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/master)"
uv run python -m tools.release validate-next --version "${RELEASE_VERSION}" --pyproject pyproject.toml
test -z "$(git ls-remote --tags origin "refs/tags/${RELEASE_VERSION}")"
test -z "$(git ls-remote --heads origin "refs/heads/release/${RELEASE_VERSION}")"
! gh release view "${RELEASE_VERSION}" >/dev/null 2>&1
uv run towncrier build --yes --version "${RELEASE_VERSION}" --date "$(date -u +%F)"
PREVIOUS_VERSION="$(uv version --short)"
uv version "${RELEASE_VERSION}" --no-sync
uv run python -m tools.release update-links --version "${RELEASE_VERSION}" --previous "${PREVIOUS_VERSION}" --changelog CHANGELOG.md
uv run python -m tools.release notes --version "${RELEASE_VERSION}" --changelog CHANGELOG.md --output release-notes.md
git diff --check
```

In YAML, expose `PREVIOUS_VERSION` via `$GITHUB_ENV` instead of relying on one shell step's variable in later steps. Give `gh` the built-in token through `GH_TOKEN`.

- [ ] **Step 3: Implement dry-run artifacts**

When `dry_run` is true, run `git diff --binary > release.patch`, then upload `release.patch` and `release-notes.md` as `release-${{ inputs.version }}-dry-run` with the pinned upload action. The workflow ends without creating refs.

- [ ] **Step 4: Implement release branch and PR creation**

When `dry_run` is false:

```bash
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git switch -c "release/${RELEASE_VERSION}"
git add CHANGELOG.md pyproject.toml uv.lock changes
git commit -m "chore: release ${RELEASE_VERSION}"
git push origin "HEAD:release/${RELEASE_VERSION}"
gh pr create --base master --head "release/${RELEASE_VERSION}" --label release --title "chore: release ${RELEASE_VERSION}" --body-file release-notes.md
gh workflow run ci.yaml --ref "release/${RELEASE_VERSION}"
```

`release-notes.md` remains untracked and is used only for the pull-request body.

- [ ] **Step 5: Validate and commit**

```bash
rtk docker run --rm -v "$PWD:/repo" -w /repo \
  rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667
rtk git add .github/workflows/prepare-release.yaml
rtk git commit -m "ci: automate reviewable release preparation"
```

### Task 9: Harden tag validation, publishing, and release assets

**Files:**
- Modify: `.github/workflows/release.yaml`
- Modify: `.github/workflows/_publish.yaml`

- [ ] **Step 1: Make `release.yaml` tag-only**

Remove `workflow_dispatch`. Keep only stable numeric tags. Add `permissions: {}` and non-cancelling concurrency `release-${{ github.ref }}`.

Add a first `validate` job with checkout `fetch-depth: 0`, shared setup, and:

```bash
test "$(git cat-file -t "refs/tags/${GITHUB_REF_NAME}")" = tag
git fetch origin master
git merge-base --is-ancestor "${GITHUB_SHA}" origin/master
uv run python -m tools.release validate-release \
  --version "${GITHUB_REF_NAME}" \
  --pyproject pyproject.toml \
  --lockfile uv.lock \
  --changelog CHANGELOG.md
```

Make check/test/docs/build depend on validation. Pass `version: ${{ github.ref_name }}` to `_publish.yaml`, and grant the called publish workflow `contents: write`, `id-token: write`, and `attestations: write`.

After the publish call succeeds, add `deploy-release-docs`. Grant only
`actions: write`, set `GH_TOKEN` from `secrets.GITHUB_TOKEN`, and dispatch:

```bash
gh workflow run docs.yaml -f version="${GITHUB_REF_NAME}"
```

This preserves a separate documentation run while ensuring failed package
releases never update the version/`latest` aliases.

- [ ] **Step 2: Define `_publish.yaml` input and provenance job**

Add a required string `version` under `workflow_call.inputs`. The `provenance` job downloads `python-package-dist`, then runs:

```yaml
- name: Attest release artifacts
  uses: actions/attest-build-provenance@0f67c3f4856b2e3261c31976d6725780e5e4c373 # v4.1.1
  with:
    subject-path: |
      dist/*.whl
      dist/*.tar.gz
```

Grant this job `contents: read`, `id-token: write`, and `attestations: write` only.

- [ ] **Step 3: Make PyPI publication idempotent**

The PyPI job needs provenance, uses environment `pypi`, checks out source, installs pinned setup-uv directly, downloads the artifact, validates it with `tools.release`, then runs:

```bash
uv publish \
  --trusted-publishing always \
  --check-url https://pypi.org/simple/ \
  dist/*.whl dist/*.tar.gz
```

The uv `--check-url` behavior is the idempotency boundary: exact existing files are skipped, while mismatched immutable files fail. Grant `contents: read` and `id-token: write`.

- [ ] **Step 4: Create signed GitHub Release from changelog**

The final job needs successful PyPI publication. Checkout the tag, install uv, download artifacts, generate `release-notes.md`, sign wheel/sdist with pinned Sigstore, and call pinned `softprops/action-gh-release`:

```yaml
with:
  name: ${{ inputs.version }}
  tag_name: ${{ inputs.version }}
  body_path: release-notes.md
  draft: false
  prerelease: false
  files: |
    dist/*
```

Grant `contents: write` and `id-token: write`. Do not use the previous generic release body.

- [ ] **Step 5: Validate and commit**

```bash
rtk docker run --rm -v "$PWD:/repo" -w /repo \
  rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667
rtk git add .github/workflows/release.yaml .github/workflows/_publish.yaml
rtk git commit -m "ci: secure tag-only package publishing"
```

### Task 10: Harden docs, dependencies, and contributor documentation

**Files:**
- Modify: `.github/workflows/docs.yaml`
- Modify: `.github/dependabot.yml`
- Create: `docs/guide/contributing.md`
- Modify: `mkdocs.yml`

- [ ] **Step 1: Update docs deployment without changing Mike semantics**

Keep the `master` push and manual triggers and the `docs-deploy` concurrency group; remove the direct tag trigger. Change the manual `version` input to required with no default. Use `ubuntu-24.04`, timeout 15 minutes, pinned checkout and setup-uv, `uv sync --locked --all-extras --group docs`, and existing Mike commands. Keep `contents: write` only on the deploy job.

For a master push, check out `master` and deploy only `dev`. For a manual run,
check out `refs/tags/${{ inputs.version }}` and deploy that version plus `latest`.
The release workflow is the normal caller of this manual path after package and
GitHub Release success.

Do not retain `python -m pip install -U pip uv`, `setup-python`, or `|| true` around the `gh-pages` fetch. Instead, test branch existence explicitly:

```bash
if git ls-remote --exit-code --heads origin gh-pages; then
  git fetch origin gh-pages --depth=1
fi
```

- [ ] **Step 2: Make Dependabot PRs compatible with the fragment policy**

For the `github-actions` update block, add `skip-changelog` alongside `type:ci`. Keep Python dependency PRs as `type:dependency`; they must include a fragment unless a maintainer deliberately applies the exemption.

- [ ] **Step 3: Document contributor and release flows**

Create `docs/guide/contributing.md` with:

````markdown
# Contributing

Before opening a pull request, run:

```bash
make lint-ci
make test-ci
make docs-build
```

## Changelog fragments

User-visible changes need a file named `changes/<pr>.<type>.md`. Supported types
are `added`, `changed`, `breaking`, `fixed`, `deprecated`, `security`, and
`docs`. Before a pull request number exists, use an orphan filename such as
`changes/+retry-observer.added.md`.

Maintainers may apply `skip-changelog` only to internal changes that do not
affect users. Generated release pull requests carry the `release` label and are
exempt because they consume the fragments.

## Preparing a release

1. Run `Prepare release` with `dry_run=true` and inspect its patch artifact.
2. Run it again with `dry_run=false` to open `release/X.Y.Z`.
3. Review and merge the release pull request after `CI required` succeeds.
4. Create and push an annotated `X.Y.Z` tag matching `pyproject.toml`.
5. Watch package publication, GitHub Release creation, and versioned docs.

If publication partially fails, rerun only the failed GitHub jobs so the
retained verified artifact is reused. Never rebuild a published version locally:
PyPI files are immutable.
````

Add the page to the Guide section of `mkdocs.yml`.

- [ ] **Step 4: Verify and commit**

```bash
rtk make docs-build
rtk docker run --rm -v "$PWD:/repo" -w /repo \
  rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667
rtk git add .github/workflows/docs.yaml .github/dependabot.yml \
  docs/guide/contributing.md mkdocs.yml
rtk git commit -m "docs: document hardened contribution and release flow"
```

### Task 11: Codify repository rulesets

**Files:**
- Create: `.github/rulesets/master.json`
- Create: `.github/rulesets/release-tags.json`

- [ ] **Step 1: Add the default-branch ruleset payload**

Create `.github/rulesets/master.json`:

```json
{
  "name": "master",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [
    {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
  ],
  "conditions": {
    "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
  },
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {
      "type": "pull_request",
      "parameters": {
        "allowed_merge_methods": ["merge", "squash", "rebase"],
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_approving_review_count": 0,
        "required_review_thread_resolution": false
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "do_not_enforce_on_create": false,
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          {"context": "CI required", "integration_id": 15368}
        ]
      }
    }
  ]
}
```

- [ ] **Step 2: Add the immutable release-tag ruleset payload**

Create `.github/rulesets/release-tags.json`:

```json
{
  "name": "release-tags",
  "target": "tag",
  "enforcement": "active",
  "bypass_actors": [
    {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
  ],
  "conditions": {
    "ref_name": {
      "include": ["refs/tags/[0-9]*.[0-9]*.[0-9]*"],
      "exclude": []
    }
  },
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"}
  ]
}
```

- [ ] **Step 3: Validate JSON and commit without applying settings yet**

```bash
rtk jq empty .github/rulesets/master.json .github/rulesets/release-tags.json
rtk git add .github/rulesets
rtk git commit -m "ci: codify branch and release tag rulesets"
```

Do not call the GitHub ruleset API until the hardening PR has demonstrated the exact `CI required` context.

### Task 12: Run the full acceptance gate and open the hardening PR

**Files:**
- Modify only files required by failures discovered in this task

- [ ] **Step 1: Run all local gates from a clean dependency state**

```bash
rtk uv lock --check
rtk uv sync --locked --all-groups --all-extras
rtk make lint-ci
rtk make test-ci
rtk make docs-build
rtk make build-ci
rtk uv run towncrier check --compare-with master
rtk docker run --rm -v "$PWD:/repo" -w /repo \
  rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667
rtk git diff --check master...HEAD
```

Expected: every command exits zero, coverage is at least 90 percent, and package metadata reports the current project version.

- [ ] **Step 2: Run zizmor locally**

Use the official binary through uvx if the released Python package is available:

```bash
rtk uvx --from zizmor==1.28.0 zizmor --persona pedantic .github
```

If that package is not available for the local architecture, rely on the pinned zizmor Action in the PR and do not weaken or suppress findings pre-emptively.

- [ ] **Step 3: Create required labels**

```bash
rtk gh label create skip-changelog --color D4C5F9 \
  --description "No user-visible changelog entry required" --force
rtk gh label create release --color 0E8A16 \
  --description "Generated release preparation pull request" --force
```

- [ ] **Step 4: Push and open the PR**

```bash
rtk git status --short
rtk git push -u origin chore/actions-hardening
rtk gh pr create \
  --base master \
  --head chore/actions-hardening \
  --title "ci: harden Actions, releases, and changelog automation" \
  --body-file docs/superpowers/specs/2026-07-22-actions-hardening-design.md
```

Expected: GitHub starts `CI`, the PR fragment gate passes, and a status named exactly `CI required` appears.

- [ ] **Step 5: Inspect every hosted job**

```bash
rtk gh pr checks --watch --fail-fast
rtk gh run list --workflow ci.yaml --limit 1
```

Do not proceed to ruleset activation until all Python versions, minimum dependencies, strict docs, package smoke, actionlint, and zizmor are successful.

### Task 13: Merge, activate rulesets, and validate enforcement

**Files:**
- External GitHub repository settings only after merge

- [ ] **Step 1: Merge only after the hardening PR is green**

Use the repository's normal merge strategy. Confirm `master` contains the workflow commit and that the post-merge `CI required` run succeeds.

- [ ] **Step 2: Exercise release preparation in dry-run mode from master**

The workflow must exist on the default branch before GitHub accepts a manual dispatch:

First set repository workflow-token defaults to read-only while allowing the
explicitly privileged preparation workflow to create its release PR:

```bash
rtk gh api --method PUT \
  repos/andy-takker/asyncly/actions/permissions/workflow \
  -f default_workflow_permissions=read \
  -F can_approve_pull_request_reviews=true
```

Then dispatch the dry-run:

```bash
rtk gh workflow run prepare-release.yaml \
  --ref master \
  -f version=0.10.0 \
  -f dry_run=true
```

Watch the run, download `release-0.10.0-dry-run`, and inspect that the patch contains the dated changelog section, version/lock changes, comparison links, and fragment deletion, but no remote `release/0.10.0` branch.

- [ ] **Step 3: Update and enable the existing master ruleset**

The current ruleset ID is `1189247`. Apply the reviewed payload:

```bash
rtk gh api --method PUT \
  repos/andy-takker/asyncly/rulesets/1189247 \
  --input .github/rulesets/master.json
```

Read it back and assert `enforcement=active` and required context `CI required`:

```bash
rtk gh api repos/andy-takker/asyncly/rulesets/1189247 \
  --jq '{enforcement, checks: [.rules[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context]}'
```

- [ ] **Step 4: Create the release-tag ruleset**

```bash
rtk gh api --method POST \
  repos/andy-takker/asyncly/rulesets \
  --input .github/rulesets/release-tags.json
rtk gh api repos/andy-takker/asyncly/rulesets \
  --jq '.[] | select(.name == "release-tags") | {id, enforcement, target}'
```

Expected: an active tag-target ruleset is returned.

- [ ] **Step 5: Prove branch enforcement with a disposable validation PR**

Create a branch containing only a documentation typo fix and a `changes/+ruleset-validation.docs.md` fragment, push it, and open a PR. Before `CI required` completes, verify GitHub reports the PR as not mergeable. After it succeeds, verify the PR becomes mergeable. Close the PR without merging and delete the remote validation branch through the GitHub UI or `gh pr close --delete-branch`.

- [ ] **Step 6: Record the final evidence**

Capture these URLs in the implementation handoff:

```text
hardening pull request
successful CI run containing CI required
successful Prepare release dry-run
active master ruleset API/UI page
active release-tags ruleset API/UI page
```

Report that no synthetic tag or PyPI version was created. The first live test of tag publishing is the next real release.

## Final verification checklist

- [ ] `rtk git status --short` is empty on the implementation branch before push.
- [ ] `rtk uv lock --check` passes.
- [ ] `rtk make lint-ci`, `test-ci`, `docs-build`, and `build-ci` pass.
- [ ] Python 3.10-3.14 and minimum-direct CI lanes pass remotely.
- [ ] actionlint and zizmor pass without broad ignores.
- [ ] Towncrier requires a normal PR fragment and honors only maintainer labels.
- [ ] `Prepare release` dry-run writes no branch, tag, release, or package.
- [ ] Tag publishing has no `workflow_dispatch` entry point.
- [ ] Artifact provenance, trusted publishing, Sigstore, and release-body extraction use the same build artifact.
- [ ] `master` requires only the stable `CI required` status.
- [ ] Stable release tags cannot be updated or deleted without emergency bypass.
