"""Tests for :mod:`opnsense_openapi.client.base` covering paths missed by ``test_client.py``.

The existing ``tests/test_client.py`` exercises constructor wiring, ``_build_url``,
context-manager use, the no-version error path, and the ``api`` property's
spec-missing / CLI-missing messages. ``tests/test_client_auto_generate.py``
covers the standalone ``_auto_generate_client`` helper.

This module fills in the remaining gaps in ``OPNsenseClient`` itself:

- ``get()`` / ``post()`` happy + ``APIResponseError`` paths.
- ``detect_version()`` per-endpoint fallback chain (each branch + all-fail).
- ``openapi`` property lazy-load against an injected mock spec.
- The auto-detect-on-construct path (success + exception).
- ``list_endpoints`` / ``get_endpoint_info`` lazy-init wiring.

Tests reuse ``mock_httpx_response`` from ``tests/conftest.py``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from opnsense_openapi.client import OPNsenseClient
from opnsense_openapi.client.base import APIResponseError


def _attach_request(response: httpx.Response, method: str, url: str) -> httpx.Response:
    """Wire a synthetic ``httpx.Request`` so ``raise_for_status`` is callable.

    Used because the production code calls ``response.raise_for_status()`` and
    httpx will otherwise refuse on a hand-built response that has no request.
    """
    response._request = httpx.Request(method, url)
    return response


# ----------------------------- get() / post() --------------------------------


def test_get_returns_decoded_json(
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """``get`` returns the decoded JSON body for a 200 response."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        auto_detect_version=False,
    )
    response = _attach_request(
        mock_httpx_response(200, json={"status": "ok"}),
        "GET",
        "https://opnsense.local/api/firewall/alias_util/list",
    )
    with patch.object(client._client, "get", return_value=response) as get:
        result = client.get("firewall", "alias_util", "list", foo="bar")

    assert result == {"status": "ok"}
    get.assert_called_once()
    # query kwargs are forwarded as ``params``
    assert get.call_args.kwargs.get("params") == {"foo": "bar"}


def test_get_raises_api_response_error_on_invalid_json(
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """A 200 response with non-JSON content surfaces ``APIResponseError``."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        auto_detect_version=False,
    )
    response = _attach_request(
        mock_httpx_response(
            200,
            text="<html>not json</html>",
            headers={"Content-Type": "application/json"},
        ),
        "GET",
        "https://opnsense.local/api/x/y/z",
    )
    with (
        patch.object(client._client, "get", return_value=response),
        pytest.raises(APIResponseError) as exc_info,
    ):
        client.get("x", "y", "z")

    assert "<html>not json</html>" in exc_info.value.response_text


def test_post_returns_decoded_json(
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """``post`` returns the decoded JSON body and forwards ``json`` payload."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        auto_detect_version=False,
    )
    response = _attach_request(
        mock_httpx_response(200, json={"created": True}),
        "POST",
        "https://opnsense.local/api/firewall/alias/set",
    )
    with patch.object(client._client, "post", return_value=response) as post:
        result = client.post("firewall", "alias", "set", json={"name": "alias-1"})

    assert result == {"created": True}
    assert post.call_args.kwargs["json"] == {"name": "alias-1"}
    # JSON content-type is forced when a body is provided
    assert post.call_args.kwargs["headers"] == {"Content-Type": "application/json"}


def test_post_without_body_omits_content_type(
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """A POST without a body sends an empty headers dict (not application/json)."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        auto_detect_version=False,
    )
    response = _attach_request(
        mock_httpx_response(200, json={"ok": True}),
        "POST",
        "https://opnsense.local/api/x/y/z",
    )
    with patch.object(client._client, "post", return_value=response) as post:
        client.post("x", "y", "z")

    assert post.call_args.kwargs["headers"] == {}


# --------------------------- detect_version() --------------------------------


def test_detect_version_uses_first_endpoint(
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """``core/firmware/info`` is tried first and returns ``product_version``."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        auto_detect_version=False,
    )
    response = _attach_request(
        mock_httpx_response(200, json={"product_version": "24.7.1"}),
        "GET",
        "https://opnsense.local/api/core/firmware/info",
    )
    with patch.object(client._client, "get", return_value=response) as get:
        version = client.detect_version()

    assert version == "24.7.1"
    # Only the first endpoint was tried.
    assert get.call_count == 1


