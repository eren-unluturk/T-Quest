"""The running app must match contracts-draft/api/data-platform.yaml
(or ../contracts/api/data-platform.yaml once published, which takes precedence)."""
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from openapi_schema_validator import OAS30Validator

from data_platform.app import app

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT.parent / "contracts" / "api" / "data-platform.yaml"
DRAFT = ROOT / "contracts-draft" / "api" / "data-platform.yaml"
SPEC = yaml.safe_load((PUBLISHED if PUBLISHED.exists() else DRAFT).read_text(encoding="utf-8"))

client = TestClient(app)


def resolve(node):
    """Inline every #/components/... $ref (the spec has no recursive schemas)."""
    if isinstance(node, dict):
        if "$ref" in node:
            target = SPEC
            for part in node["$ref"].lstrip("#/").split("/"):
                target = target[part]
            return resolve(target)
        return {k: resolve(v) for k, v in node.items()}
    if isinstance(node, list):
        return [resolve(v) for v in node]
    return node


def validate(path, status, body):
    schema = SPEC["paths"][path]["get"]["responses"][str(status)]["content"]["application/json"]["schema"]
    OAS30Validator(resolve(schema)).validate(body)


def test_app_exposes_exactly_the_spec_paths():
    assert set(app.openapi()["paths"]) == set(SPEC["paths"])


def test_query_parameters_match_spec():
    ours = app.openapi()["paths"]
    for path, item in SPEC["paths"].items():
        spec_params = {p["name"] for p in item["get"].get("parameters", []) if p["in"] == "query"}
        app_params = {p["name"] for p in ours[path]["get"].get("parameters", []) if p["in"] == "query"}
        assert app_params == spec_params, path


def test_health_matches_spec():
    r = client.get("/health")
    assert r.status_code == 200
    validate("/health", 200, r.json())


@pytest.fixture
def seeded(api_world):
    return api_world


def test_responses_validate_against_spec(seeded):
    w = seeded
    lat, lon = w["origin"]
    calls = [
        ("/routes", {"mode": "commuter_rail"}),
        ("/lines", {}),
        ("/stops", {"lat": lat, "lon": lon, "radius_m": 1000}),
        (f"/stops/{w['stops'][0]}", {}),
        ("/vehicles", {"route_id": w["route_a"], "since_s": 600}),
        ("/predictions", {"stop_id": w["stops"][0]}),
        ("/alerts", {"route_id": w["route_a"], "active": "false"}),
    ]
    for url, params in calls:
        r = client.get(url, params=params)
        assert r.status_code == 200, (url, r.text)
        body = r.json()
        if isinstance(body, list):
            assert body, f"empty result for {url}"
        spec_path = "/stops/{id}" if url.startswith("/stops/") else url
        validate(spec_path, 200, body)


def test_unknown_stop_404_matches_error_schema(seeded):
    r = client.get("/stops/nope")
    assert r.status_code == 404
    validate("/stops/{id}", 404, r.json())
