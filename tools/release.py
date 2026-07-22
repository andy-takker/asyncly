import argparse
import hashlib
import json
import os
import re
import stat
import sys
from email.parser import Parser
from pathlib import Path, PurePosixPath
from tarfile import ReadError
from tarfile import open as open_tar
from tempfile import NamedTemporaryFile
from zipfile import BadZipFile, ZipFile, ZipInfo

import toml

_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
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


def _read_text(path: Path, description: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ReleaseError(f"unable to read {description} {path}: {exc}") from exc


def _write_text_atomic(path: Path, text: str, description: str) -> None:
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise ReleaseError(f"unable to write {description} {path}: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def project_version(path: Path) -> str:
    try:
        data = toml.load(path)
    except (OSError, toml.TomlDecodeError, UnicodeDecodeError) as exc:
        raise ReleaseError(f"unable to read pyproject {path}: {exc}") from exc
    project = data.get("project")
    if not isinstance(project, dict) or "version" not in project:
        raise ReleaseError("invalid pyproject version schema")
    return str(project["version"])


def lock_version(path: Path) -> str:
    try:
        data = toml.load(path)
    except (OSError, toml.TomlDecodeError, UnicodeDecodeError) as exc:
        raise ReleaseError(f"unable to read uv.lock {path}: {exc}") from exc
    packages = data.get("package")
    if not isinstance(packages, list) or not all(
        isinstance(item, dict) for item in packages
    ):
        raise ReleaseError("invalid uv.lock package schema")
    matches = [item for item in packages if item.get("name") == "asyncly"]
    if len(matches) != 1:
        raise ReleaseError("uv.lock must contain exactly one asyncly package")
    if "version" not in matches[0]:
        raise ReleaseError("invalid uv.lock package schema")
    return str(matches[0]["version"])


def update_comparison_links(text: str, *, previous: str, version: str) -> str:
    validate_next_version(version, previous)
    old = f"[Unreleased]: {_COMPARE_ROOT}/{previous}...HEAD"
    definitions = re.findall(r"^\[Unreleased\]:[^\r\n]*$", text, re.M)
    if len(definitions) != 1 or definitions[0] != old:
        raise ReleaseError(
            f"missing unique Unreleased link for {previous}; "
            "expected exactly one Unreleased definition"
        )
    release_link = f"[{version}]: {_COMPARE_ROOT}/{previous}...{version}"
    if re.search(rf"^\[{re.escape(version)}\]:[^\r\n]*$", text, re.M):
        raise ReleaseError(f"comparison link for {version} already exists")
    return text.replace(
        old,
        f"[Unreleased]: {_COMPARE_ROOT}/{version}...HEAD\n{release_link}",
        1,
    )


def extract_release_notes(text: str, version: str) -> str:
    stable_version(version)
    heading = re.compile(
        rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}\n", re.M
    )
    matches = list(heading.finditer(text))
    if not matches:
        raise ReleaseError(f"missing changelog section for {version}")
    if len(matches) != 1:
        raise ReleaseError(f"expected exactly one changelog section for {version}")
    match = matches[0]
    next_heading = re.search(r"^## \[", text[match.end() :], re.M)
    end = match.end() + next_heading.start() if next_heading else len(text)
    notes = text[match.end() : end].strip()
    if not notes:
        raise ReleaseError(f"empty changelog section for {version}")
    return notes + "\n"


def artifact_manifest(directory: Path, version: str) -> list[dict[str, str]]:
    stable_version(version)
    names = [f"asyncly-{version}-py3-none-any.whl", f"asyncly-{version}.tar.gz"]
    try:
        unexpected = sorted(
            path.name
            for path in directory.iterdir()
            if path.is_file()
            and path.name not in {*names, ".gitignore", "SHA256SUMS.json"}
        )
    except OSError as exc:
        raise ReleaseError(
            f"unable to inspect distribution directory {directory}: {exc}"
        ) from exc
    if unexpected:
        raise ReleaseError(f"unexpected distribution files: {unexpected}")
    result = []
    for name in names:
        path = directory / name
        if not path.is_file():
            raise ReleaseError(f"missing distribution: {name}")
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise ReleaseError(f"unable to hash distribution {path}: {exc}") from exc
        result.append({"filename": name, "sha256": digest})
    return result


def _validate_member_names(names: list[str], archive_name: str) -> None:
    if len(names) != len(set(names)):
        raise ReleaseError(f"{archive_name} must contain unique member names")
    for name in names:
        path = PurePosixPath(name)
        if (
            not name
            or path.is_absolute()
            or "\\" in name
            or "\0" in name
            or ".." in path.parts
        ):
            raise ReleaseError(f"{archive_name} contains unsafe member path: {name}")


def _zip_regular_file(info: ZipInfo) -> bool:
    if info.is_dir():
        return False
    file_type = stat.S_IFMT(info.external_attr >> 16)
    return file_type in {0, stat.S_IFREG}


def _validate_metadata(contents: bytes, version: str, archive_name: str) -> None:
    try:
        decoded = contents.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseError(f"{archive_name} metadata is not valid UTF-8") from exc
    metadata = Parser().parsestr(decoded)
    required_headers = ("Name", "Version", "Requires-Python")
    if metadata.defects or any(
        len(metadata.get_all(header, [])) != 1 for header in required_headers
    ):
        raise ReleaseError(f"{archive_name} metadata is malformed")
    if metadata["Name"] != "asyncly" or metadata["Version"] != version:
        raise ReleaseError(f"{archive_name} name/version metadata mismatch")
    if metadata["Requires-Python"] != "<4,>=3.10":
        raise ReleaseError(f"{archive_name} Requires-Python metadata mismatch")


def verify_wheel(directory: Path, version: str) -> None:
    stable_version(version)
    wheel = directory / f"asyncly-{version}-py3-none-any.whl"
    try:
        with ZipFile(wheel) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            _validate_member_names(names, "wheel")
            metadata_name = f"asyncly-{version}.dist-info/METADATA"
            if metadata_name not in names:
                raise ReleaseError("wheel must contain the exact METADATA path")
            required = {
                metadata_name,
                "asyncly/client/retry.py",
                "asyncly/srvmocker/responses/faults.py",
            }
            missing = sorted(required - set(names))
            if missing:
                raise ReleaseError(f"wheel missing public files: {missing}")
            by_name = {member.filename: member for member in members}
            special = sorted(
                name for name in required if not _zip_regular_file(by_name[name])
            )
            if special:
                raise ReleaseError(
                    f"wheel required members must be regular files: {special}"
                )
            _validate_metadata(archive.read(metadata_name), version, "wheel")
    except (BadZipFile, OSError) as exc:
        raise ReleaseError(f"unable to read wheel {wheel}: {exc}") from exc


def verify_sdist(directory: Path, version: str) -> None:
    stable_version(version)
    sdist = directory / f"asyncly-{version}.tar.gz"
    prefix = f"asyncly-{version}/"
    required = {
        prefix + "PKG-INFO",
        prefix + "pyproject.toml",
        prefix + "asyncly/client/retry.py",
        prefix + "asyncly/srvmocker/responses/faults.py",
    }
    try:
        with open_tar(sdist, "r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            _validate_member_names(names, "sdist")
            missing = sorted(required - set(names))
            if missing:
                raise ReleaseError(f"sdist missing public files: {missing}")
            by_name = {member.name: member for member in members}
            special = sorted(name for name in required if not by_name[name].isreg())
            if special:
                raise ReleaseError(
                    f"sdist required members must be regular files: {special}"
                )
            metadata_file = archive.extractfile(by_name[prefix + "PKG-INFO"])
            if metadata_file is None:
                raise ReleaseError("sdist PKG-INFO could not be read")
            _validate_metadata(metadata_file.read(), version, "sdist")
    except (OSError, ReadError) as exc:
        raise ReleaseError(f"unable to read sdist {sdist}: {exc}") from exc


def _validate_artifact_output(directory: Path, output: Path) -> None:
    try:
        expected = (directory / "SHA256SUMS.json").resolve()
        actual = output.resolve()
    except OSError as exc:
        raise ReleaseError(f"unable to resolve artifact output: {exc}") from exc
    if actual != expected:
        raise ReleaseError(f"artifact output must be {expected}")


def validate_release(
    version: str,
    pyproject: Path,
    lockfile: Path,
    changelog: Path,
) -> None:
    stable_version(version)
    if project_version(pyproject) != version:
        raise ReleaseError("tag does not match pyproject version")
    if lock_version(lockfile) != version:
        raise ReleaseError("tag does not match uv.lock version")
    extract_release_notes(_read_text(changelog, "changelog"), version)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_next = subparsers.add_parser("validate-next")
    validate_next.add_argument("--version", required=True)
    validate_next.add_argument("--pyproject", required=True, type=Path)

    update_links = subparsers.add_parser("update-links")
    update_links.add_argument("--version", required=True)
    update_links.add_argument("--previous", required=True)
    update_links.add_argument("--changelog", required=True, type=Path)

    validate = subparsers.add_parser("validate-release")
    validate.add_argument("--version", required=True)
    validate.add_argument("--pyproject", required=True, type=Path)
    validate.add_argument("--lockfile", required=True, type=Path)
    validate.add_argument("--changelog", required=True, type=Path)

    notes = subparsers.add_parser("notes")
    notes.add_argument("--version", required=True)
    notes.add_argument("--changelog", required=True, type=Path)
    notes.add_argument("--output", required=True, type=Path)

    artifacts = subparsers.add_parser("artifacts")
    artifacts.add_argument("--version", required=True)
    artifacts.add_argument("--directory", required=True, type=Path)
    artifacts.add_argument("--output", required=True, type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-next":
            validate_next_version(args.version, project_version(args.pyproject))
        elif args.command == "update-links":
            text = _read_text(args.changelog, "changelog")
            updated = update_comparison_links(
                text,
                previous=args.previous,
                version=args.version,
            )
            _write_text_atomic(args.changelog, updated, "changelog")
        elif args.command == "validate-release":
            validate_release(
                args.version,
                args.pyproject,
                args.lockfile,
                args.changelog,
            )
        elif args.command == "notes":
            notes = extract_release_notes(
                _read_text(args.changelog, "changelog"), args.version
            )
            _write_text_atomic(args.output, notes, "release notes")
        elif args.command == "artifacts":
            _validate_artifact_output(args.directory, args.output)
            verify_wheel(args.directory, args.version)
            verify_sdist(args.directory, args.version)
            manifest = artifact_manifest(args.directory, args.version)
            _write_text_atomic(
                args.output,
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                "artifact manifest",
            )
    except ReleaseError as exc:
        sys.stderr.write(f"release validation failed: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
