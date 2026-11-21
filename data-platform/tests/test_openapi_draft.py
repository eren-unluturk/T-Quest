from pathlib import Path

import yaml
from openapi_spec_validator import validate

SPEC = Path(__file__).resolve().parents[1] / "contracts-draft" / "api" / "data-platform.yaml"

EXPECTED_PATHS = {
    "/health", "/routes", "/lines", "/stops", "/stops/{id}", "/vehicles", "/predictions", "/alerts",
}


def _load():
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


def test_spec_is_valid_openapi():
    validate(_load())


def test_spec_lists_all_paths():
    assert set(_load()["paths"]) == EXPECTED_PATHS
