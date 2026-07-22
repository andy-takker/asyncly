import hashlib
import io
import json
import stat
from pathlib import Path
from tarfile import REGTYPE, SYMTYPE, TarFile, TarInfo
from tarfile import open as open_tar
from zipfile import ZipFile, ZipInfo

import pytest

from tools.release import (
    ReleaseError,
    artifact_manifest,
    extract_release_notes,
    lock_version,
    main,
    project_version,
    stable_version,
    update_comparison_links,
    validate_next_version,
    verify_sdist,
    verify_wheel,
)

_PUBLIC_FILES = (
    "asyncly/client/retry.py",
    "asyncly/srvmocker/responses/faults.py",
)


def _metadata(version: str = "0.10.0", *, name: str = "asyncly") -> bytes:
    return (
        "Metadata-Version: 2.4\n"
        f"Name: {name}\n"
        f"Version: {version}\n"
        "Requires-Python: <4,>=3.10\n\n"
    ).encode()


def _pyproject(
    version: str = "0.10.0",
    *,
    name: str = "asyncly",
    requires_python: str = "<4,>=3.10",
) -> bytes:
    return (
        "[project]\n"
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        f'requires-python = "{requires_python}"\n'
    ).encode()


def _write_wheel(
    path: Path,
    *,
    version: str = "0.10.0",
    metadata: bytes | None = None,
    metadata_path: str | None = None,
    missing: str | None = None,
    extra: str | None = None,
    duplicate: str | None = None,
    special: str | None = None,
    extra_special: str | None = None,
) -> None:
    members = (
        metadata_path or f"asyncly-{version}.dist-info/METADATA",
        *_PUBLIC_FILES,
    )
    with ZipFile(path, "w") as archive:
        for member in members:
            if member == missing:
                continue
            contents = metadata if member.endswith("/METADATA") else b"contents"
            if contents is None:
                contents = _metadata(version)
            if member == special:
                info = ZipInfo(member)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, b"target")
            else:
                archive.writestr(member, contents)
        if extra is not None:
            archive.writestr(extra, b"extra")
        if duplicate is not None:
            archive.writestr(duplicate, b"duplicate")
        if extra_special is not None:
            info = ZipInfo(extra_special)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b"target")


def _add_tar_member(
    archive: TarFile,
    name: str,
    contents: bytes,
    *,
    special: bool = False,
) -> None:
    info = TarInfo(name)
    if special:
        info.type = SYMTYPE
        info.linkname = "target"
    else:
        info.type = REGTYPE
        info.size = len(contents)
    archive.addfile(info, io.BytesIO(contents))


def _write_sdist(
    path: Path,
    *,
    version: str = "0.10.0",
    metadata: bytes | None = None,
    pyproject: bytes | None = None,
    missing: str | None = None,
    extra: str | None = None,
    duplicate: str | None = None,
    special: str | None = None,
    extra_special: str | None = None,
) -> None:
    prefix = f"asyncly-{version}/"
    members = {
        prefix + "PKG-INFO": metadata or _metadata(version),
        prefix + "pyproject.toml": pyproject or _pyproject(version),
        prefix + _PUBLIC_FILES[0]: b"contents",
        prefix + _PUBLIC_FILES[1]: b"contents",
    }
    with open_tar(path, "w:gz") as archive:
        for name, contents in members.items():
            if name != missing:
                _add_tar_member(
                    archive,
                    name,
                    contents,
                    special=name == special,
                )
        if extra is not None:
            _add_tar_member(archive, extra, b"extra")
        if duplicate is not None:
            _add_tar_member(archive, duplicate, b"duplicate")
        if extra_special is not None:
            _add_tar_member(archive, extra_special, b"target", special=True)


def test_stable_version_accepts_semver() -> None:
    assert stable_version("1.20.3") == (1, 20, 3)


@pytest.mark.parametrize(
    "value",
    [
        "1.2",
        "v1.2.3",
        "1.2.3rc1",
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "1.2٢.3",
    ],
)
def test_stable_version_rejects_non_release_values(value: str) -> None:
    with pytest.raises(ReleaseError, match="stable X.Y.Z"):
        stable_version(value)


def test_validate_next_version_requires_increase() -> None:
    validate_next_version("0.10.0", "0.9.0")
    with pytest.raises(ReleaseError, match="greater than 0.9.0"):
        validate_next_version("0.9.0", "0.9.0")


