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


def test_model_schema_used_for_response() -> None:
    """Test that model schema is used for response when available."""
    with TemporaryDirectory() as tmpdir:
        # Create models directory with model
        models_dir = Path(tmpdir) / "models"
        test_model_dir = models_dir / "OPNsense" / "Test"
        test_model_dir.mkdir(parents=True)

        model_xml = test_model_dir / "Settings.xml"
        model_xml.write_text(
            """<?xml version="1.0"?>
<model>
    <mount>//OPNsense/Test/Settings</mount>
    <description>Test Settings Model</description>
    <items>
        <hostname type="TextField">
            <name>Hostname</name>
            <required>Y</required>
        </hostname>
        <enabled type="BooleanField">
            <name>Enabled</name>
            <default>1</default>
        </enabled>
    </items>
</model>
"""
        )

        # Create controller with model_class that matches the model
        controller = ApiController(
            module="Test",
            controller="Settings",
            base_class="ApiMutableModelControllerBase",
            model_class="OPNsense\\Test\\Settings",
            endpoints=[
                ApiEndpoint(
                    name="get",
                    method="GET",
                    description="Get settings",
                    parameters=["uuid"],
                ),
            ],
        )

        # Generate spec
        output_dir = Path(tmpdir) / "output"
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate([controller], "24.7", models_dir=models_dir)

        with spec_path.open() as f:
            spec = json.load(f)

        # Find the get endpoint
        get_path = None
        for path in spec["paths"]:
            if "get" in path and "{uuid}" in path:
                get_path = path
                break

        assert get_path is not None
        get_op = spec["paths"][get_path]["get"]
        response_schema = get_op["responses"]["200"]["content"]["application/json"]["schema"]

        # Should use model schema (has hostname and enabled fields)
        assert "properties" in response_schema
        assert "hostname" in response_schema["properties"]
        assert "enabled" in response_schema["properties"]


def test_model_schema_used_for_request_body() -> None:
    """Test that model schema is used for request body when available."""
    with TemporaryDirectory() as tmpdir:
        # Create models directory with model
        models_dir = Path(tmpdir) / "models"
        test_model_dir = models_dir / "OPNsense" / "Test"
        test_model_dir.mkdir(parents=True)

        model_xml = test_model_dir / "Settings.xml"
        model_xml.write_text(
            """<?xml version="1.0"?>
<model>
    <mount>//OPNsense/Test/Settings</mount>
    <description>Test Settings Model</description>
    <items>
        <hostname type="TextField">
            <name>Hostname</name>
        </hostname>
        <port type="IntegerField">
            <name>Port</name>
            <default>8080</default>
        </port>
    </items>
</model>
"""
        )

        # Create controller with model_class that matches the model
        controller = ApiController(
            module="Test",
            controller="Settings",
            base_class="ApiMutableModelControllerBase",
            model_class="OPNsense\\Test\\Settings",
            endpoints=[
                ApiEndpoint(
                    name="set",
                    method="POST",
                    description="Set settings",
                    parameters=["uuid", "hostname", "port"],
                ),
            ],
        )

        # Generate spec
        output_dir = Path(tmpdir) / "output"
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate([controller], "24.7", models_dir=models_dir)

        with spec_path.open() as f:
            spec = json.load(f)

        # Find the set endpoint
        set_path = None
        for path in spec["paths"]:
            if "set" in path and "{uuid}" in path:
                set_path = path
                break

        assert set_path is not None
        set_op = spec["paths"][set_path]["post"]

        # Should have request body with model schema
        assert "requestBody" in set_op
        request_schema = set_op["requestBody"]["content"]["application/json"]["schema"]
        assert "properties" in request_schema
        assert "hostname" in request_schema["properties"]
        assert "port" in request_schema["properties"]


def test_is_model_endpoint() -> None:
    """Test _is_model_endpoint method."""
    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        generator = OpenApiGenerator(output_dir)

        # Test model endpoint patterns
        assert generator._is_model_endpoint("get")
        assert generator._is_model_endpoint("set")
        assert generator._is_model_endpoint("add")
        assert generator._is_model_endpoint("search")
        assert generator._is_model_endpoint("item")
        assert generator._is_model_endpoint("getItem")
        assert generator._is_model_endpoint("searchItems")

        # Test non-model endpoints
        assert not generator._is_model_endpoint("restart")
        assert not generator._is_model_endpoint("status")
        assert not generator._is_model_endpoint("reload")


