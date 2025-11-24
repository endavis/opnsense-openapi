"""Tests for model parser."""

import pytest
from opnsense_api.parser.model_parser import ModelParser, ModelDefinition, ModelField


def test_convert_default_boolean():
    """Test that boolean defaults are converted from 0/1 to false/true."""
    parser = ModelParser()

    # Test "0" -> false
    assert parser._convert_default_value("0", "boolean") is False

    # Test "1" -> true
    assert parser._convert_default_value("1", "boolean") is True

    # Test "Y" -> true
    assert parser._convert_default_value("Y", "boolean") is True

    # Test "N" -> false
    assert parser._convert_default_value("N", "boolean") is False


def test_convert_default_integer():
    """Test that integer defaults are converted from strings."""
    parser = ModelParser()

    assert parser._convert_default_value("42", "integer") == 42
    assert parser._convert_default_value("2048", "integer") == 2048
    assert parser._convert_default_value("0", "integer") == 0


def test_convert_default_number():
    """Test that number defaults are converted from strings."""
    parser = ModelParser()

    assert parser._convert_default_value("3.14", "number") == 3.14
    assert parser._convert_default_value("0.5", "number") == 0.5


def test_convert_default_string():
    """Test that string defaults remain strings."""
    parser = ModelParser()

    assert parser._convert_default_value("hello", "string") == "hello"
    assert parser._convert_default_value("RSA-2048", "string") == "RSA-2048"


def test_to_json_schema_boolean_field():
    """Test JSON schema generation with boolean field."""
    parser = ModelParser()

    model = ModelDefinition(
        name="Test",
        module="Test",
        mount="//Test",
        description="Test model",
        fields={
            "root": [
                ModelField(
                    name="enabled",
                    field_type="BooleanField",
                    default="1",
                )
            ]
        },
    )

    schema = parser.to_json_schema(model, "root")

    assert schema["properties"]["enabled"]["type"] == "boolean"
    assert schema["properties"]["enabled"]["default"] is True  # Not "1"


def test_to_json_schema_enum_with_default_not_in_enum():
    """Test that default values are added to enum if missing."""
    parser = ModelParser()

    model = ModelDefinition(
        name="Test",
        module="Test",
        mount="//Test",
        description="Test model",
        fields={
            "root": [
                ModelField(
                    name="key_type",
                    field_type="OptionField",
                    default="2048",  # Not in the enum originally
                    options={
                        "RSA-512": "RSA 512 bit",
                        "RSA-1024": "RSA 1024 bit",
                        # "2048" is missing but is the default
                    },
                )
            ]
        },
    )

    schema = parser.to_json_schema(model, "root")

    # Default should be added to enum
    assert "2048" in schema["properties"]["key_type"]["enum"]
    assert schema["properties"]["key_type"]["default"] == "2048"


def test_to_json_schema_enum_with_integer_default():
    """Test that enum with integer-like default is handled correctly."""
    parser = ModelParser()

    model = ModelDefinition(
        name="Test",
        module="Test",
        mount="//Test",
        description="Test model",
        fields={
            "root": [
                ModelField(
                    name="pcp",
                    field_type="OptionField",
                    default="0",
                    options={
                        "pcp1": "Priority 1",
                        "pcp2": "Priority 2",
                    },
                )
            ]
        },
    )

    schema = parser.to_json_schema(model, "root")

    # "0" should be added to enum
    assert "0" in schema["properties"]["pcp"]["enum"]
    assert schema["properties"]["pcp"]["default"] == "0"


def test_parse_directory_with_models():
    """Test parsing directory containing XML model files."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    parser = ModelParser()

    with TemporaryDirectory() as tmpdir:
        # Create models directory structure
        models_dir = Path(tmpdir)
        test_model_dir = models_dir / "OPNsense" / "Test"
        test_model_dir.mkdir(parents=True)

        # Create a simple XML model
        model_xml = test_model_dir / "TestModel.xml"
        model_xml.write_text(
            """<?xml version="1.0"?>
<model>
    <mount>//OPNsense/Test/TestModel</mount>
    <description>Test Model for parsing</description>
    <items>
        <testField type="TextField">
            <name>TestField</name>
            <default>default_value</default>
        </testField>
        <enabledField type="BooleanField">
            <name>EnabledField</name>
            <default>1</default>
        </enabledField>
    </items>
