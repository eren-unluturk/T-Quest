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
    "/analytics/boston": ["get"],
    "/place-visits": ["post", "delete"],
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


def test_version_and_changelog():
    info = load()["info"]
    assert info["version"] == "0.5.0"
    log = info["x-changelog"]
    assert any(e.startswith("0.3.0:") and "/place-visits" in e for e in log)
    assert any(e.startswith("0.2.0:") and "/analytics/boston" in e for e in log)
    assert any(e.startswith("0.1.1:") and "409" in e and "ConsentRequired" in e for e in log)


def test_post_consent_documents_409_policy_mismatch():
    spec = load()
    resp = spec["paths"]["/consent"]["post"]["responses"]["409"]
    assert resp["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/PolicyMismatch"}
    assert spec["components"]["schemas"]["PolicyMismatch"]["required"] == ["detail", "current"]


def test_consent_required_response_exists():
    spec = load()
    resp = spec["components"]["responses"]["ConsentRequired"]
    assert "consent required" in resp["description"].lower()
    assert resp["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/Error"}


def test_recommendations_description_says_no_403():
    spec = load()
    op = spec["paths"]["/recommendations"]["get"]
    assert "never returns 403" in op["description"]
    assert "403" not in op["responses"]


def test_409_body_from_the_app_matches_policy_mismatch(client, auth_headers):
    from openapi_shape import check_shape

    r = client.post("/consent", json={"scope": "location", "policy_version": "1999-01-01"}, headers=auth_headers)
    assert r.status_code == 409
    check_shape({"$ref": "#/components/schemas/PolicyMismatch"}, r.json())
