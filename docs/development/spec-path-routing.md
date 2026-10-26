---
title: Spec Path Routing Checks
description: The spec path routing lint and the live OPNsense API contract test, and how to run them
audience:
  - contributors
tags:
  - testing
  - ci
---

# Spec Path Routing Checks

Two checks guard how API paths are routed to bundled specs. They are project-specific, so they
live here rather than in the template-managed [CI/CD Testing Guide](ci-cd-testing.md).

## Spec Path Routing Lint

### What It Checks

The structural lint in `tests/test_spec_path_routing.py` verifies that every
`/api/{module}/{controller}/{action}` path in the latest committed OpenAPI
spec resolves to a real `*Controller.php` file in the matching OPNsense
source archive. It exists to catch regressions of issue #32, where the
generator emitted collapsed-lowercase URL segments (e.g.,
`/api/interfaces/vlansettings`) that did not reverse-map to any real
controller (`OPNsense/Interfaces/Api/VlanSettingsController.php`).

The lint walks the latest spec returned by `opnsense_openapi.list_available_specs()`,
parses each path, applies `to_class_name(controller_segment) + "Controller.php"`,
and asserts the resulting file exists. Module directory resolution is
case-insensitive to mirror OPNsense's `Mvc/Router.php` namespace fallback
(so `/api/dhcrelay` resolves to `OPNsense/DHCRelay`, etc.). All failures
are collected and reported in a single assertion so a single test run
surfaces every broken path.

### The `requires_opnsense_source` Marker

The lint test is decorated with `@pytest.mark.requires_opnsense_source`.
When the OPNsense source archive cannot be materialized (e.g., no network
in a developer sandbox), the test skips with a clear reason instead of
hard-failing. CI pre-downloads the archive in a dedicated workflow step
and caches it keyed on the spec version, so the lint runs unconditionally
in CI and stays fast across reruns.

### Running Locally

```bash
uv run pytest tests/test_spec_path_routing.py -v
```

The test downloads the OPNsense source via `SourceDownloader` if the
archive is not already cached at `tmp/opnsense_source/{version}/`. To
pre-populate the cache without running the test:

```bash
uv run python -c "from opnsense_openapi.downloader import SourceDownloader; SourceDownloader().download('26.1.6')"
```

The unmarked unit tests in the same file exercise the path-checking helper
against synthetic fake-tree fixtures (no network required) and run on
every CI pass.

## Live API Contract Test

### What It Asserts

The runtime counterpart to the structural lint above:
`tests/test_live_opnsense.py` samples ~25 read-only operations from the
matching committed spec, calls each against a live OPNsense instance, and
asserts every response is non-404 and roughly shape-matched (top-level
JSON type matches the operation's declared response schema). It is the
runtime test that would have caught issue #32 (collapsed-lowercase URL
segments returning 404) against any real box.

Per-response validation is intentionally light:

- Status is not 404 (and no other HTTP error).
- Body parses as JSON.
- Top-level type (object vs. array) matches the operation's declared
  response schema. No deep `jsonschema` validation — strict shape
  validation would couple the test to spec drift.

### The `live_opnsense` Marker

The live test is decorated with `@pytest.mark.live_opnsense` and is
**off by default**. The default `doit test` collects it but skips it
because the marker is unselected. Opt in explicitly with the marker
filter shown below.

### Required Environment Variables

| Variable | Purpose |
| :--- | :--- |
| `OPNSENSE_URL` | Base URL of the OPNsense instance (e.g., `https://192.168.1.1`). |
| `OPNSENSE_API_KEY` | API key for Basic Auth. |
| `OPNSENSE_API_SECRET` | API secret for Basic Auth. |

These mirror `.envrc.local.example`. The test skips with a clear reason
if any are missing. Two optional knobs are also honored:

- `OPNSENSE_LIVE_SAMPLE_SIZE` (default `25`) — upper bound on how many
  ops to sample per run.
- `OPNSENSE_LIVE_SEED` (default `0`) — RNG seed for reproducible
  sampling.

### Running Locally

```bash
uv run pytest -m live_opnsense -v
```

The test:

1. Constructs an `OPNsenseClient` and calls `detect_version()`.
2. Looks up `src/opnsense_openapi/specs/opnsense-{version}.json` by
   exact filename match (no major.minor fallback — version mismatch is
   a skip, not a silent contract swap).
3. Filters paths to GET-only, biases sampling toward segments
   `get`/`list`/`show`/`search`, samples up to `n`.
4. Calls each, records per-op pass/fail, asserts zero failures with all
   failing paths listed in the assertion message.

### Version-Match Rule and Skip Behavior

Version match is exact only. The test does **not** apply the
`find_best_matching_spec` major.minor fallback used at runtime, because
testing a 24.7.10 box against a 24.7.5 spec would silently obscure
contract drift. If `detect_version()` returns a version with no
committed spec, the test skips with a clear reason (filename it
expected, what it found).

### Why Not in Default CI

The project does not maintain a shared OPNsense box with stable
credentials, so the contract test cannot be wired into the default CI
matrix. A separate manually-triggered workflow could run it on demand
against a developer's box; that is acceptable but explicitly optional.
The structural lint
([Spec Path Routing Lint](#spec-path-routing-lint)) provides PR-time
signal without requiring a live target and ships in the default suite.

The unmarked unit tests in the same file exercise the helper functions
(`_load_spec_for_version`, `_sample_read_only_ops`, `_validate_light`)
against synthetic specs and run on every CI pass.
