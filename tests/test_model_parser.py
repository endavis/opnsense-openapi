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
