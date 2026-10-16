"""GET /v1/posts/{id}, /v1/posts/by-ids, `mine`, latest_id, oldest_at."""

import uuid
from datetime import datetime

import pytest

pytestmark = pytest.mark.min


def _dt(s):
    # Python 3.11+ fromisoformat takes any ISO offset.
    return datetime.fromisoformat(s)


def test_get_post(api, tag):
    p = api.create("one", tags=[tag()])
    got = api.ok("GET", "/v1/posts/" + p["id"])
    for k in ("id", "text", "created_at", "tags", "parent_id", "root_id", "status", "author"):
        assert got[k] == p[k], k


def test_get_unknown_404(api):
    r = api.get("/v1/posts/" + str(uuid.uuid4()))
    assert r.status == 404, r
    assert isinstance(r.json["detail"], str)


@pytest.mark.diverges
def test_get_malformed_id_404(api):
    r = api.get("/v1/posts/not-a-uuid")
    assert r.status == 404, r


def test_mine(api, tag):
    p = api.create("mine?", tags=[tag()])
    path = "/v1/posts/" + p["id"]
    assert api.ok("GET", path, headers={"X-Client-Id": p["_client_id"]})["mine"] is True
    assert api.ok("GET", path, headers={"X-Client-Id": str(uuid.uuid4())})["mine"] is False
    assert api.ok("GET", path)["mine"] is None


def test_client_id_never_disclosed(api, tag):
    p = api.create("secret", tags=[tag()])
    got = api.ok("GET", "/v1/posts/" + p["id"], headers={"X-Client-Id": p["_client_id"]})
    assert got.get("client_id") is None
    assert p.get("client_id") is None
    listed = api.ok("GET", "/v1/posts", query={"tags": p["tags"][0]})
    assert all(x.get("client_id") is None for x in listed)


def test_by_ids(api, tag):
    t = tag()
    a = api.create("a", tags=[t])
    b = api.create("b", tags=[t])
    got = api.ok("GET", "/v1/posts/by-ids", query={"ids": [a["id"], b["id"], str(uuid.uuid4())]})
    assert sorted(x["id"] for x in got) == sorted([a["id"], b["id"]])


def test_by_ids_mine(api, tag):
    a = api.create("a", tags=[tag()])
    got = api.ok("GET", "/v1/posts/by-ids", query={"ids": [a["id"]]}, headers={"X-Client-Id": a["_client_id"]})
    assert got[0]["mine"] is True


def test_by_ids_too_many_400(api):
    r = api.get("/v1/posts/by-ids", query={"ids": [str(uuid.uuid4()) for _ in range(101)]})
    assert r.status == 400, r


def test_by_ids_missing_422(api):
    r = api.get("/v1/posts/by-ids")
    assert r.status == 422, r


def test_latest_id_and_oldest_at(api, tag):
    p = api.create("latest", tags=[tag()])
    assert api.ok("GET", "/v1/posts/latest_id") == {"id": p["id"]}
    oldest = api.ok("GET", "/v1/posts/oldest_at")["created_at"]
    assert oldest is not None
    assert _dt(oldest) <= _dt(p["created_at"])
