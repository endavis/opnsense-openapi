#!/usr/bin/env python3
"""Print the generate-matrix version list as compact JSON.

The list holds the highest bundled point release of every OPNsense ``YY.M``
series. ``.github/workflows/generate-matrix.yml`` feeds it to ``fromJSON``.

Usage:
    python tools/generate_matrix_versions.py [--specs-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from opnsense_openapi.specs import latest_spec_per_series


def main(argv: Sequence[str] | None = None) -> int:
    """Print the JSON version list.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        0 on success, 1 when no spec matches.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs-dir", type=Path, default=None, help="Specs directory to scan.")
    args = parser.parse_args(argv)

    versions = latest_spec_per_series(args.specs_dir)
    if not versions:
        print("No bundled specs found; cannot build the version matrix.", file=sys.stderr)
        return 1
    print(json.dumps(versions, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
