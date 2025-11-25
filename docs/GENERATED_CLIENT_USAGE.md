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
  --path src/opnsense_openapi/specs/opnsense-25.7.6.json \
  --output-path src/opnsense_openapi/generated/v25_7_6 \
  --overwrite
```

### 2. Use With Auto-Detection (Version-Agnostic!)

```python
import os
from opnsense_openapi import OPNsenseClient

# Client auto-detects version from your OPNsense instance
client = OPNsenseClient(
    base_url=os.getenv("OPNSENSE_URL"),
    api_key=os.getenv("OPNSENSE_API_KEY"),
    api_secret=os.getenv("OPNSENSE_API_SECRET"),
    verify_ssl=False,
    auto_detect_version=True,  # Magic!
)

# Get the version-agnostic API wrapper
api = client.api

# Call any API function - NO version-specific imports needed! 🎉
info = api.core.firmware_info()
status = api.core.firmware_status()
aliases = api.firewall.alias_search_item()

print(f"OPNsense version: {info.product_version}")
```

**Key Advantage:** Your code works across different OPNsense versions without any changes!

## Using client.api - Detailed Examples

The `client.api` property returns a version-agnostic API wrapper that provides dynamic access to all generated functions without needing version-specific imports.

### Basic Usage Pattern

```python
from opnsense_openapi import OPNsenseClient

# Initialize with auto-detection
client = OPNsenseClient(
    base_url="https://opnsense.local",
    api_key="your-key",
    api_secret="your-secret",
    verify_ssl=False,
    auto_detect_version=True,
)

# Get the version-agnostic API wrapper
api = client.api  # No version in code!
```

### Calling API Functions (Version-Agnostic)

Access any endpoint without knowing the version:

```python
# Simple calls - automatically uses sync()
info = api.core.firmware_info()
if info:
    print(f"Version: {info.product_version}")

# Explicit sync() call
info = api.core.firmware_info.sync()

# Get detailed response with status code
response = api.core.firmware_info.sync_detailed()
print(f"Status: {response.status_code}")
print(f"Data: {response.parsed}")

# Pass parameters
alias = api.firewall.alias_get_item(uuid="some-uuid")
```

**Works across all OPNsense versions** - whether 24.7, 25.7.6, or future versions!

### Working with Different Endpoints

```python
# Firewall operations - no imports needed!
aliases = api.firewall.alias_search_item()
alias_detail = api.firewall.alias_get_item(uuid="some-uuid-here")

# Core system operations
updates = api.core.firmware_check()
upgrade_result = api.core.firmware_upgrade()

# Auth operations
users = api.auth.user_search()
user = api.auth.user_get(uuid="user-uuid")

# Any module/function combination works!
# Pattern: api.<module>.<function>(<params>)
```

### Async/Await Support

All functions have async versions - no version-specific imports needed:

```python
import asyncio
from opnsense_openapi import OPNsenseClient

# Initialize client (outside async context)
client = OPNsenseClient(..., auto_detect_version=True)
api = client.api

async def get_firmware_info():
    # Use asyncio() for parsed data
    info = await api.core.firmware_info.asyncio()
    return info

# Or asyncio_detailed() for full response
async def get_firmware_info_detailed():
    response = await api.core.firmware_info.asyncio_detailed()
    return response

# Run async code
info = asyncio.run(get_firmware_info())
```

### Error Handling

Error handling works with version-agnostic access - the client auto-loads the correct error types:

```python
import httpx
from opnsense_openapi import OPNsenseClient

client = OPNsenseClient(..., auto_detect_version=True)
api = client.api

try:
    info = api.core.firmware_info()
    if info is None:
        print("Request succeeded but returned no data")
    else:
        print(f"Version: {info.product_version}")

except Exception as e:
    # Check for common error types
    if hasattr(e, 'status_code'):
        print(f"Unexpected status code: {e.status_code}")
        if hasattr(e, 'content'):
            print(f"Response content: {e.content}")
    elif isinstance(e, httpx.TimeoutException):
        print("Request timed out")
    elif isinstance(e, httpx.HTTPError):
        print(f"HTTP error occurred: {e}")
    else:
        raise
```

### Context Manager Usage

Context managers work seamlessly with version-agnostic access:

```python
from opnsense_openapi import OPNsenseClient

# Client automatically closes connections when exiting context
with OPNsenseClient(
    base_url="https://opnsense.local",
    api_key="key",
    api_secret="secret",
    verify_ssl=False,
    auto_detect_version=True,
) as client:
    api = client.api

    # No version-specific imports needed!
    info = api.core.firmware_info()
    print(f"Version: {info.product_version}")
# Connection closed automatically here
```

### Multiple API Calls

Multiple calls reuse the same authenticated connection automatically:

```python
from opnsense_openapi import OPNsenseClient

# Initialize once
client = OPNsenseClient(..., auto_detect_version=True)
api = client.api

# All these use the same authenticated HTTP connection - no imports needed!
firmware_info = api.core.firmware_info()
firmware_status = api.core.firmware_status()
aliases = api.firewall.alias_search_item()

print(f"System version: {firmware_info.product_version}")
print(f"Status: {firmware_status}")
print(f"Aliases count: {len(aliases.rows) if aliases else 0}")
```

## Benefits of Generated Client

### ✅ Full Type Hints

```python
# Your IDE knows exactly what's available
result = api.core.firmware_info()
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
try:
    result = api.core.firmware_info()
except Exception as e:
    if hasattr(e, 'status_code') and hasattr(e, 'content'):
        print(f"API returned status {e.status_code}: {e.content}")
    else:
        raise
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
  --path src/opnsense_openapi/specs/opnsense-24.7.json \
  --output-path src/opnsense_openapi/generated/v24_7

# Generate for 25.7.6
opnsense-openapi generate 25.7.6
uv run openapi-python-client generate \
  --path src/opnsense_openapi/specs/opnsense-25.7.6.json \
  --output-path src/opnsense_openapi/generated/v25_7_6
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

# Old approach - still works
client = OPNsenseClient(...)
result = client.get("core", "firmware", "info")

# New code - gradually migrate (no version-specific imports!)
api = client.api
result = api.core.firmware_info()
```

Both can coexist in the same codebase!

## Handling Incorrectly Generated Endpoints

In rare cases, the OpenApi generator might misidentify an endpoint's HTTP method (e.g., generating a `GET` for an endpoint that requires `POST`) or parameters. If you encounter a 404 or 405 error for a specific function, you can bypass the generated method and use the underlying manual client methods.

**Example: Forcing a POST request**

```python
# If api.diagnostics.interface.carp_status() incorrectly tries GET:
try:
    # Use the manual .post() method on the base client
    response = client.post(
        "diagnostics", 
        "interface", 
        "CarpStatus", 
        json={"status": "enable"}
    )
    print("Success:", response)
except Exception as e:
    print("Error:", e)
```

This ensures you are never blocked by a spec generation issue.
