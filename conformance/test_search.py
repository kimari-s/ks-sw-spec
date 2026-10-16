"""GET /v1/posts/search and /v1/posts/search/count."""

import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.min


def search(api, **q):
    return api.ok("GET", "/v1/posts/search", query=q)


def search_count(api, **q):
    n = api.ok("GET", "/v1/posts/search/count", query=q)
    assert isinstance(n, int)
    return n


def ids(posts):
    return [p["id"] for p in posts]


def test_terms_and_or(api, tag):
    t = tag()
    w1, w2 = "alpha" + uuid.uuid4().hex[:6], "beta" + uuid.uuid4().hex[:6]
    both = api.create("%s and %s" % (w1, w2), tags=[t])
    one = api.create("only %s" % w1, tags=[t])
    two = api.create("only %s" % w2, tags=[t])

    assert ids(search(api, q="%s %s" % (w1, w2))) == [both["id"]]
    assert ids(search(api, q="%s　%s" % (w1, w2))) == [both["id"]]  # full-width space splits too
    assert ids(search(api, q="%s %s" % (w1, w2), q_op="or")) == [two["id"], one["id"], both["id"]]
    assert search_count(api, q="%s %s" % (w1, w2), q_op="or") == 3


def test_case_insensitive_ascii(api, tag):
    w = "MiXeD" + uuid.uuid4().hex[:6]
    p = api.create("say %s here" % w, tags=[tag()])
    assert ids(search(api, q=w.lower())) == [p["id"]]
    assert ids(search(api, q=w.upper())) == [p["id"]]


def test_like_wildcards_are_literal(api, tag):
    w = uuid.uuid4().hex[:8]
    p = api.create("100%_" + w, tags=[tag()])
    api.create("100ab" + w, tags=[tag()])
    assert ids(search(api, q="100%_" + w)) == [p["id"]]


def test_tags_and_author_and_exclude(api, tag):
    t, ex = tag(), tag("ex")
    name = "s-" + uuid.uuid4().hex[:8]
    a = api.create("one", tags=[t], author=name)
    b = api.create("two", tags=[t, ex])
    assert ids(search(api, tags=t)) == [b["id"], a["id"]]
    assert ids(search(api, tags=t, exclude_tags=ex)) == [a["id"]]
    assert ids(search(api, author=name)) == [a["id"]]


def test_deleted_left_out(api, tag):
    t = tag()
    keep = api.create("keep", tags=[t])
    gone = api.create("gone", tags=[t])
    api.ok("DELETE", "/v1/posts/" + gone["id"], headers={"X-Client-Id": gone["_client_id"]})
    assert ids(search(api, tags=t)) == [keep["id"]]
    assert search_count(api, tags=t) == 1


def test_since_until(api, tag):
    t = tag()
    a = api.create("a", tags=[t])
    time.sleep(1.1)
    b = api.create("b", tags=[t])
    tb = datetime.fromisoformat(b["created_at"])
    # Whole seconds with an explicit offset, the way kuzuha-ui sends them.
    cut = (tb - timedelta(seconds=1)).replace(microsecond=0)
    if cut <= datetime.fromisoformat(a["created_at"]):
        cut = cut + timedelta(seconds=1)
    since = cut.isoformat()
    assert ids(search(api, tags=t, since=since)) == [b["id"]]
    assert ids(search(api, tags=t, until=since)) == [a["id"]]
    # Same instant in UTC.
    assert ids(search(api, tags=t, since=cut.astimezone(timezone.utc).isoformat())) == [b["id"]]
    z = cut.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert ids(search(api, tags=t, since=z)) == [b["id"]]


def test_since_date_only(api, tag):
    t = tag()
    p = api.create("dated", tags=[t])
    day = p["created_at"][:10]
    assert p["id"] in ids(search(api, tags=t, since=day))
    assert p["id"] in ids(search(api, tags=t, since=day + "T00:00:00" + p["created_at"][-6:]))


def test_paging(api, tag):
    t = tag()
    made = [api.create("p%d" % i, tags=[t]) for i in range(3)]
    assert ids(search(api, tags=t, page=2, page_size=2)) == [made[0]["id"]]


def test_needs_a_filter_400(api):
    assert api.get("/v1/posts/search").status == 400
    assert api.get("/v1/posts/search", query={"q": "   "}).status == 400
    assert api.get("/v1/posts/search/count").status == 400


@pytest.mark.parametrize(
    "q",
    [{"q": "x", "page_size": "51"}, {"q": "x", "page_size": "0"}, {"q": "x", "page": "0"}, {"since": "yesterday"}],
    ids=["page_size-51", "page_size-0", "page-0", "bad-since"],
)
def test_invalid_422(api, q):
    r = api.get("/v1/posts/search", query=q)
    assert r.status == 422, r
