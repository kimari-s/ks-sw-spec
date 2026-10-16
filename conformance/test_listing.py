"""GET /v1/posts and /v1/posts/count: filters, trees, order, paging."""

import uuid

import pytest

pytestmark = pytest.mark.min


def ids(posts):
    return [p["id"] for p in posts]


def listing(api, **q):
    return api.ok("GET", "/v1/posts", query=q)


def count(api, **q):
    n = api.ok("GET", "/v1/posts/count", query=q)
    assert isinstance(n, int)
    return n


def test_newest_first_and_paging(api, tag):
    t = tag()
    made = [api.create("p%d" % i, tags=[t]) for i in range(5)]
    newest_first = ids(reversed(made))
    assert ids(listing(api, tags=t)) == newest_first
    assert ids(listing(api, tags=t, page=1, page_size=2)) == newest_first[:2]
    assert ids(listing(api, tags=t, page=2, page_size=2)) == newest_first[2:4]
    assert ids(listing(api, tags=t, page=3, page_size=2)) == newest_first[4:]
    assert listing(api, tags=t, page=4, page_size=2) == []
    assert count(api, tags=t) == 5


def test_default_page_size_20(api, tag):
    t = tag()
    for i in range(21):
        api.create("p%d" % i, tags=[t])
    assert len(listing(api, tags=t)) == 20


def test_tags_op_and_exclude(api, tag):
    a, b, c = tag("a"), tag("b"), tag("c")
    ab = api.create("ab", tags=[a, b])
    a_only = api.create("a", tags=[a])
    b_only = api.create("b", tags=[b])
    abc = api.create("abc", tags=[a, b, c])

    assert set(ids(listing(api, tags=[a, b]))) == {ab["id"], a_only["id"], b_only["id"], abc["id"]}
    assert set(ids(listing(api, tags=[a, b], tags_op="and"))) == {ab["id"], abc["id"]}
    assert count(api, tags=[a, b], tags_op="and") == 2

    # exclude_op or (default): drop posts carrying any of the excluded tags.
    assert set(ids(listing(api, tags=a, exclude_tags=[b, c]))) == {a_only["id"]}
    # exclude_op and: drop only posts carrying all of them.
    assert set(ids(listing(api, tags=a, exclude_tags=[b, c], exclude_op="and"))) == {ab["id"], a_only["id"]}
    assert count(api, tags=a, exclude_tags=[b, c], exclude_op="and") == 2


def test_author_filter(api, tag):
    t = tag()
    name = "author-" + uuid.uuid4().hex[:8]
    mine = api.create("by name", tags=[t], author=name)
    api.create("other", tags=[t], author=name + "x")
    api.create("anon", tags=[t])
    assert ids(listing(api, author=name)) == [mine["id"]]
    assert ids(listing(api, author="  %s " % name)) == [mine["id"]]
    assert count(api, author=name) == 1


def test_root_id_thread_order(api, tag):
    t = tag()
    root = api.create("root", tags=[t])
    c1 = api.create("c1", tags=[t], parent_id=root["id"])
    c2 = api.create("c2", tags=[t], parent_id=c1["id"])
    c3 = api.create("c3", tags=[tag("other")], parent_id=root["id"])
    assert ids(listing(api, root_id=root["id"])) == [root["id"], c1["id"], c2["id"], c3["id"]]
    assert count(api, root_id=root["id"]) == 4
    # root_id ignores tag filters but still honours exclude_tags.
    assert ids(listing(api, root_id=root["id"], tags=tag("nothing"))) == ids(listing(api, root_id=root["id"]))
    assert ids(listing(api, root_id=root["id"], exclude_tags=c3["tags"])) == [root["id"], c1["id"], c2["id"]]


def test_root_ids(api, tag):
    t = tag()
    r1 = api.create("r1", tags=[t])
    r2 = api.create("r2", tags=[t])
    c = api.create("c", tags=[t], parent_id=r1["id"])
    got = listing(api, root_ids=[r1["id"], r2["id"]])
    assert ids(got) == [r1["id"], r2["id"], c["id"]]  # oldest first


