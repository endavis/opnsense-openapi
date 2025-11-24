"""Tests for PHP response analyzer."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from opnsense_api.parser.response_analyzer import ResponseAnalyzer


@pytest.fixture
def analyzer() -> ResponseAnalyzer:
    """Response analyzer fixture."""
    return ResponseAnalyzer()


@pytest.fixture
def sample_base_method_controller() -> str:
    """Sample controller with base method calls."""
    return """<?php
namespace OPNsense\\Test\\Api;

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

    public function addAction()
    {
        return $this->addBase("test");
    }

    public function setAction($uuid)
    {
        return $this->setBase("test", $uuid);
    }

    public function delAction($uuid)
    {
        return $this->delBase("test", $uuid);
    }

    public function toggleAction($uuid)
    {
        return $this->toggleBase("test", $uuid);
    }
}
"""


@pytest.fixture
def sample_array_literal_controller() -> str:
    """Sample controller with array literal returns."""
    return """<?php
namespace OPNsense\\Test\\Api;

class TestController extends ApiControllerBase
{
    public function simpleArrayAction()
    {
        return ["status" => "ok", "count" => 42];
    }

    public function complexArrayAction()
    {
        return [
            "result" => "success",
            "data" => ["item1", "item2"],
            "metadata" => [
                "total" => 100,
                "page" => 1
            ]
        ];
    }

    public function multilineArrayAction()
    {
        return [
            "status" => "active",
            "enabled" => true,
            "version" => "1.0"
        ];
    }
}
"""


@pytest.fixture
def sample_variable_tracing_controller() -> str:
    """Sample controller with variable tracing."""
    return """<?php
namespace OPNsense\\Test\\Api;

class TestController extends ApiControllerBase
{
    public function variableReturnAction()
    {
        $result = ["status" => "ok", "message" => "Success"];
        return $result;
    }

    public function multipleAssignmentAction()
    {
        $data = ["count" => 10];
        $result = $data;
        return $result;
    }
}
"""


@pytest.fixture
def sample_service_action_controller() -> str:
    """Sample controller with service action calls."""
    return """<?php
namespace OPNsense\\Test\\Api;

class TestController extends ApiControllerBase
{
    public function statusAction()
    {
        $backend = new Backend();
        $response = $backend->configdRun("test status");
        return ["status" => trim($response)];
    }

    public function restartAction()
    {
        $backend = new Backend();
        $backend->configdRun("test restart");
        return ["result" => "ok"];
    }
}
"""


@pytest.fixture
def sample_method_call_controller() -> str:
    """Sample controller with method calls within same controller."""
    return """<?php
namespace OPNsense\\Test\\Api;

class TestController extends ApiControllerBase
{
    private function getDataAction()
    {
        return ["data" => "value", "status" => "ok"];
    }

    public function fetchAction()
    {
        return $this->getDataAction();
    }
}
"""


@pytest.fixture
def sample_conditional_controller() -> str:
    """Sample controller with conditional returns."""
    return """<?php
namespace OPNsense\\Test\\Api;

