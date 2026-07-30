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
