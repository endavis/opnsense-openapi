"""Advanced tests for OpenAPI generator features."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest

from opnsense_api.generator.openapi_generator import OpenApiGenerator
from opnsense_api.parser import ApiController, ApiEndpoint


@pytest.fixture
def generator(tmp_path):
    gen = OpenApiGenerator(tmp_path)
    # Initialize spec structure for tests that bypass generate()
    gen.spec = {
        "paths": {},
        "components": {
            "schemas": {}
        }
    }
    return gen


def create_mock_model_xml(content: str, tmp_path: Path, vendor="OPNsense", module="Test", model="Model") -> Path:
    """Helper to create a mock XML model file."""
    model_dir = tmp_path / vendor / module
    model_dir.mkdir(parents=True, exist_ok=True)
    xml_path = model_dir / f"{model}.xml"
    xml_path.write_text(content)
    return tmp_path


def test_polymorphic_option_field(generator):
    """Test that OptionField generates a oneOf schema."""
    xml_content = """
    <model>
        <items>
            <myopt type="OptionField">
                <OptionValues>
                    <opt1>Option 1</opt1>
                    <opt2>Option 2</opt2>
                </OptionValues>
            </myopt>
        </items>
    </model>
    """
    
    # Parse the XML fragment directly using the generator's method
    root = ET.fromstring(xml_content)
    items = root.find("items")
    
    props = generator._parse_model_nodes(items)
    
    assert "myopt" in props
    assert "oneOf" in props["myopt"]
    # Expect 3 items: Object Ref, String Enum, Array (empty list)
    assert len(props["myopt"]["oneOf"]) == 3
    
    # Check for Object reference
    assert any("$ref" in s for s in props["myopt"]["oneOf"])
    
    # Check for String enum
    string_variant = next(s for s in props["myopt"]["oneOf"] if s.get("type") == "string" and "enum" in s)
    assert "enum" in string_variant
    assert set(string_variant["enum"]) == {"opt1", "opt2"}

    # Check for Array variant
    array_variant = next(s for s in props["myopt"]["oneOf"] if s.get("type") == "array")
    assert array_variant["maxItems"] == 0


def test_polymorphic_list_field(generator):
    """Test that AsList="Y" triggers polymorphic schema (Object/String/Array)."""
    xml_content = """
    <model>
        <items>
            <mylist type="NetworkField">
                <AsList>Y</AsList>
            </mylist>
        </items>
    </model>
    """
    root = ET.fromstring(xml_content)
    items = root.find("items")
    
    props = generator._parse_model_nodes(items)
    
    assert "mylist" in props
    assert "oneOf" in props["mylist"]
    
    # Should allow object ref, string, and array
    assert len(props["mylist"]["oneOf"]) == 3
    assert any(s.get("type") == "array" for s in props["mylist"]["oneOf"])


def test_recursive_container_parsing(generator):
    """Test that container nodes are parsed recursively."""
    xml_content = """
    <model>
        <items>
            <general>
                <enabled type="BooleanField"/>
                <subgroup>
                    <port type="IntegerField"/>
                </subgroup>
            </general>
        </items>
    </model>
    """
    root = ET.fromstring(xml_content)
    items = root.find("items")
    
    props = generator._parse_model_nodes(items)
    
    assert "general" in props
    assert props["general"]["type"] == "object"
    
    gen_props = props["general"]["properties"]
    assert "enabled" in gen_props
    assert "subgroup" in gen_props
    
    # Check deeper nesting
    assert gen_props["subgroup"]["type"] == "object"
    assert "port" in gen_props["subgroup"]["properties"]


def test_integer_as_string(generator):
    """Test that IntegerField maps to string type."""
    xml_content = """
    <model>
        <items>
            <count type="IntegerField"/>
        </items>
    </model>
    """
    root = ET.fromstring(xml_content)
    items = root.find("items")
    props = generator._parse_model_nodes(items)
    
    assert props["count"]["type"] == "string"
    assert "Integer value" in props["count"]["description"]


def test_boolean_as_enum(generator):
    """Test that BooleanField maps to string enum 0/1."""
    xml_content = """
    <model>
        <items>
            <enabled type="BooleanField"/>
        </items>
    </model>
    """
    root = ET.fromstring(xml_content)
    items = root.find("items")
    props = generator._parse_model_nodes(items)
    
    assert props["enabled"]["type"] == "string"
    assert props["enabled"]["enum"] == ["0", "1"]


def test_response_wrapping_logic(generator):
    """Test that correct response wrapper name is used."""
    # Use actual ApiEndpoint objects
    endpoint = ApiEndpoint(name="get", method="GET", description="Get settings", parameters=[])
    
    controller = ApiController(
        module="Test",
        controller="SettingsController",
        base_class="ApiMutableModelControllerBase",
        endpoints=[endpoint],
        model_name="custom_wrapper" # Simulate parsed $internalModelName
    )
    
    # Mock finding a model so schema logic runs
    generator._find_and_parse_model = MagicMock(return_value={"type": "object"})
    
    generator._process_controller(controller)
    
    # Check generated paths
    # URL construction: /api/{module}/{controller}/{action} -> /api/test/settings/get
    path_item = generator.spec["paths"]["/api/test/settings/get"]
    response_schema = path_item["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    
    # Should use "custom_wrapper" as property key
    assert "custom_wrapper" in response_schema["properties"]
    assert "settings" not in response_schema["properties"]


def test_response_wrapping_fallback(generator):
    """Test fallback to controller name if model_name is missing."""
    endpoint = ApiEndpoint(name="get", method="GET", description="Get settings", parameters=[])

    controller = ApiController(
        module="Test",
        controller="SettingsController",
        base_class="ApiMutableModelControllerBase",
        endpoints=[endpoint],
        model_name=None # Missing model name
    )
    
    generator._find_and_parse_model = MagicMock(return_value={"type": "object"})
    generator._process_controller(controller)
    
    path_item = generator.spec["paths"]["/api/test/settings/get"]
    response_schema = path_item["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    
    # Should fallback to "settings" (lowercase controller name)
    assert "settings" in response_schema["properties"]
