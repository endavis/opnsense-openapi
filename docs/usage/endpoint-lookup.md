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
