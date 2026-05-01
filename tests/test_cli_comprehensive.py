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
    assert f"Generated {Path('output/spec.json')}" in result.stdout

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


# === Build Client: install hint, auto-detect, overwrite, no version ===


@patch("shutil.which")
def test_build_client_install_hint_emitted(mock_which):
    """Missing openapi-python-client tool emits the install hint (cli.py:344)."""
    mock_which.return_value = None

    result = runner.invoke(app, ["build-client", "--version", "25.7.6"])

    assert result.exit_code == 1
    # Stderr carries the secho error; stdout carries the typer.echo install hint.
    assert "uv tool install openapi-python-client" in result.stdout


@patch("shutil.which")
@patch("subprocess.check_call")
@patch("opnsense_openapi.client.OPNsenseClient")
def test_build_client_auto_detects_version(
    mock_client_cls,
    mock_call,
    mock_which,
    mock_find_spec,
):
    """build-client without --version uses OPNsenseClient auto-detect."""
    mock_which.return_value = "/usr/bin/openapi-python-client"
    mock_find_spec.return_value = Path("spec.json")
    mock_client_cls.return_value._detected_version = "24.7.5"

    result = runner.invoke(app, ["build-client"])

    assert result.exit_code == 0
    # The detected version should appear in output and used for spec lookup.
    assert "24.7.5" in result.stdout
    mock_find_spec.assert_called_once_with("24.7.5")


@patch("shutil.which")
@patch("subprocess.check_call")
@patch("opnsense_openapi.client.OPNsenseClient")
def test_build_client_auto_detect_failure_then_no_version(
    mock_client_cls,
    mock_call,
    mock_which,
):
    """If auto-detect raises and no --version is given, command exits with hint."""
    mock_which.return_value = "/usr/bin/openapi-python-client"
    mock_client_cls.side_effect = Exception("network down")

    result = runner.invoke(app, ["build-client"])

    assert result.exit_code == 1
    assert "Please specify --version" in result.stderr


@patch("shutil.which")
@patch("subprocess.check_call")
def test_build_client_no_spec_found(mock_call, mock_which, mock_find_spec):
    """build-client surfaces 'No spec found' when find_best_matching_spec raises."""
    mock_which.return_value = "/usr/bin/openapi-python-client"
    mock_find_spec.side_effect = FileNotFoundError

    result = runner.invoke(app, ["build-client", "--version", "25.7.6"])

    assert result.exit_code == 1
    assert "No spec found" in result.stderr


@patch("shutil.which")
@patch("subprocess.check_call")
def test_build_client_overwrite_passes_flag(mock_call, mock_which, mock_find_spec):
    """--overwrite must propagate to the openapi-python-client subprocess command."""
    mock_which.return_value = "/usr/bin/openapi-python-client"
    mock_find_spec.return_value = Path("spec.json")

    result = runner.invoke(app, ["build-client", "--version", "25.7.6", "--overwrite"])

    assert result.exit_code == 0
    cmd = mock_call.call_args.args[0]
    assert "--overwrite" in cmd


@patch("shutil.which")
@patch("subprocess.check_call")
def test_build_client_custom_output_path(mock_call, mock_which, mock_find_spec, tmp_path):
    """When --output is provided, the explicit path is used (skips default-version dir branch)."""
    mock_which.return_value = "/usr/bin/openapi-python-client"
    mock_find_spec.return_value = Path("spec.json")
    custom = tmp_path / "client_out"

    result = runner.invoke(app, ["build-client", "--version", "25.7.6", "--output", str(custom)])

    assert result.exit_code == 0
    cmd = mock_call.call_args.args[0]
    assert str(custom) in cmd


# === Validate: spec-found / detected-version branches ===


def test_validate_no_version_and_detect_fails(mock_client_init):
    """validate() exits with 'Could not determine version' when detect returns None."""
    # Construct a client whose _detected_version is None
    instance = MagicMock()
    instance._detected_version = None
    mock_client_init.return_value = instance

    with patch.dict(
        "os.environ", {"OPNSENSE_URL": "x", "OPNSENSE_API_KEY": "x", "OPNSENSE_API_SECRET": "x"}
    ):
        result = runner.invoke(app, ["validate"])  # No --version

    assert result.exit_code == 1
    assert "Could not determine version" in result.stderr


def test_validate_uses_detected_version(mock_client_init, mock_find_spec, mock_validator):
    """validate() picks up client._detected_version when --version omitted."""
    instance = MagicMock()
    instance._detected_version = "25.1.0"
    mock_client_init.return_value = instance

    mock_find_spec.return_value = Path("spec.json")
    mock_validator.return_value.validate_endpoints.return_value = []

    with patch.dict(
        "os.environ", {"OPNSENSE_URL": "x", "OPNSENSE_API_KEY": "x", "OPNSENSE_API_SECRET": "x"}
    ):
        result = runner.invoke(app, ["validate"])

    assert result.exit_code == 0
    assert "Detected version: 25.1.0" in result.stdout


def test_validate_skipped_result(mock_client_init, mock_find_spec, mock_validator):
    """validate() prints SKIPPED for results that are neither valid nor errored."""
    mock_find_spec.return_value = Path("spec.json")
    mock_validator.return_value.validate_endpoints.return_value = [
        {
            "path": "/api/skipped",
            "method": "GET",
            "valid": False,
            "error": None,
            "status": None,
        }
    ]

    with patch.dict(
        "os.environ", {"OPNSENSE_URL": "x", "OPNSENSE_API_KEY": "x", "OPNSENSE_API_SECRET": "x"}
    ):
        result = runner.invoke(app, ["validate", "--version", "25.7.6"])

    assert result.exit_code == 0
    assert "SKIPPED" in result.stdout
    assert "0 passed, 0 failed, 1 skipped" in result.stdout


