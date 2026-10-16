"""Black-box tests of the kssw admin API (../../openapi/kssw-admin.openapi.yaml, spec §9).

    BASE_URL=http://127.0.0.1:8080 ADMIN_TOKEN=... pytest conformance/admin

Skipped without ADMIN_TOKEN. The server must list `admin` in /v1/meta and
accept that token; like the rest of the conformance suite it must trust
X-Forwarded-For, and over plain http it must allow admin requests (a test
setting, e.g. admin_allow_http for the PHP reference implementation). It writes posts and
toggles maintenance mode: never point it at production.

Markers:
- admin_feature(name, ...): the test uses optional admin operations
  (x-feature); skipped unless capabilities.features lists them.
"""

import os

import pytest

from client import Api, random_ip

TOKEN = os.environ.get("ADMIN_TOKEN") or None


def pytest_configure(config):
    config.addinivalue_line("markers", "admin_feature(*names): optional admin operations (skipped unless capabilities lists them)")


class AdminApi:
    """Api plus the bearer token. Each instance is one client IP."""

    def __init__(self, base, token, ip=None):
        self.api = Api(base)
        self.token = token
        self.ip = ip or random_ip()

    def request(self, method, path, query=None, body=None, token=None, headers=None):
        h = {}
        tok = self.token if token is None else token
        if tok:
            h["Authorization"] = "Bearer " + tok
        h.update(headers or {})
        return self.api.request(method, path, query=query, body=body, headers=h, ip=self.ip)

    def ok(self, method, path, **kw):
        r = self.request(method, path, **kw)
        assert r.status == 200, r
        return r.json

    def delete(self, ids, dry_run=None, query=None):
        body = {"ids": list(ids)}
        if dry_run is not None:
            body["dry_run"] = dry_run
        return self.ok("POST", "/v1/admin/posts/delete", body=body, query=query)

    def restore(self, ids, dry_run=None):
        body = {"ids": list(ids)}
        if dry_run is not None:
            body["dry_run"] = dry_run
        return self.ok("POST", "/v1/admin/posts/restore", body=body)

    def posts(self, **query):
        return self.ok("GET", "/v1/admin/posts", query=query)


@pytest.fixture(autouse=True)
def _need_token():
    if TOKEN is None:
        pytest.skip("ADMIN_TOKEN not set")


@pytest.fixture(scope="session")
def admin_base():
    return os.environ["BASE_URL"]


@pytest.fixture
def admin(admin_base):
    return AdminApi(admin_base, TOKEN)


@pytest.fixture
def capabilities(admin_base):
    if TOKEN is None:
        pytest.skip("ADMIN_TOKEN not set")
    return AdminApi(admin_base, TOKEN).ok("GET", "/v1/admin/capabilities")


@pytest.fixture(autouse=True)
def _skip_by_admin_features(request, admin_base):
    needed = set()
    for m in request.node.iter_markers("admin_feature"):
        needed.update(m.args)
    if not needed or TOKEN is None:
        return
    have = set(AdminApi(admin_base, TOKEN).ok("GET", "/v1/admin/capabilities")["features"])
    if needed - have:
        pytest.skip("server does not list admin feature(s) %s" % ", ".join(sorted(needed - have)))


@pytest.fixture
def maintenance_off(admin_base):
    """Leaves maintenance mode off whatever the test did."""
    yield
    AdminApi(admin_base, TOKEN).ok("PUT", "/v1/admin/maintenance", body={"maintenance": False})
