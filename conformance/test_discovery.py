"""GET /.well-known/kssw (spec §6): optional for operators, checked when present.

The document is fetched from the root of BASE_URL's host. Absent (404) or
not served at all: skipped, since a server on a shared host may be unable
to place it.
"""

import urllib.parse

import pytest

from client import Api

pytestmark = pytest.mark.min


@pytest.fixture(scope="module")
def discovery(api):
    p = urllib.parse.urlsplit(api.base)
    url = urllib.parse.urlunsplit((p.scheme, p.netloc, "/.well-known/kssw", "", ""))
    r = Api(urllib.parse.urlunsplit((p.scheme, p.netloc, "", "", ""))).get("/.well-known/kssw")
    if r.status == 404 or not isinstance(r.json, dict):
        pytest.skip("no /.well-known/kssw on this host (%s)" % r.status)
    return url, r


def test_shape(discovery):
    url, r = discovery
    assert r.status == 200, r
    assert r.headers.get("Content-Type", "").startswith("application/json"), r
    d = r.json
    assert d["protocol"] == "kssw"
    assert isinstance(d["apis"], list) and d["apis"]
    for a in d["apis"]:
        assert isinstance(a["version"], str) and a["version"].isdigit(), a
        assert isinstance(a["base"], str) and a["base"], a
        assert "?" not in a["base"] and "#" not in a["base"], a
        if "name" in a:
            assert isinstance(a["name"], str)


def test_v1_entries_lead_to_kssw_servers(discovery):
    url, r = discovery
    v1 = [a for a in r.json["apis"] if a["version"] == "1"]
    if not v1:
        pytest.skip("no version 1 API advertised")
    for a in v1:
        base = urllib.parse.urljoin(url, a["base"]).rstrip("/")
        m = Api(base).ok("GET", "/v1/meta")
        assert m["protocol"] == "kssw" and m["version"] == "1", (base, m)
