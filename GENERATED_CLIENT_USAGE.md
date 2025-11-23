# Using Generated Clients with Auto-Detection

This document shows how to use the generated OpenAPI clients with automatic version detection.

## Overview

The OPNsense API wrapper now supports **two approaches**:

1. **Generated Client (Recommended)** - Full type hints, IDE autocomplete, battle-tested code
2. **Legacy Wrapper** - Dynamic runtime introspection, simpler but no type checking

## Quick Start - Generated Client

### 1. Generate the Client

```bash
# Generate OpenAPI spec from OPNsense source
opnsense-openapi generate 25.7.6

# Generate Python client from spec
uv run openapi-python-client generate \
  --path src/opnsense_api/specs/opnsense-25.7.6.json \
  --output-path src/opnsense_api/generated/v25_7_6 \
  --overwrite
```

### 2. Use With Auto-Detection

```python
import os
from opnsense_api.client import OPNsenseClient

# Client auto-detects version from your OPNsense instance
client = OPNsenseClient(
    base_url=os.getenv("OPNSENSE_URL"),
    api_key=os.getenv("OPNSENSE_API_KEY"),
    api_secret=os.getenv("OPNSENSE_API_SECRET"),
    verify_ssl=False,
    auto_detect_version=True,  # Magic!
)

# Get the version-specific generated client
api = client.api  # Returns generated client for detected version

# Use the generated API functions with full type hints
from opnsense_api.generated.v25_7_6.op_nsense_api_client.api.core import (
    core_firmware_info,
    core_firmware_status,
)

# IDE autocomplete works perfectly!
info = core_firmware_info.sync(client=api)
status = core_firmware_status.sync(client=api)

print(f"OPNsense version: {info.product_version}")
```

## Benefits of Generated Client

### ✅ Full Type Hints

```python
# Your IDE knows exactly what's available
result = core_firmware_info.sync(client=api)
# ↑ IDE shows: CoreFirmwareInfoResponse200 | None

# Autocomplete shows all fields
version = result.product_version  # ← IDE suggests this
packages = result.package_list     # ← And this
```

### ✅ Compile-Time Validation

```python
# Typos caught immediately
info.product_verison  # ❌ mypy/pyright error!
info.product_version  # ✅ Correct
```

### ✅ Better Error Messages

```python
# Generated code raises clear exceptions
from opnsense_api.generated.v25_7_6.op_nsense_api_client import errors

try:
    result = core_firmware_info.sync(client=api)
except errors.UnexpectedStatus as e:
    print(f"API returned status {e.status_code}: {e.content}")
```

## Legacy Wrapper (Still Supported)

The dynamic wrapper still works for backwards compatibility:

```python
client = OPNsenseClient(...)

# Old approach - still works
client.get("core", "firmware", "info")
client.post("firewall", "alias", "addItem", json={...})

# OpenAPI wrapper with introspection
endpoints = client.openapi.list_endpoints()
params = client.openapi.suggest_parameters("/core/firmware/info")
```

## Architecture

```
User Code
    ↓
OPNsenseClient (auto-detects version 25.7.6)
    ↓
client.api → Returns generated Client for v25_7_6
    ↓
Generated API functions (core_firmware_info.sync, etc.)
    ↓
httpx with Basic Auth (reuses OPNsenseClient's authenticated session)
```

## Multiple Versions

You can pre-generate clients for multiple versions:

```bash
# Generate for 24.7
opnsense-openapi generate 24.7
uv run openapi-python-client generate \
  --path src/opnsense_api/specs/opnsense-24.7.json \
  --output-path src/opnsense_api/generated/v24_7

# Generate for 25.7.6
opnsense-openapi generate 25.7.6
uv run openapi-python-client generate \
  --path src/opnsense_api/specs/opnsense-25.7.6.json \
  --output-path src/opnsense_api/generated/v25_7_6
```

The client automatically selects the right one based on auto-detection!

## IDE Setup

For best experience with type hints:

### VS Code

```json
{
  "python.analysis.typeCheckingMode": "basic",
  "python.analysis.autoImportCompletions": true
}
```

### PyCharm

Settings → Editor → Inspections → Python → Type Checker (enable)

## Comparison

| Feature | Generated Client | Legacy Wrapper |
|---------|-----------------|----------------|
| Type hints | ✅ Full | ❌ None |
| IDE autocomplete | ✅ Perfect | ⚠️ Limited |
| Compile-time checks | ✅ Yes | ❌ No |
| Runtime discovery | ❌ No | ✅ Yes |
| Build step required | ✅ Yes | ❌ No |
| Battle-tested code | ✅ Yes | ⚠️ Custom |
| Async support | ✅ Built-in | ❌ No |

## When to Use Each

**Use Generated Client when:**
- You want type safety and IDE support
- Building production applications
- Working in a team (better code review)
- Need async/await support

**Use Legacy Wrapper when:**
- Quick prototyping
- Runtime endpoint discovery needed
- Don't want build step
- Simple scripts

## Migration Path

Existing code continues to work:

```python
# Old code - still works
client = OPNsenseClient(...)
result = client.get("core", "firmware", "info")

# New code - gradually migrate
api = client.api
from opnsense_api.generated.v25_7_6.op_nsense_api_client.api.core import core_firmware_info
result = core_firmware_info.sync(client=api)
```

Both can coexist in the same codebase!
