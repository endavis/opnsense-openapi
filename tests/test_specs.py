"""Tests for spec loading functions."""

import pytest

from opnsense_api import get_spec_path, list_available_specs


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
    assert "No spec for version" in str(exc_info.value)
    assert "Available:" in str(exc_info.value)
