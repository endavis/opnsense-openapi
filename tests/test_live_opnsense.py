"""Live-API contract test for spec path routing.

This is the runtime counterpart to ``tests/test_spec_path_routing.py``. The
structural lint there asserts that every spec path reverse-maps to a real
``*Controller.php`` file in the matching OPNsense source archive — a static
check. This test asserts the same paths actually return non-404 with
shape-matching JSON when called against a live OPNsense instance — the
runtime check.

It is opt-in via ``pytest -m live_opnsense``. The default ``doit test`` run
collects it but skips it cleanly because the marker is unselected. When run
explicitly with ``-m live_opnsense``, it skips with a clear reason if any of
``OPNSENSE_URL``, ``OPNSENSE_API_KEY``, ``OPNSENSE_API_SECRET`` are missing
or if the box's detected firmware version has no committed spec.

Two layers of tests live here:

* The marked live test (``live_opnsense``) instantiates
  :class:`OPNsenseClient`, calls :meth:`OPNsenseClient.detect_version`, loads
  the matching committed spec, samples ~25 read-only operations, hits each,
  collects per-op pass/fail, and asserts zero failures.
* Unmarked unit tests exercise the module-level helpers
  (:func:`_load_spec_for_version`, :func:`_sample_read_only_ops`,
  :func:`_validate_light`) against synthetic specs. These run on every CI
  pass and verify the helpers without needing a live target.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any

import httpx
import pytest

from opnsense_openapi.client.base import APIResponseError, OPNsenseClient
from opnsense_openapi.specs import get_specs_dir

# Tokens in a path segment that strongly imply a read-only operation. Used to
# bias sampling toward endpoints that are safe to call against a live box.
READ_ONLY_TOKENS: tuple[str, ...] = ("get", "list", "show", "search")

# Default sample size. Override at runtime with the env var below; useful when
# debugging a misbehaving box or restricting load on a slow target.
DEFAULT_SAMPLE_SIZE: int = 25
SAMPLE_SIZE_ENV: str = "OPNSENSE_LIVE_SAMPLE_SIZE"

# Deterministic seed so a failing run is reproducible. Override only when
# investigating sampling bias.
DEFAULT_SEED: int = 0
SEED_ENV: str = "OPNSENSE_LIVE_SEED"


def _load_spec_for_version(version: str) -> dict[str, Any] | None:
    """Load the committed spec whose filename exactly matches ``version``.

    Spec lookup is intentionally exact-match only (no major.minor fallback
    like :func:`opnsense_openapi.specs.find_best_matching_spec`). The live
    test treats a version mismatch as a skip condition rather than silently
    testing the box against a different version's contract.

    Args:
        version: OPNsense marketing version string from
            :meth:`OPNsenseClient.detect_version` (e.g., ``"24.7.10"``).

    Returns:
        Parsed spec dict, or ``None`` if no exact-match file exists under
        ``src/opnsense_openapi/specs/opnsense-{version}.json``.
    """
    spec_path: Path = get_specs_dir() / f"opnsense-{version}.json"
    if not spec_path.is_file():
        return None
    return json.loads(spec_path.read_text(encoding="utf-8"))


def _is_read_only_path(path: str) -> bool:
    """Return True if any path segment hints at a read-only operation.

    Used as a sampling bias, not a hard filter — paths without any of the
    :data:`READ_ONLY_TOKENS` are still eligible (since ``GET`` already
    implies read-only at the HTTP level), they just sort after biased ones.

    Args:
        path: A spec path like ``/api/firewall/alias/searchItem``.

    Returns:
        True if a segment of ``path`` starts with one of the read-only
        tokens (case-insensitive).
    """
    for segment in path.split("/"):
        seg_lower: str = segment.lower()
        for token in READ_ONLY_TOKENS:
            if seg_lower.startswith(token):
                return True
    return False


def _collect_get_only_paths(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(path, get_operation)`` pairs for every GET-only path.

    A path is GET-only when its operation map contains only the ``get``
    method (case-insensitive). The plan filters to GET-only because some
    paths declare both GET and POST and we never want a sampler to hit the
    POST variant against a live box.

    Args:
        spec: Parsed OpenAPI spec dict.

    Returns:
        List of ``(path, operation)`` tuples sorted by path for stable
        sampling. Empty if no eligible paths.
    """
    pairs: list[tuple[str, dict[str, Any]]] = []
    paths: dict[str, Any] = spec.get("paths", {})
    for path, ops in paths.items():
        method_keys: list[str] = [m.lower() for m in ops]
        if method_keys == ["get"]:
            pairs.append((path, ops["get"]))
    pairs.sort(key=lambda item: item[0])
    return pairs