def test_root_ids_errors(api):
    rid = str(uuid.uuid4())
    r = api.get("/v1/posts", query={"root_ids": [str(uuid.uuid4()) for _ in range(51)]})
    assert r.status == 400, r
    r = api.get("/v1/posts", query={"root_ids": [rid], "root_id": rid})
    assert r.status == 400, r
    r = api.get("/v1/posts", query={"root_ids": [rid], "roots_only": "true"})
    assert r.status == 400, r


def test_roots_only_bumped_by_reply(api, tag):
    t = tag()
    old = api.create("old thread", tags=[t])
    new = api.create("new thread", tags=[t])
    assert ids(listing(api, tags=t, roots_only="true")) == [new["id"], old["id"]]
    api.create("reply", tags=[t], parent_id=old["id"])
    assert ids(listing(api, tags=t, roots_only="true")) == [old["id"], new["id"]]
    assert count(api, tags=t, roots_only="true") == 2


def test_include_tree(api, tag):
    t, hit, ex = tag(), tag("hit"), tag("ex")
    root = api.create("root", tags=[t])
    c1 = api.create("c1", tags=[t, hit], parent_id=root["id"])
    c2 = api.create("c2", tags=[t], parent_id=root["id"])
    c3 = api.create("c3", tags=[t, ex], parent_id=c1["id"])
    other = api.create("unrelated root", tags=[t])

    got = listing(api, tags=hit, include_tree="true")
    assert ids(got) == [c3["id"], c2["id"], c1["id"], root["id"]]  # newest first
    assert other["id"] not in ids(got)
    assert count(api, tags=hit, include_tree="true") == 4

    # Excluded posts drop out, the rest of the tree stays.
    got = listing(api, tags=hit, include_tree="true", exclude_tags=ex)
    assert ids(got) == [c2["id"], c1["id"], root["id"]]

    # A tree whose only match is excluded is not picked.
    assert listing(api, tags=ex, include_tree="true", exclude_tags=ex) == []


def test_include_tree_by_author(api, tag):
    t = tag()
    name = "tree-" + uuid.uuid4().hex[:8]
    root = api.create("root", tags=[t])
    reply = api.create("reply", tags=[t], parent_id=root["id"], author=name)
    assert ids(listing(api, author=name, include_tree="true")) == [reply["id"], root["id"]]


def test_deleted_posts_stay_in_lists(api, tag):
    t = tag()
    p = api.create("will be deleted", tags=[t])
    api.ok("DELETE", "/v1/posts/" + p["id"], headers={"X-Client-Id": p["_client_id"]})
    got = listing(api, root_id=p["id"])
    assert ids(got) == [p["id"]]
    assert got[0]["status"] == "deleted"


def test_mine_in_list(api, tag):
    t = tag()
    p = api.create("x", tags=[t])
    got = api.ok("GET", "/v1/posts", query={"tags": t}, headers={"X-Client-Id": p["_client_id"]})
    assert got[0]["mine"] is True


@pytest.mark.parametrize(
    "q",
    [{"page": "x"}, {"page_size": "abc"}, {"tags_op": "xor"}, {"roots_only": "maybe"}],
    ids=["page", "page_size", "tags_op", "roots_only"],
)
def test_list_invalid_422(api, q):
    r = api.get("/v1/posts", query=q)
    assert r.status == 422, r


@pytest.mark.diverges
@pytest.mark.parametrize("q", [{"page": "0"}, {"page_size": "0"}, {"page_size": "10001"}])
def test_list_out_of_range_422(api, q):
    r = api.get("/v1/posts", query=q)
    assert r.status == 422, r


def test_large_page_size_allowed(api, tag):
    # kuzuha-ui asks for whole threads with page_size=10000.
    root = api.create("root", tags=[tag()])
    assert ids(listing(api, root_id=root["id"], page_size=10000)) == [root["id"]]
