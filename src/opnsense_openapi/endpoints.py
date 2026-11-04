"""Connection-free endpoint lookup against the bundled OpenAPI specs.

Nothing here touches the network: only the bundled spec JSON is read, and each
spec is parsed once per process. Versions resolve with floor matching (see
[`docs/development/spec-version-resolution.md`](../../docs/development/spec-version-resolution.md)).
"""

import difflib
import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from opnsense_openapi.specs import (
    _version_key,
    find_best_matching_spec,
    get_spec_path,
    list_available_specs,
)

_REPEATED_SLASH_RE = re.compile(r"/{2,}")


def _resolve_spec_path(version: str) -> Path:
    """Resolve a version to a spec file with floor matching.

    Args:
        version: OPNsense version string.

    Returns:
        Path to the best matching spec.

    Raises:
        FileNotFoundError: If the version is malformed or has no spec at or below it.
    """
    try:
        return find_best_matching_spec(version, mode="floor")
    except ValueError as exc:
        raise FileNotFoundError(f"Invalid version {version!r}: {exc}") from exc


@cache
def _load_spec_paths(spec_path: Path) -> dict[str, frozenset[str]]:
    """Load a spec file into a mapping of path to uppercase HTTP methods.

    Args:
        spec_path: Path to an ``opnsense-<version>.json`` file.

    Returns:
        Mapping of API path to the set of methods it supports.
    """
    with spec_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    paths = data.get("paths", {})
    return {path: frozenset(m.upper() for m in ops) for path, ops in paths.items()}


def _normalize_path(path: str) -> str:
    """Normalize a user-supplied endpoint path to the spec's ``/api/...`` form.

    Strips the query string and fragment, collapses repeated slashes, drops a
    trailing slash and ensures a leading ``/api/``.

    Args:
        path: Endpoint path, with or without leading slash or ``api/`` prefix.

    Returns:
        The normalized path, or an empty string if nothing remains.
    """
    path = path.split("#", 1)[0].split("?", 1)[0].strip()
    path = _REPEATED_SLASH_RE.sub("/", "/" + path).rstrip("/")
    if not path:
        return ""
    if path != "/api" and not path.startswith("/api/"):
        path = "/api" + path
    return path


@cache
def _template_index(spec_path: Path) -> dict[int, tuple[tuple[str, tuple[str, ...]], ...]]:
    """Index templated spec paths by segment count.

    Args:
        spec_path: Path to a spec file.

    Returns:
        Mapping of segment count to ``(path, segments)`` pairs for paths
        containing a ``{param}`` segment.
    """
    index: dict[int, list[tuple[str, tuple[str, ...]]]] = {}
    for path in _load_spec_paths(spec_path):
        if "{" not in path:
            continue
        segments = tuple(path.split("/"))
        index.setdefault(len(segments), []).append((path, segments))
    return {count: tuple(items) for count, items in index.items()}


def _is_param(segment: str) -> bool:
    """Return whether a path segment is a ``{param}`` template segment."""
    return segment.startswith("{") and segment.endswith("}")


def _match_template(path: str, spec_path: Path) -> str | None:
    """Find the spec path matching a normalized path, exact or templated.

    A ``{x}`` segment matches any non-empty segment. When several templates
    match, the one with the most literal segments wins.

    Args:
        path: Normalized path (see ``_normalize_path``).
        spec_path: Spec file to match against.

    Returns:
        The matching spec path, or ``None``.
    """
    if path in _load_spec_paths(spec_path):
        return path
    segments = path.split("/")
    best: str | None = None
    best_literals = -1
    for candidate, cand_segments in _template_index(spec_path).get(len(segments), ()):
        literals = 0
        for cand_seg, seg in zip(cand_segments, segments, strict=True):
            if _is_param(cand_seg):
                if not seg:
                    break
            elif cand_seg == seg:
                literals += 1
            else:
                break
        else:
            if literals > best_literals:
                best, best_literals = candidate, literals
    return best


def endpoint_exists(path: str, method: str = "GET", *, version: str) -> bool:
    """Check whether an endpoint exists in the spec for an OPNsense version.

    The leading slash and ``api/`` prefix are optional; a trailing slash,
    repeated slashes and a query string are ignored. Templated segments such
    as ``{uuid}`` match any non-empty value.

    Args:
        path: Endpoint path (e.g., ``"core/tunables/addItem"``).
        method: HTTP method, compared case-insensitively.
        version: OPNsense version (e.g., ``"26.1.6"`` or ``"26.1.6_2"``).

    Returns:
        ``True`` if the path exists in the resolved spec with that method.

    Raises:
        FileNotFoundError: If the version cannot be resolved to a bundled spec.
    """
    spec_path = _resolve_spec_path(version)
    found = _lookup(path, spec_path)
    if found is None:
        return False
    return method.strip().upper() in found[1]


def _lookup(path: str, spec_path: Path) -> tuple[str, frozenset[str]] | None:
    """Match a user-supplied path against one spec file.

    Args:
        path: Endpoint path in any form ``endpoint_exists`` accepts.
        spec_path: Spec file to match against.

    Returns:
        ``(spec path template, allowed methods)``, or ``None`` if nothing matches.
    """
    normalized = _normalize_path(path)
    if not normalized:
        return None
    matched = _match_template(normalized, spec_path)
    if matched is None:
        return None
    return matched, _load_spec_paths(spec_path)[matched]