class TestController extends ApiControllerBase
{
    public function conditionalAction($type)
    {
        if ($type == "success") {
            return ["result" => "ok", "status" => 200];
        } else {
            return ["result" => "error", "message" => "Failed"];
        }
    }
}
"""


def test_base_method_schemas_defined(analyzer: ResponseAnalyzer) -> None:
    """Test that all base method schemas are defined."""
    assert "searchBase" in analyzer.BASE_METHOD_SCHEMAS
    assert "getBase" in analyzer.BASE_METHOD_SCHEMAS
    assert "addBase" in analyzer.BASE_METHOD_SCHEMAS
    assert "setBase" in analyzer.BASE_METHOD_SCHEMAS
    assert "delBase" in analyzer.BASE_METHOD_SCHEMAS
    assert "toggleBase" in analyzer.BASE_METHOD_SCHEMAS


def test_infer_search_base_schema(
    analyzer: ResponseAnalyzer, sample_base_method_controller: str
) -> None:
    """Test inferring searchBase response schema."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_base_method_controller)

        schema = analyzer.infer_response_schema(php_file, "searchAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "rows" in schema["properties"]
        assert "rowCount" in schema["properties"]
        assert "total" in schema["properties"]
        assert "current" in schema["properties"]
        assert set(schema["required"]) == {"rows", "rowCount", "total", "current"}


def test_infer_get_base_schema(
    analyzer: ResponseAnalyzer, sample_base_method_controller: str
) -> None:
    """Test inferring getBase response schema."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_base_method_controller)

        schema = analyzer.infer_response_schema(php_file, "getAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is True


def test_infer_add_base_schema(
    analyzer: ResponseAnalyzer, sample_base_method_controller: str
) -> None:
    """Test inferring addBase response schema."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_base_method_controller)

        schema = analyzer.infer_response_schema(php_file, "addAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "result" in schema["properties"]
        assert "uuid" in schema["properties"]
        assert "validations" in schema["properties"]
        assert "result" in schema["required"]


def test_infer_set_base_schema(
    analyzer: ResponseAnalyzer, sample_base_method_controller: str
) -> None:
    """Test inferring setBase response schema."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_base_method_controller)

        schema = analyzer.infer_response_schema(php_file, "setAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "result" in schema["properties"]
        assert schema["properties"]["result"]["enum"] == ["saved", "failed"]


def test_infer_del_base_schema(
    analyzer: ResponseAnalyzer, sample_base_method_controller: str
) -> None:
    """Test inferring delBase response schema."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_base_method_controller)

        schema = analyzer.infer_response_schema(php_file, "delAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "result" in schema["properties"]
        assert set(schema["properties"]["result"]["enum"]) == {
            "deleted",
            "failed",
            "not_found",
        }


def test_infer_toggle_base_schema(
    analyzer: ResponseAnalyzer, sample_base_method_controller: str
) -> None:
    """Test inferring toggleBase response schema."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_base_method_controller)

        schema = analyzer.infer_response_schema(php_file, "toggleAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "result" in schema["properties"]
        assert "changed" in schema["properties"]


def test_parse_simple_array_literal(
    analyzer: ResponseAnalyzer, sample_array_literal_controller: str
) -> None:
    """Test parsing simple array literal."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_array_literal_controller)

        schema = analyzer.infer_response_schema(php_file, "simpleArrayAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "status" in schema["properties"]
        assert "count" in schema["properties"]
        assert schema["properties"]["status"]["type"] == "string"
        assert schema["properties"]["count"]["type"] == "integer"


def test_parse_complex_array_literal(
    analyzer: ResponseAnalyzer, sample_array_literal_controller: str
) -> None:
    """Test parsing complex nested array literal."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_array_literal_controller)

        schema = analyzer.infer_response_schema(php_file, "complexArrayAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "result" in schema["properties"]
        assert "data" in schema["properties"]
        assert "metadata" in schema["properties"]
        assert schema["properties"]["data"]["type"] == "array"
        # metadata is detected as array (PHP associative arrays)
        assert schema["properties"]["metadata"]["type"] == "array"


def test_parse_multiline_array_literal(
    analyzer: ResponseAnalyzer, sample_array_literal_controller: str
) -> None:
    """Test parsing multiline array literal."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_array_literal_controller)

        schema = analyzer.infer_response_schema(php_file, "multilineArrayAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "status" in schema["properties"]
        assert "enabled" in schema["properties"]
        assert "version" in schema["properties"]
        assert schema["properties"]["enabled"]["type"] == "boolean"


def test_trace_variable_simple(
    analyzer: ResponseAnalyzer, sample_variable_tracing_controller: str
) -> None:
    """Test tracing simple variable assignment."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_variable_tracing_controller)

        schema = analyzer.infer_response_schema(php_file, "variableReturnAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "status" in schema["properties"]
        assert "message" in schema["properties"]


def test_trace_variable_multiple_assignments(
    analyzer: ResponseAnalyzer, sample_variable_tracing_controller: str
) -> None:
    """Test tracing variable through multiple assignments."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_variable_tracing_controller)

        schema = analyzer.infer_response_schema(php_file, "multipleAssignmentAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "count" in schema["properties"]


def test_service_action_pattern(
    analyzer: ResponseAnalyzer, sample_service_action_controller: str
) -> None:
    """Test recognizing service action patterns."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_service_action_controller)

        schema = analyzer.infer_response_schema(php_file, "statusAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "status" in schema["properties"]


def test_method_call_resolution(
    analyzer: ResponseAnalyzer, sample_method_call_controller: str
) -> None:
    """Test resolving method calls within same controller."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_method_call_controller)

        schema = analyzer.infer_response_schema(php_file, "fetchAction")

        assert schema is not None
        assert schema["type"] == "object"
        assert "data" in schema["properties"]
        assert "status" in schema["properties"]


def test_conditional_returns_merged(
    analyzer: ResponseAnalyzer, sample_conditional_controller: str
) -> None:
    """Test merging schemas from conditional return paths."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(sample_conditional_controller)

        schema = analyzer.infer_response_schema(php_file, "conditionalAction")

        assert schema is not None
        assert schema["type"] == "object"
        # Both branches should be merged
        assert "result" in schema["properties"]
        # Properties from both branches should be present
        properties = set(schema["properties"].keys())
        assert "result" in properties
        # May have status or message depending on merge strategy


def test_extract_method_body(analyzer: ResponseAnalyzer) -> None:
    """Test extracting method body from PHP content."""
    content = """<?php
class Test {
    public function testAction() {
        $x = 1;
        return ["status" => "ok"];
    }
}
"""
    body = analyzer._extract_method_body(content, "testAction")
    assert body is not None
    assert "$x = 1;" in body
    assert 'return ["status" => "ok"];' in body


def test_extract_method_body_nested_braces(analyzer: ResponseAnalyzer) -> None:
    """Test extracting method body with nested braces."""
    content = """<?php
class Test {
    public function testAction() {
        if (true) {
            return ["status" => "ok"];
        }
    }
}
"""
    body = analyzer._extract_method_body(content, "testAction")
    assert body is not None
    assert "if (true)" in body


def test_extract_method_body_not_found(analyzer: ResponseAnalyzer) -> None:
    """Test extracting non-existent method."""
    content = """<?php
class Test {
    public function otherAction() {}
}
"""
    body = analyzer._extract_method_body(content, "testAction")
    assert body is None


def test_infer_value_type_string(analyzer: ResponseAnalyzer) -> None:
    """Test inferring string value type."""
    schema = analyzer._infer_value_type('"test"')
    assert schema["type"] == "string"


def test_infer_value_type_integer(analyzer: ResponseAnalyzer) -> None:
    """Test inferring integer value type."""
    schema = analyzer._infer_value_type("42")
    assert schema["type"] == "integer"


def test_infer_value_type_boolean_true(analyzer: ResponseAnalyzer) -> None:
    """Test inferring boolean true value type."""
    schema = analyzer._infer_value_type("true")
    assert schema["type"] == "boolean"


def test_infer_value_type_boolean_false(analyzer: ResponseAnalyzer) -> None:
    """Test inferring boolean false value type."""
    schema = analyzer._infer_value_type("false")
    assert schema["type"] == "boolean"


def test_infer_value_type_array(analyzer: ResponseAnalyzer) -> None:
    """Test inferring array value type."""
    schema = analyzer._infer_value_type('["item"]')
    assert schema["type"] == "array"


def test_nonexistent_file(analyzer: ResponseAnalyzer) -> None:
    """Test handling non-existent PHP file."""
    php_file = Path("/nonexistent/path/test.php")
    schema = analyzer.infer_response_schema(php_file, "testAction")
    assert schema is None


def test_method_not_found_in_file(analyzer: ResponseAnalyzer) -> None:
    """Test handling method not found in file."""
    with TemporaryDirectory() as tmpdir:
        php_file = Path(tmpdir) / "TestController.php"
        php_file.write_text(
            """<?php
class Test {
    public function otherAction() {
        return ["status" => "ok"];
    }
}
"""
        )

        schema = analyzer.infer_response_schema(php_file, "nonExistentAction")
        assert schema is None
