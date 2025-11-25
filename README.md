# OPNsense API Python Wrapper Generator

Auto-generate Python client libraries for the OPNsense API by parsing controller source code from specific OPNsense versions.

## Overview

This tool downloads OPNsense source code from GitHub, parses PHP controller files to extract API endpoint definitions, and generates a type-hinted Python client library that mirrors the OPNsense API structure.

## Features

- **Version-agnostic API**: Auto-detects OPNsense version, no version-specific imports needed
- **Auto-generation**: Automatically generates Python client on first use if spec exists
- **Full type hints**: Generated code uses Python 3.12+ type annotations with Pydantic models
- **OpenAPI-based**: Generates OpenAPI 3.0 specs from OPNsense PHP source code
- **IDE support**: Complete autocomplete and type checking in modern IDEs
- **Async support**: Built-in async/await support for all endpoints
- **Battle-tested**: Uses openapi-python-client for reliable code generation

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd opn-sense

# Install with uv
just install

# Or manually
uv pip install -e ".[dev]"
```

## Quick Start

### Complete Setup (Easiest)

The fastest way to get started is using the `setup` command, which does everything in one step:

```bash
# Complete setup for OPNsense 25.7.6: download, generate spec, build client
uv run opnsense-openapi setup 25.7.6
```

This command:
1. Downloads OPNsense source code
2. Generates OpenAPI specification
3. Builds Python client

### Use the API Client

```python
import os
from opnsense_openapi import OPNsenseClient

# Initialize client with auto-detection
client = OPNsenseClient(
    base_url=os.getenv("OPNSENSE_URL"),
    api_key=os.getenv("OPNSENSE_API_KEY"),
    api_secret=os.getenv("OPNSENSE_API_SECRET"),
    verify_ssl=False,
    auto_detect_version=True,  # Automatically detect OPNsense version
)

# Access the API - automatically generates client if needed
# If the OpenAPI spec exists but the Python client hasn't been generated yet,
# it will be automatically generated on first access (takes ~2 minutes)
api = client.api

# Call any API function - no version-specific imports needed!
info = api.core.firmware_info()
aliases = api.firewall.alias_search_item()

print(f"OPNsense version: {info.product_version}")
print(f"Aliases: {aliases.rows if aliases else []}")
```

**Note:** The first time you access `client.api`, if the OpenAPI spec exists for your version, the Python client will be automatically generated. This takes about 2 minutes. Subsequent uses are instant.

If you don't have the OpenAPI spec yet (because you skipped the `setup` command), you'll get a helpful error message with the exact commands to run:
```bash
opnsense-openapi setup <version>
# or step-by-step:
opnsense-openapi download <version>
opnsense-openapi generate <version>
```

See [GENERATED_CLIENT_USAGE.md](docs/GENERATED_CLIENT_USAGE.md) for complete documentation.

## CLI Commands

### Complete Setup (Recommended)

```bash
opnsense-openapi setup [VERSION] [OPTIONS]

Options:
  -o, --output PATH  Output directory for generated client
  -c, --cache PATH   Cache directory for source files (default: tmp/opnsense_source)
  --force            Re-download source even when cached
  --meta TEXT        Meta type: none, poetry, setup, pdm, uv (default: setup)
  --overwrite        Overwrite existing client directory
```

**One command to do it all!** This convenience command runs all three steps:
1. Downloads OPNsense source code
2. Generates OpenAPI specification
3. Builds Python client

Use this when setting up a new OPNsense version for the first time.

**Example:**
```bash
opnsense-openapi setup 25.7.6
```

### Download Controller Sources

```bash
opnsense-openapi download [VERSION] [OPTIONS]

Options:
  -d, --dest PATH       Override the cache directory (default: tmp/opnsense_source)
  --force / --no-force  Re-download files even if cached
```

The command clones `https://github.com/opnsense/core` at the requested tag, caches
it locally, and extracts the controller files that downstream parsing and code
generation steps consume.

### Generate OpenAPI Spec

```bash
opnsense-openapi generate [VERSION] [OPTIONS]

Options:
  -o, --output PATH  Output directory for OpenAPI spec (default: specs/)
  -c, --cache PATH   Cache directory for source files (default: tmp/opnsense_source)
  --force            Re-download source even when cached
```

Generates an OpenAPI 3.0 specification from OPNsense controller source code. The spec is saved to the specs directory and can be used for client generation or documentation.

### Build Python Client (Optional)

```bash
opnsense-openapi build-client [OPTIONS]

Options:
  -v, --version TEXT  OPNsense version (e.g., '25.7.6'). Auto-detects if not specified.
  -o, --output PATH   Output directory for generated client
  --meta TEXT         Meta type: none, poetry, setup, pdm, uv (default: setup)
  --overwrite         Overwrite existing client directory
  --no-auto-detect    Disable auto-detection (requires --version)
```

