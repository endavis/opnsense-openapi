---
title: Spec Version Resolution
description: How a live OPNsense version maps to a committed OpenAPI spec
audience:
  - contributors
  - integrators
tags:
  - specs
  - versioning
  - architecture
---

# Spec Version Resolution

## Overview

When an `OPNsenseClient` connects to a live box, the box reports a version
string (for example `25.7.5` or `26.1.6_2`). That version is rarely the
version of an OpenAPI spec we have committed in
`src/opnsense_openapi/specs/`. The resolver in
[`opnsense_openapi.specs`](../reference/api.md) maps the reported version
to a spec file and a generated-client module directory using two rules.

## Rule 1: Security-patch suffixes are normalized

OPNsense releases security patches by appending `_1`, `_2`, ... to the
underlying release (`26.1.6_2` is a security patch of `26.1.6`). The
**OpenAPI surface does not change between security patches** of the same
release — controllers, parameters, and responses are identical. The
resolver therefore treats `26.1.6_2` as equivalent to `26.1.6` for spec
selection and generated-client identity.

In code this is implemented by `_version_key()` stripping a trailing `_N`
from the last component before parsing:

```python
_version_key("26.1.6")     == (26, 1, 6)
_version_key("26.1.6_2")   == (26, 1, 6)
```

A direct consequence: the generated-client directory is keyed off the
*resolved* spec version, not the raw input. The first time the client
auto-generates for a `26.1.6_2` box, codegen lands in
`src/opnsense_openapi/generated/v26_1_6/`. A subsequent boot reporting
`26.1.6_3` finds the existing `v26_1_6/` directory and skips codegen.

## Rule 2: Floor matching is the default

When no exact spec exists for the requested version, the resolver collects
all specs sharing the requested `major.minor` and picks one based on the
`mode` argument to `find_best_matching_spec`:

- **`"floor"` (default)** — the highest committed spec **at or below** the
  requested version. This is the conservative choice: it never claims an
  endpoint exists on a box that may not have shipped it yet.
- **`"highest"`** — the highest committed spec sharing `major.minor`. This
  is the legacy behavior, retained for callers that want to bias toward
  newer surfaces (interactive docs browsing where false positives are
  acceptable, for instance).

Concrete example: a box reports `25.7.5`. Committed specs are
`[25.7.4, 25.7.6, 25.7.7]`. The resolver picks:

| Mode | Result | Rationale |
|------|--------|-----------|
| `floor` (default) | `25.7.4` | Highest spec at or below the box's version. |
| `highest` | `25.7.7` | Highest spec sharing `25.7`, ignoring the box's actual version. |

If no spec is at or below the requested version under floor mode, the
resolver raises `FileNotFoundError` rather than silently picking a spec
above the box.

## Why these defaults

In direct-API integrations (the use case that drives this project), an
endpoint that exists in the spec but not on the box returns 404 at
runtime. That failure mode is more painful than the inverse — a missing
endpoint that the box happens to support — because users hit it during
normal operation, not during exploration. Floor matching biases the
client toward the conservative subset that is guaranteed to exist on the
box.

## Related

- [ADR-0001: Spec matching: floor over highest, module path keyed by resolved spec version](../decisions/0001-spec-matching-floor-over-highest-module-path-keyed-by-resolved-spec-version.md) (Accepted)
- Issue #34 — the bug report and discussion that drove this rule.
- `src/opnsense_openapi/specs.py` — `find_best_matching_spec`,
  `_version_key`, `version_from_spec_path`.
- `src/opnsense_openapi/client/base.py` — `_resolved_module_dir`, the
  helper that ties the generated-client path to the resolved spec
  version.
