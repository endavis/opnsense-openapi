---
title: Endpoint Lookup
description: Check whether OPNsense API endpoints exist for a version, without a connection
audience:
  - users
tags:
  - usage
  - endpoints
---

# Endpoint Lookup

`opnsense_openapi` can answer "does this endpoint exist on OPNsense X?" using
only the bundled specs. No network access or running firewall is needed, which
makes it suitable for CI.

```python
from opnsense_openapi import endpoint_exists, list_spec_endpoints

endpoint_exists("core/tunables/addItem", "POST", version="26.1.6")  # True
endpoint_exists("system/general/get", "GET", version="26.1.6")      # False
endpoint_exists("core/tunables/setItem/some-uuid", "POST", version="26.1.6")  # True

list_spec_endpoints("26.1.6")  # [("/api/core/...", "GET"), ...]
```

Path handling: the leading slash and `api/` prefix are optional, a trailing
slash, repeated slashes and a query string are ignored, and `{uuid}`-style
segments match any non-empty value. Methods are case-insensitive.

Versions resolve with floor matching, and `_N` security-patch suffixes are
ignored (see [spec version resolution](../development/spec-version-resolution.md)).
A version with no spec at or below it raises `FileNotFoundError`, which is
different from an endpoint being absent.

## Check endpoints in CI

```python
import sys
from opnsense_openapi import endpoint_exists

USED = [("core/tunables/addItem", "POST"), ("core/firmware/status", "GET")]
TARGET = "26.1.6"

missing = [(p, m) for p, m in USED if not endpoint_exists(p, m, version=TARGET)]
for path, method in missing:
    print(f"missing in {TARGET}: {method} {path}")
sys.exit(1 if missing else 0)
```

## Warn when the version is not covered

```python
import warnings
from opnsense_openapi import is_version_covered, newest_spec_version

if not is_version_covered("26.1.99"):
    warnings.warn(
        f"No exact spec for 26.1.99; using a nearby one. Newest bundled: {newest_spec_version()}",
        stacklevel=2,
    )
```

`newest_spec_version("26.1")` restricts the answer to one series.

## Compare two versions

```python
from opnsense_openapi import diff_specs

result = diff_specs("26.1.6", "26.1.11", module="core")
for path, method in result.added:
    print(f"+ {method} {path}")
for path, method in result.removed:
    print(f"- {method} {path}")
```

From the command line:

```bash
opnsense-openapi diff 26.1.6 26.1.11
opnsense-openapi diff 26.1.6 26.1.11 --module core --format json
```

Endpoints are `(path, METHOD)` pairs. A path that differs only in case shows up as one
removed and one added endpoint. Changed parameters or request bodies are not reported.
An unknown version or module exits with status 1; a non-empty diff still exits 0.

## Strict mode on the client

`OPNsenseClient(validate_endpoints=True)` checks every `get()` and `post()` against the
box's spec before sending. The spec comes from `spec_version` or the detected version.
A miss raises `UnknownEndpointError` (a subclass of `APIResponseError`) and sends no request:

```python
from opnsense_openapi import OPNsenseClient, UnknownEndpointError

client = OPNsenseClient(
    "https://fw.example", api_key="...", api_secret="...", validate_endpoints=True
)
try:
    client.post("core", "firmware", "frobnicate")
except UnknownEndpointError as exc:
    print(exc)  # POST core/firmware/frobnicate is not in the OPNsense 26.1.6 spec (...)
    print(exc.suggestions)  # closest known paths in the same module
```

- Templated endpoints such as `core/tunables/setItem/<uuid>` pass. A known path with the
  wrong method raises and lists the allowed methods.
- A box version with no exact bundled spec logs one warning and validates against the
  floor spec, so calls are not failed for being newer than the library.
- With no known version, or a version older than every bundled spec, a validated call
  raises `RuntimeError`.
- The default is `False`: nothing is validated and no spec is loaded. Version detection
  is never validated.
