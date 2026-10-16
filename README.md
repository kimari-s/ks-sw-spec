# ks-sw-spec

The specification of **kssw**, an HTTP API between a kuzuha-style BBS UI
and its server.

- **Protocol version:** 1 (Draft)
- **Release:** 0.1.0-alpha.1 ([CHANGELOG](CHANGELOG.md))

| Path | What |
|---|---|
| [`spec/kssw.md`](spec/kssw.md) | The specification (normative prose, RFC 2119 keywords) |
| [`openapi/kssw.openapi.yaml`](openapi/kssw.openapi.yaml) | The client API in OpenAPI 3.0 (`x-tier`, `x-feature` per operation) |
| [`openapi/kssw-admin.openapi.yaml`](openapi/kssw-admin.openapi.yaml) | The admin API (feature `admin`) |
| [`conformance/`](conformance/) | Black-box conformance suite (pytest, stdlib HTTP client) |

Where the prose and the OpenAPI files disagree, the prose wins.

## In short

- A server has an **API base** (e.g. `https://example.com/bbs/api`).
  `GET <base>/v1/meta` says `{"protocol": "kssw", "version": "1", "profile": "min", …, "features": […]}`.
- Optionally, `GET https://<host>/.well-known/kssw` points to the API base.
- Two conformance classes, `min` ⊂ `full`, and optional **features**
  (`presence`, `active_count`, `link_preview`, `tag_create`, `admin`, …);
  third-party extensions are named `x-<owner>-<name>`.
- Out of scope: federation (e.g. ActivityPub; a separate layer), web
  analytics, accounts, and the storage schema.

## Implementations

| Repository | Role |
|---|---|
| [ks-sw-api](https://github.com/kimari-s/ks-sw-api) | Server: the PHP reference implementation (`min` + `admin`) |
| [ks-kuzuha-ui](https://github.com/kimari-s/ks-kuzuha-ui) | Client: a kuzuha-style board UI (React, static) |
| [ks-kuzuha-alternative](https://github.com/kimari-s/ks-kuzuha-alternative) | Distribution: server + UI in one zip for shared hosting |

kssw derives from the API of [6umi.net](https://6umi.net), which is not a
kssw server; the differences are in the specification's Appendix A.

## Running the conformance suite

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/) (or pytest
installed some other way).

```sh
make conformance BASE_URL=http://127.0.0.1:8080          # any server's API base
ADMIN_TOKEN=... make conformance BASE_URL=...            # plus the admin API
make conformance BASE_URL=... PYTEST_ARGS='-m min'        # only the min class
```

The suite **writes posts and toggles maintenance mode**: never point it at
production. The server under test must trust `X-Forwarded-For` from the
test client (every request sends a random one, so per-address rate limits
do not get in the way), and for the admin tests accept the token over plain
HTTP. See [`conformance/conftest.py`](conformance/conftest.py).

Against the PHP reference implementation, in docker:

```sh
make reference                                   # clones ks-sw-api (public URL) at main
make reference IMPL_DIR=../ks-sw-api             # an existing checkout
make reference IMPL_URL=<git url> IMPL_REF=dev   # another remote or ref
```

`IMPL_URL` defaults to the public `https://github.com/kimari-s/ks-sw-api`;
`make reference` without `IMPL_DIR` and the `reference` CI job work only
once that repository is public.

## Checks

```sh
make check   # validate the OpenAPI files, check Markdown links
```

CI (`.github/workflows/ci.yml`) runs the checks and the conformance suite
against the reference implementation on PHP 7.4 and 8.3.

## Contributing

Changes within protocol version 1 must be additive (spec §10). Every
normative change goes with its OpenAPI change, a conformance test where
possible, and a CHANGELOG entry.

Security issues: see [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE), for the prose, the OpenAPI files and the suite.