def test_detect_version_falls_back_to_status_endpoint(
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """When ``info`` fails, ``status`` is tried next and parsed via ``versions``."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        auto_detect_version=False,
    )
    info_response = _attach_request(
        mock_httpx_response(500, text="boom", headers={}),
        "GET",
        "https://opnsense.local/api/core/firmware/info",
    )
    status_response = _attach_request(
        mock_httpx_response(200, json={"versions": {"product_version": "25.1"}}),
        "GET",
        "https://opnsense.local/api/core/firmware/status",
    )
    with patch.object(client._client, "get", side_effect=[info_response, status_response]) as get:
        version = client.detect_version()

    assert version == "25.1"
    assert get.call_count == 2


def test_detect_version_falls_back_to_diagnostics(
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """The third endpoint exposes the version via the ``product`` nested key."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        auto_detect_version=False,
    )
    fail_info = _attach_request(
        mock_httpx_response(500, text="x", headers={}),
        "GET",
        "https://opnsense.local/api/core/firmware/info",
    )
    fail_status = _attach_request(
        mock_httpx_response(500, text="x", headers={}),
        "GET",
        "https://opnsense.local/api/core/firmware/status",
    )
    diag_response = _attach_request(
        mock_httpx_response(200, json={"product": {"product_version": "26.1"}}),
        "GET",
        "https://opnsense.local/api/diagnostics/system/systemInformation",
    )
    with patch.object(
        client._client,
        "get",
        side_effect=[fail_info, fail_status, diag_response],
    ) as get:
        version = client.detect_version()

    assert version == "26.1"
    assert get.call_count == 3


def test_detect_version_raises_when_all_endpoints_fail(
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """All endpoints failing raises ``APIResponseError`` with the last error."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        auto_detect_version=False,
    )
    failures = [
        _attach_request(
            mock_httpx_response(500, text=f"boom {i}", headers={}),
            "GET",
            f"https://opnsense.local/api/x/{i}",
        )
        for i in range(3)
    ]
    with (
        patch.object(client._client, "get", side_effect=failures),
        pytest.raises(APIResponseError) as exc_info,
    ):
        client.detect_version()

    assert "Could not detect OPNsense version" in str(exc_info.value)


def test_detect_version_skips_response_without_recognized_keys(
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """A 200 response missing every known key is skipped without raising."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        auto_detect_version=False,
    )
    # First response is a 200 but contains no version keys at all -> the loop
    # falls through to the next endpoint.
    bare_response = _attach_request(
        mock_httpx_response(200, json={"unrelated": "x"}),
        "GET",
        "https://opnsense.local/api/core/firmware/info",
    )
    fallback_response = _attach_request(
        mock_httpx_response(200, json={"product_version": "24.1"}),
        "GET",
        "https://opnsense.local/api/core/firmware/status",
    )
    with patch.object(client._client, "get", side_effect=[bare_response, fallback_response]):
        # The function loops; the second endpoint succeeds via product_version.
        version = client.detect_version()
    assert version == "24.1"


# ------------------- auto-detect on construct (warn path) --------------------


def test_auto_detect_version_warns_and_disables_on_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If auto-detect fails, the constructor logs a warning and clears the version."""
    with (
        patch.object(
            OPNsenseClient,
            "detect_version",
            side_effect=APIResponseError("no", ""),
        ),
        caplog.at_level("WARNING"),
    ):
        client = OPNsenseClient(
            base_url="https://opnsense.local",
            api_key="key",
            api_secret="secret",
            auto_detect_version=True,
        )
    assert client._detected_version is None
    assert any("Could not auto-detect" in r.message for r in caplog.records)


def test_auto_detect_version_records_detected_version(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A successful auto-detect populates ``_detected_version``."""
    with (
        patch.object(OPNsenseClient, "detect_version", return_value="24.7.1"),
        caplog.at_level("INFO"),
    ):
        client = OPNsenseClient(
            base_url="https://opnsense.local",
            api_key="key",
            api_secret="secret",
            auto_detect_version=True,
        )
    assert client._detected_version == "24.7.1"
    assert any("Detected OPNsense version: 24.7.1" in r.message for r in caplog.records)


