"""Benchmark tests for ControllerParser.parse_directory.

These benchmarks build a small synthetic tree of OPNsense-style PHP controller
files in a tmp_path and measure how long it takes the parser to walk the tree
and extract endpoints.

Inputs are intentionally small (a handful of controllers) so each benchmark
finishes in well under a second.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from opnsense_openapi.parser import ControllerParser

# Modules used to lay out a realistic-but-small controller directory.
_MODULES: tuple[tuple[str, str], ...] = (
    ("Firewall", "Alias"),
    ("Firewall", "Filter"),
    ("System", "Info"),
    ("System", "Settings"),
    ("Diagnostics", "Interface"),
    ("Diagnostics", "Routes"),
    ("Interfaces", "Vlan"),
    ("Interfaces", "Loopback"),
)


def _controller_php(module: str, controller: str) -> str:
    """Return a minimal but realistic OPNsense-style controller PHP source."""
    return f"""<?php
namespace OPNsense\\{module}\\Api;

use OPNsense\\Base\\ApiControllerBase;

/**
 * Class {controller}Controller
 */
class {controller}Controller extends ApiControllerBase
{{
    /**
     * Find {controller} entries
     * @return array
     */
    public function findAction()
    {{
        return $this->searchBase("{controller.lower()}", $this->request->getPost());
    }}

    /**
     * Get a single {controller}
     * @param string $uuid
     * @return array
     */
    public function getAction($uuid)
    {{
        return $this->getBase("{controller.lower()}", "field", $uuid);
    }}

    /**
     * Add a new {controller}
     * @return array
     */
    public function addAction()
    {{
        return $this->addBase("{controller.lower()}");
    }}

    /**
     * Update {controller} settings
     * @param string $uuid
     * @return array
     */
    public function setAction($uuid)
    {{
        return $this->setBase("{controller.lower()}", $uuid);
    }}
}}
"""


@pytest.fixture
def controller_tree(tmp_path: Path) -> Path:
    """Create a small synthetic OPNsense controllers tree under ``tmp_path``."""
    for module, controller in _MODULES:
        api_dir = tmp_path / module / "Api"
        api_dir.mkdir(parents=True, exist_ok=True)
        (api_dir / f"{controller}Controller.php").write_text(
            _controller_php(module, controller),
            encoding="utf-8",
        )
    return tmp_path


@pytest.mark.benchmark
def test_bench_parse_directory(benchmark, controller_tree: Path) -> None:
    """Benchmark parsing a small synthetic controller directory."""
    parser = ControllerParser()
    controllers = benchmark(parser.parse_directory, controller_tree)
    # Sanity check: the synthetic tree should fully parse.
    assert len(controllers) == len(_MODULES)
