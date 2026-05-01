# ADR-0001: Spec matching: floor over highest, module path keyed by resolved spec version

## Status

Accepted

## Decision

`find_best_matching_spec(version)` defaults to **floor** matching: when no
exact spec is committed, return the highest spec at or below the
requested version, not the highest spec sharing `major.minor`. The
generated-client module directory is keyed off the *resolved* spec
version, not the raw user-supplied version, so security-patch revisions
of the same release (`26.1.6`, `26.1.6_2`, ...) share a single generated
client.

The legacy "highest" behavior remains available via
`find_best_matching_spec(version, mode="highest")` for callers that
want it.

## Rationale

Two failure modes in InfraFoundry's direct-API spike against a `26.1.6_2`
box drove this decision:

1. **Wrong-direction matching.** With `[25.7.4, 25.7.6, 25.7.7]`
   committed and the box reporting `25.7.5`, the resolver returned
   `25.7.7`. Endpoints introduced between `25.7.5` and `25.7.7` then
   appeared in the generated client and surfaced as 404s at runtime.
   Floor matching biases the client toward a subset that is guaranteed
   to exist on the box.

2. **Module-path churn across security patches.** The auto-generator
   keyed its output directory off `version.replace(".", "_")`, so each
   security-patch boot (`26.1.6_1`, `26.1.6_2`, ...) wrote a fresh
   `generated/v26_1_6_N/` even though the resolver mapped them all to
   `opnsense-26.1.6.json`. Codegen ran on every boot. Keying the module
   directory off the resolved spec version (which strips the `_N`
   suffix) collapses these to a single `generated/v26_1_6/` and the
   second boot is a no-op.

The default flip is a deliberate breaking change: callers requesting a
non-exact version receive a different spec than before. The PR
description and changelog flag it explicitly.

## Consequences

- **Breaking change.** `find_best_matching_spec("25.7.5")` against
  `[25.7.4, 25.7.6, 25.7.7]` now returns `25.7.4`, not `25.7.7`. Callers
  that need the old behavior must opt in with `mode="highest"`.
- **Stable generated-client paths.** A `26.1.6_2` box and a `26.1.6_3`
  box share a single `generated/v26_1_6/` directory. Old per-revision
  directories (`v26_1_6_2/`) are not auto-deleted; they sit unused.
- **Floor failure raises.** If no committed spec is at or below the
  requested version, `find_best_matching_spec` raises `FileNotFoundError`
  rather than silently returning a spec above the box. CLI surfaces
  surface this with a clear message.

## Related Issues

- Issue #34 — refactor: stabilize generated-client module path across
  patch revisions; add closest-floor spec matching

## Related Documentation

- [Spec Version Resolution](../development/spec-version-resolution.md) —
  end-user explanation of the matching rule and the `_N` suffix policy.
- `src/opnsense_openapi/specs.py` — `find_best_matching_spec`,
  `_version_key`, `version_from_spec_path`.
- `src/opnsense_openapi/client/base.py` — `_resolved_module_dir`,
  `_auto_generate_client`, `OPNsenseClient.api`.

