"""Tests for code generator."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from opnsense_api.generator import CodeGenerator
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
        ApiController(
            module="System",
            controller="Info",
            base_class="ApiControllerBase",
            endpoints=[
                ApiEndpoint(
                    name="version",
                    method="GET",
                    description="Get system version",
                    parameters=[],
                ),
            ],
        ),
    ]


def test_generate_basic(sample_controllers: list[ApiController]) -> None:
    """Test basic code generation."""
    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "generated"
        generator = CodeGenerator(output_dir)
        generator.generate(sample_controllers, "24.7")

        # Check main init file
        init_file = output_dir / "__init__.py"
        assert init_file.exists()
        content = init_file.read_text()
        assert "OPNsenseClient" in content
        assert "Firewall" in content
        assert "System" in content

        # Check module files
        firewall_file = output_dir / "firewall.py"
        assert firewall_file.exists()
        content = firewall_file.read_text()
        assert "class Firewall:" in content
        assert "class Alias:" in content
        assert "def get" in content
        assert "def set" in content

        system_file = output_dir / "system.py"
        assert system_file.exists()
        content = system_file.read_text()
        assert "class System:" in content
        assert "class Info:" in content
        assert "def version" in content


def test_to_class_name() -> None:
    """Test class name conversion."""
    generator = CodeGenerator(Path("tmp"))

    assert generator._to_class_name("firewall") == "Firewall"
    assert generator._to_class_name("system_info") == "SystemInfo"
    assert generator._to_class_name("api") == "Api"


def test_to_snake_case() -> None:
    """Test snake_case conversion."""
    generator = CodeGenerator(Path("tmp"))

    assert generator._to_snake_case("AliasUtil") == "alias_util"
    assert generator._to_snake_case("Info") == "info"
    assert generator._to_snake_case("findAlias") == "find_alias"
