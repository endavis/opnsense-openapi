"""Tests for PHP controller parser."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from opnsense_openapi.parser import ApiController, ApiEndpoint, ControllerParser
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


def test_parse_directory_returns_controllers_in_path_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Controllers come back in sorted path order, whatever order rglob yields (#138)."""
    for module in ("Alpha", "Beta", "Gamma"):
        api_dir = tmp_path / module / "Api"
        api_dir.mkdir(parents=True)
        (api_dir / "ItemController.php").write_text(
            f"""<?php
namespace OPNsense\\{module}\\Api;
use OPNsense\\Base\\ApiControllerBase;

class ItemController extends ApiControllerBase
{{
    public function getAction() {{}}
}}
"""
        )

    real_rglob = Path.rglob

    def reversed_rglob(self: Path, pattern: str) -> list[Path]:
        # Simulate a filesystem that lists entries in reverse order.
        return sorted(real_rglob(self, pattern), reverse=True)

    monkeypatch.setattr(Path, "rglob", reversed_rglob)

    controllers = ControllerParser().parse_directory(tmp_path)

    assert [c.module for c in controllers] == ["Alpha", "Beta", "Gamma"]


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


def _endpoints_for(php_signature: str) -> list[ApiEndpoint]:
    """Parse a one-action controller with the given signature text."""
    content = (
        "<?php\nnamespace OPNsense\\Test\\Api;\n"
        "class DemoController extends ApiControllerBase\n{\n"
        f"    public function fooAction({php_signature})\n    {{}}\n}}\n"
    )
    return ControllerParser()._extract_endpoints(content)


def test_required_parameter() -> None:
    (ep,) = _endpoints_for("$pkg_name")
    assert ep.parameters == ["pkg_name"]
    assert ep.optional_parameters == []


def test_defaulted_parameter_is_optional() -> None:
    (ep,) = _endpoints_for("$uuid = null")
    assert ep.parameters == ["uuid"]
    assert ep.optional_parameters == ["uuid"]


def test_trailing_optional_only() -> None:
    (ep,) = _endpoints_for("$uuid, $enabled = null")
    assert ep.parameters == ["uuid", "enabled"]
    assert ep.optional_parameters == ["enabled"]


def test_default_before_required_is_not_optional() -> None:
    (ep,) = _endpoints_for("$a = null, $b")
    assert ep.parameters == ["a", "b"]
    assert ep.optional_parameters == []


def test_typed_default_parameter() -> None:
    (ep,) = _endpoints_for("string $type = 'secret'")
    assert ep.parameters == ["type"]
    assert ep.optional_parameters == ["type"]


def test_default_literal_containing_comma() -> None:
    (ep,) = _endpoints_for("$a = 'x,y', $b = 0")
    assert ep.parameters == ["a", "b"]
    assert ep.optional_parameters == ["a", "b"]


def test_multiline_signature() -> None:
    (ep,) = _endpoints_for("\n        $a = '',\n        $b = 0,\n        $c = -1\n    ")
    assert ep.parameters == ["a", "b", "c"]
    assert ep.optional_parameters == ["a", "b", "c"]


# --- Inheritance resolution (#171) ---------------------------------------------------------


def _write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _php(namespace: str, header: str, body: str = "") -> str:
    return f"<?php\nnamespace {namespace};\n\n{header}\n{{\n{body}\n}}\n"


@pytest.fixture
def inheritance_tree(tmp_path: Path) -> Path:
    """A synthetic controllers tree with Base classes, an abstract Api parent and subclasses."""
    _write(
        tmp_path,
        "OPNsense/Base/ApiControllerBase.php",
        _php("OPNsense\\Base", "class ApiControllerBase extends ControllerRoot"),
    )
    _write(
        tmp_path,
        "OPNsense/Base/ApiMutableModelControllerBase.php",
        _php(
            "OPNsense\\Base",
            "abstract class ApiMutableModelControllerBase extends ApiControllerBase",
            "    public function getAction() {}\n"
            "    public function setAction() {}\n"
            "    protected function searchBase() {}\n",
        ),
    )
    _write(
        tmp_path,
        "OPNsense/Base/ApiMutableServiceControllerBase.php",
        _php(
            "OPNsense\\Base",
            "abstract class ApiMutableServiceControllerBase extends ApiControllerBase",
            "    public function reconfigureAction() {}\n    public function statusAction() {}\n",
        ),
    )
    _write(
        tmp_path,
        "OPNsense/Demo/Api/ThingBaseController.php",
        _php(
            "OPNsense\\Demo\\Api",
            "abstract class ThingBaseController extends ApiMutableModelControllerBase",
            "    protected static $internalModelName = 'thing';\n"
            "    public function applyAction() {}\n",
        ),
    )
    _write(
        tmp_path,
        "OPNsense/Demo/Api/ThingController.php",
        _php(
            "OPNsense\\Demo\\Api",
            "class ThingController extends ThingBaseController",
            "    public function searchRuleAction() {}\n"
            "    public function getAction($uuid = null) {}\n",
        ),
    )
    _write(
        tmp_path,
        "OPNsense/Demo/Api/ServiceController.php",
        _php(
            "OPNsense\\Demo\\Api", "class ServiceController extends ApiMutableServiceControllerBase"
        ),
    )
    return tmp_path


