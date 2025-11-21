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
    uv run black src/ tests/
    uv run ruff check --fix src/ tests/

# Lint code
lint:
    uv run black --check src/ tests/
    uv run ruff check src/ tests/
    uv run mypy src/

# Generate wrapper for a specific OPNsense version
generate version="24.7":
    uv run opnsense-gen generate {{version}}

# Clean temporary files
clean:
    rm -rf tmp/ htmlcov/ .coverage .pytest_cache/ .ruff_cache/ .mypy_cache/
    find . -type d -name __pycache__ -exec rm -rf {} +
