from pathlib import Path

from typer.testing import CliRunner

from opnsense_api.cli import app


runner = CliRunner()


def test_download_command_success(tmp_path, monkeypatch):
    controllers_path = tmp_path / "24.1" / "src"
    controllers_path.mkdir(parents=True)

    def fake_download(self, version: str, force: bool = False):  # noqa: ANN001
        assert version == "24.1"
        return controllers_path

    monkeypatch.setattr("opnsense_api.cli.SourceDownloader.download", fake_download)

    result = runner.invoke(app, ["download", "24.1", "--dest", str(tmp_path)])

    assert result.exit_code == 0
    assert "Stored controller files for 24.1" in result.stdout
    assert str(controllers_path) in result.stdout


def test_download_command_failure(tmp_path, monkeypatch):
    def fake_download(self, version: str, force: bool = False):  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr("opnsense_api.cli.SourceDownloader.download", fake_download)

    result = runner.invoke(app, ["download", "24.1", "--dest", str(tmp_path)])

    assert result.exit_code == 1
    assert "boom" in result.stderr
