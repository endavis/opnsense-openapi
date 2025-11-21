# OPNsense API Python Wrapper Generator

Auto-generate Python client libraries for the OPNsense API by parsing controller source code from specific OPNsense versions.

## Overview

This tool downloads OPNsense source code from GitHub, parses PHP controller files to extract API endpoint definitions, and generates a type-hinted Python client library that mirrors the OPNsense API structure.

## Features

- **Version-specific**: Generate wrappers for any OPNsense version
- **Automatic parsing**: Extracts endpoints from PHP controller source code
- **Type hints**: Generated code uses Python 3.12+ type annotations
- **Structured clients**: Organized by module and controller
- **HTTP method detection**: Intelligently determines GET vs POST based on endpoint names

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

### Download Controller Sources

```bash
# Download controller files for OPNsense 24.7 into tmp/opnsense_source
uv run opnsense-wrapper download 24.7

# Store the snapshot in a custom directory
uv run opnsense-wrapper download 24.7 --dest tmp/releases --force
```

The `download` command clones the `opnsense/core` repository at the requested tag,
caches it under `tmp/opnsense_source/<version>/`, and extracts the controller
files that later steps of the wrapper pipeline will parse.

> Wrapper generation is still under construction; the example below shows how the
> produced client library will eventually be consumed.

### Use Generated Wrapper

```python
from opnsense_api.client import OPNsenseClient
from generated.firewall import Firewall

# Initialize client
client = OPNsenseClient(
    base_url="https://opnsense.local",
    api_key="your-api-key",
    api_secret="your-api-secret",
    verify_ssl=True
)

# Use generated API
firewall = Firewall(client)
aliases = firewall.alias_util.find_alias()
print(aliases)
```

## CLI Commands

### Download Controller Sources

```bash
opnsense-wrapper download [VERSION] [OPTIONS]

Options:
  -d, --dest PATH       Override the cache directory (default: tmp/opnsense_source)
  --force / --no-force  Re-download files even if cached
```

The command clones `https://github.com/opnsense/core` at the requested tag, caches
it locally, and extracts the controller files that downstream parsing and code
generation steps consume.

### Display Tool Version

```bash
opnsense-wrapper --version
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

1. **Downloader** (`src/opnsense_api/downloader/`)
   - Clones OPNsense core repository from GitHub
   - Manages version-specific source code cache
   - Supports tag-based version selection

2. **Parser** (`src/opnsense_api/parser/`)
   - Parses PHP controller files using regex
   - Extracts namespace, class, and method information
   - Determines HTTP methods and parameters

3. **Generator** (`src/opnsense_api/generator/`)
   - Generates Python module structure
   - Creates type-hinted method signatures
   - Organizes code by module and controller

4. **Client** (`src/opnsense_api/client/`)
   - Base HTTP client with OPNsense authentication
   - Handles API key/secret via Basic Auth
   - Provides GET/POST methods for API calls

### How It Works

1. **Download**: Clone OPNsense core repository for specified version
2. **Parse**: Scan `src/opnsense/mvc/app/controllers/OPNsense/*/Api/` for controllers
3. **Extract**: Parse controller classes to find public `*Action()` methods
4. **Generate**: Create Python classes mirroring the API structure
5. **Use**: Import generated modules and call methods with type hints

### URL Mapping

OPNsense API URLs follow the pattern:
```
/api/{module}/{controller}/{command}/[params]
```

For example:
- PHP: `OPNsense\Firewall\Api\AliasUtilController::findAliasAction()`
- URL: `/api/firewall/alias_util/findAlias`
- Python: `firewall.alias_util.find_alias()`

## Example: Generated Code Structure

```
generated/
├── __init__.py
├── firewall.py
│   └── class Firewall
│       └── class AliasUtil
│           ├── find_alias()
│           ├── get()
│           └── set()
└── system.py
    └── class System
        └── class Info
            └── version()
```

## Limitations

- Requires git to be installed for downloading source
- PHP parameter types not fully captured (uses `Any`)
- Some complex endpoints may need manual adjustment
- Documentation extraction is best-effort from PHP docblocks

## Contributing

See `CLAUDE.md` for development guidelines and coding standards.

## License

See LICENSE file for details.
