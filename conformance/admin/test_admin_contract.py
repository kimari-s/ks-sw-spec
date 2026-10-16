"""The kssw admin API: auth, errors, capabilities, posts, maintenance, backup, log."""

import hashlib
import uuid

import pytest

REQUIRED_OPS = {"getCapabilities", "listPosts", "getPost", "deletePosts", "restorePosts", "listLog"}


def tok():
    return "adm-" + uuid.uuid4().hex[:12]


def is_error(r, status, code=None):
    assert r.status == status, r
    assert isinstance(r.json, dict), r
    assert isinstance(r.json.get("detail"), str) and r.json["detail"], r
    assert isinstance(r.json.get("code"), str) and r.json["code"], r
    if code is not None:
        assert r.json["code"] == code, r


# ---- discovery, auth, errors ------------------------------------------------


def test_meta_lists_admin(api):
    assert "admin" in api.ok("GET", "/v1/meta")["features"]


def test_capabilities(api, capabilities):
    c = capabilities
    assert c["version"] == "1"
    assert isinstance(c["impl"], str) and isinstance(c["impl_version"], str)
    meta = api.ok("GET", "/v1/meta")
    assert c["impl"] == meta["impl"] and c["impl_version"] == meta["impl_version"]
    assert REQUIRED_OPS <= set(c["operations"])
    assert all(isinstance(f, str) for f in c["features"])
    if "maintenance" in c["features"]:
        assert {"getMaintenance", "setMaintenance"} <= set(c["operations"])
    if "backup" in c["features"]:
        assert "getBackup" in c["operations"]
    assert c["limits"]["page_size_max"] >= 50 and c["limits"]["ids_max"] >= 1


@pytest.mark.parametrize("path", ["/v1/admin/capabilities", "/v1/admin/posts", "/v1/admin/log"])
def test_needs_token(admin, path):
    r = admin.request("GET", path, token="")
    is_error(r, 401, "unauthorized")
    assert r.headers.get("WWW-Authenticate", "").lower().startswith("bearer")
    is_error(admin.request("GET", path, token="wrong-" + uuid.uuid4().hex), 401, "unauthorized")
    is_error(admin.request("GET", path, token="", headers={"Authorization": "Basic YWRtaW46YWRtaW4="}), 401, "unauthorized")


def test_mutations_need_token(api, admin):
    p = api.create("guarded", tags=[tok()])
    is_error(admin.request("POST", "/v1/admin/posts/delete", body={"ids": [p["id"]]}, token=""), 401, "unauthorized")
    assert api.ok("GET", "/v1/posts/" + p["id"])["status"] == "active"


def test_unknown_path_and_method(admin):
    is_error(admin.request("GET", "/v1/admin/no-such-thing"), 404)
    is_error(admin.request("DELETE", "/v1/admin/posts"), 405, "method_not_allowed")


@pytest.mark.parametrize("query", [{"page_size": "0"}, {"page": "0"}, {"status": "gone"}, {"since": "yesterday"}, {"page_size": "100000"}])
def test_bad_list_params(admin, query):
    is_error(admin.request("GET", "/v1/admin/posts", query=query), 422, "invalid")


@pytest.mark.parametrize("body", [{}, {"ids": []}, {"ids": "x"}, {"ids": [1]}, {"ids": ["a"], "dry_run": "yes"}])
def test_bad_ids_body(admin, body):
    is_error(admin.request("POST", "/v1/admin/posts/delete", body=body), 422, "invalid")


def test_too_many_ids(admin, capabilities):
    n = capabilities["limits"]["ids_max"] + 1
    ids = [str(uuid.uuid4()) for _ in range(n)]
    is_error(admin.request("POST", "/v1/admin/posts/delete", body={"ids": ids}), 422, "invalid")


# ---- posts ------------------------------------------------------------------


def test_list_newest_first_with_fields(api, admin):
    t = tok()
    a = api.create("first " + t, tags=[t], author="adm-a")
    b = api.create("second " + t, tags=[t, t + "-x"])
    r = admin.posts(tags=t)
    assert r["total"] == 2 and r["page"] == 1 and r["has_more"] is False
    assert [p["id"] for p in r["items"]] == [b["id"], a["id"]]
    pa = r["items"][1]
    assert set(pa) >= {"id", "created_at", "status", "author", "tags", "text", "parent_id", "root_id"}
    assert pa["author"] == "adm-a" and pa["text"] == "first " + t and pa["tags"] == [t]
    assert pa["status"] == "active" and pa["parent_id"] is None and pa["root_id"] == a["id"]
    assert pa["created_at"] == a["created_at"]


