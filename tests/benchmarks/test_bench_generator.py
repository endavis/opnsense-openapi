"""Benchmark tests for OpenApiGenerator.generate.

Builds a small in-memory list of ApiController/ApiEndpoint instances and
measures how long the generator takes to assemble and serialize an OpenAPI
spec to disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from opnsense_openapi.generator.openapi_generator import OpenApiGenerator
from opnsense_openapi.parser import ApiController, ApiEndpoint


def _make_controllers() -> list[ApiController]:
    """Return a small set of synthetic controllers covering common HTTP shapes."""
    modules: tuple[tuple[str, str], ...] = (
        ("Firewall", "Alias"),
        ("Firewall", "Filter"),
        ("System", "Info"),
        ("System", "Settings"),
        ("Diagnostics", "Interface"),
        ("Diagnostics", "Routes"),
    )
    controllers: list[ApiController] = []
    for module, controller in modules:
        endpoints = [
            ApiEndpoint(
                name="find",
                method="POST",
                description=f"Find {controller} entries",
                parameters=[],
            ),
            ApiEndpoint(
                name="get",
                method="GET",
                description=f"Get {controller}",
                parameters=["uuid"],
            ),
            ApiEndpoint(
                name="add",
                method="POST",
                description=f"Add {controller}",
                parameters=[],
            ),
            ApiEndpoint(
                name="set",
                method="POST",
                description=f"Update {controller}",
                parameters=["uuid"],
            ),
        ]
        controllers.append(
            ApiController(
                module=module,
                controller=controller,
                base_class="ApiControllerBase",
                endpoints=endpoints,
                model_class=None,
            )
        )
    return controllers


@pytest.fixture
def controllers() -> list[ApiController]:
    """Provide a small set of ApiController instances for benchmarking."""
    return _make_controllers()


@pytest.mark.benchmark
def test_bench_generate_spec(benchmark, tmp_path: Path, controllers: list[ApiController]) -> None:
    """Benchmark generating an OpenAPI spec from synthetic controllers."""
    generator = OpenApiGenerator(tmp_path)
    spec_path = benchmark(generator.generate, controllers, "24.7")
    assert spec_path.exists()
