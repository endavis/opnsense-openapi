"""Tests for :mod:`opnsense_openapi.downloader.source_downloader`."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opnsense_openapi.downloader.source_downloader import SourceDownloader


def test_initializes_default_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SourceDownloader creates the default cache directory on init."""
    monkeypatch.chdir(tmp_path)
    downloader = SourceDownloader()
    assert downloader.cache_dir == Path("tmp/opnsense_source")
    assert downloader.cache_dir.exists()


def test_initializes_custom_cache_dir(tmp_path: Path) -> None:
    """SourceDownloader creates a caller-provided cache directory."""
    cache = tmp_path / "custom-cache"
    downloader = SourceDownloader(cache_dir=cache)
    assert downloader.cache_dir == cache
    assert cache.exists()


def test_download_rejects_invalid_version(tmp_path: Path) -> None:
    """download() raises ValueError for malformed version strings."""
    downloader = SourceDownloader(cache_dir=tmp_path)
    with pytest.raises(ValueError, match="Invalid version format"):
        downloader.download("not-a-version")


def test_download_returns_cached_controllers_when_present(tmp_path: Path) -> None:
    """download() skips cloning when the controllers directory already exists."""
    downloader = SourceDownloader(cache_dir=tmp_path)
    expected = tmp_path / "24.7" / SourceDownloader.CONTROLLERS_PATH
    expected.mkdir(parents=True)

    with patch.object(downloader, "_git_clone_tag") as clone:
        result = downloader.download("24.7")

    assert result == expected
    clone.assert_not_called()


def test_download_removes_cache_when_force(tmp_path: Path) -> None:
    """download(force=True) wipes the version directory before re-cloning."""
    downloader = SourceDownloader(cache_dir=tmp_path)
    version_dir = tmp_path / "24.7"
    controllers_dir = version_dir / SourceDownloader.CONTROLLERS_PATH
    controllers_dir.mkdir(parents=True)
    marker = version_dir / "stale.txt"
    marker.write_text("old")

    def fake_clone(_tag: str, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / SourceDownloader.CONTROLLERS_PATH).mkdir(parents=True, exist_ok=True)

    with patch.object(downloader, "_git_clone_tag", side_effect=fake_clone) as clone:
        downloader.download("24.7", force=True)

    assert not marker.exists()
    clone.assert_called_once()


def test_download_falls_back_to_v_prefixed_tag(tmp_path: Path) -> None:
    """download() retries with a ``v``-prefixed tag when the plain tag fails."""
    downloader = SourceDownloader(cache_dir=tmp_path)
    calls: list[str] = []

    def fake_clone(tag: str, target: Path) -> None:
        calls.append(tag)
        if tag == "24.7":
            raise RuntimeError("tag not found")
        target.mkdir(parents=True, exist_ok=True)
        (target / SourceDownloader.CONTROLLERS_PATH).mkdir(parents=True, exist_ok=True)

    with patch.object(downloader, "_git_clone_tag", side_effect=fake_clone):
        result = downloader.download("24.7")

    assert calls == ["24.7", "v24.7"]
    assert result.exists()


def test_download_raises_runtime_error_when_both_tags_fail(tmp_path: Path) -> None:
    """download() wraps both clone failures in a RuntimeError."""
    downloader = SourceDownloader(cache_dir=tmp_path)

    def fake_clone(_tag: str, _target: Path) -> None:
        raise RuntimeError("nope")

    with (
        patch.object(downloader, "_git_clone_tag", side_effect=fake_clone),
        pytest.raises(RuntimeError, match=r"Failed to download OPNsense version 24\.7"),
    ):
        downloader.download("24.7")


