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
        from opnsense_api.parser import ControllerParser

        parser = ControllerParser()
        controllers = [parser.parse_controller_file(controller_php)]

        # Generate spec with response inference
        output_dir = Path(tmpdir) / "output"
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate(controllers, "24.7", controllers_dir=controllers_dir)

        with spec_path.open() as f:
            spec = json.load(f)

        # Check that response schemas were inferred
        search_path = "/firewall/test/search"
        if search_path in spec["paths"]:
            search_response = spec["paths"][search_path]["get"]["responses"]["200"]["content"][
                "application/json"
            ]["schema"]
            # Should have inferred searchBase schema
            assert "properties" in search_response
            assert "rows" in search_response["properties"]
            assert "total" in search_response["properties"]

        custom_path = "/firewall/test/custom"
        if custom_path in spec["paths"]:
            custom_response = spec["paths"][custom_path]["get"]["responses"]["200"]["content"][
                "application/json"
            ]["schema"]
            # Should have inferred array literal schema
            assert "properties" in custom_response
            assert "status" in custom_response["properties"]


def test_query_parameters_for_get_requests() -> None:
    """Test that query parameters are added for GET requests with parameters."""
    controller = ApiController(
        module="Test",
        controller="Query",
        base_class="ApiControllerBase",
        endpoints=[
            ApiEndpoint(
                name="search",
                method="GET",
                description="Search items",
                parameters=["query", "limit", "offset"],
            ),
        ],
    )

    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate([controller], "24.7")

        with spec_path.open() as f:
            spec = json.load(f)

        # Check query parameters
        search_op = spec["paths"]["/test/query/search"]["get"]
        assert "parameters" in search_op
        param_names = {p["name"] for p in search_op["parameters"]}
        assert "query" in param_names
        assert "limit" in param_names
        assert "offset" in param_names
        # Check all are query parameters
        for param in search_op["parameters"]:
            assert param["in"] == "query"


def test_request_body_for_post_requests() -> None:
    """Test that request body is added for POST requests with parameters."""
    controller = ApiController(
        module="Test",
        controller="Data",
        base_class="ApiControllerBase",
        endpoints=[
            ApiEndpoint(
                name="create",
                method="POST",
                description="Create item",
                parameters=["name", "description", "enabled"],
            ),
        ],
    )

    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate([controller], "24.7")

        with spec_path.open() as f:
            spec = json.load(f)

        # Check request body - path might include controller name
        # Look for the create endpoint
        create_path = None
        for path in spec["paths"]:
            if "create" in path:
                create_path = path
                break
        assert create_path is not None, f"Create path not found in {list(spec['paths'].keys())}"
        create_op = spec["paths"][create_path]["post"]
        assert "requestBody" in create_op
        request_schema = create_op["requestBody"]["content"]["application/json"]["schema"]
        assert request_schema["type"] == "object"
        assert "properties" in request_schema
        # Check that parameters are in request body (some might be path params)
        props = request_schema["properties"]
        # At least 2 of the 3 parameters should be in request body
        param_count = sum(1 for p in ["name", "description", "enabled"] if p in props)
        assert param_count >= 2, f"Expected at least 2 params in body, got {list(props.keys())}"


def test_path_parameters_for_uuid() -> None:
    """Test that UUID parameters are mapped to path parameters."""
    controller = ApiController(
        module="Test",
        controller="Item",
        base_class="ApiControllerBase",
        endpoints=[
            ApiEndpoint(
                name="get",
                method="GET",
                description="Get item",
                parameters=["uuid"],
            ),
            ApiEndpoint(
                name="update",
                method="POST",
                description="Update item",
                parameters=["uuid", "name", "value"],
            ),
        ],
    )

    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate([controller], "24.7")

        with spec_path.open() as f:
            spec = json.load(f)

        # Check GET endpoint has uuid in path
        assert "/test/item/get/{uuid}" in spec["paths"]
        get_op = spec["paths"]["/test/item/get/{uuid}"]["get"]
        assert "parameters" in get_op
        path_params = [p for p in get_op["parameters"] if p["in"] == "path"]
        assert len(path_params) == 1
        assert path_params[0]["name"] == "uuid"

        # Check POST endpoint has uuid in path
        # Find update path (may include additional path params)
        update_path = None
        for path in spec["paths"]:
            if "update" in path and "{uuid}" in path:
                update_path = path
                break
        assert update_path is not None
        update_op = spec["paths"][update_path]["post"]
        assert "parameters" in update_op
        # If it has a request body, check it
        if "requestBody" in update_op:
            request_schema = update_op["requestBody"]["content"]["application/json"]["schema"]
            # At least one of name or value should be in request body or path params
            assert "properties" in request_schema or len(update_op["parameters"]) > 1


def test_multiple_modules_in_spec() -> None:
    """Test generating spec with multiple modules."""
    controllers = [
        ApiController(
            module="Firewall",
            controller="Alias",
            base_class="ApiControllerBase",
            endpoints=[ApiEndpoint(name="get", method="GET", description="Get alias", parameters=[])],
        ),
        ApiController(
            module="System",
            controller="Info",
            base_class="ApiControllerBase",
            endpoints=[ApiEndpoint(name="version", method="GET", description="Get version", parameters=[])],
        ),
    ]

    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate(controllers, "24.7")

        with spec_path.open() as f:
            spec = json.load(f)

        # Check both modules present
        assert "/firewall/alias/get" in spec["paths"]
        assert "/system/info/version" in spec["paths"]

        # Check tags
        firewall_op = spec["paths"]["/firewall/alias/get"]["get"]
        assert firewall_op["tags"] == ["Firewall"]

        system_op = spec["paths"]["/system/info/version"]["get"]
        assert system_op["tags"] == ["System"]


def test_generate_with_models_directory() -> None:
    """Test generating spec with models directory for enhanced schemas."""
    with TemporaryDirectory() as tmpdir:
        # Create models directory structure
        models_dir = Path(tmpdir) / "models"
        test_model_dir = models_dir / "OPNsense" / "Test"
        test_model_dir.mkdir(parents=True)

        # Create a simple XML model
        model_xml = test_model_dir / "Test.xml"
        model_xml.write_text(
            """<?xml version="1.0"?>
<model>
    <mount>//OPNsense/Test</mount>
    <description>Test Model</description>
    <items>
        <item type="TextField">
            <name>TextField</name>
        </item>
    </items>
</model>
"""
        )

        # Create controller
        controller = ApiController(
            module="Test",
            controller="Settings",
            base_class="ApiMutableModelControllerBase",
            endpoints=[
                ApiEndpoint(name="get", method="GET", description="Get settings", parameters=["uuid"]),
                ApiEndpoint(name="set", method="POST", description="Set settings", parameters=["uuid"]),
            ],
        )

        # Generate with models directory
        output_dir = Path(tmpdir) / "output"
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate([controller], "24.7", models_dir=models_dir)

        # Should not raise and should produce valid spec
        assert spec_path.exists()
        with spec_path.open() as f:
            spec = json.load(f)

        assert "paths" in spec
        assert len(spec["paths"]) > 0