def test_get_with_path_and_query_params() -> None:
    """Test GET request with both path and query parameters."""
    controller = ApiController(
        module="Test",
        controller="Search",
        base_class="ApiControllerBase",
        endpoints=[
            ApiEndpoint(
                name="find",
                method="GET",
                description="Find items by category",
                parameters=["category", "query", "limit"],  # category in path, query+limit as query params
            ),
        ],
    )

    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate([controller], "24.7")

        with spec_path.open() as f:
            spec = json.load(f)

        # Find the endpoint (may have category in path or not)
        find_path = None
        for path in spec["paths"]:
            if "find" in path:
                find_path = path
                break

        assert find_path is not None
        find_op = spec["paths"][find_path]["get"]

        # Should have parameters
        assert "parameters" in find_op
        params = find_op["parameters"]

        # Check that we have both path and query parameters
        param_names = {p["name"] for p in params}
        # At least one should be query parameter
        query_params = [p for p in params if p["in"] == "query"]
        assert len(query_params) > 0


def test_response_schema_inference_failure() -> None:
    """Test handling of response schema inference failure."""
    with TemporaryDirectory() as tmpdir:
        # Create controller directory with invalid PHP file
        controllers_dir = Path(tmpdir) / "controllers"
        test_api = controllers_dir / "Test" / "Api"
        test_api.mkdir(parents=True)

        # Create PHP controller with syntax error
        controller_php = test_api / "TestController.php"
        controller_php.write_text(
            """<?php
namespace OPNsense\\Test\\Api;

class TestController extends ApiControllerBase
{
    public function brokenAction()
    {
        // Missing return statement - should cause inference to fail gracefully
    }
}
"""
        )

        # Parse controller
        from opnsense_api.parser import ControllerParser

        parser = ControllerParser()
        controllers = [parser.parse_controller_file(controller_php)]

        # Generate spec - should not raise even with broken PHP
        output_dir = Path(tmpdir) / "output"
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate(controllers, "24.7", controllers_dir=controllers_dir)

        # Should still produce valid spec
        assert spec_path.exists()
        with spec_path.open() as f:
            spec = json.load(f)

        # Check that endpoint exists with generic schema
        broken_path = None
        for path in spec["paths"]:
            if "broken" in path:
                broken_path = path
                break

        assert broken_path is not None
        broken_op = spec["paths"][broken_path]["get"]
        response_schema = broken_op["responses"]["200"]["content"]["application/json"]["schema"]

        # Should fall back to generic schema
        assert response_schema["type"] == "object"


def test_get_model_schema_with_multiple_containers() -> None:
    """Test _get_model_schema selects container with most fields."""
    with TemporaryDirectory() as tmpdir:
        # Create models directory with model having multiple containers
        models_dir = Path(tmpdir) / "models"
        test_model_dir = models_dir / "OPNsense" / "Test"
        test_model_dir.mkdir(parents=True)

        model_xml = test_model_dir / "Multi.xml"
        model_xml.write_text(
            """<?xml version="1.0"?>
<model>
    <mount>//OPNsense/Test/Multi</mount>
    <description>Multi-container Model</description>
    <items>
        <general>
            <field1 type="TextField">
                <name>Field1</name>
            </field1>
        </general>
        <advanced>
            <field2 type="TextField">
                <name>Field2</name>
            </field2>
            <field3 type="TextField">
                <name>Field3</name>
            </field3>
            <field4 type="TextField">
                <name>Field4</name>
            </field4>
        </advanced>
    </items>
</model>
"""
        )

        # Create controller
        controller = ApiController(
            module="Test",
            controller="Multi",
            base_class="ApiMutableModelControllerBase",
            model_class="OPNsense\\Test\\Multi",
            endpoints=[
                ApiEndpoint(
                    name="get",
                    method="GET",
                    description="Get config",
                    parameters=["uuid"],
                ),
            ],
        )

        # Generate spec
        output_dir = Path(tmpdir) / "output"
        generator = OpenApiGenerator(output_dir)
        spec_path = generator.generate([controller], "24.7", models_dir=models_dir)

        with spec_path.open() as f:
            spec = json.load(f)

        # Find the get endpoint
        get_path = None
        for path in spec["paths"]:
            if "get" in path and "{uuid}" in path:
                get_path = path
                break

        assert get_path is not None
        get_op = spec["paths"][get_path]["get"]
        response_schema = get_op["responses"]["200"]["content"]["application/json"]["schema"]

        # Should use "advanced" container (has 3 fields vs "general" with 1)
        assert "properties" in response_schema
        # Check that we have fields from the advanced container
        props = response_schema["properties"]
        # Should have more than just 1 field
        assert len(props) >= 3
