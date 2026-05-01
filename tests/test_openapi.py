"""Tests for :mod:`opnsense_openapi.openapi`.

Covers ``APIWrapper`` construction, endpoint discovery, schema introspection,
parameter suggestion, body validation, and ``call_endpoint`` request flow.
Tests reuse the shared fixtures from ``tests/conftest.py`` (``minimal_openapi_spec``,
``minimal_openapi_spec_file``, ``mock_httpx_response``) — no per-module spec
duplicates.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import httpx
import pytest

from opnsense_openapi.openapi import APIWrapper

# --------------------------- Construction / config --------------------------


def test_apiwrapper_loads_spec_from_file(minimal_openapi_spec_file: Path) -> None:
    """Constructor parses the spec file and exposes ``api_spec`` as a dict."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://opnsense.local",
    )
    assert wrapper.api_spec["openapi"] == "3.0.3"
    assert "/api/firewall/alias/set" in wrapper.api_spec["paths"]


def test_apiwrapper_strips_trailing_slash_from_base_url(
    minimal_openapi_spec_file: Path,
) -> None:
    """``base_url`` keeps no trailing slash so URL formatting stays predictable."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://opnsense.local/",
    )
    assert wrapper.base_url == "https://opnsense.local"


def test_apiwrapper_uses_base_path_from_spec(tmp_path: Path) -> None:
    """OpenAPI 2.0 ``basePath`` overrides empty ``base_api_path``."""
    spec = {"swagger": "2.0", "basePath": "/api/v2", "paths": {}}
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec))

    wrapper = APIWrapper(api_json_file=str(spec_file), base_url="https://x")
    assert wrapper.base_api_path == "/api/v2"


def test_apiwrapper_uses_servers_url_from_spec(tmp_path: Path) -> None:
    """OpenAPI 3.0 ``servers[0].url`` populates ``base_api_path``."""
    spec = {
        "openapi": "3.0.3",
        "servers": [{"url": "https://{host}/api"}],
        "paths": {},
    }
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec))

    wrapper = APIWrapper(api_json_file=str(spec_file), base_url="https://x")
    assert wrapper.base_api_path == "/api"


def test_apiwrapper_warns_when_no_base_path(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """No ``basePath``/``servers`` and no override -> warning logged, value empty."""
    spec = {"openapi": "3.0.3", "paths": {}}
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec))

    with caplog.at_level("WARNING"):
        wrapper = APIWrapper(api_json_file=str(spec_file), base_url="https://x")

    assert wrapper.base_api_path == ""
    assert any("No base api path" in rec.message for rec in caplog.records)


def test_apiwrapper_basic_auth_credentials(minimal_openapi_spec_file: Path) -> None:
    """``api_key`` + ``api_secret`` populate the session's basic auth."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
        api_key="key",
        api_secret="secret",
    )
    # httpx wraps the (user, secret) tuple into a BasicAuth instance.
    assert isinstance(wrapper.session.auth, httpx.BasicAuth)


def test_apiwrapper_auth_header_takes_effect(minimal_openapi_spec_file: Path) -> None:
    """``auth_header`` adds custom headers when api_key/secret are absent."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
        auth_header={"X-Token": "abc"},
    )
    assert wrapper.session.headers["X-Token"] == "abc"


def test_apiwrapper_accepts_injected_session(minimal_openapi_spec_file: Path) -> None:
    """Caller-provided ``httpx.Client`` is reused, not replaced."""
    session = httpx.Client()
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
        session=session,
    )
    assert wrapper.session is session


# ----------------------------- Endpoint discovery ----------------------------


def test_list_endpoints_returns_path_method_summary(
    minimal_openapi_spec_file: Path,
) -> None:
    """Each entry is ``(path, METHOD, summary)`` with method uppercased."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    endpoints = wrapper.list_endpoints()

    assert len(endpoints) == 2
    methods = {e[1] for e in endpoints}
    assert methods == {"GET", "POST"}


