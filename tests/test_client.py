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
    )

    url = client._build_url("system", "info", "version")
    assert url == "https://opnsense.local/api/system/info/version"


def test_context_manager() -> None:
    """Test using client as context manager."""
    with OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="test_key",
        api_secret="test_secret",
    ) as client:
        assert client is not None
