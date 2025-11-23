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