def test_list_endpoints_falls_back_to_description(tmp_path: Path) -> None:
    """When ``summary`` is missing, the first sentence of ``description`` is used."""
    spec = {
        "openapi": "3.0.3",
        "paths": {
            "/api/x": {
                "get": {
                    "description": "Returns the current X. Ignored second sentence.",
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec))

    wrapper = APIWrapper(api_json_file=str(spec_file), base_url="https://x")
    [(_, _, summary)] = wrapper.list_endpoints()

    assert summary == "Returns the current X"


# ------------------------------- Schema lookup -------------------------------


def test_get_request_schema_resolves_ref(minimal_openapi_spec_file: Path) -> None:
    """``$ref`` in request body is resolved into the underlying schema."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    schema = cast(
        "dict[str, Any]",
        wrapper.get_request_schema_for_endpoint(
            "/api/firewall/alias/set", method="POST", human_readable=False
        ),
    )
    assert schema["type"] == "object"
    assert "name" in schema["properties"]


def test_get_request_schema_human_readable_returns_description(
    minimal_openapi_spec_file: Path,
) -> None:
    """Human-readable form returns a ``SchemaDescription`` mapping."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    description = wrapper.get_request_schema_for_endpoint("/api/firewall/alias/set", method="POST")
    assert isinstance(description, dict)
    assert "fields" in description
    assert "sample" in description
    assert description["fields"]["name"]["required"] is True


def test_get_request_schema_returns_none_for_endpoint_without_body(
    minimal_openapi_spec_file: Path,
) -> None:
    """GET endpoints without a request body return ``None``."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    assert wrapper.get_request_schema_for_endpoint("/api/core/firmware/info", method="GET") is None


def test_get_request_schema_unknown_path_raises(
    minimal_openapi_spec_file: Path,
) -> None:
    """A bogus path raises ``KeyError`` listing the available paths."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    with pytest.raises(KeyError, match="Path not found"):
        wrapper.get_request_schema_for_endpoint("/api/does/not/exist", method="GET")


def test_get_request_schema_unknown_method_raises(
    minimal_openapi_spec_file: Path,
) -> None:
    """A path that exists but no such method raises ``KeyError``."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    with pytest.raises(KeyError, match="Method 'DELETE' not found"):
        wrapper.get_request_schema_for_endpoint("/api/core/firmware/info", method="DELETE")


def test_get_response_schema_human_readable(
    minimal_openapi_spec_file: Path,
) -> None:
    """Response schema returns a ``SchemaDescription`` for documented status codes."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    description = wrapper.get_response_schema_for_endpoint("/api/core/firmware/info", method="GET")
    assert isinstance(description, dict)
    assert "product_version" in description["fields"]


def test_get_response_schema_returns_none_for_undocumented_status(
    minimal_openapi_spec_file: Path,
) -> None:
    """A status code without a documented body returns ``None``."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    assert (
        wrapper.get_response_schema_for_endpoint(
            "/api/core/firmware/info", method="GET", status_code="404"
        )
        is None
    )


def test_get_request_schema_caches_operation_lookups(
    minimal_openapi_spec_file: Path,
) -> None:
    """The second lookup hits the operation cache (functional regression check)."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )

    # Trigger lookup, then mutate the spec underneath. The cached operation
    # should remain authoritative.
    wrapper.get_request_schema_for_endpoint(
        "/api/firewall/alias/set", method="POST", human_readable=False
    )
    wrapper.api_spec["paths"]["/api/firewall/alias/set"] = {}

    # The cached operation is reused; a fresh dict would now raise KeyError
    # on method lookup.
    cached = wrapper.get_request_schema_for_endpoint(
        "/api/firewall/alias/set", method="POST", human_readable=False
    )
    assert isinstance(cached, dict)


# ------------------------------ Sample builder -------------------------------


def test_build_sample_object_with_typed_properties(
    minimal_openapi_spec_file: Path,
) -> None:
    """Sample generation walks ``properties`` and uses sensible defaults."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "count": {"type": "integer"},
            "ratio": {"type": "number"},
            "active": {"type": "boolean"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "kind": {"type": "string", "enum": ["a", "b"]},
            "blob": {"type": "binary"},
            "nested": {"type": "object", "properties": {"inner": {"type": "string"}}},
        },
    }
    sample = wrapper._build_sample_from_schema(schema)
    assert sample == {
        "name": "<name>",
        "count": 0,
        "ratio": 0.0,
        "active": False,
        "tags": ["<string>"],
        "kind": "a",
        "blob": None,
        "nested": {"inner": "<inner>"},
    }


def test_build_sample_array_returns_single_sample_item(
    minimal_openapi_spec_file: Path,
) -> None:
    """Top-level ``array`` schemas yield a single-element list."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    sample = wrapper._build_sample_from_schema({"type": "array", "items": {"type": "integer"}})
    assert sample == [0]


def test_build_sample_one_of_picks_first(minimal_openapi_spec_file: Path) -> None:
    """When ``type`` is missing but ``oneOf`` is present, the first variant is used."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    schema: dict[str, Any] = {
        "oneOf": [
            {"type": "integer"},
            {"type": "string"},
        ]
    }
    assert wrapper._build_sample_from_schema(schema) == 0


def test_build_sample_scalar_types(minimal_openapi_spec_file: Path) -> None:
    """Top-level scalar schemas produce literal placeholder values."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    assert wrapper._build_sample_from_schema({"type": "string"}) == "<string>"
    assert wrapper._build_sample_from_schema({"type": "integer"}) == 0
    assert wrapper._build_sample_from_schema({"type": "number"}) == 0.0
    assert wrapper._build_sample_from_schema({"type": "boolean"}) is False
    # Unknown / null types fall through to the empty-dict default.
    assert wrapper._build_sample_from_schema({"type": "null"}) == {}


# ------------------------------ Ref resolution -------------------------------


def test_resolve_refs_walks_nested_structures(
    minimal_openapi_spec_file: Path,
) -> None:
    """Refs are resolved recursively through dicts and lists."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    schema = {
        "type": "array",
        "items": {"$ref": "#/components/schemas/Alias"},
    }
    resolved = wrapper._resolve_refs(schema)
    assert resolved["items"]["type"] == "object"
    assert resolved["items"]["properties"]["name"]["type"] == "string"


def test_resolve_ref_returns_empty_for_external_uri(
    minimal_openapi_spec_file: Path,
) -> None:
    """External (non-``#``-prefixed) refs short-circuit to ``{}``."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    assert wrapper._resolve_ref("http://example.com/x.json#/Foo") == {}


# ----------------------------- Parameter suggest -----------------------------


def test_suggest_parameters_returns_typed_dict_shape(tmp_path: Path) -> None:
    """``suggest_parameters`` returns the ``SuggestedParameters`` shape."""
    spec = {
        "openapi": "3.0.3",
        "paths": {
            "/api/x/{uuid}": {
                "get": {
                    "summary": "Fetch X",
                    "parameters": [
                        {
                            "name": "uuid",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Resource UUID",
                        },
                        {
                            "name": "verbose",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "boolean"},
                        },
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec))

    wrapper = APIWrapper(api_json_file=str(spec_file), base_url="https://x")
    suggestion = wrapper.suggest_parameters("/api/x/{uuid}", method="GET")

    assert suggestion["path"] == "/api/x/{uuid}"
    assert suggestion["method"] == "GET"
    assert suggestion["summary"] == "Fetch X"
    assert {p.get("name") for p in suggestion["path_params"]} == {"uuid"}
    assert {p.get("name") for p in suggestion["query_params"]} == {"verbose"}
    # GET has no requestBody -> body_sample is None.
    assert suggestion["body_sample"] is None


def test_suggest_parameters_with_body_sample(
    minimal_openapi_spec_file: Path,
) -> None:
    """POST endpoints get a non-None ``body_sample`` derived from the schema."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    suggestion = wrapper.suggest_parameters("/api/firewall/alias/set", method="POST")
    assert suggestion["body_sample"] is not None
    assert suggestion["body_sample"]["name"] == "<name>"


# ------------------------------- Body validation -----------------------------


def test_validate_body_returns_true_when_no_body(
    minimal_openapi_spec_file: Path,
) -> None:
    """``body=None`` short-circuits to ``True`` regardless of schema."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    assert wrapper.validate_body("/api/firewall/alias/set", method="POST", body=None) is True


def test_validate_body_returns_true_when_no_schema(
    minimal_openapi_spec_file: Path,
) -> None:
    """Endpoints without a schema treat any body as valid."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    # GET has no requestBody -> validate_body returns True.
    assert wrapper.validate_body("/api/core/firmware/info", method="GET", body={"x": "y"}) is True


def test_validate_body_passes_for_valid_payload(
    minimal_openapi_spec_file: Path,
) -> None:
    """A payload satisfying the schema validates successfully."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    assert (
        wrapper.validate_body(
            "/api/firewall/alias/set",
            method="POST",
            body={"name": "alias", "type": "host"},
        )
        is True
    )


def test_validate_body_fails_with_logged_error(
    minimal_openapi_spec_file: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Schema mismatches return ``False`` and emit a structured error log."""
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
    )
    with caplog.at_level("ERROR"):
        ok = wrapper.validate_body(
            "/api/firewall/alias/set",
            method="POST",
            body={"type": "host"},  # missing required 'name'
        )
    assert ok is False
    assert any("Request body validation error" in r.message for r in caplog.records)


# ------------------------------- call_endpoint -------------------------------


def _attach_request(response: httpx.Response, method: str, url: str) -> httpx.Response:
    """Attach a synthetic ``httpx.Request`` so ``raise_for_status`` works.

    ``httpx.Response.raise_for_status`` requires a non-None ``_request``; when
    we hand-build responses through the ``mock_httpx_response`` factory we
    have to wire one up ourselves.
    """
    response._request = httpx.Request(method, url)
    return response


def test_call_endpoint_returns_json_for_200(
    minimal_openapi_spec_file: Path,
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """A 200 JSON response is decoded into a Python dict."""
    session = MagicMock(spec=httpx.Client)
    session.headers = {}
    session.request.return_value = _attach_request(
        mock_httpx_response(200, json={"product_version": "24.7.1"}),
        "GET",
        "https://x/api/core/firmware/info",
    )
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
        session=session,
    )
    result = wrapper.call_endpoint("/api/core/firmware/info", method="GET")
    assert result == {"product_version": "24.7.1"}
    session.request.assert_called_once()


def test_call_endpoint_returns_text_when_not_json(
    minimal_openapi_spec_file: Path,
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """Non-JSON 200 responses fall back to returning the response text."""
    session = MagicMock(spec=httpx.Client)
    session.headers = {}
    session.request.return_value = _attach_request(
        mock_httpx_response(200, text="not really json", headers={"Content-Type": "text/plain"}),
        "GET",
        "https://x/api/core/firmware/info",
    )
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
        session=session,
    )
    result = wrapper.call_endpoint("/api/core/firmware/info", method="GET")
    assert result == "not really json"


def test_call_endpoint_raises_on_invalid_body(
    minimal_openapi_spec_file: Path,
) -> None:
    """A body that fails validation raises ``ValueError`` before HTTP dispatch."""
    session = MagicMock(spec=httpx.Client)
    session.headers = {}
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
        session=session,
    )
    with pytest.raises(ValueError, match="validation failed"):
        wrapper.call_endpoint(
            "/api/firewall/alias/set",
            method="POST",
            body={"type": "host"},  # missing 'name'
        )
    session.request.assert_not_called()


def test_call_endpoint_propagates_http_errors(
    minimal_openapi_spec_file: Path,
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """``raise_for_status`` propagates upstream HTTP errors."""
    session = MagicMock(spec=httpx.Client)
    session.headers = {}
    response = _attach_request(
        mock_httpx_response(500, text="boom", headers={}),
        "GET",
        "https://x/api/core/firmware/info",
    )
    session.request.return_value = response
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
        session=session,
    )
    with pytest.raises(httpx.HTTPStatusError):
        wrapper.call_endpoint("/api/core/firmware/info", method="GET")


def test_call_endpoint_appends_query_params(
    minimal_openapi_spec_file: Path,
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """Query parameters are URL-encoded onto the final request URL."""
    session = MagicMock(spec=httpx.Client)
    session.headers = {}
    session.request.return_value = _attach_request(
        mock_httpx_response(200, json={"ok": True}),
        "GET",
        "https://x/api/core/firmware/info",
    )
    wrapper = APIWrapper(
        api_json_file=str(minimal_openapi_spec_file),
        base_url="https://x",
        session=session,
    )
    wrapper.call_endpoint(
        "/api/core/firmware/info",
        method="GET",
        query_params={"foo": "bar", "baz": [1, 2]},
    )
    called_url = session.request.call_args.args[1]
    assert called_url.startswith("https://x/api/core/firmware/info?")
    assert "foo=bar" in called_url
    assert "baz=1" in called_url and "baz=2" in called_url


def test_call_endpoint_substitutes_path_params(
    tmp_path: Path,
    mock_httpx_response: Callable[..., httpx.Response],
) -> None:
    """Path placeholders like ``{uuid}`` are replaced with provided values."""
    spec = {
        "openapi": "3.0.3",
        "paths": {"/api/x/{uuid}": {"get": {"responses": {"200": {"description": "ok"}}}}},
    }
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec))

    session = MagicMock(spec=httpx.Client)
    session.headers = {}
    session.request.return_value = _attach_request(
        mock_httpx_response(200, json={"ok": True}),
        "GET",
        "https://x/api/x/abc-123",
    )

    wrapper = APIWrapper(
        api_json_file=str(spec_file),
        base_url="https://x",
        session=session,
    )
    wrapper.call_endpoint(
        "/api/x/{uuid}",
        method="GET",
        path_params={"uuid": "abc-123"},
    )
    called_url = session.request.call_args.args[1]
    assert called_url == "https://x/api/x/abc-123"
