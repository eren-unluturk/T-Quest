"""Compare response bodies with the OpenAPI draft by shape.

Walks $refs, arrays and objects and checks that object keys equal the schema
properties and that required keys are present. Simpler than full JSON Schema
validation, which does not understand OpenAPI 3.0 `nullable`.
"""

from pathlib import Path

import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "openapi" / "insights-sponsors.yaml"
SPEC = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def _resolve(schema: dict) -> dict:
    while "$ref" in schema:
        node = SPEC
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        schema = node
    return schema


def check_shape(schema: dict, data, path: str = "$") -> None:
    schema = _resolve(schema)
    if data is None:
        assert schema.get("nullable"), f"{path} is null but not nullable"
        return
    kind = schema.get("type")
    if kind == "array":
        assert isinstance(data, list), path
        for i, item in enumerate(data):
            check_shape(schema["items"], item, f"{path}[{i}]")
    elif kind == "object":
        assert isinstance(data, dict), path
        props = schema.get("properties", {})
        assert set(data) == set(props), f"{path}: {sorted(data)} != {sorted(props)}"
        for key in schema.get("required", []):
            assert key in data, f"{path}.{key} missing"
        for key, value in data.items():
            check_shape(props[key], value, f"{path}.{key}")


def response_schema(path: str, method: str, status: str = "200") -> dict:
    op = SPEC["paths"][path][method]
    return op["responses"][status]["content"]["application/json"]["schema"]
