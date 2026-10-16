"""GET /v1/tags (min), POST /v1/tags (full, tag_create)."""

import uuid
from datetime import datetime, timedelta

import pytest


def tags(api, **q):
    return api.ok("GET", "/v1/tags", query=q)


@pytest.mark.min
def test_tag_appears_after_post(api, tag):
    t = tag()
    p = api.create("x", tags=[t])
    got = tags(api, q=t)
    assert [x["name"] for x in got] == [t]
    created = datetime.fromisoformat(got[0]["created_at"])
    assert abs(created - datetime.fromisoformat(p["created_at"])) < timedelta(minutes=1)
    assert got[0].get("count") is None  # only with with_counts


@pytest.mark.min
def test_q_is_case_insensitive_substring(api, tag):
    t = tag("CaseTag")
    api.create("x", tags=[t])
    assert [x["name"] for x in tags(api, q=t.lower()[3:])] == [t]


@pytest.mark.min
def test_with_counts_by_names(api, tag):
    a, b, unused = tag("a"), tag("b"), tag("unused")
    api.create("1", tags=[a, b])
    last = api.create("2", tags=[a])
    got = {x["name"]: x for x in tags(api, names=[a, b, unused], with_counts="true")}
    assert set(got) == {a, b}
    assert got[a]["count"] == 2 and got[b]["count"] == 1
    assert got[a]["last_posted_at"] == last["created_at"]


@pytest.mark.min
def test_sort_and_paging(api, tag):
    base = tag()
    x, y, z = base + "-x", base + "-y", base + "-z"
    api.create("1", tags=[y])
    api.create("2", tags=[x, y])
    api.create("3", tags=[z])
    api.create("4", tags=[y])
    api.create("5", tags=[z])

    assert [t["name"] for t in tags(api, q=base, sort="name")] == [x, y, z]
    assert [t["name"] for t in tags(api, q=base, sort="count", with_counts="true")] == [y, z, x]
    assert [t["name"] for t in tags(api, q=base, sort="recent")] == [z, x, y]  # newest first use
    assert [t["name"] for t in tags(api, q=base, sort="name", limit=1, offset=1)] == [y]


@pytest.mark.min
def test_count_includes_deleted_posts(api, tag):
    t = tag()
    p = api.create("x", tags=[t])
    api.ok("DELETE", "/v1/posts/" + p["id"], headers={"X-Client-Id": p["_client_id"]})
    assert tags(api, names=t, with_counts="true")[0]["count"] == 1
    assert api.ok("GET", "/v1/posts/count", query={"tags": t}) == 1


@pytest.mark.min
def test_errors(api):
    assert api.get("/v1/tags", query={"names": ["t%d" % i for i in range(201)]}).status == 400
    assert api.get("/v1/tags", query={"sort": "random"}).status == 422
    assert api.get("/v1/tags", query={"limit": "0"}).status == 422
    assert api.get("/v1/tags", query={"offset": "-1"}).status == 422


@pytest.mark.full
@pytest.mark.feature("tag_create")
def test_create_tag(api):
    t = "cf-tag-" + uuid.uuid4().hex[:8]
    r = api.post_json("/v1/tags", {"name": t})
    assert r.status == 200, r
    assert r.json["name"] == t
    assert api.post_json("/v1/tags", {"name": t}).json["name"] == t  # idempotent


@pytest.mark.min
def test_tag_shape(api, tag):
    t = tag()
    api.create("x", tags=[t])
    got = tags(api, names=t, with_counts="true")
    assert len(got) == 1
    assert set(got[0]) >= {"name", "created_at", "count", "last_posted_at"}
    assert "id" not in got[0]  # kssw calls the tag text `name`
