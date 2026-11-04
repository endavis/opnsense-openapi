"""Tests for connection-free endpoint lookup."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest

from opnsense_openapi import endpoint_exists, list_spec_endpoints
from opnsense_openapi import endpoints as endpoints_mod
from opnsense_openapi.specs import find_best_matching_spec

VERSION = "26.1.6"


def test_issue_examples() -> None:
    assert endpoint_exists("core/tunables/addItem", "POST", version=VERSION) is True
    assert endpoint_exists("system/general/get", "GET", version=VERSION) is False


@pytest.mark.parametrize(
    "path",
    [
        "core/tunables/addItem",
        "/core/tunables/addItem",
        "api/core/tunables/addItem",
        "/api/core/tunables/addItem",
        "/api/core/tunables/addItem/",
        "/api//core//tunables/addItem",
        "/api/core/tunables/addItem?x=1#frag",
    ],
)
def test_path_forms_are_equivalent(path: str) -> None:
    assert endpoint_exists(path, "POST", version=VERSION)


def test_templated_paths() -> None:
    assert endpoint_exists("core/tunables/setItem/abc-123", "POST", version=VERSION)
    assert endpoint_exists("core/tunables/getItem/abc-123", "GET", version=VERSION)
    assert not endpoint_exists("core/tunables/getItem/abc-123", "POST", version=VERSION)
    assert not endpoint_exists("core/tunables/getItem/a/b", "GET", version=VERSION)
    assert not endpoint_exists("core/tunables/getItem", "GET", version=VERSION)


def test_method_handling() -> None:
    assert not endpoint_exists("core/firmware/install", "GET", version=VERSION)
    assert endpoint_exists("core/firmware/install", " post ", version=VERSION)
    assert not endpoint_exists("core/firmware/install", "PATCH", version=VERSION)
    assert not endpoint_exists("core/firmware/install", "", version=VERSION)


@pytest.mark.parametrize("path", ["", "/", "///", "?x=1"])
def test_empty_path_is_false(path: str) -> None:
    assert endpoint_exists(path, version=VERSION) is False


def test_security_patch_suffix_equivalent() -> None:
    assert list_spec_endpoints("26.1.6_2") == list_spec_endpoints("26.1.6")
    assert endpoint_exists("core/tunables/addItem", "POST", version="26.1.6_2")


def test_floor_and_newest_resolution(
    fake_specs: Callable[[dict[str, dict[str, dict[str, object]]]], Path],
) -> None:
    specs_dir = fake_specs(
        {
            "30.1.1": {"/api/a/only_old": {"get": {}}},
            "30.1.5": {"/api/a/only_new": {"get": {}}},
        }
    )
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=specs_dir):
        # Between the two specs: floor picks 30.1.1.
        assert endpoint_exists("a/only_old", version="30.1.3")
        assert not endpoint_exists("a/only_new", version="30.1.3")
        # Above the newest: resolves to the newest.
        assert endpoint_exists("a/only_new", version="30.1.99")


def test_template_prefers_more_literal_segments(
    fake_specs: Callable[[dict[str, dict[str, dict[str, object]]]], Path],
) -> None:
    specs_dir = fake_specs(
        {"31.1.1": {"/api/x/{id}/y": {"get": {}}, "/api/x/special/y": {"post": {}}}}
    )
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=specs_dir):
        assert endpoint_exists("x/special/y", "POST", version="31.1.1")
        assert not endpoint_exists("x/special/y", "GET", version="31.1.1")
        assert endpoint_exists("x/other/y", "GET", version="31.1.1")


@pytest.mark.parametrize("version", ["1.0.0", "garbage", "", "26", "26.x.1"])
def test_unresolvable_versions_raise(version: str) -> None:
    with pytest.raises(FileNotFoundError):
        endpoint_exists("core/tunables/addItem", version=version)
    with pytest.raises(FileNotFoundError):
        list_spec_endpoints(version)


def test_below_oldest_raises(
    fake_specs: Callable[[dict[str, dict[str, dict[str, object]]]], Path],
) -> None:
    specs_dir = fake_specs({"32.1.5": {"/api/a/b": {"get": {}}}})
    with (
        patch("opnsense_openapi.specs.get_specs_dir", return_value=specs_dir),
        pytest.raises(FileNotFoundError),
    ):
        endpoint_exists("a/b", version="32.1.1")


def test_list_spec_endpoints() -> None:
    result = list_spec_endpoints(VERSION)
    spec = json.loads(find_best_matching_spec(VERSION).read_text())
    assert result == sorted(result)
    assert all(m == m.upper() for _, m in result)
    assert len(result) == sum(len(ops) for ops in spec["paths"].values())
    assert ("/api/core/tunables/addItem", "POST") in result


def test_list_returns_copy() -> None:
    first = list_spec_endpoints(VERSION)
    first.clear()
    assert list_spec_endpoints(VERSION)


def test_spec_loaded_once() -> None:
    endpoints_mod._load_spec_paths.cache_clear()
    with patch.object(endpoints_mod.json, "load", wraps=endpoints_mod.json.load) as load:
        for _ in range(5):
            endpoint_exists("core/tunables/addItem", "POST", version=VERSION)
            list_spec_endpoints(VERSION)
    assert load.call_count == 1


def test_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    assert endpoint_exists("core/tunables/addItem", "POST", version=VERSION)


def test_package_root_exports() -> None:
    import opnsense_openapi

    for name in (
        "endpoint_exists",
        "list_spec_endpoints",
        "newest_spec_version",
        "is_version_covered",
    ):
        assert callable(getattr(opnsense_openapi, name))
        assert name in opnsense_openapi.__all__


def test_resolve_validation_spec_in_series_floor() -> None:
    assert endpoints_mod.resolve_validation_spec("26.1.6_2").name == "opnsense-26.1.6.json"


def test_resolve_validation_spec_cross_series_fallback(
    fake_specs: Callable[[dict[str, dict[str, dict[str, object]]]], Path],
) -> None:
    specs_dir = fake_specs({"33.1.1": {"/api/a/b": {"get": {}}}, "33.7.2": {"/api/a/c": {}}})
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=specs_dir):
        assert endpoints_mod.resolve_validation_spec("33.7.9").name == "opnsense-33.7.2.json"
        assert endpoints_mod.resolve_validation_spec("33.4.1").name == "opnsense-33.1.1.json"
        assert endpoints_mod.resolve_validation_spec("34.1.1").name == "opnsense-33.7.2.json"


@pytest.mark.parametrize("version", ["1.0.0", "garbage", "", "26.x.1"])
def test_resolve_validation_spec_unresolvable(version: str) -> None:
    with pytest.raises(RuntimeError):
        endpoints_mod.resolve_validation_spec(version)


def test_lookup_and_suggest_endpoints() -> None:
    spec = find_best_matching_spec(VERSION)
    assert endpoints_mod._lookup("core/tunables/setItem/x", spec) == (
        "/api/core/tunables/setItem/{uuid}",
        frozenset({"POST"}),
    )
    assert endpoints_mod._lookup("", spec) is None
    assert endpoints_mod._lookup("core/nope/nope", spec) is None
    assert "core/firmware/install" in endpoints_mod.suggest_endpoints("core/firmware/inastll", spec)
    assert endpoints_mod.suggest_endpoints("nomodule/x/y", spec) == []
    assert endpoints_mod.suggest_endpoints("core", spec) == []
    assert len(endpoints_mod.suggest_endpoints("core/firmware/inastll", spec, limit=1)) == 1