def test_validate_long_path_is_truncated(mock_client_init, mock_find_spec, mock_validator):
    """validate() truncates long paths (>50 chars) with '...' when printing."""
    long_path = "/api/" + "x" * 80
    mock_find_spec.return_value = Path("spec.json")
    mock_validator.return_value.validate_endpoints.return_value = [
        {
            "path": long_path,
            "method": "GET",
            "valid": True,
            "error": None,
            "status": 200,
        }
    ]

    with patch.dict(
        "os.environ", {"OPNSENSE_URL": "x", "OPNSENSE_API_KEY": "x", "OPNSENSE_API_SECRET": "x"}
    ):
        result = runner.invoke(app, ["validate", "--version", "25.7.6"])

    assert result.exit_code == 0
    # Truncation marker
    assert "..." in result.stdout
    # Full long path should not appear unbroken
    assert long_path not in result.stdout


# === Setup Command Tests (3-step orchestration) ===


@patch("shutil.which")
@patch("subprocess.check_call")
def test_setup_success(
    mock_call,
    mock_which,
    mock_downloader,
    mock_parser,
    mock_generator,
):
    """Full setup orchestration: download -> generate -> build-client."""
    mock_which.return_value = "/usr/bin/openapi-python-client"

    dl = mock_downloader.return_value
    dl.download.return_value = Path("/tmp/source/src/opnsense/mvc/app/controllers")

    parser_inst = mock_parser.return_value
    parser_inst.parse_directory.return_value = [MagicMock()]

    gen_inst = mock_generator.return_value
    gen_inst.generate.return_value = Path("/tmp/spec.json")

    result = runner.invoke(app, ["setup", "25.7.6"])

    assert result.exit_code == 0
    # All three orchestration banners should fire.
    assert "[1/3]" in result.stdout
    assert "[2/3]" in result.stdout
    assert "[3/3]" in result.stdout
    assert "Setup complete" in result.stdout
    dl.download.assert_called_once()
    parser_inst.parse_directory.assert_called_once()
    gen_inst.generate.assert_called_once()
    mock_call.assert_called_once()


@patch("shutil.which")
def test_setup_missing_openapi_python_client(mock_which):
    """setup early-exits with install hint when openapi-python-client is absent."""
    mock_which.return_value = None

    result = runner.invoke(app, ["setup", "25.7.6"])

    assert result.exit_code == 1
    assert "uv tool install openapi-python-client" in result.stdout


@patch("shutil.which")
def test_setup_download_failure(mock_which, mock_downloader):
    """setup propagates a RuntimeError from the downloader as exit code 1."""
    mock_which.return_value = "/usr/bin/openapi-python-client"
    mock_downloader.return_value.download.side_effect = RuntimeError("git failure")

    result = runner.invoke(app, ["setup", "25.7.6"])

    assert result.exit_code == 1
    assert "git failure" in result.stderr


@patch("shutil.which")
@patch("subprocess.check_call")
def test_setup_build_client_subprocess_failure(
    mock_call,
    mock_which,
    mock_downloader,
    mock_parser,
    mock_generator,
):
    """setup surfaces subprocess.CalledProcessError from the build-client step."""
    mock_which.return_value = "/usr/bin/openapi-python-client"

    dl = mock_downloader.return_value
    dl.download.return_value = Path("/tmp/source/src/opnsense/mvc/app/controllers")

    mock_parser.return_value.parse_directory.return_value = [MagicMock()]
    mock_generator.return_value.generate.return_value = Path("/tmp/spec.json")
    mock_call.side_effect = subprocess.CalledProcessError(1, "openapi-python-client")

    result = runner.invoke(app, ["setup", "25.7.6"])

    assert result.exit_code == 1
    assert "Error generating client" in result.stderr


@patch("shutil.which")
@patch("subprocess.check_call")
def test_setup_overwrite_flag_propagates(
    mock_call,
    mock_which,
    mock_downloader,
    mock_parser,
    mock_generator,
):
    """setup --overwrite must reach the openapi-python-client subprocess command."""
    mock_which.return_value = "/usr/bin/openapi-python-client"
    mock_downloader.return_value.download.return_value = Path(
        "/tmp/source/src/opnsense/mvc/app/controllers"
    )
    mock_parser.return_value.parse_directory.return_value = [MagicMock()]
    mock_generator.return_value.generate.return_value = Path("/tmp/spec.json")

    result = runner.invoke(app, ["setup", "25.7.6", "--overwrite"])

    assert result.exit_code == 0
    cmd = mock_call.call_args.args[0]
    assert "--overwrite" in cmd


@patch("shutil.which")
@patch("subprocess.check_call")
def test_setup_custom_output_path(
    mock_call,
    mock_which,
    mock_downloader,
    mock_parser,
    mock_generator,
    tmp_path,
):
    """setup --output overrides the default version-derived output directory."""
    mock_which.return_value = "/usr/bin/openapi-python-client"
    mock_downloader.return_value.download.return_value = Path(
        "/tmp/source/src/opnsense/mvc/app/controllers"
    )
    mock_parser.return_value.parse_directory.return_value = [MagicMock()]
    mock_generator.return_value.generate.return_value = Path("/tmp/spec.json")

    custom = tmp_path / "out_dir"
    result = runner.invoke(app, ["setup", "25.7.6", "--output", str(custom)])

    assert result.exit_code == 0
    cmd = mock_call.call_args.args[0]
    assert str(custom) in cmd
