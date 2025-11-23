"""Tests for OpenAPI generator."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from opnsense_api.generator.openapi_generator import OpenApiGenerator
from opnsense_api.parser import ApiController, ApiEndpoint


@pytest.fixture
def sample_controllers() -> list[ApiController]:
    """Sample controllers for testing."""
    return [
        ApiController(
            module="Firewall",
            controller="Alias",
            base_class="ApiControllerBase",
            endpoints=[
                ApiEndpoint(
                    name="get",
                    method="GET",
                    description="Get alias by UUID",
                    parameters=["uuid"],
                ),
                ApiEndpoint(
                    name="set",
                    method="POST",
                    description="Update alias",
                    parameters=["uuid"],
                ),
            ],
        ),
    ]


def test_generate_openapi_spec(sample_controllers: list[ApiController]) -> None:
    """Test generating OpenAPI spec."""
    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate(sample_controllers, "24.7")

        assert spec_path.exists()
        assert spec_path.name == "opnsense-24.7.json"

        with spec_path.open() as f:
            spec = json.load(f)

        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["version"] == "24.7"
        assert "paths" in spec
        assert (
            "/firewall/alias/get" in spec["paths"] or "/firewall/alias/get/{uuid}" in spec["paths"]
        )


def test_generator_creates_output_dir() -> None:
    """Test that generator creates output directory if needed."""
    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "nested" / "output"
        _ = OpenApiGenerator(output_dir)  # Side effect: creates directory
        assert output_dir.exists()


def test_spec_has_security_scheme(sample_controllers: list[ApiController]) -> None:
    """Test that generated spec includes security scheme."""
    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate(sample_controllers, "24.7")

        with spec_path.open() as f:
            spec = json.load(f)

        assert "components" in spec
        assert "securitySchemes" in spec["components"]
        assert "basicAuth" in spec["components"]["securitySchemes"]
