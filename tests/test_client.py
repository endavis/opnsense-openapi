"""Tests for OPNsense API client."""

import pytest

from opnsense_api.client import OPNsenseClient


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
    from opnsense_api.client.base import APIResponseError

    error = APIResponseError("Failed to parse JSON", "<html>Error</html>")

    assert str(error) == "Failed to parse JSON"
    assert error.response_text == "<html>Error</html>"
