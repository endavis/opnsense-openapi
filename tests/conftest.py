"""Shared pytest fixtures for the opnsense-openapi test suite.

This module centralizes reusable fixtures so individual test modules can stay
focused on the behavior under test. Fixtures here are used by multiple test
modules and follow the patterns established during the initial coverage
ratchet (issue #6).
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - guarding subprocess use, not invoking it
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from hypothesis import HealthCheck, settings

# CI profile: fewer examples, no deadline.
#
# `deadline=None` rather than a larger number (#736). These are property tests
# over string validation — they assert what a value *is*, never how long it took,
# and `benchmark.yml` covers timing separately. A wall-clock budget on a shared
# runner only adds a way for them to fail for reasons unrelated to the property.
#
# Windows runners were seen taking 1506ms on an example's first call and 0.01ms
# on the retry: interpreter and import warmup, not the code under test. The
# earlier 200ms -> 500ms relaxation did not survive that, and any finite
# replacement is a threshold a bad runner can still cross.
#
# Note that `suppress_health_check=[HealthCheck.too_slow]` does *not* cover this.
# The health check and the per-example deadline are separate mechanisms, which is
# why the profile looked protected against slow runners while still failing on
# them.
settings.register_profile(
    "ci",
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.differing_executors],
)

# Default profile: more thorough exploration for local development.
# Keeps Hypothesis's default deadline — a developer machine is not a shared
# runner, so a genuinely pathological slowdown is worth surfacing locally.
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


# ---------------------------------------------------------------------------
# Hermetic PATH (#710)
# ---------------------------------------------------------------------------

# Unit tests were reaching the real `gh` binary 18 times per run — 14 of them
# `gh api user`, which is a *network* call. That makes results depend on whether
# the developer happens to be authenticated: #689 spent time diagnosing a 0.54pp
# coverage difference that turned out to be exactly this.
#
# Every test now runs with a stub `gh` ahead of the real one. It answers the
# handful of commands the code under test invokes with fixed output matching an
# unauthenticated CI runner, and exits 127 with a loud marker for anything else —
# so a new unmocked call fails visibly rather than depending on the machine.
#
# Tests needing specific `gh` behaviour prepend their own stub ahead of this one
# (see tests/test_statusline_gh_user.py::_stub_gh), which still works. Tests of
# Python code that shells out should mock `subprocess.run` instead; this fixture
# is the backstop for what slips through, and for shell scripts under test, which
# cannot be mocked at the Python level.
_GH_STUB_PY = """import sys

args = sys.argv[1:]
head = " ".join(args[:2])

if head == "auth status":
    # No token markers, so `_check_token_permissions` takes its else branch.
    # Both branches are pinned explicitly in test_setup_repo.py.
    print("Logged in to github.com as test-user", file=sys.stderr)
    sys.exit(0)

if head == "api user":
    # Unauthenticated: the statusline must render no user segment.
    print("gh: authentication required", file=sys.stderr)
    sys.exit(1)

if args[:1] == ["--version"]:
    print("gh version 0.0.0-stub (hermetic test stub)")
    sys.exit(0)

print(
    "HERMETIC-STUB: unmocked 'gh " + " ".join(args) + "' reached the real PATH (#710)",
    file=sys.stderr,
)
sys.exit(127)
"""


# Commands no test may reach through Python's subprocess. The PATH stub above
# covers shell scripts under test, but it cannot help on Windows: CreateProcess
# searches only `gh` and `gh.exe` and never consults PATHEXT for `.CMD`, so a
# Python-level `subprocess.run(["gh", ...])` would still find the real binary
# there. Failing the call outright makes hermeticity hold on every platform
# rather than on POSIX only (#710).
#
# Only `gh` is covered. `git` is invoked against tmp_path repositories where
# running the real binary is the point of the test, not a leak.
_UNMOCKED_COMMANDS = frozenset({"gh"})


@pytest.fixture(autouse=True)
def _no_unmocked_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if a test shells out to `gh` without mocking it."""
    real_run = subprocess.run

    def guarded(cmd: object, *args: object, **kwargs: object) -> object:
        if isinstance(cmd, (list, tuple)) and cmd and str(cmd[0]) in _UNMOCKED_COMMANDS:
            raise AssertionError(
                f"unmocked subprocess call to {list(cmd)!r}. Patch subprocess.run in "
                "the module under test — a real call makes the result depend on the "
                "developer's machine (#710)."
            )
        # Deliberately signature-agnostic: this forwards arbitrary calls, so it
        # cannot match subprocess.run's overload set.
        return real_run(cmd, *args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(subprocess, "run", guarded)


@pytest.fixture(autouse=True)
def _hermetic_path(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Put a stub `gh` ahead of the real one for every test.

    The dispatch lives in Python so there is one implementation; only the
    launcher differs per platform. Windows resolves executables through
    ``PATHEXT``, so an extensionless shell script named ``gh`` is not executable
    there — the first version of this fixture silently no-opped on Windows and
    the suite kept calling the real binary.

    Both launchers are written on Windows: ``gh.CMD`` for ``PATHEXT`` resolution,
    and an extensionless ``gh`` for the Git Bash used to run the shell scripts
    under test, which does not consult ``PATHEXT``.
    """
    bin_dir = tmp_path_factory.mktemp("hermetic-bin")
    (bin_dir / "_gh_stub.py").write_text(_GH_STUB_PY, encoding="utf-8")

    shim = bin_dir / "gh"
    shim.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/_gh_stub.py" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)

    if os.name == "nt":
        (bin_dir / "gh.CMD").write_text(
            f'@echo off\r\n"{sys.executable}" "%~dp0_gh_stub.py" %*\r\n',
            encoding="utf-8",
        )

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
