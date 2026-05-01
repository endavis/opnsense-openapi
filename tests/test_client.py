"""Tests for OPNsense API client."""

from pathlib import Path

import pytest

from opnsense_openapi.client import OPNsenseClient


def test_client_initialization() -> None:
    """Test client initialization."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="test_key",
        api_secret="test_secret",
        verify_ssl=False,
        auto_detect_version=False,
    )

    assert client.base_url == "https://opnsense.local"
    assert client.api_key == "test_key"
    assert client.api_secret == "test_secret"
    assert client.verify_ssl is False


def test_build_url() -> None:
    """Test URL building."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="test_key",
        api_secret="test_secret",
        auto_detect_version=False,
    )

    url = client._build_url("firewall", "alias_util", "findAlias")
    assert url == "https://opnsense.local/api/firewall/alias_util/findAlias"

    url = client._build_url("firewall", "alias_util", "get", "uuid-123")
    assert url == "https://opnsense.local/api/firewall/alias_util/get/uuid-123"


def test_build_url_with_trailing_slash() -> None:
    """Test URL building with trailing slash in base_url."""
    client = OPNsenseClient(
        base_url="https://opnsense.local/",
        api_key="test_key",
        api_secret="test_secret",
        auto_detect_version=False,
    )

    url = client._build_url("system", "info", "version")
    assert url == "https://opnsense.local/api/system/info/version"


def test_context_manager() -> None:
    """Test using client as context manager."""
    with OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="test_key",
        api_secret="test_secret",
        auto_detect_version=False,
    ) as client:
        assert client is not None


def test_client_with_spec_version() -> None:
    """Test client initialization with specific spec version."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="test_key",
        api_secret="test_secret",
        spec_version="24.7.1",
        auto_detect_version=False,
    )

    assert client._spec_version == "24.7.1"
    assert client._detected_version is None


def test_openapi_property_without_version() -> None:
    """Test accessing openapi property without version raises error."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="test_key",
        api_secret="test_secret",
        auto_detect_version=False,
    )

    with pytest.raises(RuntimeError) as exc_info:
        _ = client.openapi
    assert "No OPNsense version available" in str(exc_info.value)


def test_openapi_property_with_spec_version() -> None:
    """Test accessing openapi property with spec version."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="test_key",
        api_secret="test_secret",
        spec_version="24.7.1",
        auto_detect_version=False,
    )

    # Should initialize successfully
    openapi = client.openapi
    assert openapi is not None
    assert client._openapi is openapi  # Same instance


def test_list_endpoints() -> None:
    """Test list_endpoints method."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="test_key",
        api_secret="test_secret",
        spec_version="24.7.1",
        auto_detect_version=False,
    )

    endpoints = client.list_endpoints()
    assert isinstance(endpoints, list)
    assert len(endpoints) > 0
    # Each endpoint is a tuple of (path, method, summary)
    for endpoint in endpoints[:5]:  # Check first 5
        assert isinstance(endpoint, tuple)
        assert len(endpoint) == 3
        path, method, summary = endpoint
        assert isinstance(path, str)
        assert isinstance(method, str)
        assert summary is None or isinstance(summary, str)


def test_api_response_error() -> None:
    """Test APIResponseError exception."""
    from opnsense_openapi.client.base import APIResponseError

    error = APIResponseError("Failed to parse JSON", "<html>Error</html>")

    assert str(error) == "Failed to parse JSON"
    assert error.response_text == "<html>Error</html>"


def test_auto_generate_client_spec_missing() -> None:
    """Test auto-generation raises a spec-missing RuntimeError when no spec exists."""
    from opnsense_openapi.client.base import _auto_generate_client

    with pytest.raises(RuntimeError) as exc_info:
        _auto_generate_client("99.99.99")

    msg = str(exc_info.value)
    assert "No OpenAPI spec for version 99.99.99" in msg
    assert "opnsense-openapi generate 99.99.99" in msg


def test_auto_generate_client_spec_exists() -> None:
    """Test auto-generation when a spec exists.

    Returns the *resolved* spec version (a string) when codegen succeeds or the
    generated client already exists; raises a CLI-missing RuntimeError when the
    spec is present but ``openapi-python-client`` is not on PATH.
    """
    import shutil

    from opnsense_openapi.client.base import _auto_generate_client

    # Check whether the generated client dir already exists or the tool is on PATH.
    version_module = "24_7_1"
    client_dir = (
        Path(__file__).parent.parent / "src/opnsense_openapi/generated" / f"v{version_module}"
    )
    has_tool = shutil.which("openapi-python-client") is not None

    if client_dir.exists() or has_tool:
        # Either the generated client is already present, or codegen will
        # succeed: function should return the resolved version string.
        result = _auto_generate_client("24.7.1")
        assert result == "24.7.1"
    else:
        # Spec exists but the tool is missing → CLI-missing error.
        with pytest.raises(RuntimeError, match="openapi-python-client is not on PATH"):
            _auto_generate_client("24.7.1")


def test_api_property_no_spec_error_message() -> None:
    """Test that api property provides a spec-missing error when the spec is absent."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="test_key",
        api_secret="test_secret",
        spec_version="99.99.99",  # Non-existent version
        auto_detect_version=False,
    )

    with pytest.raises(RuntimeError) as exc_info:
        _ = client.api

    error_msg = str(exc_info.value)
    assert "No OpenAPI spec for version 99.99.99" in error_msg
    assert "opnsense-openapi generate 99.99.99" in error_msg


def test_api_property_cli_missing_error_message(tmp_path: Path) -> None:
    """Test that api property names the missing CLI rather than a phantom missing spec.

    When the spec is present but ``openapi-python-client`` is not on PATH, the
    error must say so and recommend the correct install command — not the
    misleading "No OpenAPI spec found" message we used to surface.
    """
    from unittest.mock import patch

    spec_path = tmp_path / "opnsense-24.7.1.json"
    spec_path.write_text("{}")

    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="test_key",
        api_secret="test_secret",
        spec_version="24.7.1",
        auto_detect_version=False,
    )

    with (
        patch(
            "opnsense_openapi.client.base.find_best_matching_spec",
            return_value=spec_path,
        ),
        # Ensure the generated client dir does not exist for this version,
        # so the helper falls through to the shutil.which check.
        patch("pathlib.Path.exists", return_value=False),
        patch("opnsense_openapi.client.base.shutil.which", return_value=None),
        pytest.raises(RuntimeError) as exc_info,
    ):
        _ = client.api

    error_msg = str(exc_info.value)
    assert "openapi-python-client is not on PATH" in error_msg
    assert "uv tool install openapi-python-client" in error_msg
    # Must not regress to the old misleading "spec missing" wording.
    assert "No OpenAPI spec for version" not in error_msg
