from pathlib import Path

import yaml
from openapi_spec_validator import validate

SPEC_PATH = Path(__file__).resolve().parent.parent / "openapi" / "insights-sponsors.yaml"

EXPECTED = {
    "/stops/{stop_id}/facts": ["get"],
    "/stops/{stop_id}/local-picks": ["get"],
    "/freedom-trail": ["get"],
    "/fun-facts": ["get"],
    "/offers": ["get"],
    "/physical-rewards/catalog": ["get"],
    "/recommendations": ["get"],
    "/analytics/me": ["get"],
    "/consent": ["get", "post"],
    "/consent/{scope}": ["delete"],
}


def load():
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def test_spec_is_valid():
    validate(load())


def test_expected_paths_and_methods():
    paths = load()["paths"]
    for path, methods in EXPECTED.items():
        assert path in paths, path
        for m in methods:
            assert m in paths[path], f"{m} {path}"


def test_fun_facts_is_public():
    assert load()["paths"]["/fun-facts"]["get"]["security"] == []


def test_query_params_present():
    paths = load()["paths"]

    def names(p):
        return {x["name"] for x in paths[p]["get"].get("parameters", []) if "name" in x}

    assert {"limit"} <= names("/stops/{stop_id}/local-picks")
    assert {"limit", "random"} <= names("/fun-facts")
    assert {"stop_id", "store_id", "category", "eligible_only"} <= names("/offers")
    assert {"kind", "limit"} <= names("/recommendations")
    assert {"period"} <= names("/analytics/me")
