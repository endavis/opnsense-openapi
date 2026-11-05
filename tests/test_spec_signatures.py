"""Parity between generated spec paths and PHP controller signatures (#168)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from opnsense_openapi import get_spec_path, list_available_specs
from opnsense_openapi.downloader import SourceDownloader
from opnsense_openapi.generator.openapi_generator import OpenApiGenerator
from opnsense_openapi.parser import ControllerParser
from opnsense_openapi.utils import to_snake_case

CONTROLLER = """<?php
namespace OPNsense\\Demo\\Api;

class ThingController extends ApiControllerBase
{
    public function installAction($pkg_name) {}
    public function getAction($uuid = null) {}
    public function toggleAction($uuid, $enabled = null) {}
    public function listAction() {}
    public function multiAction(
        $a = '',
        $b = 0
    ) {}
}
"""


def _expected_paths(controllers: list[object]) -> set[str]:
    """Compute expected paths straight from parsed signatures."""
    paths: set[str] = set()
    for ctrl in controllers:
        base = f"/api/{ctrl.module.lower()}/{to_snake_case(ctrl.controller)}"  # type: ignore[attr-defined]
        for ep in ctrl.endpoints:  # type: ignore[attr-defined]
            required = len(ep.parameters) - len(ep.optional_parameters)
            for k in range(required, len(ep.parameters) + 1):
                paths.add(base + f"/{ep.name}" + "".join(f"/{{{n}}}" for n in ep.parameters[:k]))
    return paths


def test_generated_paths_match_signatures(tmp_path: Path) -> None:
    api = tmp_path / "src" / "Demo" / "Api"
    api.mkdir(parents=True)
    (api / "ThingController.php").write_text(CONTROLLER, encoding="utf-8")
    controllers = ControllerParser().parse_directory(tmp_path / "src")
    generator = OpenApiGenerator(tmp_path / "out")
    generator.generate(controllers, "0.0", models_dir=None)
    spec = json.loads((tmp_path / "out" / "opnsense-0.0.json").read_text(encoding="utf-8"))

    assert set(spec["paths"]) == _expected_paths(list(controllers))
    assert set(spec["paths"]) == {
        "/api/demo/thing/install/{pkg_name}",
        "/api/demo/thing/get",
        "/api/demo/thing/get/{uuid}",
        "/api/demo/thing/toggle/{uuid}",
        "/api/demo/thing/toggle/{uuid}/{enabled}",
        "/api/demo/thing/list",
        "/api/demo/thing/multi",
        "/api/demo/thing/multi/{a}",
        "/api/demo/thing/multi/{a}/{b}",
    }


def test_search_find_methods_end_to_end(tmp_path: Path) -> None:
    """Search/find get GET+POST unless gated on isPost(); operationIds stay unique (#172)."""
    api = tmp_path / "src" / "Demo" / "Api"
    api.mkdir(parents=True)
    (api / "ThingController.php").write_text(
        "<?php\nnamespace OPNsense\\Demo\\Api;\n\n"
        "class ThingController extends ApiControllerBase\n{\n"
        "    public function searchItemAction() { return []; }\n"
        "    public function searchGatedAction()\n    {\n"
        "        if ($this->request->isPost()) { return []; }\n    }\n"
        "    public function findThingAction() { return []; }\n}\n",
        encoding="utf-8",
    )
    controllers = ControllerParser().parse_directory(tmp_path / "src")
    generator = OpenApiGenerator(tmp_path / "out")
    generator.generate(controllers, "0.0", models_dir=None)
    spec = json.loads((tmp_path / "out" / "opnsense-0.0.json").read_text(encoding="utf-8"))
    paths = spec["paths"]
    assert set(paths["/api/demo/thing/searchItem"]) == {"get", "post"}
    assert set(paths["/api/demo/thing/findThing"]) == {"get", "post"}
    assert set(paths["/api/demo/thing/searchGated"]) == {"post"}
    ids = [op["operationId"] for item in paths.values() for op in item.values()]
    assert len(ids) == len(set(ids))


@pytest.mark.requires_opnsense_source
def test_latest_spec_matches_signatures() -> None:
    available = list_available_specs()
    if not available:
        pytest.skip("No committed specs available")
    latest = available[-1]
    spec = json.loads(get_spec_path(latest).read_text(encoding="utf-8"))
    try:
        controllers_root = SourceDownloader().download(latest)
    except (RuntimeError, OSError) as exc:
        pytest.skip(f"Unable to materialize OPNsense source for {latest}: {exc}")
    controllers = ControllerParser().parse_directory(controllers_root)
    assert set(spec["paths"]) == _expected_paths(list(controllers))


def test_inherited_actions_appear_in_generated_spec(tmp_path: Path) -> None:
    """Inherited actions are routable; abstract parents are not (#171)."""
    base = tmp_path / "src" / "OPNsense" / "Base"
    base.mkdir(parents=True)
    (base / "ApiMutableModelControllerBase.php").write_text(
        "<?php\nnamespace OPNsense\\Base;\nabstract class ApiMutableModelControllerBase\n{\n"
        "    public function setAction() {}\n}\n",
        encoding="utf-8",
    )
    api = tmp_path / "src" / "OPNsense" / "Demo" / "Api"
    api.mkdir(parents=True)
    (api / "ThingBaseController.php").write_text(
        "<?php\nnamespace OPNsense\\Demo\\Api;\n"
        "use OPNsense\\Base\\ApiMutableModelControllerBase;\n"
        "abstract class ThingBaseController extends ApiMutableModelControllerBase\n{\n"
        "    public function applyAction() {}\n}\n",
        encoding="utf-8",
    )
    (api / "ThingController.php").write_text(
        "<?php\nnamespace OPNsense\\Demo\\Api;\nclass ThingController extends ThingBaseController\n"
        "{\n    public function searchRuleAction() {}\n}\n",
        encoding="utf-8",
    )
    controllers = ControllerParser().parse_directory(tmp_path / "src")
    generator = OpenApiGenerator(tmp_path / "out")
    generator.generate(controllers, "0.0", models_dir=None)
    spec = json.loads((tmp_path / "out" / "opnsense-0.0.json").read_text(encoding="utf-8"))
    assert set(spec["paths"]) == {
        "/api/demo/thing/searchRule",
        "/api/demo/thing/set",
        "/api/demo/thing/apply",
    }
