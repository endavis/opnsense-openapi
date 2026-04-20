"""Tests for :mod:`opnsense_openapi.client.generated_api`."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from opnsense_openapi.client.generated_api import (
    FunctionProxy,
    GeneratedAPI,
    ModuleProxy,
)


def test_generated_api_repr_includes_version() -> None:
    """GeneratedAPI.__repr__ surfaces the version string."""
    api = GeneratedAPI(generated_client=MagicMock(), version="25.7.6")
    assert repr(api) == "GeneratedAPI(version=25.7.6)"


def test_generated_api_getattr_returns_module_proxy() -> None:
    """Attribute access yields a ModuleProxy carrying the normalized version."""
    client = MagicMock()
    api = GeneratedAPI(generated_client=client, version="25.7.6")

    proxy = api.core

    assert isinstance(proxy, ModuleProxy)
    assert proxy._client is client
    assert proxy._module_name == "core"
    assert proxy._version_module == "25_7_6"


def test_module_proxy_repr_includes_module_name() -> None:
    """ModuleProxy.__repr__ surfaces the module name."""
    proxy = ModuleProxy(client=MagicMock(), version_module="25_7_6", module_name="firewall")
    assert repr(proxy) == "ModuleProxy(module=firewall)"


def test_module_proxy_getattr_returns_function_proxy() -> None:
    """ModuleProxy attribute access yields a FunctionProxy bound to the module."""
    client = MagicMock()
    module = ModuleProxy(client=client, version_module="25_7_6", module_name="core")

    func = module.firmware_info

    assert isinstance(func, FunctionProxy)
    assert func._client is client
    assert func._module_name == "core"
    assert func._function_name == "firmware_info"
    assert func._version_module == "25_7_6"


def test_function_proxy_repr_includes_fully_qualified_name() -> None:
    """FunctionProxy.__repr__ surfaces ``module.function`` for debuggability."""
    proxy = FunctionProxy(
        client=MagicMock(),
        version_module="25_7_6",
        module_name="core",
        function_name="firmware_info",
    )
    assert repr(proxy) == "FunctionProxy(function=core.firmware_info)"


def _build_proxy(client: Any = None) -> FunctionProxy:
    """Build a FunctionProxy wired to the given client (or a fresh MagicMock)."""
    return FunctionProxy(
        client=client if client is not None else MagicMock(),
        version_module="25_7_6",
        module_name="core",
        function_name="firmware_info",
    )


def test_load_function_module_imports_expected_path(fake_generated_module: MagicMock) -> None:
    """_load_function_module imports the generated module via importlib."""
    proxy = _build_proxy()

    with patch("importlib.import_module", return_value=fake_generated_module) as imp:
        module = proxy._load_function_module()

    imp.assert_called_once_with(
        "opnsense_openapi.generated.v25_7_6.opnsense_openapi_client.api.core.core_firmware_info"
    )
    assert module is fake_generated_module


def test_load_function_module_caches_result(fake_generated_module: MagicMock) -> None:
    """Subsequent calls reuse the cached module rather than re-importing."""
    proxy = _build_proxy()

    with patch("importlib.import_module", return_value=fake_generated_module) as imp:
        first = proxy._load_function_module()
        second = proxy._load_function_module()

    assert first is second
    imp.assert_called_once()


def test_load_function_module_converts_import_error(
    fake_generated_module: MagicMock,
) -> None:
    """ImportError is re-raised as AttributeError with a helpful message."""
    proxy = _build_proxy()

    with (
        patch("importlib.import_module", side_effect=ImportError("boom")),
        pytest.raises(AttributeError, match=r"core\.firmware_info"),
    ):
        proxy._load_function_module()


def test_call_delegates_to_sync(fake_generated_module: MagicMock) -> None:
    """FunctionProxy.__call__ is shorthand for ``.sync(**kwargs)``."""
    client = MagicMock()
    proxy = _build_proxy(client=client)

    with patch("importlib.import_module", return_value=fake_generated_module):
        result = proxy(foo="bar")

    assert result == {"sync": True}
    fake_generated_module.sync.assert_called_once_with(client=client, foo="bar")


def test_sync_detailed_routes_through_generated_module(
    fake_generated_module: MagicMock,
) -> None:
    """sync_detailed() forwards kwargs to the generated helper."""
    client = MagicMock()
    proxy = _build_proxy(client=client)

    with patch("importlib.import_module", return_value=fake_generated_module):
        result = proxy.sync_detailed(a=1)

    assert result == {"sync_detailed": True}
    fake_generated_module.sync_detailed.assert_called_once_with(client=client, a=1)


def test_asyncio_awaits_generated_coroutine(fake_generated_module: MagicMock) -> None:
    """asyncio() awaits the generated ``asyncio`` coroutine."""
    client = MagicMock()
    proxy = _build_proxy(client=client)

    with patch("importlib.import_module", return_value=fake_generated_module):
        result = asyncio.run(proxy.asyncio(foo=1))

    assert result == {"asyncio": True}


def test_asyncio_detailed_awaits_generated_coroutine(
    fake_generated_module: MagicMock,
) -> None:
    """asyncio_detailed() awaits the generated ``asyncio_detailed`` coroutine."""
    proxy = _build_proxy()

    with patch("importlib.import_module", return_value=fake_generated_module):
        result = asyncio.run(proxy.asyncio_detailed())

    assert result == {"asyncio_detailed": True}