def _sample_read_only_ops(
    spec: dict[str, Any],
    n: int,
    rng: random.Random,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Sample up to ``n`` ``(method, path, operation)`` triples from ``spec``.

    Restricts to GET-only paths, then biases the sample toward paths whose
    segments start with one of :data:`READ_ONLY_TOKENS`. Bias is implemented
    by sampling biased and unbiased buckets in a 2:1 weight: up to
    ``2 * n // 3`` from the biased bucket, the remainder from the
    unbiased bucket. If either bucket is short, the other tops up.

    Args:
        spec: Parsed OpenAPI spec dict.
        n: Upper bound on sample size. The result may be smaller if the
            spec has fewer than ``n`` eligible paths.
        rng: Seeded :class:`random.Random` instance for determinism.

    Returns:
        List of ``(method, path, operation)`` triples. ``method`` is always
        ``"GET"``.

    Raises:
        ValueError: If the spec contains zero GET-only paths.
    """
    candidates: list[tuple[str, dict[str, Any]]] = _collect_get_only_paths(spec)
    if not candidates:
        raise ValueError("Spec has no GET-only paths to sample from")

    biased: list[tuple[str, dict[str, Any]]] = [c for c in candidates if _is_read_only_path(c[0])]
    unbiased: list[tuple[str, dict[str, Any]]] = [
        c for c in candidates if not _is_read_only_path(c[0])
    ]

    biased_quota: int = min(len(biased), max(1, (2 * n) // 3))
    unbiased_quota: int = min(len(unbiased), n - biased_quota)
    # Top up either side if the other was short.
    if biased_quota + unbiased_quota < n:
        slack: int = n - biased_quota - unbiased_quota
        if len(biased) > biased_quota:
            extra: int = min(slack, len(biased) - biased_quota)
            biased_quota += extra
            slack -= extra
        if slack and len(unbiased) > unbiased_quota:
            unbiased_quota += min(slack, len(unbiased) - unbiased_quota)

    sampled_biased: list[tuple[str, dict[str, Any]]] = (
        rng.sample(biased, biased_quota) if biased_quota else []
    )
    sampled_unbiased: list[tuple[str, dict[str, Any]]] = (
        rng.sample(unbiased, unbiased_quota) if unbiased_quota else []
    )

    combined: list[tuple[str, dict[str, Any]]] = sampled_biased + sampled_unbiased
    # Shuffle the combined output so callers don't see all biased items
    # first; deterministic given the seeded rng.
    rng.shuffle(combined)
    return [("GET", path, op) for path, op in combined]


def _expected_top_level_types(operation: dict[str, Any]) -> set[str] | None:
    """Extract the declared top-level JSON type(s) for a 200 response.

    Drills into ``operation.responses['200'].content['application/json']``
    and reads either an inline ``schema`` or a ``$ref``. Top-level types are
    exactly ``"object"`` and ``"array"`` (the only two compositions used in
    the committed specs). If the schema uses ``oneOf``/``anyOf``, every
    branch's type is unioned. ``$ref`` is treated as opaque (returns
    ``None``) — drilling into ``components/schemas`` to validate every
    referenced shape would couple this test too tightly to spec drift.

    Args:
        operation: OpenAPI operation dict.

    Returns:
        A set of expected top-level types (subset of ``{"object",
        "array"}``), or ``None`` if no usable schema is declared.
    """
    responses: dict[str, Any] = operation.get("responses", {})
    response_200: dict[str, Any] = responses.get("200", {})
    if not response_200:
        return None

    content: dict[str, Any] = response_200.get("content", {})
    json_content: dict[str, Any] = content.get("application/json", {})
    if not json_content:
        return None

    # Some operations declare ``$ref`` directly under content/json (legacy
    # shape in the committed specs). Treated as opaque.
    if "$ref" in json_content:
        return None

    schema: dict[str, Any] | None = json_content.get("schema")
    if not schema:
        return None
    if "$ref" in schema:
        return None

    types: set[str] = set()
    declared_type: str | None = schema.get("type")
    if declared_type in ("object", "array"):
        types.add(declared_type)

    for branch_key in ("oneOf", "anyOf"):
        branches: list[dict[str, Any]] = schema.get(branch_key, [])
        for branch in branches:
            if "$ref" in branch:
                # Opaque branch — give up on strict validation.
                return None
            branch_type: str | None = branch.get("type")
            if branch_type in ("object", "array"):
                types.add(branch_type)

    return types or None


def _validate_light(body: Any, operation: dict[str, Any]) -> str | None:
    """Light-touch shape check for a parsed JSON response body.

    Asserts the top-level type (object vs. array) matches the operation's
    declared response schema. Permissive when no schema is declared or the
    schema is opaque (``$ref``). Does not validate nested fields, types,
    enums, or constraints — that level of strictness would couple the
    contract test to spec drift.

    Args:
        body: Already-decoded JSON body.
        operation: OpenAPI operation dict.

    Returns:
        ``None`` if the body matches (or no expectation can be derived).
        A human-readable failure reason otherwise.
    """
    expected: set[str] | None = _expected_top_level_types(operation)
    if expected is None:
        return None

    actual: str
    if isinstance(body, dict):
        actual = "object"
    elif isinstance(body, list):
        actual = "array"
    else:
        actual = type(body).__name__

    if actual not in expected:
        return f"top-level type mismatch: expected one of {sorted(expected)}, got {actual!r}"
    return None


def _split_api_path(path: str) -> tuple[str, str, str, tuple[str, ...]] | None:
    """Split ``/api/{module}/{controller}/{command}[/...]`` into parts.

    The :class:`OPNsenseClient` ``get`` method takes ``module``,
    ``controller``, ``command``, and trailing ``*params``. This splits a
    spec path into those components.

    Args:
        path: A spec path like ``/api/firewall/alias/searchItem``.

    Returns:
        ``(module, controller, command, params)`` or ``None`` if the path
        does not match the expected shape (in which case the caller should
        skip this op).
    """
    parts: list[str] = path.strip("/").split("/")
    if len(parts) < 4 or parts[0] != "api":
        return None
    module: str = parts[1]
    controller: str = parts[2]
    command: str = parts[3]
    params: tuple[str, ...] = tuple(parts[4:])
    return module, controller, command, params


def _has_unresolved_path_params(params: tuple[str, ...]) -> bool:
    """Return True if any path param is a literal placeholder.

    Spec paths with templates like ``/api/.../{uuid}`` cannot be hit
    blindly against a live box because we have no real UUID. The caller
    skips these in the live sampling loop.
    """
    return any(p.startswith("{") and p.endswith("}") for p in params)


# ---------------------------------------------------------------------------
# Unmarked unit tests — exercise helpers against synthetic specs.
# These run on every CI pass without needing a live OPNsense instance.
# ---------------------------------------------------------------------------


def test_load_spec_for_version_returns_dict_for_known_version() -> None:
    """An exact-match committed spec is loaded and parsed."""
    # Pick the first available committed spec to avoid hard-coding a version.
    specs_dir: Path = get_specs_dir()
    spec_files: list[Path] = sorted(specs_dir.glob("opnsense-*.json"))
    if not spec_files:
        pytest.skip("No committed specs available")

    version: str = spec_files[0].stem.removeprefix("opnsense-")
    spec: dict[str, Any] | None = _load_spec_for_version(version)

    assert spec is not None
    assert spec.get("openapi", "").startswith("3.")
    assert "paths" in spec


def test_load_spec_for_version_returns_none_for_unknown_version() -> None:
    """A version with no committed spec returns None (not an exception)."""
    assert _load_spec_for_version("0.0.0-nonexistent") is None


def test_sample_read_only_ops_returns_only_get_operations() -> None:
    """Sampler restricts to paths whose only declared op is GET."""
    spec: dict[str, Any] = {
        "paths": {
            "/api/m/c/getOne": {"get": {"responses": {"200": {}}}},
            "/api/m/c/post_only": {"post": {"responses": {"200": {}}}},
            "/api/m/c/getAndPost": {
                "get": {"responses": {"200": {}}},
                "post": {"responses": {"200": {}}},
            },
            "/api/m/c/listAll": {"get": {"responses": {"200": {}}}},
        }
    }
    rng: random.Random = random.Random(0)
    triples: list[tuple[str, str, dict[str, Any]]] = _sample_read_only_ops(spec, n=10, rng=rng)

    methods: set[str] = {m for m, _, _ in triples}
    paths: set[str] = {p for _, p, _ in triples}
    assert methods == {"GET"}
    # POST-only and GET+POST mixed paths are excluded.
    assert "/api/m/c/post_only" not in paths
    assert "/api/m/c/getAndPost" not in paths


def test_sample_read_only_ops_caps_at_n_and_is_deterministic() -> None:
    """``n`` is an upper bound; identical seed yields identical samples."""
    spec: dict[str, Any] = {
        "paths": {f"/api/m/c/getItem{i}": {"get": {"responses": {"200": {}}}} for i in range(50)}
    }
    rng_a: random.Random = random.Random(42)
    rng_b: random.Random = random.Random(42)
    triples_a: list[tuple[str, str, dict[str, Any]]] = _sample_read_only_ops(spec, n=10, rng=rng_a)
    triples_b: list[tuple[str, str, dict[str, Any]]] = _sample_read_only_ops(spec, n=10, rng=rng_b)

    assert len(triples_a) == 10
    paths_a: list[str] = [p for _, p, _ in triples_a]
    paths_b: list[str] = [p for _, p, _ in triples_b]
    assert paths_a == paths_b


def test_sample_read_only_ops_biases_toward_read_only_tokens() -> None:
    """Output proportion of biased paths exceeds input proportion."""
    # 4 read-only-ish paths, 16 neutral paths. Biased proportion in input is
    # 4/20 = 0.20. With 2:1 weighting and a sample of 9, the biased bucket
    # gets ceil(9 * 2/3) = 6 slots, so output proportion should be 6/9 = 0.67.
    spec: dict[str, Any] = {
        "paths": {
            **{f"/api/m/c/getItem{i}": {"get": {"responses": {"200": {}}}} for i in range(2)},
            **{f"/api/m/c/listItem{i}": {"get": {"responses": {"200": {}}}} for i in range(2)},
            **{f"/api/m/c/op{i}": {"get": {"responses": {"200": {}}}} for i in range(16)},
        }
    }
    rng: random.Random = random.Random(0)
    triples: list[tuple[str, str, dict[str, Any]]] = _sample_read_only_ops(spec, n=9, rng=rng)
    biased_count: int = sum(1 for _, p, _ in triples if _is_read_only_path(p))

    input_prop: float = 4 / 20
    output_prop: float = biased_count / len(triples)
    assert output_prop > input_prop, (
        f"expected output bias {output_prop} > input bias {input_prop}; "
        f"sample paths: {[p for _, p, _ in triples]}"
    )


def test_sample_read_only_ops_raises_on_no_get_paths() -> None:
    """Spec with zero GET-only paths surfaces a clear error."""
    spec: dict[str, Any] = {
        "paths": {
            "/api/m/c/post1": {"post": {"responses": {"200": {}}}},
            "/api/m/c/post2": {"post": {"responses": {"200": {}}}},
        }
    }
    rng: random.Random = random.Random(0)
    with pytest.raises(ValueError, match="GET-only paths"):
        _sample_read_only_ops(spec, n=5, rng=rng)


def test_validate_light_passes_when_top_level_object_matches() -> None:
    """Object body satisfies an operation declaring ``type: object``."""
    operation: dict[str, Any] = {
        "responses": {
            "200": {
                "content": {"application/json": {"schema": {"type": "object"}}},
            }
        }
    }
    assert _validate_light({"foo": 1}, operation) is None


def test_validate_light_passes_when_top_level_array_matches() -> None:
    """Array body satisfies an operation declaring ``type: array``."""
    operation: dict[str, Any] = {
        "responses": {
            "200": {
                "content": {"application/json": {"schema": {"type": "array"}}},
            }
        }
    }
    assert _validate_light([1, 2, 3], operation) is None


def test_validate_light_fails_when_top_level_type_mismatches() -> None:
    """List body does not satisfy an operation declaring ``type: object``."""
    operation: dict[str, Any] = {
        "responses": {
            "200": {
                "content": {"application/json": {"schema": {"type": "object"}}},
            }
        }
    }
    reason: str | None = _validate_light([1, 2, 3], operation)
    assert reason is not None
    assert "array" in reason
    assert "object" in reason


def test_validate_light_is_permissive_when_no_schema() -> None:
    """No declared schema (or ``$ref``) produces no failure."""
    no_response: dict[str, Any] = {"responses": {"200": {"description": "ok"}}}
    assert _validate_light({"anything": True}, no_response) is None

    ref_only: dict[str, Any] = {
        "responses": {"200": {"content": {"application/json": {"$ref": "#/components/schemas/X"}}}}
    }
    assert _validate_light([1, 2, 3], ref_only) is None

    schema_ref: dict[str, Any] = {
        "responses": {
            "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/X"}}}}
        }
    }
    assert _validate_light(42, schema_ref) is None


def test_split_api_path_handles_well_formed_path() -> None:
    """Path splitter returns module/controller/command and trailing params."""
    result: tuple[str, str, str, tuple[str, ...]] | None = _split_api_path(
        "/api/firewall/alias/searchItem"
    )
    assert result == ("firewall", "alias", "searchItem", ())


def test_split_api_path_returns_none_for_malformed_path() -> None:
    """Path that is not ``/api/{m}/{c}/{cmd}`` returns None."""
    assert _split_api_path("/health") is None
    assert _split_api_path("/api/onlytwo") is None
    assert _split_api_path("/api/three/segments") is None


def test_has_unresolved_path_params_detects_template_segments() -> None:
    """Template segments like ``{uuid}`` are flagged."""
    assert _has_unresolved_path_params(("{uuid}",)) is True
    assert _has_unresolved_path_params(("foo", "{uuid}")) is True
    assert _has_unresolved_path_params(("foo", "bar")) is False
    assert _has_unresolved_path_params(()) is False


# ---------------------------------------------------------------------------
# Live test — opt-in via ``-m live_opnsense``.
# Skipped cleanly if env vars are missing or the box's version has no spec.
# ---------------------------------------------------------------------------


@pytest.mark.live_opnsense
def test_live_opnsense_paths_resolve() -> None:
    """Sampled spec paths return non-404 with shape-matching JSON.

    This is the runtime contract test promised by issue #40. It would have
    caught issue #32 (collapsed-lowercase URL segments returning 404)
    against any real OPNsense box. It is opt-in because it requires a live
    target with credentials, and not every environment has one.

    Skips with a clear reason when:

    * Any of ``OPNSENSE_URL``, ``OPNSENSE_API_KEY``,
      ``OPNSENSE_API_SECRET`` is missing from the environment.
    * The box's :meth:`OPNsenseClient.detect_version` return value has no
      exact-match committed spec under
      ``src/opnsense_openapi/specs/opnsense-{version}.json``.

    Reports per-op pass/fail in the assertion message so a failing run
    surfaces every broken path in one go.
    """
    base_url: str | None = os.getenv("OPNSENSE_URL")
    api_key: str | None = os.getenv("OPNSENSE_API_KEY")
    api_secret: str | None = os.getenv("OPNSENSE_API_SECRET")
    if not base_url or not api_key or not api_secret:
        pytest.skip(
            "Live test requires OPNSENSE_URL, OPNSENSE_API_KEY, and "
            "OPNSENSE_API_SECRET environment variables. "
            "See .envrc.local.example."
        )

    sample_size: int = int(os.getenv(SAMPLE_SIZE_ENV, str(DEFAULT_SAMPLE_SIZE)))
    seed: int = int(os.getenv(SEED_ENV, str(DEFAULT_SEED)))

    # auto_detect_version=False so construction does not implicitly fire a
    # request; we call detect_version() explicitly and treat its failure as
    # a test failure rather than as silently-disabled OpenAPI features.
    with OPNsenseClient(
        base_url=base_url,
        api_key=api_key,
        api_secret=api_secret,
        verify_ssl=False,
        auto_detect_version=False,
    ) as client:
        try:
            version: str = client.detect_version()
        except (APIResponseError, httpx.HTTPError) as exc:
            pytest.fail(f"Could not detect OPNsense version from {base_url}: {exc}")

        spec: dict[str, Any] | None = _load_spec_for_version(version)
        if spec is None:
            pytest.skip(
                f"Detected OPNsense version {version!r} has no exact-match "
                f"committed spec under {get_specs_dir()}. "
                "Multi-version coverage is out of scope for this test; add "
                "the matching spec or run against a box with a covered version."
            )

        rng: random.Random = random.Random(seed)
        triples: list[tuple[str, str, dict[str, Any]]] = _sample_read_only_ops(
            spec, n=sample_size, rng=rng
        )

        failures: list[str] = []
        for method, path, operation in triples:
            split: tuple[str, str, str, tuple[str, ...]] | None = _split_api_path(path)
            if split is None:
                # Defensive: a well-formed spec shouldn't yield this, but
                # don't crash the whole run on one malformed entry.
                failures.append(f"{method} {path}: malformed spec path (cannot split)")
                continue
            module, controller, command, params = split
            if _has_unresolved_path_params(params):
                # Cannot fabricate a real {uuid}; record as skipped, not failed.
                continue
            try:
                body: dict[str, Any] = client.get(module, controller, command, *params)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    failures.append(f"{method} {path}: 404 Not Found")
                else:
                    # Non-404 HTTP errors (e.g., 401, 500) are still failures
                    # — the test asserts the path is reachable, not that the
                    # box is permissive.
                    status_code: int = exc.response.status_code
                    reason_phrase: str = exc.response.reason_phrase
                    failures.append(f"{method} {path}: HTTP {status_code} {reason_phrase}")
                continue
            except APIResponseError as exc:
                failures.append(f"{method} {path}: non-JSON response ({exc})")
                continue
            except httpx.HTTPError as exc:
                failures.append(f"{method} {path}: transport error ({exc})")
                continue

            reason: str | None = _validate_light(body, operation)
            if reason is not None:
                failures.append(f"{method} {path}: {reason}")

        rendered: str = "\n".join(f"  {line}" for line in failures)
        assert not failures, (
            f"{len(failures)} of {len(triples)} sampled spec paths failed against "
            f"{base_url} (OPNsense {version}):\n{rendered}"
        )
