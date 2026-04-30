#!/usr/bin/env bash
# Regenerate every committed OPNsense spec via the current generator.
# Run from repo root: tools/regenerate_all_specs.sh

set -uo pipefail
specs_dir="src/opnsense_openapi/specs"
cache_dir="tmp/opnsense_source"
failed=()

versions=$(ls "$specs_dir" | sed 's/^opnsense-//; s/\.json$//' | sort -V)

for v in $versions; do
  echo "=== Regenerating $v ==="
  if uv run opnsense-openapi generate "$v"; then
    rm -rf "$cache_dir/$v"   # free disk; ~500MB per clone
  else
    failed+=("$v")
    echo "FAILED: $v — removing committed spec" >&2
    rm -f "$specs_dir/opnsense-$v.json"
  fi
done

echo
echo "=== Summary ==="
echo "Versions:        $(echo "$versions" | wc -l)"
echo "Failed/deleted:  ${#failed[@]}"
[ "${#failed[@]}" -gt 0 ] && printf '  - %s\n' "${failed[@]}"
