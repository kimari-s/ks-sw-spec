# Changelog

Protocol versions and releases of this repository. The protocol version
(`/v1/meta` `version`) and the repository release version are separate:
the protocol is `1`; releases of this repository follow SemVer.

## Unreleased

- §5.7: the suggested post rate-limit window is a few seconds (e.g. 5),
  was 30 seconds. Still the operator's choice (SHOULD, non-normative).

## 0.1.0-alpha.1 — protocol 1, Draft

First public draft of kssw protocol version 1, taken from the contract of
the PHP reference implementation (ks-sw-api), with these changes against
it:

- The protocol has a name: `/v1/meta` carries `protocol: "kssw"` and
  `version: "1"` (the protocol major version); the implementation's
  release version moved to `impl_version`. `contract` is gone.
- Discovery: `GET /.well-known/kssw` at the host root.
- `POST /v1/access_log` is now `POST /v1/presence` (feature `presence`),
  with an empty body; analytics are out of scope.
- Tags: the tag object's text is `name` (was `id`); `GET /v1/tags?names=`
  (was `ids`); `POST /v1/tags` takes `{name}` (was `{id}`).
- Errors carry a stable `code` in the client API too, not only in the admin
  API. Maintenance is `{"detail": "maintenance", "code": "maintenance"}`.
- Admin API: log entries use `created_at` (was `at`); capabilities carry
  `version` (the admin API version, was `contract`) and `impl_version`
  (was `version`).
- Feature names: a registry, and `x-<owner>-<name>` for third-party
  extensions.
- The database schema is no longer part of the contract (implementation
  detail).
