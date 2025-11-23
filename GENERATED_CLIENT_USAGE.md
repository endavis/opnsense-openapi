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
from opnsense_api.generated.v25_7_6.opnsense_api_client.api.core import (
    core_firmware_info,
    core_firmware_status,
)

# IDE autocomplete works perfectly!
info = core_firmware_info.sync(client=api)
status = core_firmware_status.sync(client=api)

print(f"OPNsense version: {info.product_version}")
```

## Using client.api - Detailed Examples

The `client.api` property returns a generated client that gives you full type safety and IDE support.

### Basic Usage Pattern

```python
from opnsense_api import OPNsenseClient

# Initialize with auto-detection
client = OPNsenseClient(
    base_url="https://opnsense.local",
    api_key="your-key",
    api_secret="your-secret",
    verify_ssl=False,
    auto_detect_version=True,
)

# Get the generated client
api = client.api
```

### Calling API Functions

Each endpoint becomes a Python module with multiple functions:

```python
from opnsense_api.generated.v25_7_6.opnsense_api_client.api.core import core_firmware_info

# sync() - Returns parsed data or None
info = core_firmware_info.sync(client=api)
if info:
    print(f"Version: {info.product_version}")

# sync_detailed() - Returns full Response object
from opnsense_api.generated.v25_7_6.opnsense_api_client.types import Response
response = core_firmware_info.sync_detailed(client=api)
print(f"Status: {response.status_code}")
print(f"Data: {response.parsed}")
```

### Working with Different Endpoints

```python
# Firewall operations
from opnsense_api.generated.v25_7_6.opnsense_api_client.api.firewall import (
    firewall_alias_search_item,
    firewall_alias_get_item,
)

# Search for aliases
aliases = firewall_alias_search_item.sync(client=api)

# Get specific alias by UUID
alias_detail = firewall_alias_get_item.sync(client=api, uuid="some-uuid-here")

# Core system operations
from opnsense_api.generated.v25_7_6.opnsense_api_client.api.core import (
    core_firmware_check,
    core_firmware_upgrade,
)

# Check for updates
updates = core_firmware_check.sync(client=api)

# Upgrade system (returns upgrade status)
upgrade_result = core_firmware_upgrade.sync(client=api)
```

### Async/Await Support

All functions have async versions:

```python
import asyncio
from opnsense_api.generated.v25_7_6.opnsense_api_client.api.core import core_firmware_info

async def get_firmware_info():
    # Use asyncio() for parsed data
    info = await core_firmware_info.asyncio(client=api)
    return info

# Or asyncio_detailed() for full response
async def get_firmware_info_detailed():
    response = await core_firmware_info.asyncio_detailed(client=api)
    return response

# Run async code
info = asyncio.run(get_firmware_info())
```

### Error Handling

```python
from opnsense_api.generated.v25_7_6.opnsense_api_client import errors
from opnsense_api.generated.v25_7_6.opnsense_api_client.api.core import core_firmware_info

try:
    info = core_firmware_info.sync(client=api)
    if info is None:
        print("Request succeeded but returned no data")
    else:
        print(f"Version: {info.product_version}")

except errors.UnexpectedStatus as e:
    print(f"Unexpected status code: {e.status_code}")
    print(f"Response content: {e.content}")

except httpx.TimeoutException:
    print("Request timed out")

except httpx.HTTPError as e:
    print(f"HTTP error occurred: {e}")
```

### Context Manager Usage

```python
from opnsense_api import OPNsenseClient
from opnsense_api.generated.v25_7_6.opnsense_api_client.api.core import core_firmware_info

# Client automatically closes connections when exiting context
with OPNsenseClient(
    base_url="https://opnsense.local",
    api_key="key",
    api_secret="secret",
    verify_ssl=False,
    auto_detect_version=True,
) as client:
    api = client.api
    info = core_firmware_info.sync(client=api)
    print(f"Version: {info.product_version}")
# Connection closed automatically here
```

### Multiple API Calls

```python
from opnsense_api.generated.v25_7_6.opnsense_api_client.api.core import (
    core_firmware_info,
    core_firmware_status,
)
from opnsense_api.generated.v25_7_6.opnsense_api_client.api.firewall import (
    firewall_alias_search_item,
)

# The generated client reuses the same authenticated HTTP connection
api = client.api

# All these use the same connection
firmware_info = core_firmware_info.sync(client=api)
firmware_status = core_firmware_status.sync(client=api)
aliases = firewall_alias_search_item.sync(client=api)

print(f"System version: {firmware_info.product_version}")
print(f"Status: {firmware_status}")
print(f"Aliases count: {len(aliases.rows) if aliases else 0}")
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
from opnsense_api.generated.v25_7_6.opnsense_api_client import errors

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
from opnsense_api.generated.v25_7_6.opnsense_api_client.api.core import core_firmware_info
result = core_firmware_info.sync(client=api)
```

Both can coexist in the same codebase!