def test_validate_next_version_rejects_downgrade() -> None:
    with pytest.raises(ReleaseError, match="greater than 0.9.0"):
        validate_next_version("0.8.9", "0.9.0")


def test_update_comparison_links() -> None:
    source = """[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.9.0...HEAD
[0.9.0]: https://github.com/andy-takker/asyncly/compare/0.8.0...0.9.0
"""
    expected = """[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.10.0...HEAD
[0.10.0]: https://github.com/andy-takker/asyncly/compare/0.9.0...0.10.0
[0.9.0]: https://github.com/andy-takker/asyncly/compare/0.8.0...0.9.0
"""
    assert (
        update_comparison_links(source, previous="0.9.0", version="0.10.0") == expected
    )


def test_update_comparison_links_rewrites_only_anchored_definition() -> None:
    old = "https://github.com/andy-takker/asyncly/compare/0.9.0...HEAD"
    new = "https://github.com/andy-takker/asyncly/compare/0.10.0...HEAD"
    release = "https://github.com/andy-takker/asyncly/compare/0.9.0...0.10.0"
    source = f"Prose quotes [Unreleased]: {old} here.\n\n[Unreleased]: {old}\n"
    expected = (
        f"Prose quotes [Unreleased]: {old} here.\n\n"
        f"[Unreleased]: {new}\n[0.10.0]: {release}\n"
    )

    assert (
        update_comparison_links(source, previous="0.9.0", version="0.10.0") == expected
    )


def test_update_comparison_links_requires_unique_unreleased_link() -> None:
    source = """[0.9.0]: https://github.com/andy-takker/asyncly/compare/0.8.0...0.9.0
"""
    with pytest.raises(ReleaseError, match="missing unique Unreleased link for 0.9.0"):
        update_comparison_links(source, previous="0.9.0", version="0.10.0")


def test_update_comparison_links_rejects_duplicate_unreleased_link() -> None:
    source = """[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.9.0...HEAD
[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.9.0...HEAD
"""
    with pytest.raises(ReleaseError, match="missing unique Unreleased link for 0.9.0"):
        update_comparison_links(source, previous="0.9.0", version="0.10.0")


def test_update_comparison_links_rejects_mixed_unreleased_definitions() -> None:
    source = """[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.9.0...HEAD
[Unreleased]: https://example.com/conflicting
"""
    with pytest.raises(ReleaseError, match="exactly one Unreleased definition"):
        update_comparison_links(source, previous="0.9.0", version="0.10.0")


@pytest.mark.parametrize(
    ("previous", "version"),
    [("0.9.0", "0.9.0"), ("0.9.0", "invalid"), ("invalid", "0.10.0")],
)
def test_update_comparison_links_requires_increasing_stable_versions(
    previous: str,
    version: str,
) -> None:
    source = (
        "[Unreleased]: "
        f"https://github.com/andy-takker/asyncly/compare/{previous}...HEAD\n"
    )

    with pytest.raises(ReleaseError):
        update_comparison_links(source, previous=previous, version=version)


def test_update_comparison_links_rejects_existing_version_link() -> None:
    source = """[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.9.0...HEAD
[0.10.0]: https://github.com/andy-takker/asyncly/compare/0.9.0...0.10.0
"""
    with pytest.raises(ReleaseError, match="comparison link for 0.10.0 already exists"):
        update_comparison_links(source, previous="0.9.0", version="0.10.0")