</model>
"""
        )

        # Parse directory
        models = parser.parse_directory(models_dir)

        # Should find the model
        assert len(models) > 0
        # Model is keyed by its mount path
        model_key = list(models.keys())[0]
        assert "TestModel" in model_key
        model = models[model_key]
        assert model.name == "TestModel"
        assert model.module == "Test"
        # Items are grouped under "root" key
        assert len(model.fields) > 0


def test_parse_model_file_with_nested_items():
    """Test parsing model file with nested item structure."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    parser = ModelParser()

    with TemporaryDirectory() as tmpdir:
        xml_file = Path(tmpdir) / "nested.xml"
        xml_file.write_text(
            """<?xml version="1.0"?>
<model>
    <mount>//OPNsense/Core/Settings</mount>
    <description>Settings with nested structure</description>
    <items>
        <general>
            <hostname type="TextField">
                <name>Hostname</name>
                <required>Y</required>
            </hostname>
            <domain type="TextField">
                <name>Domain</name>
            </domain>
        </general>
        <dns>
            <server1 type="TextField">
                <name>DNS Server 1</name>
            </server1>
        </dns>
    </items>
</model>
"""
        )

        model = parser.parse_model_file(xml_file)

        assert model is not None
        assert "general" in model.fields
        assert "dns" in model.fields
        # Check that nested fields are parsed
        assert len(model.fields["general"]) > 0
        assert len(model.fields["dns"]) > 0


def test_to_json_schema_with_required_fields():
    """Test JSON schema generation with required fields."""
    parser = ModelParser()

    model = ModelDefinition(
        name="Test",
        module="Test",
        mount="//Test",
        description="Test model",
        fields={
            "root": [
                ModelField(
                    name="required_field",
                    field_type="TextField",
                    required=True,
                ),
                ModelField(
                    name="optional_field",
                    field_type="TextField",
                    required=False,
                ),
            ]
        },
    )

    schema = parser.to_json_schema(model, "root")

    # Required field should be in required list
    assert "required" in schema
    assert "required_field" in schema["required"]
    assert "optional_field" not in schema["required"]


def test_convert_default_value_invalid_integer():
    """Test conversion of invalid integer default."""
    parser = ModelParser()

    # Invalid integer should return the original string
    result = parser._convert_default_value("not_a_number", "integer")
    assert result == "not_a_number"


def test_convert_default_value_invalid_number():
    """Test conversion of invalid number default."""
    parser = ModelParser()

    # Invalid number should return the original string
    result = parser._convert_default_value("not_a_float", "number")
    assert result == "not_a_float"


def test_parse_model_file_non_xml():
    """Test parsing non-XML file."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    parser = ModelParser()

    with TemporaryDirectory() as tmpdir:
        # Try to parse a non-XML file
        txt_file = Path(tmpdir) / "test.txt"
        txt_file.write_text("not xml")

        model = parser.parse_model_file(txt_file)
        assert model is None


def test_parse_model_file_nonexistent():
    """Test parsing nonexistent file."""
    from pathlib import Path

    parser = ModelParser()

    nonexistent = Path("/nonexistent/file.xml")
    model = parser.parse_model_file(nonexistent)
    assert model is None


def test_parse_model_file_invalid_xml():
    """Test parsing invalid XML."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    parser = ModelParser()

    with TemporaryDirectory() as tmpdir:
        xml_file = Path(tmpdir) / "invalid.xml"
        xml_file.write_text("<?xml version='1.0'?><broken>")

        model = parser.parse_model_file(xml_file)
        assert model is None


def test_parse_model_file_wrong_root_tag():
    """Test parsing XML with wrong root tag."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    parser = ModelParser()

    with TemporaryDirectory() as tmpdir:
        xml_file = Path(tmpdir) / "wrong.xml"
        xml_file.write_text("""<?xml version='1.0'?>
<config>
    <item>test</item>