**Note:** This command is **optional** because the Python client is automatically generated when you first access `client.api` if the OpenAPI spec exists. Only use this command if you want to:
- Pre-generate the client before first use
- Customize the generation options (meta type, output path)
- Regenerate/overwrite an existing client

### Serve Documentation

```bash
opnsense-openapi serve-docs [OPTIONS]

Options:
  -v, --version TEXT    OPNsense version (e.g., '25.7.6'). Auto-detects if not specified.
  -p, --port INTEGER    Port to run server on (default: 8080)
  -h, --host TEXT       Host to bind to (default: 127.0.0.1)
  -l, --list            List available spec versions and exit
  --no-auto-detect      Disable auto-detection (requires --version)
```

Launch a local Swagger UI server to browse the generated OpenAPI documentation.
If credentials are provided via environment variables (`OPNSENSE_URL`, `OPNSENSE_API_KEY`, `OPNSENSE_API_SECRET`), it acts as a proxy to the OPNsense instance, allowing you to test API calls directly from the browser.

### Display Tool Version

```bash
opnsense-openapi --version
```

## Development

### Running Tests

```bash
# Run all tests
just test

# Run with coverage
just coverage
```

### Code Quality

```bash
# Format code
just format

# Lint code
just lint
```

## Architecture

### Components

1. **Downloader** (`src/opnsense_openapi/downloader/`)
   - Clones OPNsense core repository from GitHub
   - Manages version-specific source code cache
   - Supports tag-based version selection

2. **Parser** (`src/opnsense_openapi/parser/`)
   - Parses PHP controller files using regex
   - Extracts namespace, class, and method information
   - Determines HTTP methods and parameters

3. **Generator** (`src/opnsense_openapi/generator/`)
   - Generates OpenAPI 3.0 specifications from PHP source
   - Infers response schemas from controller patterns
   - Creates reusable spec files for each version

4. **Client** (`src/opnsense_openapi/client/`)
   - Base HTTP client with OPNsense authentication
   - Handles API key/secret via Basic Auth
   - Auto-generates Python client on first use
   - Provides version-agnostic API access

### How It Works

**Quick Setup (Recommended):**
```bash
opnsense-openapi setup 25.7.6
```

**Or step-by-step:**
1. **Download**: Clone OPNsense core repository for specified version
2. **Parse**: Scan `src/opnsense/mvc/app/controllers/OPNsense/*/Api/` for controllers
3. **Extract**: Parse controller classes to find public `*Action()` methods
4. **Generate Spec**: Create OpenAPI 3.0 specification from parsed controllers
5. **Auto-Generate Client**: When accessing `client.api`, automatically generate Python client if spec exists
6. **Use**: Call API methods with full type hints and IDE autocomplete

The auto-generation step (5) happens seamlessly on first use. If the OpenAPI spec exists for your version, the Python client is generated automatically (takes ~2 minutes). Subsequent uses are instant.

### URL Mapping

OPNsense API URLs follow the pattern:
```
/api/{module}/{controller}/{command}/[params]
```

For example:
- PHP: `OPNsense\Firewall\Api\AliasController::searchItemAction()`
- URL: `/api/firewall/alias/searchItem`
- Python: `api.firewall.alias_search_item()`

The version-agnostic wrapper automatically maps Python function names to API endpoints.

## Example: Generated Code Structure

```
src/opnsense_openapi/
├── generated/
│   └── v25_7_6/                    # Version-specific generated client
│       └── opnsense_openapi_client/
│           ├── __init__.py
│           ├── client.py           # HTTP client
│           ├── models/             # Response models
│           └── api/                # API endpoints
│               ├── core/           # Core module
│               │   ├── core_firmware_info.py
│               │   └── core_firmware_status.py
│               └── firewall/       # Firewall module
│                   ├── firewall_alias_search_item.py
│                   └── firewall_alias_get_item.py
└── client/
    ├── base.py                     # OPNsenseClient with auto-detection
    └── generated_api.py            # Version-agnostic wrapper

# Users access via version-agnostic API:
# api.core.firmware_info()
# api.firewall.alias_search_item()
```

## Limitations

- Requires git to be installed for downloading OPNsense source
- Requires `openapi-python-client` for auto-generating Python clients
- First-time client generation takes ~2 minutes (subsequent uses are instant)
- Some complex XML model definitions may not parse perfectly
- Requires access to OPNsense instance for version auto-detection

## Contributing

See `CLAUDE.md` for development guidelines and coding standards.

## License

See LICENSE file for details.
