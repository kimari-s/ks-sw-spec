"""/v1/meta and its features, presence + active_count, links/by-urls, errors, unknown routes."""

import re
import urllib.parse
import uuid

import pytest

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.+-]+)?$")
# Registered names, or third-party extensions x-<owner>-<name> (spec §8.3).
FEATURE_NAME_RE = re.compile(r"^([a-z][a-z0-9_]*|x-[a-z0-9]+-[a-z0-9_-]+)$")
ERROR_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _probe_presence(api):
    r = api.post_json("/v1/presence", {})
    return r.status == 200 and r.json == {"ok": True}, r


def _probe_active_count(api):
    r = api.get("/v1/active_count")
    return r.status == 200 and isinstance((r.json or {}).get("count"), int), r


def _probe_link_preview(api):
    r = api.get("/v1/links/by-urls", query={"urls": ["https://example.invalid/%s" % uuid.uuid4().hex]})
    return r.status == 200 and isinstance(r.json, list), r


def _probe_tag_create(api):
    t = "cf-probe-" + uuid.uuid4().hex[:8]
    r = api.post_json("/v1/tags", {"name": t})
    return r.status == 200 and (r.json or {}).get("name") == t, r


# Every client-API feature in the registry, with a minimal working call.
FEATURE_PROBES = {
    "presence": _probe_presence,
    "active_count": _probe_active_count,
    "link_preview": _probe_link_preview,
    "tag_create": _probe_tag_create,
}


def is_error(r, status, code=None):
    assert r.status == status, r
    assert r.headers.get("Content-Type", "").startswith("application/json"), r
    assert isinstance(r.json, dict), r
    assert isinstance(r.json.get("detail"), str) and r.json["detail"], r
    assert isinstance(r.json.get("code"), str) and ERROR_CODE_RE.match(r.json["code"]), r
    if code is not None:
        assert r.json["code"] == code, r


@pytest.mark.min
@pytest.mark.diverges
def test_meta(api):
    m = api.ok("GET", "/v1/meta")
    assert m["protocol"] == "kssw"
    assert m["version"] == "1"
    assert m["profile"] in ("min", "full")
    assert isinstance(m["impl"], str) and m["impl"]
    assert isinstance(m["impl_version"], str) and SEMVER_RE.match(m["impl_version"]), m["impl_version"]
    if "impl_url" in m:  # optional; an absolute http(s) URL
        u = urllib.parse.urlsplit(m["impl_url"]) if isinstance(m["impl_url"], str) else None
        assert u and u.scheme.lower() in ("http", "https") and u.netloc, m["impl_url"]
    assert isinstance(m["features"], list)
    assert all(isinstance(f, str) and FEATURE_NAME_RE.match(f) for f in m["features"]), m["features"]
    assert len(set(m["features"])) == len(m["features"])


@pytest.mark.min
@pytest.mark.parametrize("name", sorted(FEATURE_PROBES))
def test_feature_listed_works_unlisted_not_required(api, features, name):
    # A listed feature's operation must work. An unlisted one is not
    # required: whatever it answers (404 for a route the server lacks, or a
    # working endpoint it chose not to advertise) is fine, short of a crash.
    ok, r = FEATURE_PROBES[name](api)
    if name in features:
        assert ok, r
    else:
        assert r.status < 500, r


@pytest.mark.min
@pytest.mark.feature("presence", "active_count")
def test_presence_and_active_count(api):
    r = api.post_json("/v1/presence", {})
    assert r.status == 200, r
    assert r.json == {"ok": True}
    got = api.ok("GET", "/v1/active_count")
    assert isinstance(got["count"], int) and got["count"] >= 1
    assert isinstance(api.ok("GET", "/v1/active_count", query={"minutes": 60})["count"], int)


@pytest.mark.min
@pytest.mark.diverges
@pytest.mark.feature("presence", "active_count")
def test_active_count_counts_distinct_participants(api):
    # Distinct client addresses are distinct participants (the suite sends a
    # new X-Forwarded-For per request). The 6umi.net API caches the count.
    before = api.ok("GET", "/v1/active_count")["count"]
    for _ in range(2):
        api.ok("POST", "/v1/presence", body={})
    assert api.ok("GET", "/v1/active_count")["count"] >= before + 2


@pytest.mark.min
@pytest.mark.feature("presence")
def test_presence_body_optional_and_unknown_fields_ignored(api):
    assert api.request("POST", "/v1/presence").status == 200
    body = {"session_id": str(uuid.uuid4()), "client_id": str(uuid.uuid4()), "x-anything": [1, 2]}
    assert api.post_json("/v1/presence", body).status == 200


@pytest.mark.min
@pytest.mark.feature("presence")
@pytest.mark.parametrize("body", [b"[]", b"not json", b'"x"'], ids=["array", "not-json", "string"])
def test_presence_body_not_object_422(api, body):
    is_error(api.post_json("/v1/presence", body), 422, "invalid")


@pytest.mark.min
@pytest.mark.feature("active_count")
@pytest.mark.parametrize("minutes", ["0", "61", "x"])
def test_active_count_invalid_422(api, minutes):
    is_error(api.get("/v1/active_count", query={"minutes": minutes}), 422, "invalid")


@pytest.mark.full
@pytest.mark.feature("link_preview")
def test_links_by_urls_unknown_is_empty(api):
    url = "https://example.invalid/%s" % uuid.uuid4().hex
    assert api.ok("GET", "/v1/links/by-urls", query={"urls": [url]}) == []
    assert api.ok("GET", "/v1/links/by-urls") == []


@pytest.mark.min
@pytest.mark.diverges
def test_unknown_route_404(api):
    is_error(api.get("/v1/no-such-thing"), 404, "not_found")


@pytest.mark.min
@pytest.mark.diverges
def test_error_body_detail_and_code(api):
    is_error(api.get("/v1/posts/" + str(uuid.uuid4())), 404, "post_not_found")
    is_error(api.get("/v1/posts", query={"page": "x"}), 422, "invalid")
    is_error(api.get("/v1/posts/search"), 400, "bad_request")


@pytest.mark.min
@pytest.mark.diverges
def test_method_not_allowed_405(api):
    is_error(api.request("PUT", "/v1/posts"), 405, "method_not_allowed")

