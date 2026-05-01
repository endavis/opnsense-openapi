# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


### Added
- First release
- Core functionality
- Documentation
- Test coverage

[Unreleased]: https://github.com/username/package_name/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/username/package_name/releases/tag/v0.1.0

## Unreleased

### BREAKING CHANGE

- find_best_matching_spec(version) now defaults to
mode="floor" instead of returning the highest committed
major.minor.x. Callers that need the prior behavior must pass
mode="highest" explicitly. Floor mode also raises FileNotFoundError
when no committed spec is at or below the request, instead of
silently returning a spec above the box.

### Fix

- raise APIResponseError on non-JSON responses in post() (merges PR #45, addresses #44)
- distinguish codegen failure modes in OPNsenseClient.api (merges PR #43, addresses #33)
- emit snake_case controller segments in generated URL paths (merges PR #36, addresses #32)

### Refactor

- stabilize generated-client module path; add floor spec matching (merges PR #42, addresses #34)

## v0.3.0 (2026-04-23)

### Feat

- add specs for OPNsense 26.1.2-26.1.6 (merges PR #11, addresses #10)

## v0.2.0 (2026-02-11)

### Feat

- add specs for OPNsense 25.7.8–25.7.11 and 26.1–26.1.1

### Fix

- add mypy type ignore for optional flask import
- make flask import lazy in CLI to avoid ImportError without ui extras

## v0.1.0 (2025-11-25)

### Feat

- Comprehensive OpenAPI spec generation and validation improvements (#1)
- add truly version-agnostic API access with GeneratedAPI wrapper
- add .api property for generated client with auto-detection
- add CORS proxy support to Swagger UI server
- add serve-docs CLI command and declare dependencies
- add Swagger UI server for browsing API docs
- improve diagnostic script to test GET and POST methods
- add API diagnostics script for troubleshooting
- integrate OpenAPI wrapper with OPNsense client
- add TypedDict definitions for structured return types
- enhance error messages with contextual information
- make SSL verification configurable
- add version string validation
- add OpenAPI specs for OPNSense versions 24.1-25.7
- add PyPI publishing workflow
- add bundled specs directory with helper functions
- **cli**: add generate command for OpenAPI spec creation
- **generator**: add path parameters to OpenAPI URLs
- **openapi**: suppress SSL warnings for self-signed certs
- **openapi**: add get_response_schema_for_endpoint method
- **openapi**: add basic auth helper with api_key/api_secret params
- initial commit - OPNsense API wrapper generator

### Fix

- correct generated package name from op_nsense to opnsense
- convert boolean/enum defaults to proper JSON types in OpenAPI spec
- resolve ruff linting errors
- handle missing endpoints gracefully in basic_usage example
- remove default Content-Type header causing 400 errors
- improve version detection robustness and error handling
- improve JSON parsing error handling
- add XML parsing error logging in model parser
- clear model cache between generate() calls
- add JSON decode error handling in HTTP client
- merge OpenAPI paths instead of overwriting
- add UTF-8 encoding to file write operations
- parser regex to match ApiControllerBase

### Perf

- **openapi**: add caching for _get_operation lookups

### Refactor

- update basic_usage.py with OpenAPI integration
- use slicing instead of del for list manipulation
- extract magic strings to class constants
- extract duplicate describe() into _describe_schema()
- migrate from requests to httpx
- replace print() with logging in downloader
- extract shared string conversion to utils.py
- remove unused openapi.py module
- **openapi**: improve error handling with exceptions
- **openapi**: remove __desc__ and __required__ noise from samples
- **openapi**: modernize type hints and move imports
