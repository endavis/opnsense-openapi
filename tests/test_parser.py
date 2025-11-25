"""Tests for PHP controller parser."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from opnsense_openapi.parser import ControllerParser
from opnsense_openapi.utils import to_snake_case


@pytest.fixture
def sample_controller() -> str:
    """Sample PHP controller content for testing."""
    return """<?php
namespace OPNsense\\Firewall\\Api;

use OPNsense\\Base\\ApiControllerBase;

/**
 * Class AliasUtilController
 */
class AliasUtilController extends ApiControllerBase
{
    /**
     * Find aliases
     * @return array
     */
    public function findAliasAction()
    {
        return $this->searchBase("alias", $this->request->getPost());
    }

    /**
     * Add new alias
     * @param string $uuid
     * @return array
     */
    public function addAction($uuid)
    {
        return $this->addBase("alias", $uuid);
    }

    /**
     * Update alias settings
     * @return array
     */
    public function setAction()
    {
        return $this->setBase("alias");
    }

    /**
     * Get alias
     * @param string $uuid
     * @return array
     */
    public function getAction($uuid)
    {
        return $this->getBase("alias", "field", $uuid);
    }
}
"""


def test_parse_controller_basic(sample_controller: str) -> None:
    """Test parsing a basic controller file."""
    parser = ControllerParser()

    with TemporaryDirectory() as tmpdir:
        # Create temporary controller file
        api_dir = Path(tmpdir) / "Api"
        api_dir.mkdir()
        controller_file = api_dir / "AliasUtilController.php"
        controller_file.write_text(sample_controller)

        # Parse the controller
        controller = parser.parse_controller_file(controller_file)

        assert controller is not None
        assert controller.module == "Firewall"
        assert controller.controller == "AliasUtil"
        assert controller.base_class == "ApiControllerBase"
        assert len(controller.endpoints) == 4


def test_parse_endpoints(sample_controller: str) -> None:
    """Test parsing endpoint methods from controller."""
    parser = ControllerParser()

    with TemporaryDirectory() as tmpdir:
        api_dir = Path(tmpdir) / "Api"
        api_dir.mkdir()
        controller_file = api_dir / "AliasUtilController.php"
        controller_file.write_text(sample_controller)

        controller = parser.parse_controller_file(controller_file)

        assert controller is not None

        # Check findAlias endpoint
        find_endpoint = next(e for e in controller.endpoints if e.name == "findAlias")
        assert find_endpoint.method == "POST"
        assert find_endpoint.description == "Find aliases"
        assert find_endpoint.parameters == []

        # Check add endpoint
        add_endpoint = next(e for e in controller.endpoints if e.name == "add")
        assert add_endpoint.method == "POST"
        assert add_endpoint.description == "Add new alias"
        assert add_endpoint.parameters == ["uuid"]

        # Check set endpoint
        set_endpoint = next(e for e in controller.endpoints if e.name == "set")
        assert set_endpoint.method == "POST"
        assert set_endpoint.description == "Update alias settings"

        # Check get endpoint
        get_endpoint = next(e for e in controller.endpoints if e.name == "get")
        assert get_endpoint.method == "GET"
        assert get_endpoint.description == "Get alias"


def test_parse_directory() -> None:
    """Test parsing multiple controllers in a directory."""
    parser = ControllerParser()

    with TemporaryDirectory() as tmpdir:
        # Create multiple controller files
        firewall_api = Path(tmpdir) / "Firewall" / "Api"
        firewall_api.mkdir(parents=True)

        (firewall_api / "TestController.php").write_text(
            """<?php
namespace OPNsense\\Firewall\\Api;
use OPNsense\\Base\\ApiControllerBase;

class TestController extends ApiControllerBase
{
    public function getAction() {}
}
"""
        )

        system_api = Path(tmpdir) / "System" / "Api"
        system_api.mkdir(parents=True)

        (system_api / "InfoController.php").write_text(
            """<?php
namespace OPNsense\\System\\Api;
use OPNsense\\Base\\ApiControllerBase;

class InfoController extends ApiControllerBase
{
    public function versionAction() {}
}
"""
        )

        controllers = parser.parse_directory(Path(tmpdir))

        assert len(controllers) == 2
        modules = {c.module for c in controllers}
        assert modules == {"Firewall", "System"}


def test_to_snake_case() -> None:
    """Test snake_case conversion."""
    assert to_snake_case("findAlias") == "find_alias"
    assert to_snake_case("AliasUtil") == "alias_util"
    assert to_snake_case("get") == "get"
    assert to_snake_case("setItem") == "set_item"


def test_validate_version() -> None:
    """Test version validation."""
    from opnsense_openapi.utils import validate_version

    # Valid versions
    assert validate_version("24.7")
    assert validate_version("24.7.1")
    assert validate_version("v24.7")
    assert validate_version("25.1.10")

    # Invalid versions
    assert not validate_version("invalid")
    assert not validate_version("24")
    assert not validate_version("24.7.1.2")


def test_to_class_name() -> None:
    """Test snake_case to PascalCase conversion."""
    from opnsense_openapi.utils import to_class_name

    assert to_class_name("firewall_alias") == "FirewallAlias"
    assert to_class_name("test") == "Test"
    assert to_class_name("api_controller_base") == "ApiControllerBase"


def test_parse_controller_nonexistent_file() -> None:
    """Test parsing nonexistent controller file."""
    parser = ControllerParser()

    nonexistent = Path("/nonexistent/Controller.php")
    controller = parser.parse_controller_file(nonexistent)

    assert controller is None


def test_parse_controller_non_controller_file() -> None:
    """Test parsing non-controller PHP file."""
    parser = ControllerParser()

    with TemporaryDirectory() as tmpdir:
        # Create a PHP file that doesn't end with Controller.php
        php_file = Path(tmpdir) / "Api" / "Helper.php"
        php_file.parent.mkdir(parents=True)
        php_file.write_text(
            """<?php
namespace OPNsense\\Firewall\\Api;

class Helper
{
    public function helpAction() {}
}
"""
        )

        controller = parser.parse_controller_file(php_file)
        assert controller is None


def test_parse_controller_no_namespace() -> None:
    """Test parsing controller without namespace."""
    parser = ControllerParser()

    with TemporaryDirectory() as tmpdir:
        api_dir = Path(tmpdir) / "Api"
        api_dir.mkdir()
        controller_file = api_dir / "TestController.php"
        controller_file.write_text(
            """<?php
// Missing namespace

class TestController extends ApiControllerBase
{
    public function getAction() {}
}
"""
        )

        controller = parser.parse_controller_file(controller_file)
        assert controller is None


def test_parse_controller_no_class() -> None:
    """Test parsing controller without class definition."""
    parser = ControllerParser()

    with TemporaryDirectory() as tmpdir:
        api_dir = Path(tmpdir) / "Api"
        api_dir.mkdir()
        controller_file = api_dir / "TestController.php"
        controller_file.write_text(
            """<?php
namespace OPNsense\\Test\\Api;

// Missing class definition
function someFunction() {}
"""
        )

        controller = parser.parse_controller_file(controller_file)
        assert controller is None
