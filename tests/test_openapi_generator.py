"""Tests for OpenAPI generator."""

import json
import os
import subprocess  # nosec B404 - runs the generator in a child interpreter
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from opnsense_openapi.generator.openapi_generator import OpenApiGenerator
from opnsense_openapi.parser import ApiController, ApiEndpoint, ControllerParser


@pytest.fixture
def sample_controllers() -> list[ApiController]:
    """Sample controllers for testing."""
    return [
        ApiController(
            module="Firewall",
            controller="Alias",
            base_class="ApiControllerBase",
            endpoints=[
                ApiEndpoint(name="get", method="GET", description="Get alias", parameters=["uuid"]),
                ApiEndpoint(
                    name="set", method="POST", description="Update alias", parameters=["uuid"]
                ),
            ],
            model_class=None,
        )
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

        assert spec["openapi"] == "3.0.3"
        assert spec["info"]["version"] == "24.7"
        assert "paths" in spec
        assert (
            "/api/firewall/alias/get" in spec["paths"]
            or "/api/firewall/alias/get/{uuid}" in spec["paths"]
        )


def test_generator_creates_output_dir() -> None:
    """Test that generator creates output directory if needed."""
    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        assert not output_dir.exists()

        OpenApiGenerator(output_dir)
        assert output_dir.exists()


def test_spec_has_security_scheme() -> None:
    """Test that generated spec includes security schemes."""
    controller = ApiController(
        module="Test",
        controller="Secure",
        base_class="ApiControllerBase",
        endpoints=[
            ApiEndpoint(name="action", method="POST", description="Test action", parameters=[])
        ],
    )

    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate([controller], "24.7")

        with spec_path.open() as f:
            spec = json.load(f)

        assert "components" in spec
        assert "securitySchemes" in spec["components"]
        assert "basicAuth" in spec["components"]["securitySchemes"]
        assert "security" in spec


def test_response_inference_integration() -> None:
    """Test response inference integration with actual PHP controller files."""
    with TemporaryDirectory() as tmpdir:
        # Create controller directory with PHP file
        controllers_dir = Path(tmpdir) / "controllers"
        firewall_api = controllers_dir / "Firewall" / "Api"
        firewall_api.mkdir(parents=True)

        # Create PHP controller with base method calls
        controller_php = firewall_api / "TestController.php"
        controller_php.write_text(
            """<?php
namespace OPNsense\\Firewall\\Api;

class TestController extends ApiMutableModelControllerBase
{
    public function searchAction()
    {
        return $this->searchBase("test");
    }

    public function getAction($uuid)
    {
        return $this->getBase("test", $uuid);
    }

    public function customAction()
    {
        return ["status" => "ok", "result" => "success"];
    }
}
"""
        )

        # Parse controller
        parser = ControllerParser()
        controller = parser.parse_controller_file(controller_php)
        assert controller is not None
        controllers = [controller]

        # Generate spec with response inference
        output_dir = Path(tmpdir) / "output"
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate(controllers, "24.7")

        with spec_path.open() as f:
            spec = json.load(f)

        # Verify spec was generated
        assert "paths" in spec
        assert len(spec["paths"]) > 0


def test_generate_with_models_directory() -> None:
    """Test generating spec with models directory for enhanced schemas."""
    controller = ApiController(
        module="Firewall",
        controller="Alias",
        base_class="ApiControllerBase",
        endpoints=[
            ApiEndpoint(name="search", method="POST", description="Search aliases", parameters=[])
        ],
    )

    with TemporaryDirectory() as tmpdir:
        # Create models directory structure
        models_dir = Path(tmpdir) / "models" / "OPNsense" / "Firewall"
        models_dir.mkdir(parents=True)

        # Create simple model XML
        model_xml = models_dir / "Alias.xml"
        model_xml.write_text(
            """<?xml version="1.0"?>
<model>
    <mount>//OPNsense/Firewall/Alias</mount>
    <description>Firewall Alias</description>
    <items>
        <aliases>
            <alias type="ArrayField">
                <name type="TextField" required="Y"/>
                <type type="OptionField"/>
                <enabled type="BooleanField"/>
            </alias>
        </aliases>
    </items>
</model>
"""
        )

        # Generate spec
        output_dir = Path(tmpdir) / "output"
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate([controller], "24.7", models_dir=models_dir.parent.parent)

        with spec_path.open() as f:
            spec = json.load(f)

        # Verify schema was created
        assert "components" in spec
        assert "schemas" in spec["components"]


_DETERMINISM_SCRIPT = """
import sys
from pathlib import Path

from opnsense_openapi.generator.openapi_generator import OpenApiGenerator
from opnsense_openapi.parser import ControllerParser

source, models, output = (Path(arg) for arg in sys.argv[1:4])
controllers = ControllerParser().parse_directory(source)
OpenApiGenerator(output).generate(controllers, "24.7", models_dir=models)
"""


def test_generate_is_byte_identical_across_hash_seeds(tmp_path: Path) -> None:
    """The same source yields the same bytes regardless of PYTHONHASHSEED (#138).

    Set iteration order follows string hashing, so a spec built from a set
    differs between runs. Generating in two interpreters with different seeds
    catches any such ordering, not only the enum case fixed in #138.
    """
    source = tmp_path / "controllers"
    models = tmp_path / "models"
    for module in ("Firewall", "Interfaces", "Routes"):
        api_dir = source / "OPNsense" / module / "Api"
        api_dir.mkdir(parents=True)
        (api_dir / "SettingsController.php").write_text(
            f"""<?php
namespace OPNsense\\{module}\\Api;
use OPNsense\\Base\\ApiMutableModelControllerBase;

class SettingsController extends ApiMutableModelControllerBase
{{
    public function getAction() {{}}
    public function setAction() {{}}
}}
"""
        )
        model_dir = models / "OPNsense" / module
        model_dir.mkdir(parents=True)
        options = "".join(f"<opt{i}>Option {i}</opt{i}>" for i in range(20))
        (model_dir / "Settings.xml").write_text(
            f"""<?xml version="1.0"?>
<model>
    <mount>//OPNsense/{module}/Settings</mount>
    <items>
        <mode type="OptionField"><OptionValues>{options}</OptionValues></mode>
    </items>
</model>
"""
        )

    outputs = []
    for seed in ("1", "2"):
        output = tmp_path / f"out-{seed}"
        subprocess.run(  # nosec B603 - fixed interpreter and arguments, no shell
            [sys.executable, "-c", _DETERMINISM_SCRIPT, str(source), str(models), str(output)],
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        outputs.append((output / "opnsense-24.7.json").read_bytes())

    assert b'"opt19"' in outputs[0], "fixture must exercise enum generation"
    assert outputs[0] == outputs[1]