def test_project_version(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "asyncly"\nversion = "0.10.0"\n')
    assert project_version(pyproject) == "0.10.0"


def test_project_version_rejects_invalid_schema(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('name = "asyncly"\n', encoding="utf-8")

    with pytest.raises(ReleaseError, match="invalid pyproject version schema"):
        project_version(pyproject)


def test_lock_version(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_text('version = 1\n[[package]]\nname = "asyncly"\nversion = "0.10.0"\n')
    assert lock_version(lock) == "0.10.0"


def test_lock_version_rejects_missing_asyncly_package(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_text(
        'version = 1\n[[package]]\nname = "dependency"\nversion = "1.0.0"\n'
    )
    with pytest.raises(ReleaseError, match="exactly one asyncly package"):
        lock_version(lock)


def test_lock_version_rejects_duplicate_asyncly_packages(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_text(
        'version = 1\n[[package]]\nname = "asyncly"\nversion = "0.10.0"\n'
        '[[package]]\nname = "asyncly"\nversion = "0.10.0"\n'
    )
    with pytest.raises(ReleaseError, match="exactly one asyncly package"):
        lock_version(lock)


def test_lock_version_rejects_invalid_schema(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_text('version = 1\npackage = "invalid"\n', encoding="utf-8")

    with pytest.raises(ReleaseError, match="invalid uv.lock package schema"):
        lock_version(lock)


def test_extract_release_notes() -> None:
    changelog = """## [Unreleased]

<!-- towncrier release notes start -->

## [0.10.0] - 2026-08-01

### Added
- Retry budgets.

## [0.9.0] - 2026-07-22
"""
    expected = """### Added
- Retry budgets.
"""
    assert extract_release_notes(changelog, "0.10.0") == expected


def test_extract_release_notes_rejects_missing_version_section() -> None:
    changelog = """## [Unreleased]

## [0.9.0] - 2026-07-22
"""
    with pytest.raises(ReleaseError, match="missing changelog section for 0.10.0"):
        extract_release_notes(changelog, "0.10.0")


def test_extract_release_notes_rejects_empty_version_section() -> None:
    changelog = """## [0.10.0] - 2026-08-01

## [0.9.0] - 2026-07-22
"""
    with pytest.raises(ReleaseError, match="empty changelog section for 0.10.0"):
        extract_release_notes(changelog, "0.10.0")


def test_extract_release_notes_rejects_duplicate_version_sections() -> None:
    changelog = """## [0.10.0] - 2026-08-01

First.

## [0.10.0] - 2026-08-02

Second.
"""
    with pytest.raises(ReleaseError, match="exactly one changelog section"):
        extract_release_notes(changelog, "0.10.0")


def test_artifact_manifest_hashes_exact_pair(tmp_path: Path) -> None:
    wheel = tmp_path / "asyncly-0.10.0-py3-none-any.whl"
    sdist = tmp_path / "asyncly-0.10.0.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    manifest = artifact_manifest(tmp_path, "0.10.0")
    assert [item["filename"] for item in manifest] == [wheel.name, sdist.name]
    assert [item["sha256"] for item in manifest] == [
        hashlib.sha256(b"wheel").hexdigest(),
        hashlib.sha256(b"sdist").hexdigest(),
    ]
    assert all(len(item["sha256"]) == 64 for item in manifest)


def test_artifact_manifest_rejects_missing_wheel(tmp_path: Path) -> None:
    (tmp_path / "asyncly-0.10.0.tar.gz").write_bytes(b"sdist")
    with pytest.raises(
        ReleaseError,
        match=r"missing distribution: asyncly-0\.10\.0-py3-none-any\.whl",
    ):
        artifact_manifest(tmp_path, "0.10.0")


def test_artifact_manifest_rejects_missing_sdist(tmp_path: Path) -> None:
    (tmp_path / "asyncly-0.10.0-py3-none-any.whl").write_bytes(b"wheel")
    with pytest.raises(
        ReleaseError, match=r"missing distribution: asyncly-0\.10\.0\.tar\.gz"
    ):
        artifact_manifest(tmp_path, "0.10.0")


def test_artifact_manifest_rejects_unexpected_file(tmp_path: Path) -> None:
    (tmp_path / "asyncly-0.10.0-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / "asyncly-0.10.0.tar.gz").write_bytes(b"sdist")
    (tmp_path / "unexpected.txt").write_text("unexpected")
    with pytest.raises(ReleaseError, match="unexpected distribution entries"):
        artifact_manifest(tmp_path, "0.10.0")


def test_artifact_manifest_rejects_unexpected_directory(tmp_path: Path) -> None:
    (tmp_path / "asyncly-0.10.0-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / "asyncly-0.10.0.tar.gz").write_bytes(b"sdist")
    (tmp_path / "unexpected").mkdir()

    with pytest.raises(ReleaseError, match="unexpected distribution entries"):
        artifact_manifest(tmp_path, "0.10.0")


def test_artifact_manifest_rejects_artifact_symlink(tmp_path: Path) -> None:
    target = tmp_path.parent / f"{tmp_path.name}-wheel-target"
    target.write_bytes(b"wheel")
    wheel = tmp_path / "asyncly-0.10.0-py3-none-any.whl"
    wheel.symlink_to(target)
    (tmp_path / "asyncly-0.10.0.tar.gz").write_bytes(b"sdist")

    with pytest.raises(ReleaseError, match="non-symlink regular file"):
        artifact_manifest(tmp_path, "0.10.0")


def test_artifact_manifest_allows_gitignore(tmp_path: Path) -> None:
    (tmp_path / "asyncly-0.10.0-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / "asyncly-0.10.0.tar.gz").write_bytes(b"sdist")
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")

    assert len(artifact_manifest(tmp_path, "0.10.0")) == 2


def test_manifest_is_json_serializable(tmp_path: Path) -> None:
    (tmp_path / "asyncly-0.10.0-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / "asyncly-0.10.0.tar.gz").write_bytes(b"sdist")
    json.dumps(artifact_manifest(tmp_path, "0.10.0"))


def test_verify_wheel_accepts_valid_archive(tmp_path: Path) -> None:
    _write_wheel(tmp_path / "asyncly-0.10.0-py3-none-any.whl")

    verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_requires_exact_metadata_path(tmp_path: Path) -> None:
    _write_wheel(
        tmp_path / "asyncly-0.10.0-py3-none-any.whl",
        metadata_path="wrong-0.10.0.dist-info/METADATA",
    )

    with pytest.raises(ReleaseError, match="exact METADATA"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_rejects_additional_metadata_file(tmp_path: Path) -> None:
    _write_wheel(
        tmp_path / "asyncly-0.10.0-py3-none-any.whl",
        extra="other-1.0.0.dist-info/METADATA",
    )

    with pytest.raises(ReleaseError, match="only METADATA"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_rejects_metadata_mismatch(tmp_path: Path) -> None:
    _write_wheel(
        tmp_path / "asyncly-0.10.0-py3-none-any.whl",
        metadata=_metadata(name="other"),
    )

    with pytest.raises(ReleaseError, match="name/version metadata mismatch"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_rejects_requires_python_mismatch(tmp_path: Path) -> None:
    metadata = _metadata().replace(b"<4,>=3.10", b">=3.10,<4")
    _write_wheel(
        tmp_path / "asyncly-0.10.0-py3-none-any.whl",
        metadata=metadata,
    )

    with pytest.raises(ReleaseError, match="Requires-Python metadata mismatch"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_rejects_missing_public_file(tmp_path: Path) -> None:
    _write_wheel(
        tmp_path / "asyncly-0.10.0-py3-none-any.whl",
        missing=_PUBLIC_FILES[0],
    )

    with pytest.raises(ReleaseError, match="wheel missing public files"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_rejects_duplicate_member(tmp_path: Path) -> None:
    with pytest.warns(UserWarning, match="Duplicate name"):
        _write_wheel(
            tmp_path / "asyncly-0.10.0-py3-none-any.whl",
            duplicate=_PUBLIC_FILES[0],
        )

    with pytest.raises(ReleaseError, match="unique member names"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_rejects_unsafe_member(tmp_path: Path) -> None:
    _write_wheel(
        tmp_path / "asyncly-0.10.0-py3-none-any.whl",
        extra="../escape",
    )

    with pytest.raises(ReleaseError, match="unsafe member path"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_rejects_special_public_member(tmp_path: Path) -> None:
    _write_wheel(
        tmp_path / "asyncly-0.10.0-py3-none-any.whl",
        special=_PUBLIC_FILES[0],
    )

    with pytest.raises(ReleaseError, match="regular file"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_rejects_extra_special_member(tmp_path: Path) -> None:
    _write_wheel(
        tmp_path / "asyncly-0.10.0-py3-none-any.whl",
        extra_special="asyncly/extra.py",
    )

    with pytest.raises(ReleaseError, match="regular files or directories"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_rejects_corrupt_non_metadata_payload(tmp_path: Path) -> None:
    wheel = tmp_path / "asyncly-0.10.0-py3-none-any.whl"
    _write_wheel(wheel)
    contents = bytearray(wheel.read_bytes())
    payload_offset = contents.index(b"contents")
    contents[payload_offset] ^= 1
    wheel.write_bytes(contents)

    with pytest.raises(ReleaseError, match="corrupt wheel payload"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_rejects_non_utf8_metadata(tmp_path: Path) -> None:
    _write_wheel(
        tmp_path / "asyncly-0.10.0-py3-none-any.whl",
        metadata=b"\xff",
    )

    with pytest.raises(ReleaseError, match="metadata is not valid UTF-8"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_rejects_malformed_metadata(tmp_path: Path) -> None:
    _write_wheel(
        tmp_path / "asyncly-0.10.0-py3-none-any.whl",
        metadata=_metadata().replace(b"\n\n", b"\nName: duplicate\n\n"),
    )

    with pytest.raises(ReleaseError, match="metadata is malformed"):
        verify_wheel(tmp_path, "0.10.0")


def test_verify_wheel_validates_version_before_archive_access(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match="stable X.Y.Z"):
        verify_wheel(tmp_path, "invalid")


def test_verify_sdist_accepts_valid_archive(tmp_path: Path) -> None:
    _write_sdist(tmp_path / "asyncly-0.10.0.tar.gz")

    verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_rejects_metadata_mismatch(tmp_path: Path) -> None:
    _write_sdist(
        tmp_path / "asyncly-0.10.0.tar.gz",
        metadata=_metadata("0.9.0"),
    )

    with pytest.raises(ReleaseError, match="name/version metadata mismatch"):
        verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_rejects_requires_python_mismatch(tmp_path: Path) -> None:
    metadata = _metadata().replace(b"<4,>=3.10", b">=3.10,<4")
    _write_sdist(
        tmp_path / "asyncly-0.10.0.tar.gz",
        metadata=metadata,
    )

    with pytest.raises(ReleaseError, match="Requires-Python metadata mismatch"):
        verify_sdist(tmp_path, "0.10.0")


@pytest.mark.parametrize(
    "pyproject",
    [
        _pyproject("0.9.0"),
        _pyproject(name="other"),
        _pyproject(requires_python=">=3.11,<4"),
    ],
)
def test_verify_sdist_rejects_embedded_pyproject_mismatch(
    tmp_path: Path,
    pyproject: bytes,
) -> None:
    _write_sdist(
        tmp_path / "asyncly-0.10.0.tar.gz",
        pyproject=pyproject,
    )

    with pytest.raises(ReleaseError, match="embedded pyproject metadata mismatch"):
        verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_accepts_source_pyproject_constraint_spelling(
    tmp_path: Path,
) -> None:
    _write_sdist(
        tmp_path / "asyncly-0.10.0.tar.gz",
        pyproject=_pyproject(requires_python=">=3.10, <4"),
    )

    verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_rejects_malformed_embedded_pyproject(tmp_path: Path) -> None:
    _write_sdist(
        tmp_path / "asyncly-0.10.0.tar.gz",
        pyproject=b"[project\n",
    )

    with pytest.raises(ReleaseError, match="embedded pyproject is invalid"):
        verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_rejects_missing_public_file(tmp_path: Path) -> None:
    _write_sdist(
        tmp_path / "asyncly-0.10.0.tar.gz",
        missing="asyncly-0.10.0/asyncly/client/retry.py",
    )

    with pytest.raises(ReleaseError, match="sdist missing public files"):
        verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_rejects_duplicate_member(tmp_path: Path) -> None:
    _write_sdist(
        tmp_path / "asyncly-0.10.0.tar.gz",
        duplicate="asyncly-0.10.0/pyproject.toml",
    )

    with pytest.raises(ReleaseError, match="unique member names"):
        verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_rejects_unsafe_member(tmp_path: Path) -> None:
    _write_sdist(
        tmp_path / "asyncly-0.10.0.tar.gz",
        extra="../escape",
    )

    with pytest.raises(ReleaseError, match="unsafe member path"):
        verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_rejects_special_required_member(tmp_path: Path) -> None:
    _write_sdist(
        tmp_path / "asyncly-0.10.0.tar.gz",
        special="asyncly-0.10.0/asyncly/client/retry.py",
    )

    with pytest.raises(ReleaseError, match="regular file"):
        verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_rejects_extra_special_member(tmp_path: Path) -> None:
    _write_sdist(
        tmp_path / "asyncly-0.10.0.tar.gz",
        extra_special="asyncly-0.10.0/extra.py",
    )

    with pytest.raises(ReleaseError, match="regular files or directories"):
        verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_rejects_out_of_prefix_member(tmp_path: Path) -> None:
    _write_sdist(
        tmp_path / "asyncly-0.10.0.tar.gz",
        extra="other-project/escape.py",
    )

    with pytest.raises(ReleaseError, match="outside asyncly-0.10.0/"):
        verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_rejects_truncated_gzip_footer(tmp_path: Path) -> None:
    sdist = tmp_path / "asyncly-0.10.0.tar.gz"
    _write_sdist(sdist)
    sdist.write_bytes(sdist.read_bytes()[:-4])

    with pytest.raises(ReleaseError):
        verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_rejects_deeply_truncated_gzip(tmp_path: Path) -> None:
    sdist = tmp_path / "asyncly-0.10.0.tar.gz"
    _write_sdist(sdist)
    sdist.write_bytes(sdist.read_bytes()[:-32])

    with pytest.raises(ReleaseError):
        verify_sdist(tmp_path, "0.10.0")


def test_verify_sdist_validates_version_before_archive_access(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match="stable X.Y.Z"):
        verify_sdist(tmp_path, "invalid")


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


def test_main_update_links_preserves_existing_mode(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.9.0...HEAD\n",
        encoding="utf-8",
    )
    changelog.chmod(0o644)

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
    assert stat.S_IMODE(changelog.stat().st_mode) == 0o644


def test_main_validates_next_version(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.9.0"\n', encoding="utf-8")

    result = main(
        [
            "validate-next",
            "--version",
            "0.10.0",
            "--pyproject",
            str(pyproject),
        ]
    )

    assert result == 0


def test_main_validates_release(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.10.0"\n', encoding="utf-8")
    lockfile = tmp_path / "uv.lock"
    lockfile.write_text(
        'version = 1\n[[package]]\nname = "asyncly"\nversion = "0.10.0"\n',
        encoding="utf-8",
    )
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "## [0.10.0] - 2026-08-01\n\n### Added\n- Item.\n",
        encoding="utf-8",
    )

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

    assert result == 0


def test_main_writes_release_notes(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "## [0.10.0] - 2026-08-01\n\n### Added\n- Item.\n",
        encoding="utf-8",
    )
    output = tmp_path / "release-notes.md"

    result = main(
        [
            "notes",
            "--version",
            "0.10.0",
            "--changelog",
            str(changelog),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert output.read_text(encoding="utf-8") == "### Added\n- Item.\n"


def test_main_validates_artifacts_and_writes_manifest(tmp_path: Path) -> None:
    _write_wheel(tmp_path / "asyncly-0.10.0-py3-none-any.whl")
    _write_sdist(tmp_path / "asyncly-0.10.0.tar.gz")
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")
    output = tmp_path / "SHA256SUMS.json"

    result = main(
        [
            "artifacts",
            "--version",
            "0.10.0",
            "--directory",
            str(tmp_path),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert json.loads(output.read_text(encoding="utf-8")) == artifact_manifest(
        tmp_path, "0.10.0"
    )


def test_main_update_links_does_not_mutate_on_validation_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    original = "[Unreleased]: https://example.com/conflicting\n"
    changelog.write_text(original, encoding="utf-8")

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

    assert result == 1
    assert changelog.read_text(encoding="utf-8") == original
    assert capsys.readouterr().err.startswith("release validation failed:")


def test_main_notes_cleans_up_after_atomic_replace_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "## [0.10.0] - 2026-08-01\n\n### Added\n- Item.\n",
        encoding="utf-8",
    )
    output = tmp_path / "release-notes.md"

    def fail_replace(source: object, destination: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("os.replace", fail_replace)

    result = main(
        [
            "notes",
            "--version",
            "0.10.0",
            "--changelog",
            str(changelog),
            "--output",
            str(output),
        ]
    )

    assert result == 1
    assert not output.exists()
    assert [path.name for path in tmp_path.iterdir()] == ["CHANGELOG.md"]
    assert capsys.readouterr().err.startswith("release validation failed:")


def test_main_notes_rejects_output_symlink_without_mutating_target(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "## [0.10.0] - 2026-08-01\n\n### Added\n- Item.\n",
        encoding="utf-8",
    )
    target = tmp_path / "target.md"
    target.write_text("keep\n", encoding="utf-8")
    output = tmp_path / "release-notes.md"
    output.symlink_to(target)

    result = main(
        [
            "notes",
            "--version",
            "0.10.0",
            "--changelog",
            str(changelog),
            "--output",
            str(output),
        ]
    )

    assert result == 1
    assert output.is_symlink()
    assert target.read_text(encoding="utf-8") == "keep\n"
    assert capsys.readouterr().err.startswith("release validation failed:")


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


def test_main_artifacts_does_not_overwrite_distribution_alias(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wheel = tmp_path / "asyncly-0.10.0-py3-none-any.whl"
    _write_wheel(wheel)
    _write_sdist(tmp_path / "asyncly-0.10.0.tar.gz")
    original = wheel.read_bytes()

    result = main(
        [
            "artifacts",
            "--version",
            "0.10.0",
            "--directory",
            str(tmp_path),
            "--output",
            str(wheel),
        ]
    )

    assert result == 1
    assert wheel.read_bytes() == original
    assert capsys.readouterr().err.startswith("release validation failed:")


def test_main_artifacts_rejects_manifest_symlink_without_mutating_target(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_wheel(tmp_path / "asyncly-0.10.0-py3-none-any.whl")
    _write_sdist(tmp_path / "asyncly-0.10.0.tar.gz")
    target = tmp_path.parent / f"{tmp_path.name}-manifest-target"
    target.write_text("keep\n", encoding="utf-8")
    output = tmp_path / "SHA256SUMS.json"
    output.symlink_to(target)

    result = main(
        [
            "artifacts",
            "--version",
            "0.10.0",
            "--directory",
            str(tmp_path),
            "--output",
            str(output),
        ]
    )

    assert result == 1
    assert output.is_symlink()
    assert target.read_text(encoding="utf-8") == "keep\n"
    assert capsys.readouterr().err.startswith("release validation failed:")


def test_main_artifacts_reports_output_resolution_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_resolve(path: Path) -> Path:
        raise OSError("resolution failed")

    monkeypatch.setattr(Path, "resolve", fail_resolve)

    result = main(
        [
            "artifacts",
            "--version",
            "0.10.0",
            "--directory",
            str(tmp_path),
            "--output",
            str(tmp_path / "SHA256SUMS.json"),
        ]
    )

    assert result == 1
    assert capsys.readouterr().err.startswith("release validation failed:")


def test_main_validate_release_reports_missing_pyproject(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        [
            "validate-release",
            "--version",
            "0.10.0",
            "--pyproject",
            str(tmp_path / "missing.toml"),
            "--lockfile",
            str(tmp_path / "uv.lock"),
            "--changelog",
            str(tmp_path / "CHANGELOG.md"),
        ]
    )

    assert result == 1
    assert capsys.readouterr().err.startswith("release validation failed:")


def test_main_validate_release_reports_malformed_pyproject(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project\n", encoding="utf-8")

    result = main(
        [
            "validate-release",
            "--version",
            "0.10.0",
            "--pyproject",
            str(pyproject),
            "--lockfile",
            str(tmp_path / "uv.lock"),
            "--changelog",
            str(tmp_path / "CHANGELOG.md"),
        ]
    )

    assert result == 1
    assert capsys.readouterr().err.startswith("release validation failed:")


def test_main_notes_reports_missing_changelog(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        [
            "notes",
            "--version",
            "0.10.0",
            "--changelog",
            str(tmp_path / "missing.md"),
            "--output",
            str(tmp_path / "notes.md"),
        ]
    )

    assert result == 1
    assert capsys.readouterr().err.startswith("release validation failed:")


def test_main_artifacts_reports_corrupt_wheel(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "asyncly-0.10.0-py3-none-any.whl").write_bytes(b"corrupt")
    _write_sdist(tmp_path / "asyncly-0.10.0.tar.gz")

    result = main(
        [
            "artifacts",
            "--version",
            "0.10.0",
            "--directory",
            str(tmp_path),
            "--output",
            str(tmp_path / "SHA256SUMS.json"),
        ]
    )

    assert result == 1
    assert capsys.readouterr().err.startswith("release validation failed:")


def test_main_artifacts_reports_corrupt_sdist(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_wheel(tmp_path / "asyncly-0.10.0-py3-none-any.whl")
    (tmp_path / "asyncly-0.10.0.tar.gz").write_bytes(b"corrupt")

    result = main(
        [
            "artifacts",
            "--version",
            "0.10.0",
            "--directory",
            str(tmp_path),
            "--output",
            str(tmp_path / "SHA256SUMS.json"),
        ]
    )

    assert result == 1
    assert capsys.readouterr().err.startswith("release validation failed:")
