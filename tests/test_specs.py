"""Tests for spec loading functions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from opnsense_openapi import find_best_matching_spec, get_spec_path, list_available_specs
from opnsense_openapi.specs import (
    _version_key,
    latest_spec_per_series,
    newest_spec_version,
    version_from_spec_path,
)


def test_list_available_specs() -> None:
    """Test listing available specs."""
    specs = list_available_specs()
    assert isinstance(specs, list)
    assert len(specs) > 0
    assert "25.7" in specs or "24.7" in specs  # At least one version present


def test_get_spec_path_valid() -> None:
    """Test getting path to a valid spec."""
    specs = list_available_specs()
    if specs:
        path = get_spec_path(specs[0])
        assert path.exists()
        assert path.suffix == ".json"


def test_get_spec_path_invalid() -> None:
    """Test error when spec not found."""
    with pytest.raises(FileNotFoundError) as exc_info:
        get_spec_path("99.99.99")
    assert "No spec" in str(exc_info.value)
    assert "Available" in str(exc_info.value)


def test_find_best_matching_spec_exact() -> None:
    """Test finding best match with exact version."""
    specs = list_available_specs()
    if "24.7.1" in specs:
        path = find_best_matching_spec("24.7.1")
        assert path.name == "opnsense-24.7.1.json"
        assert path.exists()


def test_find_best_matching_spec_fallback() -> None:
    """A request above the highest committed patch falls back to that patch.

    Under floor matching, ``24.7.999`` is greater than every committed
    ``24.7.x``, so the highest existing patch is the correct floor.
    """
    path = find_best_matching_spec("24.7.999")
    assert path.name.startswith("opnsense-24.7.")
    assert path.exists()


def test_find_best_matching_spec_no_match() -> None:
    """Test finding best match with no suitable major.minor."""
    with pytest.raises(FileNotFoundError) as exc_info:
        find_best_matching_spec("99.99.99")
    assert "No spec found" in str(exc_info.value)


# --- _version_key ---------------------------------------------------------


def test_version_key_basic_three_part() -> None:
    """Three-part versions parse to a 3-tuple."""
    assert _version_key("26.1.6") == (26, 1, 6)


def test_version_key_strips_security_patch_suffix() -> None:
    """A trailing ``_N`` suffix on the last component is stripped, not added."""
    assert _version_key("26.1.6_2") == (26, 1, 6)
    assert _version_key("26.1.6") == _version_key("26.1.6_2")


def test_version_key_numeric_not_lexical() -> None:
    """Comparison is numeric: 26.1.10 > 26.1.6_2 (lexical would say <)."""
    assert _version_key("26.1.10") > _version_key("26.1.6_2")


def test_version_key_two_segment() -> None:
    """Two-segment versions like ``24.7`` round-trip cleanly."""
    assert _version_key("24.7") == (24, 7)


# --- version_from_spec_path ----------------------------------------------


def test_version_from_spec_path_round_trips() -> None:
    """``opnsense-26.1.6.json`` -> ``"26.1.6"``."""
    assert version_from_spec_path(Path("specs/opnsense-26.1.6.json")) == "26.1.6"


def test_version_from_spec_path_rejects_unknown_shape() -> None:
    """A path that does not match the expected filename raises ``ValueError``."""
    with pytest.raises(ValueError, match="does not match"):
        version_from_spec_path(Path("nonsense.txt"))


# --- find_best_matching_spec: mode and security-patch handling -----------


def _patched_specs_dir(tmp_path: Path, versions: list[str]) -> None:
    """Helper: write empty JSON files for each version under ``tmp_path``."""
    for v in versions:
        (tmp_path / f"opnsense-{v}.json").write_text("{}")


def test_find_best_matching_spec_default_is_floor(tmp_path: Path) -> None:
    """Calling without ``mode`` behaves identically to ``mode='floor'``."""
    _patched_specs_dir(tmp_path, ["25.7.4", "25.7.6", "25.7.7"])

    with patch("opnsense_openapi.specs.get_specs_dir", return_value=tmp_path):
        default = find_best_matching_spec("25.7.5")
        floor = find_best_matching_spec("25.7.5", mode="floor")
        assert default == floor
        assert default.name == "opnsense-25.7.4.json"


def test_find_best_matching_spec_floor_with_security_patch(tmp_path: Path) -> None:
    """``26.1.6_2`` resolves to the ``26.1.6`` spec under floor matching."""
    _patched_specs_dir(
        tmp_path,
        ["26.1.1", "26.1.2", "26.1.3", "26.1.4", "26.1.5", "26.1.6"],
    )

    with patch("opnsense_openapi.specs.get_specs_dir", return_value=tmp_path):
        path = find_best_matching_spec("26.1.6_2")
        assert path.name == "opnsense-26.1.6.json"


def test_find_best_matching_spec_floor_picks_below_not_above(tmp_path: Path) -> None:
    """``25.7.5`` against ``[25.7.4, 25.7.6, 25.7.7]`` picks ``25.7.4``."""
    _patched_specs_dir(tmp_path, ["25.7.4", "25.7.6", "25.7.7"])

    with patch("opnsense_openapi.specs.get_specs_dir", return_value=tmp_path):
        path = find_best_matching_spec("25.7.5", mode="floor")
        assert path.name == "opnsense-25.7.4.json"


def test_find_best_matching_spec_highest_preserves_legacy(tmp_path: Path) -> None:
    """``mode='highest'`` returns the highest matching ``major.minor.x``."""
    _patched_specs_dir(tmp_path, ["25.7.4", "25.7.6", "25.7.7"])

    with patch("opnsense_openapi.specs.get_specs_dir", return_value=tmp_path):
        path = find_best_matching_spec("25.7.5", mode="highest")
        assert path.name == "opnsense-25.7.7.json"


def test_find_best_matching_spec_floor_raises_when_below_all(tmp_path: Path) -> None:
    """Floor mode raises when no committed spec is at or below the request."""
    _patched_specs_dir(tmp_path, ["24.7.5", "24.7.6"])

    with (
        patch("opnsense_openapi.specs.get_specs_dir", return_value=tmp_path),
        pytest.raises(FileNotFoundError) as exc_info,
    ):
        find_best_matching_spec("24.7.1", mode="floor")

    msg = str(exc_info.value)
    assert "at or below" in msg
    assert "24.7.1" in msg
    assert "24.7.5" in msg


def test_find_best_matching_spec_exact_short_circuits_in_both_modes(tmp_path: Path) -> None:
    """An exact-match request returns the exact spec regardless of ``mode``."""
    _patched_specs_dir(tmp_path, ["25.7.4", "25.7.5", "25.7.7"])

    with patch("opnsense_openapi.specs.get_specs_dir", return_value=tmp_path):
        floor = find_best_matching_spec("25.7.5", mode="floor")
        highest = find_best_matching_spec("25.7.5", mode="highest")
        assert floor.name == highest.name == "opnsense-25.7.5.json"


# --- newest_spec_version / is_version_covered (#159) ---


def test_newest_spec_version_overall() -> None:
    from opnsense_openapi import newest_spec_version

    assert newest_spec_version() == list_available_specs()[-1]


def test_newest_spec_version_for_series() -> None:
    from opnsense_openapi import newest_spec_version

    available = list_available_specs()
    series = ".".join(available[0].split(".")[:2])
    expected = [v for v in available if v == series or v.startswith(f"{series}.")][-1]
    assert newest_spec_version(series) == expected


@pytest.mark.parametrize("bad", ["26", "26.1.6", "x.y", ""])
def test_newest_spec_version_bad_input(bad: str) -> None:
    from opnsense_openapi import newest_spec_version

    with pytest.raises(ValueError):
        newest_spec_version(bad)


def test_newest_spec_version_no_match() -> None:
    from opnsense_openapi import newest_spec_version

    with pytest.raises(FileNotFoundError):
        newest_spec_version("1.1")


def test_is_version_covered_exact_and_suffix() -> None:
    from opnsense_openapi import is_version_covered

    version = list_available_specs()[-1]
    assert is_version_covered(version)
    assert is_version_covered(f"{version}_2")


def test_is_version_covered_between_and_newer(tmp_path: Path) -> None:
    from opnsense_openapi import is_version_covered

    for v in ("30.1.1", "30.1.5"):
        (tmp_path / f"opnsense-{v}.json").write_text("{}")
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=tmp_path):
        assert is_version_covered("30.1.5")
        assert not is_version_covered("30.1.3")
        assert not is_version_covered("30.1.99")
        assert not is_version_covered("31.1.1")


@pytest.mark.parametrize("bad", ["", "garbage", "26.x.1", "26..1"])
def test_is_version_covered_malformed(bad: str) -> None:
    from opnsense_openapi import is_version_covered

    assert is_version_covered(bad) is False


def _touch_specs(directory: Path, names: list[str]) -> None:
    for name in names:
        (directory / name).write_text("{}", encoding="utf-8")


def test_latest_spec_per_series_numeric_order(tmp_path: Path) -> None:
    """24.7.12 beats 24.7.9: ordering is numeric, not lexical."""
    _touch_specs(
        tmp_path, ["opnsense-24.7.9.json", "opnsense-24.7.12.json", "opnsense-24.7.2.json"]
    )
    assert latest_spec_per_series(tmp_path) == ["24.7.12"]


def test_latest_spec_per_series_base_release_counts_as_zero(tmp_path: Path) -> None:
    """A bare YY.M is .0, so any point release in the series wins over it."""
    _touch_specs(tmp_path, ["opnsense-24.7.json", "opnsense-24.7.1.json"])
    assert latest_spec_per_series(tmp_path) == ["24.7.1"]


def test_latest_spec_per_series_base_release_alone(tmp_path: Path) -> None:
    """A series with only a base release still yields it."""
    _touch_specs(tmp_path, ["opnsense-25.1.json"])
    assert latest_spec_per_series(tmp_path) == ["25.1"]


def test_latest_spec_per_series_multiple_series_ascending(tmp_path: Path) -> None:
    """One entry per series, in ascending order."""
    _touch_specs(
        tmp_path,
        [
            "opnsense-26.1.11.json",
            "opnsense-24.7.12.json",
            "opnsense-24.7.3.json",
            "opnsense-25.1.json",
            "opnsense-25.1.12.json",
        ],
    )
    assert latest_spec_per_series(tmp_path) == ["24.7.12", "25.1.12", "26.1.11"]


def test_latest_spec_per_series_ignores_non_matching_files(tmp_path: Path) -> None:
    """Stray files do not raise and are not returned."""
    _touch_specs(
        tmp_path,
        [
            "opnsense-24.7.1.json",
            "opnsense-latest.json",
            "opnsense-24.7.5_2.json",
            "opnsense-24.7.9.json.bak",
            "opnsense-24.json",
            "notes.json",
        ],
    )
    assert latest_spec_per_series(tmp_path) == ["24.7.1"]


def test_latest_spec_per_series_empty_dir(tmp_path: Path) -> None:
    """An empty directory yields an empty list."""
    assert latest_spec_per_series(tmp_path) == []


def test_latest_spec_per_series_bundled_matches_newest_spec_version() -> None:
    """Against the bundled specs, each entry is the newest of its series."""
    result = latest_spec_per_series()
    assert result
    series = [".".join(v.split(".")[:2]) for v in result]
    assert len(series) == len(set(series))
    for version, major_minor in zip(result, series, strict=True):
        assert version == newest_spec_version(major_minor)
