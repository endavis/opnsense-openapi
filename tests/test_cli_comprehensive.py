"""Comprehensive tests for the CLI."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from opnsense_openapi.cli import app

runner = CliRunner()


@pytest.fixture
def mock_downloader():
    with patch("opnsense_openapi.cli.SourceDownloader") as mock:
        yield mock


@pytest.fixture
def mock_parser():
    with patch("opnsense_openapi.cli.ControllerParser") as mock:
        yield mock


@pytest.fixture
def mock_generator():
    with patch("opnsense_openapi.cli.OpenApiGenerator") as mock:
        yield mock


@pytest.fixture
def mock_find_spec():
    with patch("opnsense_openapi.cli.find_best_matching_spec") as mock:
        yield mock


@pytest.fixture
def mock_client_init():
    with patch("opnsense_openapi.client.OPNsenseClient") as mock:
        yield mock


@pytest.fixture
def mock_validator():
    with patch("opnsense_openapi.cli.SpecValidator") as mock:
        yield mock


# === Download Command Tests ===


def test_download_success(mock_downloader):
    """Test successful download."""
    instance = mock_downloader.return_value
    instance.download.return_value = Path("tmp/controllers")

    result = runner.invoke(app, ["download", "25.7.6"])

    assert result.exit_code == 0
    assert "Stored controller files" in result.stdout
    instance.download.assert_called_once_with("25.7.6", force=False)


def test_download_options(mock_downloader):
    """Test download with options."""
    instance = mock_downloader.return_value
    instance.download.return_value = Path("custom/dir")

    result = runner.invoke(app, ["download", "24.7", "--dest", "custom", "--force"])

    assert result.exit_code == 0
    instance.download.assert_called_once_with("24.7", force=True)
    mock_downloader.assert_called_once_with(cache_dir=Path("custom"))


def test_download_failure(mock_downloader):
    """Test download failure handling."""
    instance = mock_downloader.return_value
    instance.download.side_effect = RuntimeError("Download failed")

    result = runner.invoke(app, ["download", "25.7.6"])

    assert result.exit_code == 1
    assert "Download failed" in result.stderr


# === Generate Command Tests ===


def test_generate_success(mock_downloader, mock_parser, mock_generator):
    """Test successful generation."""
    # Setup mocks
    dl_instance = mock_downloader.return_value
    dl_instance.download.return_value = Path("tmp/source/src/opnsense/mvc/app/controllers")

    parser_instance = mock_parser.return_value
    parser_instance.parse_directory.return_value = [MagicMock()]

    gen_instance = mock_generator.return_value
    gen_instance.generate.return_value = Path("output/spec.json")

    result = runner.invoke(app, ["generate", "25.7.6", "--output", "out"])

    assert result.exit_code == 0
    assert "Generated output/spec.json" in result.stdout

    # Check logic flow
    dl_instance.download.assert_called_once()
    parser_instance.parse_directory.assert_called_once()
    gen_instance.generate.assert_called_once()


def test_generate_missing_models_warning(mock_downloader, mock_parser, mock_generator):
    """Test warning when models directory is missing."""
    # Setup mocks
    dl_instance = mock_downloader.return_value
    # Return a path that implies models dir won't exist relative to it in the mock fs
    dl_instance.download.return_value = Path("/non/existent/path/controllers")

    result = runner.invoke(app, ["generate", "25.7.6"])

    assert result.exit_code == 0
    assert "Warning: Models directory not found" in result.stdout


def test_generate_failure(mock_downloader):
    """Test generation failure at download stage."""
    mock_downloader.return_value.download.side_effect = RuntimeError("Git error")

    result = runner.invoke(app, ["generate", "25.7.6"])

    assert result.exit_code == 1
    assert "Git error" in result.stderr


# === Validate Command Tests ===


def test_validate_missing_credentials():
    """Test validation fails without env vars."""
    with patch.dict("os.environ", clear=True):
        result = runner.invoke(app, ["validate", "--version", "25.7.6"])
        assert result.exit_code == 1
        assert "Live validation requires credentials" in result.stderr


def test_validate_client_init_error(mock_client_init):
    """Test failure during client initialization."""
    mock_client_init.side_effect = Exception("Connection failed")

    with patch.dict(
        "os.environ", {"OPNSENSE_URL": "x", "OPNSENSE_API_KEY": "x", "OPNSENSE_API_SECRET": "x"}
    ):
        result = runner.invoke(app, ["validate", "--version", "25.7.6"])
        assert result.exit_code == 1
        assert "Failed to initialize client" in result.stderr


def test_validate_no_spec_found(mock_client_init, mock_find_spec):
    """Test validation fails if spec doesn't exist."""
    mock_find_spec.side_effect = FileNotFoundError

    with patch.dict(
        "os.environ", {"OPNSENSE_URL": "x", "OPNSENSE_API_KEY": "x", "OPNSENSE_API_SECRET": "x"}
    ):
        result = runner.invoke(app, ["validate", "--version", "25.7.6"])
        assert result.exit_code == 1
        assert "No spec found" in result.stderr


