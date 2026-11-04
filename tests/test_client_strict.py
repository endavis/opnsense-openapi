"""Tests for the opt-in strict endpoint validation on OPNsenseClient."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import pytest

import opnsense_openapi
from opnsense_openapi import APIResponseError, UnknownEndpointError
from opnsense_openapi.client import OPNsenseClient

VERSION = "26.1.6"


def make_client(
    version: str | None = VERSION,
    *,
    validate: bool = True,
    auto_detect: bool = False,
    body: dict[str, Any] | None = None,
) -> tuple[OPNsenseClient, list[httpx.Request]]:
    """Build a client on a MockTransport that records every request."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=body if body is not None else {"ok": True})

    client = OPNsenseClient(
        "https://fw.test",
        spec_version=version,
        auto_detect_version=auto_detect,
        validate_endpoints=validate,
        transport=httpx.MockTransport(handler),
    )
    return client, requests


def test_unknown_endpoint_raises_before_request() -> None:
    client, requests = make_client()
    with pytest.raises(UnknownEndpointError) as exc_info:
        client.post("core", "firmware", "frobnicate")
    assert requests == []
    err = exc_info.value
    assert err.method == "POST"
    assert err.path == "core/firmware/frobnicate"
    assert err.version == VERSION
    assert err.spec_path.name == f"opnsense-{VERSION}.json"
    assert str(err).startswith(
        f"POST core/firmware/frobnicate is not in the OPNsense {VERSION} spec "
        f"(opnsense-{VERSION}.json)"
    )


def test_is_api_response_error_subclass() -> None:
    assert issubclass(UnknownEndpointError, APIResponseError)
    assert opnsense_openapi.UnknownEndpointError is UnknownEndpointError
    client, _ = make_client()
    with pytest.raises(APIResponseError):
        client.get("system", "general", "get")


def test_known_endpoints_pass() -> None:
    client, requests = make_client()
    assert client.post("core", "tunables", "setItem", "abc-123", json={"a": 1}) == {"ok": True}
    assert len(requests) == 1
    assert client.get("core", "tunables", "getItem", "abc-123") == {"ok": True}
    assert client.get("core", "firmware", "info") == {"ok": True}
    assert len(requests) == 3


def test_method_mismatch_lists_allowed() -> None:
    client, requests = make_client()
    with pytest.raises(UnknownEndpointError, match=r"does not accept POST \(allowed: GET\)"):
        client.post("core", "tunables", "getItem", "abc-123")
    assert requests == []


def test_suggestions_same_module_only() -> None:
    client, _ = make_client()
    with pytest.raises(UnknownEndpointError) as exc_info:
        client.post("core", "firmware", "rebot")
    err = exc_info.value
    assert "core/firmware/reboot" in err.suggestions
    assert all(s.startswith("core/") for s in err.suggestions)
    assert "did you mean: " in str(err)


def test_cache_holds_one_entry_for_templated_paths() -> None:
    client, requests = make_client()
    client.post("core", "tunables", "setItem", "uuid-1")
    client.post("core", "tunables", "setItem", "uuid-2")
    assert len(requests) == 2
    assert client._verified_endpoints == {("/api/core/tunables/setItem/{uuid}", "POST")}


def test_newer_in_series_version_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    client, requests = make_client("26.1.99")
    with caplog.at_level(logging.WARNING, logger="opnsense_openapi.client.base"):
        client.get("core", "firmware", "info")
        client.get("core", "firmware", "info")
        with pytest.raises(UnknownEndpointError):
            client.get("core", "firmware", "nope")
    warnings = [r for r in caplog.records if "No bundled spec" in r.getMessage()]
    assert len(warnings) == 1
    assert len(requests) == 2


def test_series_gap_version_falls_back_across_series(caplog: pytest.LogCaptureFixture) -> None:
    client, requests = make_client("27.1.2")
    with caplog.at_level(logging.WARNING, logger="opnsense_openapi.client.base"):
        client.get("core", "firmware", "info")
    assert len([r for r in caplog.records if "No bundled spec" in r.getMessage()]) == 1
    assert len(requests) == 1
    assert client._validation_spec is not None


def test_covered_version_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    client, _ = make_client(VERSION)
    with caplog.at_level(logging.WARNING, logger="opnsense_openapi.client.base"):
        client.get("core", "firmware", "info")
    assert not [r for r in caplog.records if "No bundled spec" in r.getMessage()]


@pytest.mark.parametrize("version", ["1.0.0", "garbage"])
def test_unresolvable_version_raises_runtime_error(version: str) -> None:
    client, requests = make_client(version)
    with pytest.raises(RuntimeError):
        client.get("core", "firmware", "info")
    assert requests == []


def test_no_version_raises_runtime_error() -> None:
    client, requests = make_client(None)
    with pytest.raises(RuntimeError, match="No OPNsense version available"):
        client.get("core", "firmware", "info")
    assert requests == []


def test_default_off_sends_unknown_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(version: str) -> Any:
        raise AssertionError("spec must not be resolved when validation is off")

    monkeypatch.setattr("opnsense_openapi.client.base.resolve_validation_spec", boom)
    client, requests = make_client(validate=False)
    assert client.validate_endpoints is False
    client.post("core", "firmware", "frobnicate")
    assert len(requests) == 1
    assert client._validation_spec is None


def test_auto_detect_with_strict_constructs_and_validates() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=json.dumps({"product_version": VERSION}))

    client = OPNsenseClient(
        "https://fw.test",
        validate_endpoints=True,
        transport=httpx.MockTransport(handler),
    )
    assert len(requests) == 1
    assert client._detected_version == VERSION
    with pytest.raises(UnknownEndpointError):
        client.post("core", "firmware", "frobnicate")
    assert len(requests) == 1