</config>
""")

        model = parser.parse_model_file(xml_file)
        assert model is None


def test_to_json_schema_with_multiple_field():
    """Test JSON schema with field that has multiple=True."""
    parser = ModelParser()

    model = ModelDefinition(
        name="Test",
        module="Test",
        mount="//Test",
        description="Test model",
        fields={
            "root": [
                ModelField(
                    name="tags",
                    field_type="TextField",
                    multiple=True,
                )
            ]
        },
    )

    schema = parser.to_json_schema(model, "root")

    # Field should be wrapped in array
    assert schema["properties"]["tags"]["type"] == "array"
    assert "items" in schema["properties"]["tags"]


def test_to_json_schema_with_option_values():
    """Test JSON schema with field that has option values."""
    parser = ModelParser()

    model = ModelDefinition(
        name="Test",
        module="Test",
        mount="//Test",
        description="Test model",
        fields={
            "root": [
                ModelField(
                    name="protocol",
                    field_type="OptionField",
                    options={
                        "tcp": "TCP Protocol",
                        "udp": "UDP Protocol",
                        "icmp": "ICMP Protocol",
                    },
                )
            ]
        },
    )

    schema = parser.to_json_schema(model, "root")

    # Should have enum with options
    assert "enum" in schema["properties"]["protocol"]
    assert set(schema["properties"]["protocol"]["enum"]) == {"tcp", "udp", "icmp"}


def test_to_json_schema_invalid_container():
    """Test JSON schema with invalid container name."""
    parser = ModelParser()

    model = ModelDefinition(
        name="Test",
        module="Test",
        mount="//Test",
        description="Test model",
        fields={
            "root": [
                ModelField(
                    name="field1",
                    field_type="TextField",
                )
            ]
        },
    )

    # Request schema for nonexistent container
    schema = parser.to_json_schema(model, "nonexistent")

    # Should return generic object schema
    assert schema == {"type": "object"}


def test_parse_directory_nonexistent():
    """Test parsing nonexistent directory."""
    from pathlib import Path

    parser = ModelParser()

    nonexistent = Path("/nonexistent/directory")
    models = parser.parse_directory(nonexistent)

    # Should return empty dict
    assert models == {}


def test_parse_directory_skips_special_dirs():
    """Test that parse_directory skips Menu, Migrations, ACL directories."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    parser = ModelParser()

    with TemporaryDirectory() as tmpdir:
        models_dir = Path(tmpdir)

        # Create directories that should be skipped
        menu_dir = models_dir / "Menu"
        menu_dir.mkdir()
        migrations_dir = models_dir / "Migrations"
        migrations_dir.mkdir()
        acl_dir = models_dir / "ACL"
        acl_dir.mkdir()

        # Create models in each that should be skipped
        for skip_dir in [menu_dir, migrations_dir, acl_dir]:
            (skip_dir / "test.xml").write_text(
                """<?xml version="1.0"?>
<model>
    <mount>//Test/Skip</mount>
    <description>Should be skipped</description>
    <items>
        <field type="TextField">
            <name>Field</name>
        </field>
    </items>
</model>
"""
            )

        # Parse directory
        models = parser.parse_directory(models_dir)

        # Should not find any models (all were in skipped directories)
        assert len(models) == 0


def test_parse_field_with_unknown_type():
    """Test parsing field with unknown type."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    parser = ModelParser()

    with TemporaryDirectory() as tmpdir:
        xml_file = Path(tmpdir) / "unknown_type.xml"
        xml_file.write_text(
            """<?xml version="1.0"?>
<model>
    <mount>//Test/UnknownType</mount>
    <description>Test with unknown field type</description>
    <items>
        <field type="./CustomUnknownField">
            <name>CustomField</name>
        </field>
    </items>
</model>
"""
        )

        model = parser.parse_model_file(xml_file)

        # Should still parse but may not recognize the type
        assert model is not None
        assert len(model.fields) > 0


def test_parse_field_with_option_values_from_xml():
    """Test parsing field with OptionValues from XML."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    parser = ModelParser()

    with TemporaryDirectory() as tmpdir:
        xml_file = Path(tmpdir) / "options.xml"
        xml_file.write_text(
            """<?xml version="1.0"?>
<model>
    <mount>//Test/Options</mount>
    <description>Test with option values</description>
    <items>
        <protocol type="OptionField">
            <name>Protocol</name>
            <OptionValues>
                <tcp>TCP Protocol</tcp>
                <udp>UDP Protocol</udp>
                <icmp>ICMP</icmp>
            </OptionValues>
        </protocol>
    </items>
</model>
"""
        )

        model = parser.parse_model_file(xml_file)

        # Should parse with options
        assert model is not None
        assert "root" in model.fields
        protocol_field = model.fields["root"][0]
        assert protocol_field.name == "protocol"  # Element tag becomes the field name
        assert len(protocol_field.options) == 3
        assert "tcp" in protocol_field.options
        assert protocol_field.options["tcp"] == "TCP Protocol"


def test_parse_field_with_fuzzy_type_matching():
    """Test parsing field with type that requires fuzzy matching."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    parser = ModelParser()

    with TemporaryDirectory() as tmpdir:
        xml_file = Path(tmpdir) / "fuzzy_type.xml"
        xml_file.write_text(
            """<?xml version="1.0"?>
<model>
    <mount>//Test/FuzzyType</mount>
    <description>Test with type that needs fuzzy matching</description>
    <items>
        <field type="./\\OPNsense\\Base\\FieldTypes\\TextField">
            <name>TextField</name>
        </field>
    </items>
</model>
"""
        )

        model = parser.parse_model_file(xml_file)

        # Should parse and recognize TextField via fuzzy matching
        assert model is not None
        assert "root" in model.fields
        text_field = model.fields["root"][0]
        assert text_field.name == "field"  # Element tag becomes the field name
        # Type should be cleaned up to just the field type name
        assert "TextField" in text_field.field_type