def test_validate_success(mock_client_init, mock_find_spec, mock_validator):
    """Test successful validation run."""
    mock_find_spec.return_value = Path("spec.json")

    # Mock validator yielding one valid result
    validator_instance = mock_validator.return_value
    validator_instance.validate_endpoints.return_value = [
        {"path": "/api/test", "method": "GET", "valid": True, "error": None, "status": 200}
    ]

    with patch.dict(
        "os.environ", {"OPNSENSE_URL": "x", "OPNSENSE_API_KEY": "x", "OPNSENSE_API_SECRET": "x"}
    ):
        result = runner.invoke(app, ["validate", "--version", "25.7.6"])

        assert result.exit_code == 0
        assert "Crawling up to 50 safe GET endpoints" in result.stdout
        assert "1 passed, 0 failed" in result.stdout


def test_validate_failure_count(mock_client_init, mock_find_spec, mock_validator):
    """Test validation with failures returns non-zero exit code."""
    mock_find_spec.return_value = Path("spec.json")

    validator_instance = mock_validator.return_value
    validator_instance.validate_endpoints.return_value = [
        {"path": "/api/bad", "method": "GET", "valid": False, "error": "Bad schema", "status": 200}
    ]

    with patch.dict(
        "os.environ", {"OPNSENSE_URL": "x", "OPNSENSE_API_KEY": "x", "OPNSENSE_API_SECRET": "x"}
    ):
        result = runner.invoke(app, ["validate", "--version", "25.7.6"])

        assert result.exit_code == 1
        assert "0 passed, 1 failed" in result.stdout


# === Build Client Command Tests ===


@patch("shutil.which")
def test_build_client_tool_missing(mock_which):
    """Test error when openapi-python-client is missing."""
    mock_which.return_value = None
    result = runner.invoke(app, ["build-client", "--version", "25.7.6"])
    assert result.exit_code == 1
    assert "'openapi-python-client' not found" in result.stderr


@patch("shutil.which")
@patch("subprocess.check_call")
def test_build_client_success(mock_call, mock_which, mock_find_spec):
    """Test successful client build."""
    mock_which.return_value = "/usr/bin/openapi-python-client"
    mock_find_spec.return_value = Path("spec.json")

    result = runner.invoke(app, ["build-client", "--version", "25.7.6"])

    assert result.exit_code == 0
    assert "Client generated successfully" in result.stdout
    mock_call.assert_called_once()


@patch("shutil.which")
@patch("subprocess.check_call")
def test_build_client_failure(mock_call, mock_which, mock_find_spec):
    """Test failure during subprocess execution."""
    mock_which.return_value = "/usr/bin/openapi-python-client"
    mock_find_spec.return_value = Path("spec.json")
    mock_call.side_effect = subprocess.CalledProcessError(1, "cmd")

    result = runner.invoke(app, ["build-client", "--version", "25.7.6"])

    assert result.exit_code == 1
    assert "Error generating client" in result.stderr
