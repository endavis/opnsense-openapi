"""Inherited controller actions parsed from real OPNsense source (#171)."""

from __future__ import annotations

import re

import pytest

from opnsense_openapi import list_available_specs
from opnsense_openapi.downloader import SourceDownloader
from opnsense_openapi.parser import ControllerParser

CHAINS = {
    "Core/Tunables": ["Core/Api/TunablesController.php", "Base/ApiMutableModelControllerBase.php"],
    "Kea/Service": ["Kea/Api/ServiceController.php", "Base/ApiMutableServiceControllerBase.php"],
    "Firewall/Filter": [
        "Firewall/Api/FilterController.php",
        "Firewall/Api/FilterBaseController.php",
        "Base/ApiMutableModelControllerBase.php",
    ],
    "Kea/Leases4": ["Kea/Api/Leases4Controller.php", "Kea/Api/LeasesController.php"],
}


@pytest.mark.requires_opnsense_source
def test_latest_source_chain_matches_independent_read() -> None:
    available = list_available_specs()
    if not available:
        pytest.skip("No committed specs available")
    latest = available[-1]
    try:
        root = SourceDownloader().download(latest)
    except (RuntimeError, OSError) as exc:
        pytest.skip(f"Unable to materialize OPNsense source for {latest}: {exc}")
    controllers = ControllerParser().parse_directory(root)
    by_key = {f"{c.module}/{c.controller}": c for c in controllers}
    action = re.compile(r"public\s+function\s+(\w+)Action\s*\(")

    for key, files in CHAINS.items():
        expected: set[str] = set()
        for rel in files:
            text = (root / rel).read_text(encoding="utf-8")
            expected |= {n.lower() for n in action.findall(text)}
        assert {e.name.lower() for e in by_key[key].endpoints} == expected, key

    assert "Firewall/FilterBase" not in by_key
    assert "Kea/Leases" not in by_key