def test_download_raises_if_controllers_missing_after_clone(tmp_path: Path) -> None:
    """download() errors if the controllers directory is absent post-clone."""
    downloader = SourceDownloader(cache_dir=tmp_path)

    def fake_clone(_tag: str, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        # Intentionally do NOT create controllers subtree.

    with (
        patch.object(downloader, "_git_clone_tag", side_effect=fake_clone),
        pytest.raises(RuntimeError, match="Controllers directory not found"),
    ):
        downloader.download("24.7")


def test_git_clone_tag_invokes_git_with_expected_args(
    tmp_path: Path, mock_subprocess_run: MagicMock
) -> None:
    """_git_clone_tag shells out to git with the documented flags."""
    downloader = SourceDownloader(cache_dir=tmp_path)
    target = tmp_path / "24.7"

    downloader._git_clone_tag("24.7", target)

    mock_subprocess_run.assert_called_once()
    args, kwargs = mock_subprocess_run.call_args
    assert args[0] == [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        "24.7",
        SourceDownloader.GITHUB_REPO,
        str(target),
    ]
    assert kwargs == {"check": True, "capture_output": True, "text": True}


def test_git_clone_tag_wraps_called_process_error(
    tmp_path: Path, mock_subprocess_run: MagicMock
) -> None:
    """_git_clone_tag converts ``CalledProcessError`` into ``RuntimeError``."""
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=128, cmd=["git"], stderr="fatal: bad tag"
    )
    downloader = SourceDownloader(cache_dir=tmp_path)
    with pytest.raises(RuntimeError, match="fatal: bad tag"):
        downloader._git_clone_tag("24.7", tmp_path / "24.7")


def test_get_available_versions_filters_prereleases(
    tmp_path: Path, mock_subprocess_run: MagicMock
) -> None:
    """get_available_versions() drops RC, beta, alpha and peeled tags."""
    downloader = SourceDownloader(cache_dir=tmp_path)
    mock_subprocess_run.return_value = MagicMock(
        returncode=0,
        stdout=(
            "abc refs/tags/24.7\n"
            "def refs/tags/24.7^{}\n"
            "ghi refs/tags/24.7-RC1\n"
            "jkl refs/tags/24.7-rc2\n"
            "mno refs/tags/24.7-beta1\n"
            "pqr refs/tags/24.1-alpha\n"
            "stu refs/tags/25.1\n"
            "zzz not-a-tag-line\n"
        ),
        stderr="",
    )

    versions = downloader.get_available_versions()

    assert versions == ["25.1", "24.7"]


def test_get_available_versions_raises_on_git_failure(
    tmp_path: Path, mock_subprocess_run: MagicMock
) -> None:
    """get_available_versions() wraps git failure into RuntimeError."""
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["git"], stderr="network error"
    )
    downloader = SourceDownloader(cache_dir=tmp_path)
    with pytest.raises(RuntimeError, match="network error"):
        downloader.get_available_versions()


def test_clean_cache_removes_specific_version(tmp_path: Path) -> None:
    """clean_cache(version) removes only the targeted version directory."""
    downloader = SourceDownloader(cache_dir=tmp_path)
    (tmp_path / "24.7").mkdir()
    (tmp_path / "24.7" / "file").write_text("x")
    (tmp_path / "25.1").mkdir()

    downloader.clean_cache("24.7")

    assert not (tmp_path / "24.7").exists()
    assert (tmp_path / "25.1").exists()


def test_clean_cache_missing_version_is_noop(tmp_path: Path) -> None:
    """clean_cache(version) silently skips missing version directories."""
    downloader = SourceDownloader(cache_dir=tmp_path)
    # No raise.
    downloader.clean_cache("99.99")


def test_clean_cache_removes_all_when_no_version(tmp_path: Path) -> None:
    """clean_cache() nukes the entire cache dir and recreates it empty."""
    cache = tmp_path / "cache"
    cache.mkdir()
    downloader = SourceDownloader(cache_dir=cache)
    (cache / "24.7").mkdir()
    (cache / "24.7" / "file").write_text("x")

    downloader.clean_cache()

    assert cache.exists()
    assert list(cache.iterdir()) == []


def test_clean_cache_all_handles_missing_cache_dir(tmp_path: Path) -> None:
    """clean_cache() is a no-op when the cache dir has already been removed."""
    cache = tmp_path / "cache"
    downloader = SourceDownloader(cache_dir=cache)
    # Remove the cache dir that __init__ created.
    cache.rmdir()
    assert not cache.exists()

    downloader.clean_cache()

    # Neither branch in the `else` block should raise.
    assert not cache.exists()
