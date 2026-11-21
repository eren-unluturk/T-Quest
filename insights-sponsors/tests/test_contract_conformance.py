"""Every operation in the OpenAPI draft is called on the real app and its 2xx
body is checked against the documented schema. Also fails when the app serves a
route that the contract does not list."""

import pytest
from openapi_shape import SPEC, check_shape

from insights_sponsors.config import CURRENT_POLICY_VERSION, ENV_FILE

AUTH = {"Authorization": "Bearer user-1"}
IGNORED = {"/health", "/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect"}
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

# Concrete values for path parameters and request bodies, using seeded ids.
PATH_VALUES = {"stop_id": "place-pktrm", "scope": "place_visits"}
BODIES = {
    ("/consent", "post"): {"scope": "place_visits", "policy_version": CURRENT_POLICY_VERSION},
}

OPERATIONS = [
    (path, method)
    for path, item in SPEC["paths"].items()
    for method in item
    if method in HTTP_METHODS
]


def fill(path: str) -> str:
    for name, value in PATH_VALUES.items():
        path = path.replace("{" + name + "}", value)
    assert "{" not in path, f"no seeded value for a parameter in {path}"
    return path


def is_public(path: str, method: str) -> bool:
    op = SPEC["paths"][path][method]
    return op.get("security", SPEC["security"]) == []


def test_operations_found():
    assert len(OPERATIONS) == 12


@pytest.mark.parametrize("path,method", OPERATIONS, ids=[f"{m.upper()} {p}" for p, m in OPERATIONS])
def test_operation_conforms(client, path, method):
    url = fill(path)
    headers = {} if is_public(path, method) else AUTH
    kwargs = {"headers": headers}
    if (path, method) in BODIES:
        kwargs["json"] = BODIES[(path, method)]

    # Consent revoke needs something to revoke; do it as a user would.
    if (path, method) == ("/consent/{scope}", "delete"):
        client.post("/consent", json=BODIES[("/consent", "post")], headers=AUTH)

    response = client.request(method.upper(), url, **kwargs)
    assert 200 <= response.status_code < 300, f"{method.upper()} {url}: {response.status_code} {response.text}"

    declared = SPEC["paths"][path][method]["responses"]
    assert str(response.status_code) in declared, f"{response.status_code} not documented for {method} {path}"
    schema = declared[str(response.status_code)]["content"]["application/json"]["schema"]
    check_shape(schema, response.json())


@pytest.mark.parametrize("path,method", OPERATIONS, ids=[f"{m.upper()} {p}" for p, m in OPERATIONS])
def test_authed_operations_reject_missing_token(client, path, method):
    if is_public(path, method):
        pytest.skip("public operation")
    kwargs = {"json": BODIES[(path, method)]} if (path, method) in BODIES else {}
    response = client.request(method.upper(), fill(path), **kwargs)
    assert response.status_code == 401
    assert "401" in SPEC["paths"][path][method]["responses"]


def test_no_route_outside_the_contract(client):
    # app.routes only holds lazy router wrappers in current FastAPI, so read the
    # generated schema, which lists every served operation.
    served = {
        (path, method)
        for path, item in client.app.openapi()["paths"].items()
        if path not in IGNORED
        for method in item
        if method in HTTP_METHODS
    }
    assert served == set(OPERATIONS)


def test_env_file_is_resolved_from_the_package_not_cwd():
    assert ENV_FILE.is_absolute()
    assert ENV_FILE.name == ".env"
    assert (ENV_FILE.parent / "AGENTS.md").exists()  # repo root
