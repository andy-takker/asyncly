# Changelog fragments

Create a fragment as `changes/<pr-number>.<type>.md`, for example
`changes/42.fixed.md`. Before a pull request has a number, use an orphan name
such as `changes/+short-description.changed.md`.

The supported types, in release-note order, are:

- `added` for new features
- `changed` for behavior changes
- `breaking` for backward-incompatible changes
- `fixed` for bug fixes
- `deprecated` for deprecated features
- `security` for security fixes
- `docs` for documentation changes

For example, PR 42 fixing a bug uses `changes/42.fixed.md`, while an unnumbered
documentation update can use `changes/+documentation.docs.md`. Write the
fragment as a concise, user-facing Markdown description of the change.

Preview the next section:

```bash
uv run towncrier build --draft --version 0.9.1
```

Validate the current branch:

```bash
uv run towncrier check --compare-with origin/master
```

Every user-visible change requires a fragment. Only maintainers may use the
`skip-changelog` exemption.