def _by_name(controllers: list[ApiController]) -> dict[str, ApiController]:
    return {c.controller: c for c in controllers}


def test_inherited_actions_all_from_parent(inheritance_tree: Path) -> None:
    controllers = _by_name(ControllerParser().parse_directory(inheritance_tree))
    assert [e.name for e in controllers["Service"].endpoints] == ["reconfigure", "status"]


def test_inherited_actions_order_override_and_protected(inheritance_tree: Path) -> None:
    thing = _by_name(ControllerParser().parse_directory(inheritance_tree))["Thing"]
    assert [e.name for e in thing.endpoints] == ["searchRule", "get", "apply", "set"]
    endpoints = {e.name: e for e in thing.endpoints}
    assert endpoints["get"].parameters == ["uuid"]
    assert endpoints["get"].optional_parameters == ["uuid"]
    assert endpoints["set"].parameters == []
    assert "searchBase" not in endpoints


def test_model_name_inherited_and_own_kept(inheritance_tree: Path) -> None:
    _write(
        inheritance_tree,
        "OPNsense/Demo/Api/OwnController.php",
        _php(
            "OPNsense\\Demo\\Api",
            "class OwnController extends ThingBaseController",
            "    protected static $internalModelName = 'own';\n",
        ),
    )
    controllers = _by_name(ControllerParser().parse_directory(inheritance_tree))
    assert controllers["Thing"].model_name == "thing"
    assert controllers["Own"].model_name == "own"


def test_abstract_and_base_classes_not_returned(inheritance_tree: Path) -> None:
    controllers = ControllerParser().parse_directory(inheritance_tree)
    assert sorted(c.controller for c in controllers) == ["Service", "Thing"]


def test_parse_controller_file_reports_abstract_and_any_parent(inheritance_tree: Path) -> None:
    parser = ControllerParser()
    base = parser.parse_controller_file(
        inheritance_tree / "OPNsense/Demo/Api/ThingBaseController.php"
    )
    assert base is not None
    assert base.is_abstract is True
    assert base.namespace == "OPNsense\\Demo\\Api"
    thing = parser.parse_controller_file(inheritance_tree / "OPNsense/Demo/Api/ThingController.php")
    assert thing is not None
    assert thing.is_abstract is False
    assert thing.base_class == "ThingBaseController"


def test_unresolved_parent_logs_once(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    for name in ("AController", "BController"):
        _write(
            tmp_path,
            f"OPNsense/Demo/Api/{name}.php",
            _php(
                "OPNsense\\Demo\\Api",
                f"class {name} extends MissingBase",
                "    public function ownAction() {}\n",
            ),
        )
    with caplog.at_level("WARNING"):
        controllers = ControllerParser().parse_directory(tmp_path)
    assert [[e.name for e in c.endpoints] for c in controllers] == [["own"], ["own"]]
    warnings = [r for r in caplog.records if "MissingBase" in r.getMessage()]
    assert len(warnings) == 1


def test_resolution_through_use_import_and_fqn(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "OPNsense/Base/XBase.php",
        _php("OPNsense\\Base", "abstract class XBase", "    public function xAction() {}\n"),
    )
    _write(
        tmp_path,
        "OPNsense/Demo/Api/ViaUseController.php",
        "<?php\nnamespace OPNsense\\Demo\\Api;\nuse OPNsense\\Base\\XBase;\n\n"
        "class ViaUseController extends XBase\n{\n}\n",
    )
    _write(
        tmp_path,
        "OPNsense/Demo/Api/ViaFqnController.php",
        _php("OPNsense\\Demo\\Api", "class ViaFqnController extends \\OPNsense\\Base\\XBase"),
    )
    controllers = _by_name(ControllerParser().parse_directory(tmp_path))
    assert [e.name for e in controllers["ViaUse"].endpoints] == ["x"]
    assert [e.name for e in controllers["ViaFqn"].endpoints] == ["x"]


def test_extends_cycle_terminates(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "OPNsense/Demo/Api/AController.php",
        _php(
            "OPNsense\\Demo\\Api",
            "class AController extends BController",
            "    public function aAction() {}",
        ),
    )
    _write(
        tmp_path,
        "OPNsense/Demo/Api/BController.php",
        _php(
            "OPNsense\\Demo\\Api",
            "class BController extends AController",
            "    public function bAction() {}",
        ),
    )
    controllers = _by_name(ControllerParser().parse_directory(tmp_path))
    assert [e.name for e in controllers["A"].endpoints] == ["a", "b"]
