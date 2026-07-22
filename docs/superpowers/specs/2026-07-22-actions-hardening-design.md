# Asyncly CI, Release, and Changelog Hardening Design

## Summary

Harden Asyncly's GitHub Actions without replacing the project's existing release
model or versioned documentation system. The target is the agreed "2+" scope:
secure and complete CI, a stable required check, tag-safe releases, artifact
provenance, a tested minimum-dependency lane, and Towncrier-based changelog
automation.

The design retains reusable workflows, PyPI trusted publishing, Sigstore signing,
and Mike-managed documentation. It does not introduce release-please, automatic
tagging, or a new Pages backend.

## Goals

- Run the same meaningful quality gates on pull requests, merge-queue commits,
  `master`, and release tags.
- Expose one stable `CI required` status for the default-branch ruleset.
- Remove deprecated GitHub Actions runtimes and pin every external action to a
  full commit SHA.
- Use `setup-uv`, dependency caching, and locked installs.
- Test all declared Python versions, including Python 3.14, plus the minimum
  supported `aiohttp` version.
- Verify distributions by metadata and isolated wheel installation before they
  can reach PyPI.
- Make releases tag-only, validate the tag against project metadata, and publish
  the exact artifacts that passed verification.
- Add GitHub build-provenance attestations while preserving downloadable Sigstore
  bundles.
- Assemble `CHANGELOG.md` from reviewable fragments and generate release PRs.
- Enable branch and tag rulesets only after the new status names have been
  observed in a real pull request.

## Non-goals

- Migrating to release-please or generating release prose from commit messages.
- Automatically creating release tags after a release PR merges.
- Replacing Mike or the `gh-pages` branch with the GitHub Pages artifact backend.
- Adding path-filtered CI, a broad operating-system matrix, or a merge queue.
  The workflow supports the `merge_group` event, but enabling a repository merge
  queue is a separate future decision.
- Refactoring library runtime code.

## Workflow Architecture

### CI orchestrator

Replace the branch-push-only feature pipeline with a single CI orchestrator. It
runs for:

- `pull_request` targeting `master`;
- `merge_group`;
- pushes to `master`;
- `workflow_dispatch` for release branches and diagnostics.

The orchestrator calls focused reusable workflows for static checks, test
matrices, documentation, and package verification. A final job named
`CI required` uses `if: always()` and fails unless every required dependency is
either successful or intentionally skipped. Repository settings require only
this stable status, so internal matrix changes do not invalidate the ruleset.

### Shared project setup

A repository-local composite action centralizes repeated environment setup:

- install a selected Python version through `setup-uv`;
- enable the uv cache;
- run a locked dependency sync with the requested extras and groups.

External actions used by the composite action and workflows are pinned to full
commit SHAs. Dependabot continues to update GitHub Actions references in a
grouped pull request.

The publish job does not use the full project setup because it only needs uv and
the already-built distributions.

## CI Gates

### Workflow security and syntax

Run actionlint and zizmor before the more expensive test jobs. They validate
workflow syntax, expressions, permissions, unsafe interpolation, and action
pinning. The workflow starts with no token permissions and grants the minimum at
job level.

### Python quality

Static checks cover `asyncly`, `tests`, and `examples`:

- `ruff format --check`;
- `ruff check`;
- mypy for the package.

The main test matrix runs on Python 3.10 through 3.14 using the committed lockfile
and all supported extras. Coverage remains at or above the configured 90 percent
threshold. The normal pytest invocation includes the executable examples instead
of limiting collection to `tests/`. Once the 3.14 lane passes, project metadata
adds the matching Python classifier.

A separate compatibility job installs the project's lowest supported direct
dependency set, including `aiohttp==3.13.3`, and runs the core suite. This lane
detects accidental reliance on APIs introduced after the declared minimum.

### Documentation and package verification

Every pull request builds documentation with `mkdocs build --strict`; deployment
remains separate.

The package job builds wheel and sdist once, then verifies:

- standard package metadata;
- expected name, version, Python constraint, and public files;
- isolated installation of the wheel outside the source tree;
- imports of the public retry and srvmocker APIs;
- SHA-256 digests for later release steps.

The verified files are uploaded as one workflow artifact. Release workflows use
artifacts built and checked in their own tag-triggered run, so the published bytes
come from the exact tagged commit.

## Changelog Model

Towncrier is the changelog source assembler. Significant pull requests add one or
more fragments under `changes/`:

```text
changes/123.added.md
changes/123.fixed.md
changes/123.breaking.md
```

Supported fragment types are:

- `added`;
- `changed`;
- `breaking`;
- `fixed`;
- `deprecated`;
- `security`;
- `docs`.

A custom Towncrier template preserves the existing Keep a Changelog structure,
including the explicit `Changed (breaking)` heading and comparison links.

For ordinary pull requests, CI requires a fragment relative to `origin/master`.
A maintainer may apply `skip-changelog` for changes that should not appear in
release notes. Generated release pull requests use the `release` label and are
exempt because their fragments have already been consumed. Commit-message markers
cannot bypass this policy.

## Release Preparation

A manually dispatched `Prepare release` workflow accepts a stable `X.Y.Z`
version and a `dry_run` flag. Before changing files it verifies that:

- the input is valid stable SemVer and is greater than the current version;
- the workflow is operating from the current `master` commit;
- no local or remote tag and no GitHub Release exists for that version;
- releasable Towncrier fragments exist.