def test_list_filters(api, admin):
    t = tok()
    a = api.create("Apple pie " + t, tags=[t], author="who-" + t)
    b = api.create("banana split " + t, tags=[t + "-b"], author="other-" + t)
    c = api.create("apple banana " + t, tags=[t], parent_id=a["id"])
    ids = lambda r: {p["id"] for p in r["items"]}  # noqa: E731
    assert ids(admin.posts(q="apple " + t)) == {a["id"], c["id"]}  # every term, ASCII case-insensitive
    assert ids(admin.posts(q="banana " + t)) == {b["id"], c["id"]}
    assert ids(admin.posts(author="who-" + t)) == {a["id"]}
    assert a["id"] not in ids(admin.posts(author="who-"))  # exact, not a prefix
    assert ids(admin.posts(tags=[t, t + "-b"])) == {a["id"], b["id"], c["id"]}  # any of the tags
    assert ids(admin.posts(tags=t, root_id=a["id"])) == {a["id"], c["id"]}
    assert ids(admin.posts(tags=t, since="2999-01-01")) == set()
    assert ids(admin.posts(tags=t, until="2000-01-01")) == set()
    assert ids(admin.posts(tags=t, since=a["created_at"])) == {a["id"], c["id"]}
    assert ids(admin.posts(tags=t, until=c["created_at"])) == {a["id"]}


def test_pagination(api, admin):
    t = tok()
    made = [api.create("page %s %d" % (t, i), tags=[t])["id"] for i in range(5)]
    seen = []
    page = 1
    while True:
        r = admin.posts(tags=t, page=str(page), page_size="2")
        assert r["total"] == 5 and r["page_size"] == 2 and len(r["items"]) <= 2
        seen += [p["id"] for p in r["items"]]
        if not r["has_more"]:
            break
        page += 1
    assert page == 3 and seen == made[::-1]


def test_delete_dry_run_then_real_then_again(api, admin, capabilities):
    t = tok()
    p = api.create("to delete " + t, tags=[t], author="adm")
    r = admin.delete([p["id"]], dry_run=True)
    assert r["dry_run"] is True and r["changed"] == 1
    assert r["results"] == [{"id": p["id"], "result": "changed", "status_before": "active", "status_after": "deleted"}]
    assert api.ok("GET", "/v1/posts/" + p["id"])["status"] == "active"  # nothing changed
    r = admin.delete([p["id"]], query={"dry_run": "true"})  # query form
    assert r["dry_run"] is True and api.ok("GET", "/v1/posts/" + p["id"])["status"] == "active"

    r = admin.delete([p["id"]])
    assert r["dry_run"] is False and r["changed"] == 1 and r["results"][0]["result"] == "changed"
    pub = api.ok("GET", "/v1/posts/" + p["id"])
    assert pub["status"] == "deleted" and pub["text"] == "" and pub["tags"] == [] and pub["author"] is None
    # The admin still sees everything.
    got = admin.ok("GET", "/v1/admin/posts/" + p["id"])
    assert got["status"] == "deleted" and got["text"] == "to delete " + t and got["tags"] == [t] and got["author"] == "adm"
    assert [x["id"] for x in admin.posts(tags=t, status="deleted")["items"]] == [p["id"]]
    assert admin.posts(tags=t, status="active")["items"] == []

    r = admin.delete([p["id"]])  # idempotent
    assert r["changed"] == 0 and r["results"][0]["result"] == "unchanged" and r["results"][0]["status_before"] == "deleted"


def test_restore(api, admin):
    t = tok()
    p = api.create("to restore " + t, tags=[t], author="adm")
    admin.delete([p["id"]])
    r = admin.restore([p["id"]], dry_run=True)
    assert r["changed"] == 1 and api.ok("GET", "/v1/posts/" + p["id"])["status"] == "deleted"
    r = admin.restore([p["id"]])
    assert r["results"] == [{"id": p["id"], "result": "changed", "status_before": "deleted", "status_after": "active"}]
    pub = api.ok("GET", "/v1/posts/" + p["id"])
    assert pub["status"] == "active" and pub["text"] == "to restore " + t and pub["tags"] == [t] and pub["author"] == "adm"
    assert admin.restore([p["id"]])["results"][0]["result"] == "unchanged"


def test_restore_owner_deleted(api, admin):
    p = api.create("owner deleted", tags=[tok()])
    assert api.delete("/v1/posts/" + p["id"], headers={"X-Client-Id": p["_client_id"]}).status == 200
    assert admin.restore([p["id"]])["results"][0]["result"] == "changed"
    assert api.ok("GET", "/v1/posts/" + p["id"])["status"] == "active"


