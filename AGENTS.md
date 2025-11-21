# OPNSense API wrapper – AI Agent Unified Instructions

## Overview
Generate a lightweight wrapper for opnsense API endpoints.
It takes an opnsense version and downloads the relevant files
for that version to create a python wrapper for that version's api.

## Repository & Architecture
- TODO : add

## State, Data Flow, and Artifacts
- TODO : add

## Configuration & Secrets
- TODO : add

## Development & Testing
- **Use `just` for command for setup**
- **Use `uv` for Python environment and package management**
- **Run tests:** `just test` or `uv run pytest`
- **Format/lint:** `just format`, `just lint`
- **Coverage:** `just coverage`
- **Add dependencies:** `uv pip install <package>`
- **Temporary files:** Use `tmp/` (git-ignored); keep root directory clean

## CLI & Operations

## Code Style & Conventions
- Python 3.12+ type hints, `@override` decorator
- Black formatting, ruff linting, max line length 100
- Snake_case for Python, kebab-case for YAML resource names
- Use singular resource type names

## Coding Standards & Best Practices
- **Read-before-edit**: inspect files before modifying; maintain backward-compatible public APIs.
- Python style: full type hints with modern syntax (`list[str]`, `X | None`), `@override` on abstract implementations, max line 100, Google-style docstrings.
- Error handling: raise specific exceptions with contextual logging; never catch `KeyboardInterrupt`/`SystemExit`. Prefer early returns over deep nesting.
- Avoid duplication in validators/templates; consider mixins or helpers before copying logic.

## Commit Guidelines
- Use Conventional Commits: `feat`, `fix`, `refactor`, `docs`, etc.
- Markdown formatting for detailed commits
- Separate commits for refactoring, docs, tests, cleanup, dependencies

## Testing Expectations
- Maintain ≥69% coverage
- Add/update tests when refactoring or adding features; use fixtures and mocks
- Typical commands:
  - `uv run pytest`

## Troubleshooting
- Use CLI commands to check config loading, state, and secrets
- Inspect files with `cat -pp` or `batcat -pp` for consistent output

## Help & Resources
- Repository docs: `docs/`
- Issues/roadmap: GitHub issues referenced in `AGENTS.md`
- Contact: Use repo discussion/issues per AGENTS guidance.

---
This file unifies essential agent instructions for this project. For coding/development specifics, see dedicated documentation files.
