# Default recipe
default:
    @just --list

# Install dependencies
install:
    uv pip install -e ".[dev]"

# Run tests
test:
    uv run pytest

# Run tests with coverage
coverage:
    uv run pytest --cov-report=html
    @echo "Coverage report generated in htmlcov/index.html"

# Format code
format:
    uv run ruff format src/ tests/
    uv run ruff check --fix src/ tests/

# Lint code
lint:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/
    uv run mypy src/

# Generate wrapper for a specific OPNsense version
generate version="24.7":
    uv run opnsense-openapi generate {{version}}

# Clean temporary files
clean:
    rm -rf tmp/ htmlcov/ .coverage .pytest_cache/ .ruff_cache/ .mypy_cache/
    find . -type d -name __pycache__ -exec rm -rf {} +

# Build package
build: clean-dist
    uv build

# Clean dist folder
clean-dist:
    rm -rf dist/

# Upload to PyPI (requires PYPI_TOKEN environment variable)
publish: build
    uvx twine upload dist/* -u __token__ -p $PYPI_TOKEN

# Upload to TestPyPI for testing (requires TEST_PYPI_TOKEN environment variable)
publish-test: build
    uvx twine upload --repository testpypi dist/* -u __token__ -p $TEST_PYPI_TOKEN

# Bump version (usage: just bump patch|minor|major)
bump part="patch":
    #!/usr/bin/env bash
    current=$(grep 'version = ' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
    IFS='.' read -r major minor patch <<< "$current"
    case "{{part}}" in
        major) new="$((major + 1)).0.0" ;;
        minor) new="${major}.$((minor + 1)).0" ;;
        patch) new="${major}.${minor}.$((patch + 1))" ;;
        *) echo "Usage: just bump patch|minor|major"; exit 1 ;;
    esac
    sed -i "s/version = \"$current\"/version = \"$new\"/" pyproject.toml
    sed -i "s/__version__ = \"$current\"/__version__ = \"$new\"/" src/opnsense_openapi/__init__.py
    echo "Bumped version: $current -> $new"
