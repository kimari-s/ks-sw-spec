"""Black-box conformance tests for kssw 1 (../spec/kssw.md, ../openapi/).

    BASE_URL=http://127.0.0.1:8080 pytest conformance            # everything the server's profile covers
    BASE_URL=... pytest conformance -m min                       # min class only
    BASE_URL=... pytest conformance -m "min and not diverges"    # what the 6umi.net API (pre-kssw) is expected to pass
    BASE_URL=... ADMIN_TOKEN=... pytest conformance              # plus the admin API (conformance/admin)

BASE_URL is the API base (paths /v1/... are appended to it). The discovery
test fetches /.well-known/kssw from the root of BASE_URL's host and skips
when it is not there.

The server under test must:
- trust X-Forwarded-For (every request here sends a random one, so the per-IP
  post cooldown does not get in the way; tests that need one IP pick it);
- have the post cooldown on (a few seconds or more; ks-sw-api's default 5 s
  is fine): the rate-limit tests post twice in a row and expect a 429.

Tests only look at data they created (unique tags per run), so the server
may already hold posts. They do write to it: never point this at production.

Markers:
- min / full: conformance class of the operation under test. `full` tests
  are skipped when /v1/meta does not report profile "full".
- feature(name, ...): the test uses features (x-feature, optional
  operations). Skipped unless /v1/meta lists every named feature; a listed
  feature runs whatever the profile is.
- diverges: behaviour where kssw deliberately differs from the 6umi.net API
  it derives from (a pre-kssw server).
"""

import os
import uuid

import pytest

from client import Api

RUN = uuid.uuid4().hex[:8]


def pytest_configure(config):
    config.addinivalue_line("markers", "min: conformance class min")
    config.addinivalue_line("markers", "full: conformance class full (skipped unless the server reports profile full)")
    config.addinivalue_line("markers", "feature(*names): optional operations (skipped unless /v1/meta lists them)")
    config.addinivalue_line("markers", "diverges: kssw deliberately differs from the 6umi.net API here")


@pytest.fixture(scope="session")
def api():
    base = os.environ.get("BASE_URL")
    if not base:
        pytest.exit("BASE_URL is not set (e.g. BASE_URL=http://127.0.0.1:8080)", returncode=2)
    return Api(base)


@pytest.fixture(scope="session")
def meta(api):
    r = api.get("/v1/meta")
    return r.json if r.status == 200 and isinstance(r.json, dict) else {}


@pytest.fixture(scope="session")
def profile(meta):
    return meta.get("profile")


@pytest.fixture(scope="session")
def features(meta):
    f = meta.get("features")
    return set(f) if isinstance(f, list) else set()


@pytest.fixture(autouse=True)
def _skip_by_meta(request, profile, features):
    needed = set()
    for m in request.node.iter_markers("feature"):
        needed.update(m.args)
    if needed:
        missing = needed - features
        if missing:
            pytest.skip("server does not list feature(s) %s" % ", ".join(sorted(missing)))
        return
    if request.node.get_closest_marker("full") and profile != "full":
        pytest.skip("server profile is %r, not full" % profile)


@pytest.fixture
def tag():
    """A tag no one else uses: tag("x") -> "cf-<run>-<test>-x"."""
    base = "cf-%s-%s" % (RUN, uuid.uuid4().hex[:6])

    def make(name=""):
        return base + ("-" + name if name else "")

    return make
