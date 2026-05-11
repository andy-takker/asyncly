# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-05-11

### Added
- **Pytest plugin** (`asyncly.pytest_plugin`) auto-registered via `pytest11` entry-point. Provides `mock_routes` and `mock_service` fixtures so tests no longer need to wire their own `start_service` context manager.
- **Request matching** via the new `Match` builder on `MockRoute`. Multiple routes can share `(method, path)` and be dispatched by JSON body, headers (subset), query (subset), or raw body. Routes without `match=` act as fallbacks within their group.
- **Assertion helpers on `MockService`**: `get_calls(name)`, `last_call(name)`, `assert_called(name, *, times=, json=, body=, headers=, query=)`, `assert_not_called(name)`.
- **`RawResponse`** for returning arbitrary bytes with arbitrary headers — useful for testing client behavior on malformed JSON or unexpected content types.
- **TLS support** in `start_service(routes, *, ssl_context=...)` — pass an `ssl.SSLContext` to serve over HTTPS (`MockService.url.scheme == "https"`).
- `SequenceResponse(on_exhausted=...)` with three modes: `"raise"` (default, new behavior raises `SequenceExhausted` with a clear message), `"cycle"`, `"last"`. Now exported directly from `asyncly.srvmocker`.
- New exceptions: `SrvMockerError`, `SequenceExhausted`, `UnknownHandlerError`.

### Changed
- `MockService.register()` now emits `DeprecationWarning` when called with a `handler_name` not declared in any `MockRoute`. Will become `UnknownHandlerError` in 0.7.
- `SequenceResponse` on exhaustion now raises a typed `SequenceExhausted` instead of bubbling `RuntimeError` from PEP 479. Default behavior otherwise unchanged.
- `Match` defensively copies `headers` and `query` dict arguments at construction time — caller-side mutation of the original dict no longer affects matcher behavior.

### Fixed
- `SequenceResponse([])` now raises `ValueError` eagerly instead of failing on first use.

[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.6.0...HEAD
[0.6.0]: https://github.com/andy-takker/asyncly/compare/0.5.1...0.6.0
