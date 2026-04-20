# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a lightweight Python wrapper generator for OPNSense API endpoints. The tool takes an OPNSense version, downloads the relevant API files for that version, and generates a Python wrapper for that version's API.

The project follows the [`pyproject-template`](https://github.com/endavis/pyproject-template) conventions: `uv` for environments, `doit` as task runner, `hatch-vcs` for git-tag-driven versioning, `ruff` + `mypy` for quality checks, and `commitizen` for releases.

## Development Commands

Run `uv run doit list` to see every available task. Common ones:

**Setup:**
- `uv sync --all-extras --dev` - Install with dev + security + ui extras
- `uv run doit install_dev` - Same, via doit
- `uv run doit pre_commit_install` - Install git pre-commit hooks

**Testing:**
- `uv run doit test` - Run pytest in parallel (`-n auto`)
- `uv run doit coverage` - Run with coverage reporting to `tmp/htmlcov/`
- `uv run doit mutate` - Mutation testing (mutmut)

**Code Quality:**
- `uv run doit check` - Runs format_check, lint, type_check, security, spell_check, test (CI gate)
- `uv run doit format` - Format code with Ruff
- `uv run doit lint` - Ruff lint only
- `uv run doit type_check` - Mypy on src/
- `uv run doit security` - Bandit scan (requires `security` extra)
- `uv run doit deadcode` / `complexity` / `maintainability` - Radon + vulture reports

**Project-specific:**
- `uv run doit generate -v 24.7` - Generate wrapper for an OPNsense version (replaces old `just generate`)

**Docs:**
- `uv run doit docs_serve` - Serve mkdocs site locally
- `uv run doit docs_build` - Build static site to `site/`

**Release:**
- Versioning is dynamic via git tags (hatch-vcs) — do NOT set `version = "..."` in `pyproject.toml`.
- `uv run doit release` - Automated release via commitizen (bump + changelog + tag + push)
- `uv run doit bump` / `changelog` - Individual steps

**Note:** Use `tmp/` directory for temporary files (git-ignored). Keep root directory clean.

## Template Sync

This project is synchronized with `pyproject-template` using the official management tooling:

- `python tools/pyproject_template/manage.py check` - Compare against latest template
- `python tools/pyproject_template/manage.py sync` - Record sync point (auto-commits `.config/pyproject_template/settings.toml`)
- Current sync state: see `.config/pyproject_template/settings.toml`
- Sync workflow: [docs/template/ai-sync-checklist.md](docs/template/ai-sync-checklist.md)

Project-specific doit tasks live in `tools/doit/project.py` and will not be overwritten during template syncs.

## Technology Stack

- **Python:** 3.12 / 3.13 / 3.14 matrix
- **Package Manager:** `uv`
- **Task Runner:** `doit` (auto-discovers tasks from `tools/doit/`)
- **Build Backend:** `hatchling` + `hatch-vcs` (version from git tags)
- **Linter/Formatter:** Ruff (line length 100)
- **Type Checker:** mypy (strict config) + pyright (LSP)
- **Testing:** pytest + pytest-cov + pytest-xdist + hypothesis + mutmut
- **Docs:** mkdocs-material + mkdocstrings

## Code Style

- Python 3.12+ type hints using modern syntax (`list[str]`, `X | None`)
- Use `@override` decorator on abstract implementations
- Snake_case for Python identifiers, kebab-case for YAML resource names
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

Conventional Commits enforced via commitizen + pre-commit hook:

- `feat:` - New features
- `fix:` - Bug fixes
- `refactor:` - Code refactoring
- `docs:` - Documentation changes
- `test:` - Test changes
- `chore:` - Maintenance tasks

Direct commits to `main` are blocked by a pre-commit hook. Workflow: Issue → Branch → Commit → PR → Merge. Branch names must match `<type>/<issue#>-<description>` (or `release/<version>`).

## Testing Requirements

- Add/update tests when refactoring or adding features
- Use fixtures and mocks appropriately
- Coverage threshold: 80% (`[tool.coverage.report] fail_under = 80`). Current coverage (~52%) is below threshold — improving test coverage is a tracked follow-up.
