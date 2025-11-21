# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a lightweight Python wrapper generator for OPNSense API endpoints. The tool takes an OPNSense version, downloads the relevant API files for that version, and generates a Python wrapper for that version's API.

## Development Commands

**Build/Setup:**
- `just` - Run default setup tasks

**Testing:**
- `just test` or `uv run pytest` - Run test suite
- `just coverage` - Generate coverage report
- Target: Maintain ≥69% test coverage

**Code Quality:**
- `just format` - Format code with Black
- `just lint` - Lint code with Ruff

**Dependencies:**
- `uv pip install <package>` - Add new dependencies

**Note:** Use `tmp/` directory for temporary files (git-ignored). Keep root directory clean.

## Technology Stack

- **Python:** 3.12+ with full type hints
- **Package Manager:** `uv` for Python environment and package management
- **Task Runner:** `just` (justfile) for common commands
- **Formatter:** Black (max line length 100)
- **Linter:** Ruff

## Code Style

- Python 3.12+ type hints using modern syntax (`list[str]`, `X | None`)
- Use `@override` decorator on abstract implementations
- Snake_case for Python identifiers
- Kebab-case for YAML resource names
- Use singular resource type names
- Max line length: 100 characters
- Google-style docstrings

## Python Standards

- Full type hints with modern syntax
- Specific exceptions with contextual logging
- Never catch `KeyboardInterrupt` or `SystemExit`
- Prefer early returns over deep nesting
- Read files before editing to maintain backward-compatible public APIs
- Avoid duplication - consider mixins or helpers before copying logic

## Commit Conventions

Use Conventional Commits format:
- `feat:` - New features
- `fix:` - Bug fixes
- `refactor:` - Code refactoring
- `docs:` - Documentation changes
- `test:` - Test changes
- `chore:` - Maintenance tasks

Separate commits for: refactoring, docs, tests, cleanup, dependencies.

## Testing Requirements

- Add/update tests when refactoring or adding features
- Use fixtures and mocks appropriately
- Maintain minimum 69% code coverage
