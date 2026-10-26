"""Tests for CLI commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from opnsense_openapi import __version__
from opnsense_openapi.cli import app
from opnsense_openapi.parser import ApiController, ApiEndpoint

runner = CliRunner()


def test_download_command_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    controllers_path = tmp_path / "24.1" / "src"
    controllers_path.mkdir(parents=True)

    def fake_download(self: object, version: str, force: bool = False) -> Path:
        assert version == "24.1"
        return controllers_path

    monkeypatch.setattr("opnsense_openapi.cli.SourceDownloader.download", fake_download)

    result = runner.invoke(app, ["download", "24.1", "--dest", str(tmp_path)])

    assert result.exit_code == 0
    assert "Stored controller files for 24.1" in result.stdout
    assert str(controllers_path) in result.stdout


def test_download_command_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_download(self: object, version: str, force: bool = False) -> Path:
        raise RuntimeError("boom")

    monkeypatch.setattr("opnsense_openapi.cli.SourceDownloader.download", fake_download)

    result = runner.invoke(app, ["download", "24.1", "--dest", str(tmp_path)])

    assert result.exit_code == 1
    assert "boom" in result.stderr


def test_version_option() -> None:
    """Test --version option."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_generate_command_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test generate command success."""
    controllers_path = tmp_path / "controllers"
    controllers_path.mkdir()

    def fake_download(self: object, version: str, force: bool = False) -> Path:
        return controllers_path

    def fake_parse_directory(self: object, path: Path) -> list[ApiController]:
        return [
            ApiController(
                module="Test",
                controller="TestCtrl",
                base_class="ApiControllerBase",
                endpoints=[ApiEndpoint(name="get", method="GET", description="Get", parameters=[])],
            )
        ]

    monkeypatch.setattr("opnsense_openapi.cli.SourceDownloader.download", fake_download)
    monkeypatch.setattr(
        "opnsense_openapi.cli.ControllerParser.parse_directory", fake_parse_directory
    )

    output_dir = tmp_path / "output"
    result = runner.invoke(app, ["generate", "24.7", "--output", str(output_dir)])

    assert result.exit_code == 0
    assert "Generated" in result.stdout


def test_generate_command_download_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test generate command when download fails."""

    def fake_download(self: object, version: str, force: bool = False) -> Path:
        raise RuntimeError("download failed")

    monkeypatch.setattr("opnsense_openapi.cli.SourceDownloader.download", fake_download)

    result = runner.invoke(app, ["generate", "24.7", "--output", str(tmp_path)])

    assert result.exit_code == 1
    assert "download failed" in result.stderr
