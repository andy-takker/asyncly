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
    heading = re.compile(
        rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}\n", re.M
    )
    match = heading.search(text)
    if match is None:
        raise ReleaseError(f"missing changelog section for {version}")
    next_heading = re.search(r"^## \[", text[match.end() :], re.M)
    end = match.end() + next_heading.start() if next_heading else len(text)
    notes = text[match.end() : end].strip()
    if not notes:
        raise ReleaseError(f"empty changelog section for {version}")
    return notes + "\n"


def artifact_manifest(directory: Path, version: str) -> list[dict[str, str]]:
    stable_version(version)
    names = [f"asyncly-{version}-py3-none-any.whl", f"asyncly-{version}.tar.gz"]
    unexpected = sorted(
        path.name
        for path in directory.iterdir()
        if path.is_file() and path.name not in {*names, "SHA256SUMS.json"}
    )
    if unexpected:
        raise ReleaseError(f"unexpected distribution files: {unexpected}")
    result = []
    for name in names:
        path = directory / name
        if not path.is_file():
            raise ReleaseError(f"missing distribution: {name}")
        result.append(
            {
                "filename": name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return result


def verify_wheel(directory: Path, version: str) -> None:
    wheel = directory / f"asyncly-{version}-py3-none-any.whl"
    with ZipFile(wheel) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ReleaseError("wheel must contain exactly one METADATA file")
        metadata = Parser().parsestr(archive.read(metadata_names[0]).decode())
        if metadata["Name"] != "asyncly" or metadata["Version"] != version:
            raise ReleaseError("wheel name/version metadata mismatch")
        if metadata["Requires-Python"] != "<4,>=3.10":
            raise ReleaseError("wheel Requires-Python metadata mismatch")
        required = {
            "asyncly/client/retry.py",
            "asyncly/srvmocker/responses/faults.py",
        }
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
    extract_release_notes(changelog.read_text(), version)


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
            text = args.changelog.read_text()
            updated = update_comparison_links(
                text,
                previous=args.previous,
                version=args.version,
            )
            args.changelog.write_text(updated)
        elif args.command == "validate-release":
            validate_release(
                args.version,
                args.pyproject,
                args.lockfile,
                args.changelog,
            )
        elif args.command == "notes":
            notes = extract_release_notes(args.changelog.read_text(), args.version)
            args.output.write_text(notes)
        elif args.command == "artifacts":
            verify_wheel(args.directory, args.version)
            verify_sdist(args.directory, args.version)
            manifest = artifact_manifest(args.directory, args.version)
            args.output.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            )
    except ReleaseError as exc:
        sys.stderr.write(f"release validation failed: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
