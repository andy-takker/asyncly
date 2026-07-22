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
