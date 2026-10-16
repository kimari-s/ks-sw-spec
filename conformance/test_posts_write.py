"""POST /v1/posts, DELETE /v1/posts/{id}."""

import re
import uuid

import pytest

pytestmark = pytest.mark.min

TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?[+-]\d{2}:\d{2}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def test_create_root_post_shape(api, tag):
    t = tag()
    p = api.create("  hello world  ", tags=[t, t + "-b"], author="nanashi")
    assert UUID_RE.match(p["id"])
    assert p["text"] == "hello world"  # trimmed on output
    assert TIME_RE.match(p["created_at"]), p["created_at"]
    assert set(p["tags"]) >= {t, t + "-b"}
    assert p["tags"] == sorted(p["tags"])
    assert p["parent_id"] is None
    assert p["root_id"] == p["id"]
    assert p["status"] == "active"
    assert p["author"] == "nanashi"
    assert p["mine"] is True  # the writer, identified by the client id it posted with


@pytest.mark.diverges
def test_create_stores_exactly_what_was_sent(api, tag):
    # No #hashtag extraction, no author-as-tag.
    t = tag()
    p = api.create("text with #inline tag", tags=[t, " %s " % t, ""], author="poster")
    assert p["tags"] == [t]
    # Fixed width: microseconds always present.
    assert len(p["created_at"]) == len("2026-01-01T00:00:00.000000+09:00")


def test_create_without_client_id_mine_is_null(api, tag):
    r = api.post_json("/v1/posts", {"text": "anon", "tags": [tag()]})
    assert r.status == 200, r
    assert r.json["mine"] is None


def test_reply_root_id(api, tag):
    t = tag()
    root = api.create("root", tags=[t])
    child = api.create("child", tags=[t], parent_id=root["id"])
    grandchild = api.create("grandchild", tags=[t], parent_id=child["id"])
    assert child["parent_id"] == root["id"] and child["root_id"] == root["id"]
    assert grandchild["parent_id"] == child["id"] and grandchild["root_id"] == root["id"]


def test_author_trimmed_and_blank_is_null(api, tag):
    assert api.create("a", tags=[tag()], author="  name  ")["author"] == "name"
    assert api.create("b", tags=[tag()], author="   ")["author"] is None


def test_text_at_limit_ok(api, tag):
    p = api.create("あ" * 5000, tags=[tag()])
    assert len(p["text"]) == 5000


@pytest.mark.parametrize(
    "body",
    [
        {"text": "x" * 5001},
        {"text": "あ" * 5001},
        {"text": ""},
        {"text": " \n\t "},
        {},
        {"text": 123},
        {"text": "ok", "author": "x" * 41},
        {"text": "ok", "tags": "not-a-list"},
        {"text": "ok", "parent_id": "not-a-uuid"},
    ],
    ids=["too-long", "too-long-multibyte", "empty", "blank", "missing", "not-string", "author-too-long", "tags-not-list", "bad-parent"],
)
def test_create_invalid_422(api, body):
    body = dict(body, client_id=str(uuid.uuid4()))
    r = api.post_json("/v1/posts", body)
    assert r.status == 422, r
    assert "detail" in r.json


@pytest.mark.diverges
def test_create_invalid_detail_is_string(api):
    r = api.post_json("/v1/posts", {"text": "x" * 5001})
    assert r.status == 422
    assert isinstance(r.json["detail"], str)


@pytest.mark.diverges
def test_create_unknown_parent_422(api):
    r = api.post_json("/v1/posts", {"text": "x", "parent_id": str(uuid.uuid4()), "client_id": str(uuid.uuid4())})
    assert r.status == 422, r


@pytest.mark.diverges
def test_create_not_json_422(api):
    r = api.post_json("/v1/posts", b"not json")
    assert r.status == 422, r


def test_rate_limit_per_client_id(api, tag):
    cid = str(uuid.uuid4())
    api.create("first", tags=[tag()], client_id=cid)
    r = api.post_json("/v1/posts", {"text": "second", "tags": [tag()], "client_id": cid})  # new IP, same client
    assert r.status == 429, r
    assert isinstance(r.json["detail"], str)


@pytest.mark.diverges
def test_rate_limit_code(api, tag):
    cid = str(uuid.uuid4())
    api.create("first", tags=[tag()], client_id=cid)
    r = api.post_json("/v1/posts", {"text": "second", "tags": [tag()], "client_id": cid})
    assert r.status == 429 and r.json["code"] == "rate_limited", r


@pytest.mark.diverges
def test_rate_limit_per_ip(api, tag):
    ip = "198.18.250.%d" % (uuid.uuid4().int % 250 + 1)
    api.create("first", tags=[tag()], ip=ip)
    r = api.post_json("/v1/posts", {"text": "second", "client_id": str(uuid.uuid4())}, ip=ip)  # same IP, new client
    assert r.status == 429, r
    assert int(r.headers["Retry-After"]) >= 1


def test_delete_own_post(api, tag):
    p = api.create("to delete", tags=[tag()], author="someone")
    cid = p["_client_id"]

    r = api.delete("/v1/posts/" + p["id"], headers={"X-Client-Id": str(uuid.uuid4())})
    assert r.status == 403, r
    r = api.delete("/v1/posts/" + p["id"])
    assert r.status == 403, r
    assert r.json.get("code") in (None, "forbidden"), r  # None: a pre-kssw server

    r = api.delete("/v1/posts/" + p["id"], headers={"X-Client-Id": cid})
    assert r.status == 200, r
    assert r.json == {"ok": True, "status": "deleted"}

    got = api.ok("GET", "/v1/posts/" + p["id"])
    assert got["status"] == "deleted"
    assert got["tags"] == []
    assert got["author"] is None

    # Already deleted.
    r = api.delete("/v1/posts/" + p["id"], headers={"X-Client-Id": cid})
    assert r.status == 403, r


@pytest.mark.diverges
def test_deleted_post_text_is_empty(api, tag):
    p = api.create("gone", tags=[tag()])
    api.ok("DELETE", "/v1/posts/" + p["id"], headers={"X-Client-Id": p["_client_id"]})
    assert api.ok("GET", "/v1/posts/" + p["id"])["text"] == ""


def test_delete_post_without_client_id_forbidden(api, tag):
    r = api.post_json("/v1/posts", {"text": "anon", "tags": [tag()]})
    assert r.status == 200
    r = api.delete("/v1/posts/" + r.json["id"], headers={"X-Client-Id": str(uuid.uuid4())})
    assert r.status == 403


def test_delete_unknown_404(api):
    r = api.delete("/v1/posts/" + str(uuid.uuid4()), headers={"X-Client-Id": str(uuid.uuid4())})
    assert r.status == 404, r
    assert "detail" in r.json
