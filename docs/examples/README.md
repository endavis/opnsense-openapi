---
title: Examples
description: OPNsense-specific example scripts that ship with this project
audience:
  - users
tags:
  - examples
  - getting-started
---

# Examples

The project ships three OPNsense-specific scripts under `examples/`. Each one is
a runnable demonstration of `OPNsenseClient` against a live OPNsense instance.

## Prerequisites

Install the package and set the credentials each script reads from the
environment:

```bash
uv pip install -e .

export OPNSENSE_URL="https://opnsense.local"
export OPNSENSE_API_KEY="your-api-key"
export OPNSENSE_API_SECRET="your-api-secret"
export OPNSENSE_VERIFY_SSL="false"   # or "true" with a valid cert
export OPNSENSE_VERSION="24.7.1"      # optional; enables OpenAPI features without auto-detection
```

## Available Examples

### `basic_usage.py`

Initializes `OPNsenseClient` with auto-detection (or a pinned `spec_version`)
and walks through the traditional client API: firmware info, firewall aliases,
OpenAPI endpoint discovery, and using the client as a context manager.

```bash
python examples/basic_usage.py
```

### `diagnose_api.py`

Diagnostic script that probes a configurable list of OPNsense API endpoints
with both `GET` and `POST`, reports per-endpoint status, and surfaces version
information from successful responses. Useful for verifying credentials and
identifying which endpoints exist on a given OPNsense version.

```bash
python examples/diagnose_api.py
```

### `openapi_example.py`

Focused walkthrough of the OpenAPI integration: listing all endpoints, filtering
by substring, introspecting an endpoint's path and query parameters, and
accessing the underlying OpenAPI wrapper directly.

```bash
python examples/openapi_example.py
```

## Why these are the project's examples

`opnsense-openapi` is a CLI code generator for the OPNsense REST API, not a
generic Python package or a service. The upstream `pyproject-template` ships
example scripts (`advanced_usage.py`, `cli_usage.py`) and a FastAPI sample under
`examples/api/` that target a different shape of project; those are
intentionally not adopted here. See [issue
#14](https://github.com/endavis/opnsense-openapi/issues/14) for the decision
record.

## Contributing Examples

Have an interesting use case? Pull requests welcome:

1. Add a new `.py` file in `examples/`.
2. Include a module docstring explaining what it does and any required env vars.
3. Add an entry to this README under **Available Examples**.
4. Open a PR following the standard workflow.