Preparation performs these deterministic changes:

1. Assemble the dated changelog section from fragments.
2. Update `pyproject.toml` and `uv.lock` to the requested version.
3. Point `[Unreleased]` at the new version and add the new comparison link.
4. Remove the consumed fragments.
5. Verify the generated diff and run the focused release-helper tests.

With `dry_run=true`, the workflow uploads the patch and generated release notes
without pushing a branch. A normal run creates `release/X.Y.Z`, commits the
generated files, opens a pull request carrying the `release` label, and dispatches
the CI workflow on the new ref.

The explicit dispatch is required because GitHub suppresses most recursive
workflow events created with `GITHUB_TOKEN`. It avoids a long-lived personal
access token while still producing the required status on the release commit.

After the release PR merges, the maintainer creates and pushes an annotated
version tag. Tag creation remains the deliberate publication boundary.

## Tag-triggered Release

The release workflow has no manual dispatch entry point. It runs only for stable
SemVer tags and validates, before requesting an OIDC token, that:

- the ref is an annotated tag;
- the tag name matches the versions in `pyproject.toml` and `uv.lock`;
- the matching changelog section exists;
- the tagged commit is contained in `origin/master`.

The tag run repeats the critical static, test, documentation, and package gates
against the exact release commit. Its build job produces one wheel/sdist pair.
Those same files are then:

1. recorded with SHA-256 digests;
2. covered by a GitHub build-provenance attestation;
3. published to PyPI using trusted publishing and the protected `pypi`
   environment;
4. signed with Sigstore;
5. attached, with signature bundles, to a GitHub Release whose body is extracted
   from the matching changelog section.

The publish and GitHub Release jobs remain separate. If a retry sees the version
on PyPI, it compares the published filenames and SHA-256 digests. Matching files
make publishing a safe no-op so downstream release creation can resume. A missing
file or digest mismatch fails closed because PyPI artifacts are immutable.

## Permissions and Failure Handling

Workflows declare empty top-level permissions. Individual jobs grant only what
they need:

- ordinary CI: `contents: read`;
- changelog-fragment inspection: `contents: read` and `pull-requests: read`;
- release preparation: `contents: write`, `pull-requests: write`, and
  `actions: write`;
- PyPI publishing: `contents: read` and `id-token: write`;
- provenance: `contents: read`, `id-token: write`, and `attestations: write`;
- Sigstore: `contents: read` and `id-token: write`;
- GitHub Release creation: `contents: write`;
- Mike deployment: `contents: write`.

All jobs have explicit timeouts. CI cancels obsolete runs for the same pull
request. Release and documentation deployments serialize without cancelling an
in-progress publication.

Non-trivial parsing is kept out of YAML shell blocks. Small Python release helpers
handle version validation, comparison-link updates, release-note extraction, and
artifact metadata/digest verification. Their pure behavior is covered by unit
tests.

## Documentation Deployment

Mike, the `gh-pages` branch, `dev`, and version aliases remain unchanged. The docs
workflow receives the same action pinning, setup-uv, locked install, least-
privilege permissions, concurrency, and timeout treatment as the other
workflows. The stale manual default version is removed; a manual deployment
requires an explicit version input.

## Repository Rulesets

Ruleset changes happen only after the workflow pull request has demonstrated its
actual check names.

The `master` ruleset is enabled with:

- pull requests required;
- `CI required` as the only required status;
- strict up-to-date branch checks;
- force-push and deletion blocked;
- zero mandatory approvals for a solo-maintainer workflow;
- administrative bypass reserved for emergencies.

A separate tag ruleset protects stable SemVer release tags from force updates and
deletion. It does not require signed Git tags because artifact provenance and
Sigstore verify the released bytes; tags are still required to be annotated by
the release workflow.

## Rollout

1. Implement the repository changes on `chore/actions-hardening` while the old
   ruleset remains disabled.
2. Run local YAML, security, Python, docs, and package gates.
3. Open the hardening pull request and observe a successful `CI required` check.
4. Exercise `Prepare release` in dry-run mode and inspect its patch artifact.
5. Merge the pull request.
6. Update and enable the `master` and tag rulesets through the GitHub API.
7. Open a small validation pull request and prove that the ruleset blocks merge
   until `CI required` succeeds.
8. Use the normal release preparation flow for the next real version; do not
   create a synthetic PyPI release solely to test publishing.

## Acceptance Criteria

- actionlint and zizmor pass with all external actions pinned by commit SHA.
- Ruff formatting/lint, mypy, Python 3.10-3.14 tests, examples, coverage, strict
  docs, minimum dependencies, and package smoke tests pass.
- An ordinary pull request without a fragment fails the changelog gate; a
  maintainer-applied `skip-changelog` label and a generated `release` pull request
  skip it intentionally.
- Towncrier dry-run produces the expected dated section, version changes,
  comparison links, release body, and consumed-fragment deletion.
- The release workflow rejects a non-annotated tag, mismatched tag/version,
  missing changelog section, or tag outside `master` before publication.
- GitHub and PyPI receive the exact verified artifact pair, with provenance and
  Sigstore evidence.
- Mike continues to deploy `dev` from `master` and version/`latest` from tags.
- The enabled default-branch ruleset requires only the observed `CI required`
  context and prevents unverified merges.