def test_bulk_mixed_ids(api, admin):
    t = tok()
    a = api.create("bulk a " + t, tags=[t])
    b = api.create("bulk b " + t, tags=[t])
    missing = str(uuid.uuid4())
    r = admin.delete([a["id"], b["id"].upper(), missing, "not-an-id", a["id"]])
    by = {x["id"]: x["result"] for x in r["results"]}
    assert by[a["id"]] == "changed" and by[b["id"]] == "changed"
    assert by[missing] == "not_found" and by["not-an-id"] == "invalid_id"
    assert r["changed"] == 2
    assert len([x for x in r["results"] if x["id"] == a["id"]]) == 1  # duplicates dropped


def test_get_post_not_found(admin):
    is_error(admin.request("GET", "/v1/admin/posts/" + str(uuid.uuid4())), 404, "post_not_found")
    is_error(admin.request("GET", "/v1/admin/posts/not-a-uuid"), 404, "post_not_found")


# ---- maintenance --------------------------------------------------------------


@pytest.mark.admin_feature("maintenance")
def test_maintenance(api, admin, maintenance_off):
    t = tok()
    p = api.create("before maintenance " + t, tags=[t])
    m = admin.ok("GET", "/v1/admin/maintenance")
    assert m["maintenance"] is False and m["since"] is None

    r = admin.ok("PUT", "/v1/admin/maintenance", body={"maintenance": True, "dry_run": True})
    assert r["dry_run"] is True and r["changed"] is True and r["maintenance"] is True
    assert admin.ok("GET", "/v1/admin/maintenance")["maintenance"] is False
    assert api.post_json("/v1/posts", {"text": "still open", "tags": [t]}).status == 200

    r = admin.ok("PUT", "/v1/admin/maintenance", body={"maintenance": True})
    assert r["changed"] is True and r["maintenance"] is True and isinstance(r["since"], str)
    assert admin.ok("PUT", "/v1/admin/maintenance", body={"maintenance": True})["changed"] is False  # idempotent
    w = api.post_json("/v1/posts", {"text": "x", "tags": [t]})
    assert w.status == 503 and w.json == {"detail": "maintenance", "code": "maintenance"}
    # The admin API keeps working, writes included.
    assert admin.delete([p["id"]])["changed"] == 1
    assert admin.restore([p["id"]])["changed"] == 1
    assert admin.posts(tags=t)["total"] >= 1

    r = admin.ok("PUT", "/v1/admin/maintenance", body={"maintenance": False})
    assert r["changed"] is True and r["maintenance"] is False
    assert admin.ok("PUT", "/v1/admin/maintenance", body={"maintenance": False})["changed"] is False
    api.create("after maintenance", tags=[t])


@pytest.mark.admin_feature("maintenance")
def test_maintenance_bad_body(admin):
    for body in ({}, {"maintenance": "on"}, {"maintenance": 1}):
        is_error(admin.request("PUT", "/v1/admin/maintenance", body=body), 422, "invalid")


# ---- backup -------------------------------------------------------------------


@pytest.mark.admin_feature("backup")
def test_backup(api, admin):
    api.create("in the backup", tags=[tok()])
    r = admin.request("GET", "/v1/admin/backup")
    assert r.status == 200, r
    assert r.headers["Content-Type"].startswith("application/octet-stream")
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert len(r.raw) > 0
    if r.headers.get("Content-Length"):
        assert int(r.headers["Content-Length"]) == len(r.raw)
    if r.headers.get("X-Content-SHA256"):
        assert r.headers["X-Content-SHA256"].lower() == hashlib.sha256(r.raw).hexdigest()


@pytest.mark.admin_feature("backup", "maintenance")
def test_backup_during_maintenance(admin, maintenance_off):
    admin.ok("PUT", "/v1/admin/maintenance", body={"maintenance": True})
    assert admin.request("GET", "/v1/admin/backup").status == 200


# ---- log ----------------------------------------------------------------------


def test_log_records_mutations(api, admin):
    p = api.create("logged", tags=[tok()])
    admin.delete([p["id"]], dry_run=True)
    admin.delete([p["id"]])
    admin.restore([p["id"]])
    r = admin.ok("GET", "/v1/admin/log", query={"page_size": "50"})
    assert set(r) >= {"items", "page", "page_size", "total", "has_more"}
    mine = [e for e in r["items"] if e["target"] == p["id"]]
    assert [(e["action"], e["dry_run"], e["result"]) for e in mine] == [
        ("restore", False, "changed"),
        ("delete", False, "changed"),
        ("delete", True, "changed"),
    ]
    for e in mine:
        assert set(e) >= {"id", "created_at", "action", "target", "dry_run", "result"}
        assert isinstance(e["created_at"], str) and isinstance(e["id"], int)
        assert "at" not in e
    ids = [e["id"] for e in r["items"]]
    assert ids == sorted(ids, reverse=True)  # newest first
    only = admin.ok("GET", "/v1/admin/log", query={"action": "restore"})["items"]
    assert only and all(e["action"] == "restore" for e in only)
