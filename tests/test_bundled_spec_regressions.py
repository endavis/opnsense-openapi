"""Regression tests against the bundled specs for the #171 and #172 parser fixes (#173)."""

from __future__ import annotations

import pytest

from opnsense_openapi import endpoint_exists, list_available_specs

OLDEST_CHECKED = "26.1.6"


def _versions() -> list[str]:
    """Return the versions to check: 26.1.6 and the latest bundled spec."""
    available = list_available_specs()
    latest = available[-1] if available else OLDEST_CHECKED
    return [OLDEST_CHECKED] if latest == OLDEST_CHECKED else [OLDEST_CHECKED, latest]


VERSIONS = _versions()


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("core/tunables/get", "GET"),
        ("core/firmware/get", "GET"),
        ("kea/service/reconfigure", "POST"),
        ("firewall/filter/searchRule", "POST"),
        ("kea/leases4/search", "POST"),
    ],
)
def test_inherited_actions_are_in_bundled_spec(path: str, method: str, version: str) -> None:
    assert endpoint_exists(path, method, version=version)


@pytest.mark.parametrize("version", VERSIONS)
def test_abstract_controller_actions_are_not_in_bundled_spec(version: str) -> None:
    assert not endpoint_exists("firewall/filter_base/apply", "POST", version=version)


@pytest.mark.parametrize("version", VERSIONS)
def test_ungated_search_action_accepts_get_and_post(version: str) -> None:
    assert endpoint_exists("firewall/alias/searchItem", "GET", version=version)
    assert endpoint_exists("firewall/alias/searchItem", "POST", version=version)


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize(
    "path",
    ["ids/settings/searchInstalledRules", "firewall/alias_util/findReferences"],
)
def test_post_gated_search_actions_stay_post_only(path: str, version: str) -> None:
    assert endpoint_exists(path, "POST", version=version)
    assert not endpoint_exists(path, "GET", version=version)