def resolve_validation_spec(version: str) -> Path:
    """Resolve the spec used to validate calls against a box of ``version``.

    Uses floor matching inside the box's ``major.minor`` series. When that
    series has no spec at or below the version (a box newer than every bundled
    series, or in a series with no bundled spec), falls back to the highest
    bundled spec at or below the version across all series.

    Args:
        version: OPNsense version string (``_N`` suffix ignored).

    Returns:
        Path to the spec file.

    Raises:
        RuntimeError: If the version is malformed or older than every bundled spec.
    """
    try:
        return _resolve_spec_path(version)
    except FileNotFoundError:
        pass
    try:
        key = _version_key(version)
    except ValueError as exc:
        raise RuntimeError(f"Cannot validate endpoints: invalid version {version!r}") from exc
    below = [v for v in list_available_specs() if _version_key(v) <= key]
    if not below:
        raise RuntimeError(
            f"Cannot validate endpoints: no bundled spec at or below version {version!r}"
        )
    return get_spec_path(below[-1])


def suggest_endpoints(path: str, spec_path: Path, limit: int = 3) -> list[str]:
    """Suggest the closest known paths in the same module as ``path``.

    Args:
        path: Endpoint path the caller used.
        spec_path: Spec file to draw suggestions from.
        limit: Maximum number of suggestions.

    Returns:
        Spec paths without the ``/api/`` prefix, closest first. Empty if the
        module is unknown or nothing is close.
    """
    normalized = _normalize_path(path)
    parts = normalized.split("/")
    if len(parts) < 3:
        return []
    prefix = f"/api/{parts[2]}/"
    candidates = [p[len("/api/") :] for p in _load_spec_paths(spec_path) if p.startswith(prefix)]
    return difflib.get_close_matches(normalized[len("/api/") :], candidates, n=limit)


def _endpoint_set(spec_path: Path) -> set[tuple[str, str]]:
    """Return every ``(path, METHOD)`` pair of a spec file as a fresh set."""
    paths = _load_spec_paths(spec_path)
    return {(path, method) for path, methods in paths.items() for method in methods}


def _endpoint_module(path: str) -> str:
    """Return the lowercase module (first segment after ``/api/``), or ``""``."""
    if not path.startswith("/api/"):
        return ""
    return path.split("/")[2].lower()


def list_spec_endpoints(version: str) -> list[tuple[str, str]]:
    """List every ``(path, METHOD)`` pair in the spec for an OPNsense version.

    Args:
        version: OPNsense version (resolved with floor matching).

    Returns:
        Sorted list of ``(path, METHOD)`` tuples with uppercase methods. The
        list is a fresh copy; mutating it does not affect the cache.

    Raises:
        FileNotFoundError: If the version cannot be resolved to a bundled spec.
    """
    return sorted(_endpoint_set(_resolve_spec_path(version)))


@dataclass(frozen=True)
class SpecDiff:
    """Endpoints added and removed between two bundled specs.

    Attributes:
        from_version: Version requested as the baseline.
        to_version: Version requested as the target.
        from_spec: Resolved baseline spec file.
        to_spec: Resolved target spec file.
        added: Sorted ``(path, METHOD)`` pairs present only in the target.
        removed: Sorted ``(path, METHOD)`` pairs present only in the baseline.
    """

    from_version: str
    to_version: str
    from_spec: Path
    to_spec: Path
    added: list[tuple[str, str]]
    removed: list[tuple[str, str]]

    @property
    def is_empty(self) -> bool:
        """Whether no endpoint was added or removed."""
        return not self.added and not self.removed


def diff_specs(from_version: str, to_version: str, *, module: str | None = None) -> SpecDiff:
    """Compare the endpoints of two bundled specs.

    Endpoints are ``(path, METHOD)`` pairs. A path whose only difference is its
    case is reported as one removal plus one addition. Changes to parameters or
    request bodies are not reported.

    Args:
        from_version: Baseline OPNsense version (resolved with floor matching).
        to_version: Target OPNsense version (resolved with floor matching).
        module: Restrict the diff to one module, the first segment after
            ``/api/`` (case-insensitive).

    Returns:
        The diff, with sorted ``added`` and ``removed`` lists.

    Raises:
        FileNotFoundError: If either version cannot be resolved to a bundled spec.
        ValueError: If ``module`` is given and appears in neither spec.
    """
    from_spec = _resolve_spec_path(from_version)
    to_spec = _resolve_spec_path(to_version)
    old = _endpoint_set(from_spec)
    new = _endpoint_set(to_spec)
    if module is not None:
        wanted = module.strip().lower()
        if not any(_endpoint_module(path) == wanted for path, _ in old | new):
            raise ValueError(f"Unknown module {module!r}: not present in either spec")
        old = {e for e in old if _endpoint_module(e[0]) == wanted}
        new = {e for e in new if _endpoint_module(e[0]) == wanted}
    return SpecDiff(
        from_version=from_version,
        to_version=to_version,
        from_spec=from_spec,
        to_spec=to_spec,
        added=sorted(new - old),
        removed=sorted(old - new),
    )