# ------------------------- openapi property lazy-load ------------------------


def test_openapi_property_lazy_loads_with_detected_version(
    tmp_path: Path,
    minimal_openapi_spec: dict[str, Any],
) -> None:
    """Detected version takes effect when ``spec_version`` is unset."""
    spec_file = tmp_path / "opnsense-24.7.1.json"
    spec_file.write_text(json.dumps(minimal_openapi_spec))

    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        auto_detect_version=False,
    )
    # Bypass auto-detect and directly set the detected version.
    client._detected_version = "24.7.1"

    with patch(
        "opnsense_openapi.client.base.find_best_matching_spec",
        return_value=spec_file,
    ):
        wrapper_first = client.openapi
        # Second access returns the same instance (cached).
        wrapper_second = client.openapi

    assert wrapper_first is wrapper_second
    assert wrapper_first.api_spec["openapi"] == "3.0.3"


def test_openapi_property_uses_explicit_spec_version_over_detected(
    tmp_path: Path,
    minimal_openapi_spec: dict[str, Any],
) -> None:
    """``spec_version`` in the constructor takes precedence over the detected value."""
    spec_file = tmp_path / "opnsense-24.7.1.json"
    spec_file.write_text(json.dumps(minimal_openapi_spec))

    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        spec_version="24.7.1",
        auto_detect_version=False,
    )
    client._detected_version = "should-be-ignored"

    captured: dict[str, str] = {}

    def fake_find(version: str) -> Path:
        captured["version"] = version
        return spec_file

    with patch(
        "opnsense_openapi.client.base.find_best_matching_spec",
        side_effect=fake_find,
    ):
        _ = client.openapi

    assert captured["version"] == "24.7.1"


# ----------------------- list_endpoints / get_endpoint_info ------------------


def test_list_endpoints_initializes_openapi(
    tmp_path: Path, minimal_openapi_spec: dict[str, Any]
) -> None:
    """``list_endpoints`` triggers the lazy ``openapi`` property load."""
    spec_file = tmp_path / "opnsense-24.7.1.json"
    spec_file.write_text(json.dumps(minimal_openapi_spec))

    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        spec_version="24.7.1",
        auto_detect_version=False,
    )
    with patch(
        "opnsense_openapi.client.base.find_best_matching_spec",
        return_value=spec_file,
    ):
        endpoints = client.list_endpoints()

    assert len(endpoints) > 0
    assert client._openapi is not None


def test_get_endpoint_info_initializes_openapi(
    tmp_path: Path, minimal_openapi_spec: dict[str, Any]
) -> None:
    """``get_endpoint_info`` triggers the lazy ``openapi`` property load."""
    spec_file = tmp_path / "opnsense-24.7.1.json"
    spec_file.write_text(json.dumps(minimal_openapi_spec))

    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        spec_version="24.7.1",
        auto_detect_version=False,
    )
    with patch(
        "opnsense_openapi.client.base.find_best_matching_spec",
        return_value=spec_file,
    ):
        info = client.get_endpoint_info("/api/firewall/alias/set", method="POST")

    assert info["path"] == "/api/firewall/alias/set"
    assert info["method"] == "POST"


# ------------------------- close / context manager ---------------------------


def test_close_invokes_underlying_client() -> None:
    """``close`` propagates to the inner ``httpx.Client``."""
    client = OPNsenseClient(
        base_url="https://opnsense.local",
        api_key="key",
        api_secret="secret",
        auto_detect_version=False,
    )
    with patch.object(client._client, "close") as close:
        client.close()
    close.assert_called_once()


def test_context_manager_closes_on_exit() -> None:
    """Exiting the ``with`` block triggers ``close`` on the inner client."""
    inner = MagicMock(spec=httpx.Client)
    with (
        patch("httpx.Client", return_value=inner),
        OPNsenseClient(
            base_url="https://opnsense.local",
            api_key="key",
            api_secret="secret",
            auto_detect_version=False,
        ),
    ):
        pass
    inner.close.assert_called_once()
