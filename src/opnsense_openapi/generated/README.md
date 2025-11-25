# Generated Clients Directory

This directory contains auto-generated Python clients for different OPNsense versions.

## Auto-Generation

Python clients are **automatically generated** when you first access `client.api` if:
1. The OpenAPI spec exists for your version
2. The generated client doesn't exist yet
3. `openapi-python-client` is installed

Generation takes ~2 minutes on first use. Subsequent uses are instant.

## Directory Structure

Generated clients are stored in version-specific directories:
```
generated/
├── v24_7_1/
│   └── opnsense_openapi_client/
├── v25_7_5/
│   └── opnsense_openapi_client/
└── v25_7_6/
    └── opnsense_openapi_client/
```

## Manual Generation (Optional)

If you prefer to pre-generate clients:

```bash
opnsense-openapi build-client --version 25.7.6
```

## Note

Generated clients are **not tracked in git** - they are created locally as needed.
