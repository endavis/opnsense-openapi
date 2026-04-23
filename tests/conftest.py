"""Shared pytest fixtures for the opnsense-openapi test suite.

This module centralizes reusable fixtures so individual test modules can stay
focused on the behavior under test. Fixtures here are used by multiple test
modules and follow the patterns established during the initial coverage
ratchet (issue #6).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from hypothesis import HealthCheck, settings

# CI profile: fewer examples, relaxed deadline for slow CI runners
settings.register_profile(
    "ci",
    max_examples=50,
    deadline=500,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.differing_executors],
)

# Default profile: more thorough exploration for local development
settings.register_profile(
    "default",
    max_examples=200,
    suppress_health_check=[HealthCheck.differing_executors],
)

settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


Spec = dict[str, Any] | BaseException | Callable[[list[str]], MagicMock | BaseException]


@pytest.fixture
def mock_subprocess() -> Iterator[MagicMock]:
    """Patch ``tools.doit.github.subprocess.run`` with a prefix-dispatch mock.

    Register command-prefix -> spec mappings via ``.register({...})``. Spec is one
    of: a dict of MagicMock kwargs (``stdout``/``stderr``/``returncode``,
    default ``returncode=0``), a ``BaseException`` instance to raise, or a
    callable ``(cmd) -> MagicMock | BaseException`` for prefix collisions where
    behavior depends on a later argument. Unknown prefixes raise ``AssertionError``.
    """
    with patch("tools.doit.github.subprocess.run") as mock_run:
        dispatch: dict[tuple[str, ...], Spec] = {}

        def side_effect(cmd: list[str], *_a: object, **_kw: object) -> MagicMock:
            for prefix, spec in dispatch.items():
                if tuple(cmd[: len(prefix)]) == prefix:
                    if isinstance(spec, BaseException):
                        raise spec
                    if callable(spec):
                        result = spec(cmd)
                        if isinstance(result, BaseException):
                            raise result
                        return result
                    return MagicMock(
                        returncode=spec.get("returncode", 0),
                        stdout=spec.get("stdout", ""),
                        stderr=spec.get("stderr", ""),
                    )
            raise AssertionError(f"unexpected cmd: {cmd}")

        mock_run.side_effect = side_effect
        mock_run.register = dispatch.update
        yield mock_run


@pytest.fixture
def minimal_openapi_spec() -> dict[str, Any]:
    """Return a minimal OpenAPI 3.0.3 spec dictionary suitable for most tests.

    The spec contains a small but representative mix of paths, components, and
    response shapes so consumers can exercise path iteration, schema lookup,
    and `$ref` resolution.

    Returns:
        A dict representing a minimal OpenAPI spec.
    """
    return {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "24.7"},
        "paths": {
            "/api/core/firmware/info": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "product_version": {"type": "string"},
                                        },
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/firewall/alias/set": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Alias"}}
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"},
                                }
                            }
                        }
                    },
                }
            },
        },
        "components": {
            "schemas": {
                "Alias": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string", "enum": ["host", "network"]},
                    },
                }
            }
        },
    }


@pytest.fixture
def minimal_openapi_spec_file(tmp_path: Path, minimal_openapi_spec: dict[str, Any]) -> Path:
    """Write `minimal_openapi_spec` to a JSON file under ``tmp_path``.

    Args:
        tmp_path: Pytest-provided temporary directory.
        minimal_openapi_spec: The fixture-provided spec dict.

    Returns:
        Path to the written JSON spec file.
    """
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(minimal_openapi_spec))
    return spec_file


@pytest.fixture
def mock_httpx_response() -> Callable[..., httpx.Response]:
    """Return a factory that builds :class:`httpx.Response` objects.

    The factory exposes the same keyword arguments as ``httpx.Response`` but
    pre-populates a sensible JSON content-type when ``json`` is supplied and
    no explicit ``headers`` override is given.

    Returns:
        A callable that produces ``httpx.Response`` instances for tests.
    """

    def _build(
        status_code: int = 200,
        *,
        json: Any = None,
        text: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        response_headers = headers
        if response_headers is None and json is not None:
            response_headers = {"Content-Type": "application/json"}
        kwargs: dict[str, Any] = {"headers": response_headers or {}}
        if json is not None:
            kwargs["json"] = json
        if text is not None:
            kwargs["text"] = text
        return httpx.Response(status_code, **kwargs)

    return _build


@pytest.fixture
def fake_generated_module() -> MagicMock:
    """Return a ``MagicMock`` shaped like a generated API function module.

    The mock exposes ``sync``, ``sync_detailed``, ``asyncio``, and
    ``asyncio_detailed`` attributes so tests of the
    :class:`opnsense_openapi.client.generated_api.FunctionProxy` chain can
    assert call delegation without importing real generated code.

    Returns:
        A ``MagicMock`` with the four generated-API call attributes configured.
    """
    module = MagicMock()
    module.sync = MagicMock(return_value={"sync": True})
    module.sync_detailed = MagicMock(return_value={"sync_detailed": True})

    async def _async_call(**_kwargs: Any) -> dict[str, bool]:
        return {"asyncio": True}

    async def _async_detailed(**_kwargs: Any) -> dict[str, bool]:
        return {"asyncio_detailed": True}

    module.asyncio = _async_call
    module.asyncio_detailed = _async_detailed
    return module


@pytest.fixture
def mock_subprocess_run() -> Iterator[MagicMock]:
    """Patch ``subprocess.run`` and yield the resulting ``MagicMock``.

    The default return value is a ``MagicMock`` with ``returncode=0`` and an
    empty ``stdout`` / ``stderr``. Tests can customize ``return_value`` or
    ``side_effect`` as needed.

    Yields:
        The ``MagicMock`` replacing :func:`subprocess.run`.
    """
    with patch("subprocess.run") as mocked:
        mocked.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mocked
