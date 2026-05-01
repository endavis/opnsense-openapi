"""Advanced tests for OpenAPI generator features."""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from opnsense_openapi.generator.openapi_generator import OpenApiGenerator
from opnsense_openapi.parser import ApiController, ApiEndpoint


@pytest.fixture
def generator(tmp_path):
    gen = OpenApiGenerator(tmp_path)
    # Initialize spec structure for tests that bypass generate()
    gen.spec = {"paths": {}, "components": {"schemas": {}}}
    return gen


def create_mock_model_xml(
    content: str, tmp_path: Path, vendor="OPNsense", module="Test", model="Model"
) -> Path:
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
    string_variant = next(
        s for s in props["myopt"]["oneOf"] if s.get("type") == "string" and "enum" in s
    )
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
        model_name="custom_wrapper",  # Simulate parsed $internalModelName
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
        model_name=None,  # Missing model name
    )

    generator._find_and_parse_model = MagicMock(return_value={"type": "object"})
    generator._process_controller(controller)

    path_item = generator.spec["paths"]["/api/test/settings/get"]
    response_schema = path_item["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    # Should fallback to "settings" (lowercase controller name)
    assert "settings" in response_schema["properties"]


@pytest.mark.parametrize(
    ("module", "controller_class", "expected_segment"),
    [
        # Single word - regression guard, must still work
        ("Test", "SettingsController", "settings"),
        # The reported bug: VlanSettings collapsed to "vlansettings"
        ("Interfaces", "VlanSettingsController", "vlan_settings"),
        # Three-word controller
        ("Firewall", "OneToOneController", "one_to_one"),
        # Consecutive uppercase at start
        ("Firewall", "DNatController", "d_nat"),
        # Mid-name uppercase, found in real OPNsense source
        ("Core", "HasyncStatusController", "hasync_status"),
        # Two-word, also surfaced in the issue body
        ("Firewall", "FilterBaseController", "filter_base"),
    ],
)
def test_controller_path_uses_snake_case(generator, module, controller_class, expected_segment):
    """URL controller segment must be snake_case to match OPNsense's Router."""
    endpoint = ApiEndpoint(name="get", method="GET", description="Get item", parameters=[])
    controller = ApiController(
        module=module,
        controller=controller_class,
        base_class="ApiMutableModelControllerBase",
        endpoints=[endpoint],
        model_name=None,
    )

    # Mirror the test_response_wrapping_fallback pattern: mock model parsing to
    # return a schema so the schema-based path is exercised.
    generator._find_and_parse_model = MagicMock(return_value={"type": "object"})
    generator._process_controller(controller)

    expected_path = f"/api/{module.lower()}/{expected_segment}/get"
    assert expected_path in generator.spec["paths"], (
        f"Expected {expected_path!r} in generated paths, got {list(generator.spec['paths'])!r}"
    )


@pytest.mark.parametrize(
    ("module", "controller_class", "collapsed_segment"),
    [
        # The reported bug: collapsed form must NOT appear
        ("Interfaces", "VlanSettingsController", "vlansettings"),
        # Three-word controller collapsed form
        ("Firewall", "OneToOneController", "onetoone"),
        # Mid-name uppercase collapsed form
        ("Core", "HasyncStatusController", "hasyncstatus"),
    ],
)
def test_controller_path_does_not_use_collapsed_lowercase(
    generator, module, controller_class, collapsed_segment
):
    """The legacy `controller.lower()` collapsed form must not appear in paths."""
    endpoint = ApiEndpoint(name="get", method="GET", description="Get item", parameters=[])
    controller = ApiController(
        module=module,
        controller=controller_class,
        base_class="ApiMutableModelControllerBase",
        endpoints=[endpoint],
        model_name=None,
    )

    generator._find_and_parse_model = MagicMock(return_value={"type": "object"})
    generator._process_controller(controller)

    forbidden_path = f"/api/{module.lower()}/{collapsed_segment}/get"
    assert forbidden_path not in generator.spec["paths"], (
        f"Collapsed path {forbidden_path!r} must not be emitted"
    )


# === Branch coverage: _parse_xml_model fallbacks ===


def test_parse_xml_model_no_items_falls_back_to_root(generator, tmp_path):
    """When the XML has no <items>, _parse_xml_model parses root children directly."""
    xml = """
    <model>
        <title type="TextField"/>
    </model>
    """
    xml_path = tmp_path / "Model.xml"
    xml_path.write_text(xml)

    result = generator._parse_xml_model(xml_path)

    assert result is not None
    assert result["type"] == "object"
    assert "title" in result["properties"]
    assert result["properties"]["title"]["type"] == "string"


def test_parse_xml_model_returns_none_on_invalid_xml(generator, tmp_path):
    """Malformed XML triggers the except branch and yields None (logged warning)."""
    xml_path = tmp_path / "Bad.xml"
    xml_path.write_text("<model><unterminated>")

    result = generator._parse_xml_model(xml_path)

    assert result is None


# === Branch coverage: _find_and_parse_model fallbacks ===


def test_find_and_parse_model_falls_back_to_module_named_xml(generator, tmp_path):
    """If <Controller>.xml is missing but <Module>.xml exists, use the module file."""
    # Set models_dir on the generator so the function actually searches.
    generator.models_dir = tmp_path
    module_dir = tmp_path / "OPNsense" / "Firewall"
    module_dir.mkdir(parents=True)
    # Note: model is named after the *module*, not the controller.
    xml = "<model><items><name type='TextField'/></items></model>"
    (module_dir / "Firewall.xml").write_text(xml)

    result = generator._find_and_parse_model("OPNsense", "Firewall", "Alias")

    assert result is not None
    assert "name" in result["properties"]


def test_find_and_parse_model_returns_none_when_models_dir_unset(generator):
    """Without a configured models_dir, the helper short-circuits to None."""
    generator.models_dir = None
    assert generator._find_and_parse_model("OPNsense", "Firewall", "Alias") is None


def test_find_and_parse_model_returns_none_when_no_xml_found(generator, tmp_path):
    """No matching XML file yields None (final fall-through)."""
    generator.models_dir = tmp_path
    # tmp_path is empty, so neither path resolves.
    assert generator._find_and_parse_model("OPNsense", "Firewall", "Alias") is None


# === Branch coverage: _resolve_external_enums ===


def test_resolve_external_enums_no_models_dir(generator):
    """Without a models_dir set, _resolve_external_enums returns []."""
    generator.models_dir = None
    assert generator._resolve_external_enums("OPNsense.Firewall.AliasTypes") == []


def test_resolve_external_enums_short_source_string(generator, tmp_path):
    """Source strings with fewer than 3 dot-segments return []."""
    generator.models_dir = tmp_path
    assert generator._resolve_external_enums("Foo.Bar") == []
    assert generator._resolve_external_enums("Single") == []


def test_resolve_external_enums_field_types_subdir(generator, tmp_path):
    """Attempt 1: enum XML lives under .../FieldTypes/<Name>.xml."""
    generator.models_dir = tmp_path
    types_dir = tmp_path / "OPNsense" / "Firewall" / "FieldTypes"
    types_dir.mkdir(parents=True)
    (types_dir / "AliasTypes.xml").write_text("<root><host/><network/><port/></root>")

    result = generator._resolve_external_enums("OPNsense.Firewall.AliasTypes")

    assert set(result) == {"host", "network", "port"}


def test_resolve_external_enums_module_dir_fallback(generator, tmp_path):
    """Attempt 2: enum XML lives directly in the module folder."""
    generator.models_dir = tmp_path
    module_dir = tmp_path / "OPNsense" / "Firewall"
    module_dir.mkdir(parents=True)
    (module_dir / "AliasTypes.xml").write_text("<root><a/><b/></root>")

    result = generator._resolve_external_enums("OPNsense.Firewall.AliasTypes")

    assert set(result) == {"a", "b"}


def test_resolve_external_enums_no_file_found(generator, tmp_path):
    """When neither attempted path exists, returns []."""
    generator.models_dir = tmp_path
    # No files anywhere
    assert generator._resolve_external_enums("OPNsense.Firewall.Missing") == []


def test_resolve_external_enums_invalid_xml_swallows(generator, tmp_path):
    """Malformed XML at the resolved path triggers the except branch -> []."""
    generator.models_dir = tmp_path
    types_dir = tmp_path / "OPNsense" / "Firewall" / "FieldTypes"
    types_dir.mkdir(parents=True)
    (types_dir / "AliasTypes.xml").write_text("<root><unterminated>")

    assert generator._resolve_external_enums("OPNsense.Firewall.AliasTypes") == []


# === Branch coverage: _add_path_to_spec response heuristics ===


def _process_with_endpoint(
    generator, *, module="Test", controller_class="DemoController", action="run", method="GET"
):
    """Helper: process a controller carrying a single endpoint with the given action."""
    endpoint = ApiEndpoint(name=action, method=method, description="", parameters=[])
    controller = ApiController(
        module=module,
        controller=controller_class,
        base_class="ApiControllerBase",
        endpoints=[endpoint],
        model_name=None,
    )
    # No model schema: hits the fallback patterns branch.
    generator._find_and_parse_model = MagicMock(return_value=None)
    generator._process_controller(controller)


def test_add_path_service_start(generator):
    """A 'start' action emits the {response: string} schema."""
    _process_with_endpoint(generator, action="start")
    path = generator.spec["paths"]["/api/test/demo/start"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["properties"]["response"]["type"] == "string"


def test_add_path_reconfigure(generator):
    """'reconfigure' action emits {status: ok|failed}."""
    _process_with_endpoint(generator, action="reconfigure")
    path = generator.spec["paths"]["/api/test/demo/reconfigure"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["properties"]["status"]["enum"] == ["ok", "failed"]


def test_add_path_status_widget(generator):
    """A status action containing the literal substring 'widget' requires status."""
    # The is_rich_status check uses ``"widget" in action`` (case-sensitive on the
    # original action string), so the test deliberately uses lowercase 'widget'.
    _process_with_endpoint(generator, action="status_widget")
    path = generator.spec["paths"]["/api/test/demo/status_widget"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["required"] == ["status"]


def test_add_path_status_basic(generator):
    """A basic 'status' action does not require the 'status' property."""
    _process_with_endpoint(generator, action="status")
    path = generator.spec["paths"]["/api/test/demo/status"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["required"] == []


def test_add_path_array_response_pattern(generator):
    """Endpoints whose names match arp/ndp/log/etc patterns return an array."""
    _process_with_endpoint(generator, action="getArp")
    path = generator.spec["paths"]["/api/test/demo/getArp"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["type"] == "array"


def test_add_path_isenabled_pattern(generator):
    """isEnabled actions return an enabled '0'|'1' enum."""
    _process_with_endpoint(generator, action="isEnabled")
    path = generator.spec["paths"]["/api/test/demo/isEnabled"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["properties"]["enabled"]["enum"] == ["0", "1"]


def test_add_path_stats_pattern(generator):
    """A 'stats' action returns a generic object with additionalProperties."""
    _process_with_endpoint(generator, action="getStats")
    path = generator.spec["paths"]["/api/test/demo/getStats"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["additionalProperties"] is True


def test_add_path_special_operation_apply(generator):
    """An 'apply' action returns the StatusResponse $ref."""
    _process_with_endpoint(generator, action="apply", method="POST")
    path = generator.spec["paths"]["/api/test/demo/apply"]
    body = path["post"]["responses"]["200"]["content"]["application/json"]
    assert body["$ref"] == "#/components/schemas/StatusResponse"


def test_add_path_export_pattern(generator):
    """An 'export' action returns an export-data object."""
    _process_with_endpoint(generator, action="export")
    path = generator.spec["paths"]["/api/test/demo/export"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["additionalProperties"] is True
    assert "Export data" in schema["description"]


def test_add_path_list_with_schema(generator):
    """When a model schema is present and action == 'list', uses the {Schema}Search ref."""
    endpoint = ApiEndpoint(name="list", method="GET", description="", parameters=[])
    controller = ApiController(
        module="Test",
        controller="DemoController",
        base_class="ApiControllerBase",
        endpoints=[endpoint],
        model_name=None,
    )
    generator._find_and_parse_model = MagicMock(return_value={"type": "object"})
    generator._process_controller(controller)

    path = generator.spec["paths"]["/api/test/demo/list"]
    body = path["get"]["responses"]["200"]["content"]["application/json"]
    assert body["$ref"] == "#/components/schemas/OPNsenseTestDemoSearch"


def test_add_path_list_without_schema(generator):
    """List without a schema yields a generic dynamic-keys object."""
    _process_with_endpoint(generator, action="aliases")
    path = generator.spec["paths"]["/api/test/demo/aliases"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["additionalProperties"] is True


def test_add_path_search_with_schema(generator):
    """When a model schema is present and action contains 'search', uses {Schema}Search."""
    endpoint = ApiEndpoint(name="searchItem", method="GET", description="", parameters=[])
    controller = ApiController(
        module="Test",
        controller="DemoController",
        base_class="ApiControllerBase",
        endpoints=[endpoint],
        model_name=None,
    )
    generator._find_and_parse_model = MagicMock(return_value={"type": "object"})
    generator._process_controller(controller)

    path = generator.spec["paths"]["/api/test/demo/searchItem"]
    body = path["get"]["responses"]["200"]["content"]["application/json"]
    assert body["$ref"] == "#/components/schemas/OPNsenseTestDemoSearch"


def test_add_path_set_with_schema_emits_request_body(generator):
    """A 'set' mutation generates a status response and a request body when schema exists."""
    endpoint = ApiEndpoint(name="set", method="POST", description="", parameters=[])
    controller = ApiController(
        module="Test",
        controller="DemoController",
        base_class="ApiControllerBase",
        endpoints=[endpoint],
        model_name=None,
    )
    generator._find_and_parse_model = MagicMock(return_value={"type": "object"})
    generator._process_controller(controller)

    path = generator.spec["paths"]["/api/test/demo/set"]
    op = path["post"]
    assert op["responses"]["200"]["content"]["application/json"]["$ref"] == (
        "#/components/schemas/StatusResponse"
    )
    body_schema = op["requestBody"]["content"]["application/json"]["schema"]
    assert "demo" in body_schema["properties"]


def test_add_path_search_no_schema_fallback(generator):
    """search-style actions without a schema fall back to a generic paginated object."""
    _process_with_endpoint(generator, action="searchItem")
    path = generator.spec["paths"]["/api/test/demo/searchItem"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    # Generic pagination shape lives directly under properties.
    assert "current" in schema["properties"]
    assert "rows" in schema["properties"]


def test_add_path_get_no_schema_fallback(generator):
    """GET-style actions without a schema get the generic resource-data object."""
    # 'getConfig' contains 'get' but no noun keyword, so no {uuid} suffix is added.
    _process_with_endpoint(generator, action="getConfig")
    path = generator.spec["paths"]["/api/test/demo/getConfig"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["additionalProperties"] is True


def test_add_path_get_with_uuid_no_schema_fallback(generator):
    """A 'getRule' action triggers UUID heuristic and uses generic get response."""
    # 'getRule' contains a noun ('rule') but doesn't end with 'item' or contain
    # 'search'/'find', so it falls into the generic get-response branch.
    _process_with_endpoint(generator, action="getRule")
    path = generator.spec["paths"]["/api/test/demo/getRule/{uuid}"]
    schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["additionalProperties"] is True


def test_add_path_mutation_no_schema_fallback(generator):
    """Mutation actions without a schema get the StatusResponse + permissive request body."""
    _process_with_endpoint(generator, action="add", method="POST")
    path = generator.spec["paths"]["/api/test/demo/add"]
    op = path["post"]
    assert op["responses"]["200"]["content"]["application/json"]["$ref"] == (
        "#/components/schemas/StatusResponse"
    )
    assert (
        op["requestBody"]["content"]["application/json"]["schema"]["additionalProperties"] is True
    )


# === Branch coverage: _parse_model_nodes container without children ===


def test_parse_model_nodes_skips_empty_container(generator):
    """A no-type container element with no children is skipped (no property emitted)."""
    xml_content = """
    <model>
        <items>
            <typed type="TextField"/>
            <empty_container></empty_container>
        </items>
    </model>
    """
    root = ET.fromstring(xml_content)
    items = root.find("items")
    props = generator._parse_model_nodes(items)
    assert "typed" in props
    assert "empty_container" not in props


def test_parse_model_nodes_array_field_with_no_children(generator):
    """ArrayField with no children falls back to additionalProperties=True items."""
    xml_content = """
    <model>
        <items>
            <records type="ArrayField"/>
        </items>
    </model>
    """
    root = ET.fromstring(xml_content)
    items = root.find("items")
    props = generator._parse_model_nodes(items)
    assert props["records"]["type"] == "array"
    assert props["records"]["items"]["additionalProperties"] is True


def test_parse_model_nodes_multiple_field(generator):
    """A non-OptionField with <Multiple>Y</Multiple> is treated as polymorphic list."""
    xml_content = """
    <model>
        <items>
            <addrs type="NetworkField">
                <Multiple>Y</Multiple>
            </addrs>
        </items>
    </model>
    """
    root = ET.fromstring(xml_content)
    items = root.find("items")
    props = generator._parse_model_nodes(items)
    assert "oneOf" in props["addrs"]


def test_parse_model_nodes_optionfield_no_enums_defaults_to_object(generator):
    """An OptionField with no inline opts and no Source falls back to the object schema."""
    xml_content = """
    <model>
        <items>
            <opt type="OptionField"/>
        </items>
    </model>
    """
    root = ET.fromstring(xml_content)
    items = root.find("items")
    props = generator._parse_model_nodes(items)
    assert props["opt"]["type"] == "object"
    assert "additionalProperties" in props["opt"]


def test_parse_model_nodes_strips_relative_type_prefix(generator):
    """Field type with leading ./ should be stripped before TYPE_MAP lookup."""
    xml_content = """
    <model>
        <items>
            <weird type=".\\TextField"/>
        </items>
    </model>
    """
    root = ET.fromstring(xml_content)
    items = root.find("items")
    props = generator._parse_model_nodes(items)
    # TextField -> {"type": "string"}
    assert props["weird"]["type"] == "string"


def test_parse_model_nodes_unknown_type_defaults_to_string(generator):
    """An unrecognized type attribute falls back to {'type': 'string'}."""
    xml_content = """
    <model>
        <items>
            <weird type="NeverHeardOfIt"/>
        </items>
    </model>
    """
    root = ET.fromstring(xml_content)
    items = root.find("items")
    props = generator._parse_model_nodes(items)
    assert props["weird"] == {"type": "string"}


# === Module-level helper coverage ===


def test_module_level_get_xml_tag_text_returns_text():
    """_get_xml_tag_text returns the child text when the tag exists."""
    from opnsense_openapi.generator.openapi_generator import _get_xml_tag_text

    elem = ET.fromstring("<root><name>alias</name></root>")
    assert _get_xml_tag_text(elem, "name") == "alias"


def test_module_level_get_xml_tag_text_returns_none_when_missing():
    """_get_xml_tag_text returns None when the tag is missing."""
    from opnsense_openapi.generator.openapi_generator import _get_xml_tag_text

    elem = ET.fromstring("<root/>")
    assert _get_xml_tag_text(elem, "name") is None
