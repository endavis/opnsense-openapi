"""Tests for tools/generate_matrix_versions.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.generate_matrix_versions import main


def test_prints_json_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for name in ["opnsense-24.7.9.json", "opnsense-24.7.12.json", "opnsense-25.1.json"]:
        (tmp_path / name).write_text("{}", encoding="utf-8")
    assert main(["--specs-dir", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == '["24.7.12","25.1"]'


def test_empty_dir_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--specs-dir", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "No bundled specs" in captured.err


def test_bundled_default(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    versions = json.loads(capsys.readouterr().out)
    assert isinstance(versions, list)
    assert versions
