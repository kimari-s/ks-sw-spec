# kssw — protocol version 1

- **Status:** Draft. Anything here may still change before version 1 is final.
- **Protocol version:** `1`
- **This document:** <https://github.com/kimari-s/ks-sw-spec/blob/main/spec/kssw.md>
- **Machine-readable descriptions:** [`../openapi/kssw.openapi.yaml`](../openapi/kssw.openapi.yaml) (client API), [`../openapi/kssw-admin.openapi.yaml`](../openapi/kssw-admin.openapi.yaml) (admin API)
- **Conformance suite:** [`../conformance/`](../conformance/)

## Contents

1. [Introduction](#1-introduction)
2. [Conventions and terminology](#2-conventions-and-terminology)
3. [Overview](#3-overview)
4. [Conformance](#4-conformance)
5. [Common rules](#5-common-rules)
6. [Discovery](#6-discovery)
7. [Operations](#7-operations)
8. [Features and extensions](#8-features-and-extensions)
9. [Admin API](#9-admin-api)
10. [Versioning and compatibility](#10-versioning-and-compatibility)
11. [Security considerations](#11-security-considerations)
12. [Privacy considerations](#12-privacy-considerations)
13. [References](#13-references)
- [Appendix A. Differences from the 6umi.net API](#appendix-a-differences-from-the-6uminet-api)

## 1. Introduction

kssw is an HTTP API between a **board UI** — a kuzuha-style BBS front end
running in a browser — and **its server**. A board is a single stream of
short anonymous-by-default posts, threaded by replies and labelled with
tags. The protocol is deliberately small: a UI that speaks it can be put in
front of any server that implements it, and a server can be written in an
afternoon on a shared PHP host.

### 1.1 Scope

In scope:

- the client API: reading, searching, posting and deleting posts; tags;
  the participant count;
- how a client finds the API (discovery) and what the server implements
  (`/v1/meta`, conformance classes, features);
- the admin API for moderation and operation (an optional feature).

Out of scope:

- **Federation** between servers (for example ActivityPub). A server MAY
  federate, but that is a separate layer with its own protocol; kssw does
  not define or redefine it.
- **Web / traffic analytics** (page views, referrers, devices). These belong
  to a separate layer (server logs, external analytics). The only audience
  figure in kssw is the participant count (§8.2).
- **Accounts, login and cookies.** kssw 1 has none; a browser identifies
  itself only with its own random client id (§5.9).
- **Storage.** The database schema and every other implementation detail
  are not part of the protocol. Only behaviour over HTTP and the JSON shapes
  are.

## 2. Conventions and terminology

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
"SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and
"OPTIONAL" in this document are to be interpreted as described in BCP 14
[RFC 2119] [RFC 8174] when, and only when, they appear in all capitals, as
shown here.

- **Server**: an implementation of this protocol serving one board.
- **Client**: anything calling the API; usually a **UI** in a browser.
- **API base**: the URL under which a server's paths live, for example
  `https://example.com/bbs/api`. Every path in this document except
  `/.well-known/kssw` is appended to it (`<base>/v1/posts`).
- **Post**: a text with an id, a creation time, tags, an optional author
  and an optional parent.
- **Root**: a post without a parent. A **thread** (tree) is a root and every
  post that descends from it. Every post carries its `root_id`.
- **Tag**: a short string attached to posts. A tag has no kind or owner; it
  is identified by its text, its `name`.
- **Author**: a free-form display name a poster typed. Not an identity.
- **Client id**: a random string a browser generates and keeps, used to
  recognise its own posts (§5.9).
- **Participant**: a client that sent a presence heartbeat recently (§8.2).
- **Conformance class** (profile): `min` or `full` (§4).
- **Feature**: a named optional part of the protocol (§8).

## 3. Overview

```
 board UI (browser) ──HTTPS/JSON──▶ server (API base)
        │                              ├─ /v1/meta, /v1/posts…, /v1/tags   client API (§7)
        │                              ├─ /v1/presence, /v1/active_count   features (§8)
        └─ GET /.well-known/kssw ─────▶├─ /v1/admin/…                      admin API (§9)
           (host root, §6)             └─ storage: implementation-defined
```

A client:

1. finds the API base (configuration, or `/.well-known/kssw`, §6);
2. reads `GET /v1/meta` to learn the protocol version, the conformance
   class and the features;
3. calls `min` operations freely, `full` operations only on `full` servers,
   and feature operations only when the feature is listed.

## 4. Conformance

### 4.1 Classes

- A **`min` server** MUST implement every operation marked `x-tier: min`
  in the OpenAPI description that has no `x-feature`, with the semantics of
  §5 and §7.
- A **`full` server** MUST implement everything a `min` server does, plus
  every operation marked `x-tier: full` without `x-feature`. (`min` ⊂
  `full`.) kssw 1 defines no feature-less `full` operation yet, so `full`
  is reserved for servers that implement more of the protocol as it grows.
- A server MUST report its class in `GET /v1/meta` `profile`.
- Features (§8) are independent of the class: a server MAY implement any
  feature, whatever its class, and MUST list each one it implements.

### 4.2 Clients

- A client MUST NOT require a `full` operation from a server whose
  `profile` is `min`.
- A client MUST NOT call a feature operation unless the feature is listed
  in `/v1/meta` `features` (or, for admin features, in
  `/v1/admin/capabilities` `features`).
- A client MUST ignore JSON members, feature names and error codes it does
  not know.

### 4.3 Conformance suite

[`conformance/`](../conformance/) is a black-box test suite (pytest). A
server conforms when it passes every test its profile and features select.
The suite is informative where it and this document disagree; the document
wins and the suite is fixed.

## 5. Common rules

### 5.1 Transport and media type

- Servers SHOULD be reachable over HTTPS only. The admin API has stricter
  rules (§9.2).
- Request and response bodies are JSON [RFC 8259] in UTF-8, media type
  `application/json`. A server MUST send `Content-Type: application/json`
  on every JSON response, errors included.
- A server SHOULD send `Cache-Control: no-store` (or an equally strict
  policy) on API responses; board contents change constantly.
- A UI is often served from another origin than the API. A server SHOULD
  support CORS [Fetch] for the client API, with the request headers
  `Content-Type` and `X-Client-Id`, configurable by the operator. The admin
  API is not meant for browsers and SHOULD NOT send CORS headers.
- A server MUST answer an unknown path with `404` (`not_found`) and a known
  path with an unsupported method with `405` (`method_not_allowed`) and an
  `Allow` header.

### 5.2 Ids

- Post ids are UUIDs (version 4 RECOMMENDED), in lowercase canonical form
  (`8-4-4-4-12` hex digits). Servers MUST emit them in lowercase; servers
  SHOULD accept uppercase input.
- A malformed id in a path is not an error of its own: the post is not
  found (`404`).

### 5.3 Times

- Every time a server emits is an RFC 3339 [RFC 3339] date-time with an
  explicit UTC offset.
- Servers SHOULD emit a fixed width with exactly six fractional digits
  (`2026-10-16T12:34:56.123456+09:00`) in one fixed offset (the server's
  configured zone), so that times from one server sort correctly as
  strings. Clients MUST NOT rely on string order across servers.
- Query parameters that take a time (`since`, `until`) accept an RFC 3339
  date-time, a date-time without an offset (taken in the server's zone),
  or a bare date `YYYY-MM-DD` (midnight in the server's zone). Servers MUST
  accept `Z` and numeric offsets.

### 5.4 Query parameters

- A list parameter repeats its name: `?tags=a&tags=b`. Servers MUST accept
  this form. Empty values are ignored.
- Booleans are `true` / `false`. Servers SHOULD also accept `1`/`0`,
  `yes`/`no` and `on`/`off`. Any other value is `422`.
- When a non-list parameter is repeated, servers use the last value.

### 5.5 Pagination

Board listings are paged by `page` (from 1) and `page_size`; a page past
the end is an empty list. Each operation states its default and maximum
`page_size`. Values out of range are `422`. Counts for the same filters are
separate operations (`…/count`) that return a bare JSON integer.

### 5.6 Errors

An error response has a 4xx or 5xx status and the body:

```json
{"detail": "post body exceeds 5000 characters", "code": "invalid"}
```

- `detail` (string, REQUIRED): a message for people, in English.
  Clients SHOULD NOT parse it.
- `code` (string, REQUIRED): stable, machine-readable, lowercase
  `[a-z][a-z0-9_]*`. Clients MUST treat a code they do not know by its
  status, and SHOULD tolerate a missing `code` (servers that predate
  kssw).
- Further members MAY be present and are ignored by clients that do not
  know them.

Codes of the client API:

| Status | `code` | Meaning |
|---|---|---|
| 400 | `bad_request` | Well-formed request the server will not run (missing filter, too many ids, conflicting parameters) |
| 403 | `forbidden` | Not allowed (e.g. deleting someone else's post) |
| 404 | `not_found` | Unknown path (or an unimplemented feature) |
| 404 | `post_not_found` | No such post |
| 405 | `method_not_allowed` | Known path, unsupported method |
| 413 | `too_large` | Request body too large |
| 422 | `invalid` | Malformed request: bad JSON, wrong type, out of range, too long |
| 429 | `rate_limited` | Too many requests; see `Retry-After` |
| 500 | `internal` | Server error |
| 503 | `maintenance` | Writes are off (§5.8) |
| 503 | `unavailable` | Temporarily unavailable for another reason |

The admin API adds its own codes (§9.3).

### 5.7 Limits and rate limits

- Post text MUST be at most **5,000 characters**, counted in Unicode code
  points, after trimming. Longer text is `422`. A server MUST NOT accept
  longer text: UIs rely on the limit. Other limits (author 40, tag 64
  characters, 20 tags per post, `client_id` 128) are in §7.8.
- A server SHOULD limit how often one client creates posts, both per
  `client_id` and, independently, per client network address (a client
  can change its id at will). Over the limit it SHOULD answer `429`
  (`rate_limited`) with a `Retry-After` header [RFC 9110] in seconds. The
  window is the operator's choice (a few seconds, e.g. 5, is a sensible
  default).
- A server MAY rate-limit any other operation the same way.
- A server SHOULD bound request bodies (64 KiB is ample) and answer
  `413` (`too_large`) beyond that.

### 5.8 Maintenance

An operator may stop writes for a while (to move or repair data). Then a
server MUST answer every client-API request that would change data
(`POST`, `PUT`, `PATCH`, `DELETE`) with `503` and
`{"detail": "maintenance", "code": "maintenance"}`, and SHOULD keep
answering reads. The admin API keeps working (§9). Clients SHOULD show a
"maintenance" notice rather than a generic error.

### 5.9 Client identity

kssw 1 has no accounts, logins or cookies. A browser generates a random
**client id** (a UUIDv4 is RECOMMENDED), keeps it locally and sends it:

- in the body of `POST /v1/posts` (`client_id`), to be able to delete the
  post later;
- in the `X-Client-Id` request header, to learn which posts are its own
  (`mine`) and to delete one.

A server MUST NOT return client ids in any response, and SHOULD store only
a keyed hash of them (§11). `mine` is `true` / `false` when the request had
`X-Client-Id`, `null` otherwise.

## 6. Discovery

A host that runs a kssw server SHOULD serve a discovery document at
`/.well-known/kssw` [RFC 8615] at the root of the host, so that a client
given only a host name can find the API base. It is RECOMMENDED, not
required: a board on shared hosting may be unable to place a file at the
host root. Clients MUST work with a configured API base and no discovery.

```http
GET /.well-known/kssw HTTP/1.1
Host: example.com
```

```json
{
  "protocol": "kssw",
  "apis": [
    {"version": "1", "base": "/bbs/api", "name": "Example board"}
  ]
}
```

- `protocol` (REQUIRED): `"kssw"`.
- `apis` (REQUIRED): one or more entries, one per board (or per major
  version) on the host, in order of preference.
	- `version` (REQUIRED): the protocol major version the entry serves, as a
	  string of digits (`"1"`). The API's paths then begin with `/v<version>/`.
	- `base` (REQUIRED): the API base, an absolute URL or a path-absolute
	  reference resolved against the discovery document's URL [RFC 3986]. A
	  trailing `/` is not significant: clients remove it before appending a
	  path. It MUST NOT contain a query or fragment.
	- `name` (OPTIONAL): a human-readable name.
- The response MUST be `200` with `Content-Type: application/json`. It
  SHOULD carry `Access-Control-Allow-Origin: *`; the document is public.
- A client picks the first entry whose `version` it supports and then
  reads `<base>/v1/meta`. A client MUST ignore entries with versions it does
  not know and members it does not know.

The document can be a static file or generated; the protocol does not
care which.

## 7. Operations

Each operation's parameters and response shapes are in
[`kssw.openapi.yaml`](../openapi/kssw.openapi.yaml); this section gives
the semantics. All are `min` unless noted.

### 7.1 `GET /v1/meta`

Describes the server. MUST be implemented by every server.

```json
{"protocol": "kssw", "version": "1", "profile": "min",
 "impl": "php", "impl_version": "0.2.0-alpha.1",
 "impl_url": "https://github.com/kimari-s/ks-sw-api",
 "features": ["active_count", "admin", "presence"]}
```

- `protocol`: `"kssw"`.
- `version`: the protocol major version, `"1"`.
- `profile`: the conformance class, `"min"` or `"full"`.
- `impl`: a short name of the implementation. `impl_version`: its release
  version, SemVer [SemVer] RECOMMENDED. They say nothing about the
  protocol.
- `impl_url` (OPTIONAL): where the implementation's source is, e.g. its
  repository; an absolute `http` or `https` URL. A client may link
  `impl` / `impl_version` to it. Absent when the server does not say.
- `features`: the features this server implements (§8), no duplicates, in
  any order.

### 7.2 `GET /v1/posts` — list posts

Order:

- by default newest first: `created_at` descending, then `id` descending;
- with `root_id` or `root_ids`: thread order, oldest first;
- with `roots_only`: root posts, ordered by the newest post in their tree
  (a thread with a new reply comes back to the top).

Filters:

- `tags` (list) with `tags_op` (`or` default: any of them; `and`: all).
- `exclude_tags` (list) with `exclude_op` (`or` default: drop posts carrying
  any of them; `and`: only those carrying all). Always applies.
- `author`: exactly this author after trimming; posts without an author
  never match.
- `root_id` / `root_ids` (at most 50): only these trees. `tags`, `author`
  and `roots_only` are then ignored; `exclude_tags` still applies.
  `root_ids` with `root_id` or `roots_only` is `400`.
- `include_tree` with `tags` and/or `author`: every post of each tree that
  contains a matching, non-excluded post, minus excluded posts.
  `roots_only` is ignored in this mode.
- `roots_only`: root posts only.

Paging: `page` (default 1), `page_size` (default 20, at most 10,000 — a UI
fetches whole threads in one request).

Deleted posts are included: a deleted post has `status: "deleted"`, empty
`text`, empty `tags` and `author: null`, so that threads keep their shape.
With `X-Client-Id`, every post carries `mine`.

`GET /v1/posts/count` takes the same filters (except paging and
`root_ids`) and returns how many posts the listing would return across all
pages, as a JSON integer.

### 7.3 `GET /v1/posts/latest_id`, `GET /v1/posts/oldest_at`

`{"id": …}`: the id of the newest post, deleted ones included, or `null`;
a cheap check whether anything changed. `{"created_at": …}`: the time of
the oldest post, or `null`.

### 7.4 `GET /v1/posts/search` — past-log search

- At least one of `q`, `tags`, `exclude_tags`, `author`, `since`, `until`
  is REQUIRED; otherwise `400` (`bad_request`). A `q` of only whitespace
  counts as absent.
- `q` is split on whitespace (ASCII whitespace and U+3000 IDEOGRAPHIC
  SPACE). Servers use at most 5 distinct terms, each cut to 100
  characters. A term matches as a case-insensitive substring of the text;
  case folding is REQUIRED for ASCII and OPTIONAL beyond. Characters such
  as `%` and `_` are literal. `q_op`: `and` (default, every term) or `or`.
- `since` (inclusive) and `until` (exclusive) bound `created_at` (§5.3).
- `tags`, `exclude_tags`, `author` as in §7.2.
- Deleted posts are left out. Newest first. `page_size` default 20, at
  most 50.

`GET /v1/posts/search/count` returns the total, as for listings.

### 7.5 `GET /v1/posts/by-ids`

`ids` (list, REQUIRED, at most 100; missing is `422`, too many is `400`).
Returns the posts that exist, in unspecified order; unknown and malformed
ids are skipped.

### 7.6 `GET /v1/posts/{id}`

One post, or `404` (`post_not_found`).

### 7.7 Post object

| Member | Type | Notes |
|---|---|---|
| `id` | string | §5.2 |
| `text` | string | Trimmed of leading/trailing whitespace. Empty when deleted |
| `created_at` | string | §5.3 |
| `tags` | string[] | Tag names, sorted by code point. Empty when deleted |
| `parent_id` | string \| null | The post replied to |
| `root_id` | string | The thread's root; the post's own id for a root |
| `status` | `"active"` \| `"deleted"` | |
| `author` | string \| null | Null when none or deleted |
| `mine` | boolean \| null | §5.9 |

Servers MAY add members; clients ignore those they do not know.

### 7.8 `POST /v1/posts` — create a post

Body (JSON object):

- `text` (REQUIRED): not empty or whitespace only; at most 5,000 code
  points (§5.7).
- `tags`: up to 20 tag names of at most 64 characters each. Each is
  trimmed; empty strings and duplicates are dropped.
- `parent_id`: the post replied to. It MUST exist (`422` otherwise). The
  new post's `root_id` is the parent's root; without a parent, its own id.
- `author`: at most 40 characters, trimmed; empty means none.
- `client_id`: at most 128 characters (§5.9).

Unknown members are ignored. A body that is not a JSON object is `422`.

The server stores exactly what was sent: it MUST NOT extract tags from the
text and MUST NOT add the author as a tag. It answers `200` with the new
post; `mine` is `true` when `client_id` was sent, otherwise `null`.

Rate limits: §5.7. Maintenance: §5.8.

### 7.9 `DELETE /v1/posts/{id}` — delete your own post

A soft delete: the post stays, with `status: "deleted"` (§7.2). Allowed
only when the request's `X-Client-Id` equals the `client_id` the post was
created with and the post is still active; otherwise `403` (`forbidden`),
which a server MUST also answer for posts created without a client id.
An unknown post is `404`. Success is `{"ok": true, "status": "deleted"}`.

### 7.10 `GET /v1/tags`

A tag exists once a post has used it (or, with `tag_create`, once it was
registered). Each tag is:

```json
{"name": "music", "created_at": "2026-10-16T12:00:00.000000+09:00",
 "count": 12, "last_posted_at": "2026-10-16T13:00:00.000000+09:00"}
```

- `created_at`: first use. `count` and `last_posted_at`: with
  `with_counts=true`, every post carrying the tag, deleted ones included
  (the same number as `GET /v1/posts/count?tags=<name>`); otherwise
  `null`.
- `q`: case-insensitive substring of the name (ASCII folding REQUIRED).
- `names` (list, at most 200, more is `400`): only these tags.
- `sort`: `recent` (default; newest tag first), `count` (most posts first)
  or `name` (by code point). Ties break by name.
- `limit` (≥ 1) and `offset` (≥ 0, default 0).

### 7.11 `POST /v1/tags` — register a tag (`full`, feature `tag_create`)

Body `{"name": "…"}` (1–64 characters). Idempotent: answers `200` with the
tag, whether it existed or not.

### 7.12 `GET /v1/links/by-urls` — link previews (`full`, feature `link_preview`)

`urls` (list). Returns the previews the server has already fetched for
those URLs; URLs it knows nothing about are left out. The server fetches
previews on its own schedule (for example when a post links a URL); this
operation never makes it fetch.

## 8. Features and extensions

### 8.1 Registry

A feature is a named optional part of the protocol. A server lists the
client-API and admin features it implements in `/v1/meta` `features`;
admin sub-features are also listed in `/v1/admin/capabilities`
`features` (§9).

| Name | Operations | Class | Listed in | Section |
|---|---|---|---|---|
| `presence` | `POST /v1/presence` | min | `/v1/meta` | §8.2 |
| `active_count` | `GET /v1/active_count` | min | `/v1/meta` | §8.2 |
| `link_preview` | `GET /v1/links/by-urls` | full | `/v1/meta` | §7.12 |
| `tag_create` | `POST /v1/tags` | full | `/v1/meta` | §7.11 |
| `admin` | `/v1/admin/…` | min | `/v1/meta` | §9 |
| `maintenance` | `GET` / `PUT /v1/admin/maintenance` | min | `/v1/admin/capabilities` | §9.6 |
| `backup` | `GET /v1/admin/backup` | min | `/v1/admin/capabilities` | §9.6 |

"Class" is the `x-tier` of the operations: a `min` server MAY implement a
`full` feature, and lists it if it does.

New names are added to this table by a new revision of this document
(§10). A registered name is lowercase `[a-z][a-z0-9_]*`.

### 8.2 Presence and the participant count

kssw keeps one audience figure, the **participant count**: how many people
have the board open now (the "current participants" of the old kuzuha
boards). It is computed from a heartbeat:

- `POST /v1/presence` (feature `presence`): a UI sends it when a page opens
  and then about once a minute while it stays open. The body is an empty
  JSON object `{}` or absent; servers MUST ignore unknown members and MUST
  answer `422` for a body that is not a JSON object. The answer is
  `{"ok": true}`.
- `GET /v1/active_count` (feature `active_count`): `{"count": n}`, the
  number of distinct participants that sent presence in the last `minutes`
  (1–60, default 5).

How a server tells participants apart is its choice (a keyed hash of the
client address is typical). A server MUST NOT keep presence data longer
than it needs for the count (an hour is enough for `minutes` ≤ 60) and MUST
NOT store raw addresses (§12). A server MAY cache the count briefly.

This is **not analytics**. Page views, unique visitors over days,
referrers and devices are out of scope (§1.1). Counting posts and posters
from the server's own data is an implementation matter (for example an
admin statistics extension).

### 8.3 Extension names

Implementations MAY offer operations and members beyond this document.

- A feature name that is not in the registry MUST have the form
  `x-<owner>-<name>`, where `<owner>` identifies whoever defines it (for
  example a GitHub user or organisation, lowercased) and `<name>` is
  `[a-z0-9_-]+`; for example `x-example-word_filter`. Unregistered names
  without the `x-` prefix MUST NOT be used.
- Extension operations SHOULD live under a path that cannot collide with a
  future revision, `/v1/x/<owner>/…`.
- Extension members in JSON objects SHOULD be prefixed `x_<owner>_`.
- An extension MUST NOT change the meaning of anything defined here.
- An extension that proves generally useful can be registered under a
  plain name by a later revision; the `x-` name may then be listed as
  well, during a transition.

### 8.4 Clients and features

A client calls a feature operation only when the feature is listed. A
server that does not list a feature MAY answer its operations with `404`
(`not_found`), and a client SHOULD treat a `404` from a listed feature's
operation as "absent" for the rest of the session.

## 9. Admin API

The admin API (feature `admin`) is for the board's operator, through a CLI,
a script or an AI agent; not for browsers. Its shapes are in
[`kssw-admin.openapi.yaml`](../openapi/kssw-admin.openapi.yaml). Its paths
are under `<base>/v1/admin/`. Without the feature, every admin path MAY
answer `404`.

### 9.1 Authentication

- Every request carries `Authorization: Bearer <token>` [RFC 6750]. The
  token is a high-entropy secret (at least 128 bits; 32 random bytes in
  base64url is RECOMMENDED) made by the operator.
- A server MUST NOT store the token itself; it SHOULD store only a hash of
  it (SHA-256 is enough for a random token) and MUST compare in constant
  time.
- A missing or wrong token is `401` (`unauthorized`) with
  `WWW-Authenticate: Bearer …`.
- A server SHOULD limit failed attempts per client and answer `429`
  (`rate_limited`) with `Retry-After` beyond the limit, even for the right
  token, until the window passes.

### 9.2 Transport

A server MUST refuse admin requests over plain HTTP with `403`
(`https_required`), except from the server's own machine, unless the
operator explicitly allows it (for tests). Behind a TLS-terminating
proxy, the server MUST trust the proxy's forwarded scheme only from proxies
the operator configured.

### 9.3 Errors

As §5.6, with these codes in addition: `unauthorized` (401),
`https_required` (403), `conflict` (409), `database_missing` (409 or 503:
the server's data is not in place), `config_invalid` (500), and
`post_not_found`, `method_not_allowed`, `too_large`, `invalid`,
`rate_limited`, `internal`, `unavailable` as in §5.6.

### 9.4 Capabilities

`GET /v1/admin/capabilities` describes the admin API of this server:
`version` (the admin API major version, `"1"`), `impl` and `impl_version`
(as in `/v1/meta`), `features` (admin features), `operations` (the
operationIds implemented), `post_filters`, `limits` (`page_size_max` ≥ 50,
`ids_max` ≥ 1), and optionally `timezone` (IANA name) and `server_time`.

### 9.5 Posts, mutations and the log

- `GET /v1/admin/posts` lists posts newest first, deleted ones included
  **with** their text, tags and author. Filters `q`, `author`, `tags`,
  `status`, `root_id`, `since`, `until` all narrow (AND). Paged lists are
  `{"items", "page", "page_size", "total", "has_more"}`.
- `GET /v1/admin/posts/{id}`: one post, deleted or not.
- `POST /v1/admin/posts/delete` and `POST /v1/admin/posts/restore` take
  `{"ids": [...]}` (at most `limits.ids_max`) and report per-id results
  (`changed`, `unchanged`, `not_found`, `invalid_id`). Delete is the same
  soft delete as a poster's own; restore also undoes a poster's delete.
- Every mutation MUST be idempotent and MUST accept `dry_run` (in the body
  or the query; either `true` wins), which reports what would change and
  changes nothing.
- Every mutation, dry or not, MUST be written to the admin log.
  `GET /v1/admin/log` lists entries newest first: `id` (an integer that
  increases with time), `created_at`, `action`, `target`, `dry_run`,
  `result`, `via`.
- The admin API MUST keep working during maintenance (§5.8).

### 9.6 Admin features

- `maintenance`: `GET` / `PUT /v1/admin/maintenance` reads and switches
  maintenance mode (§5.8). A server MAY refuse to switch it off while its
  data is not in place (`409`, `database_missing`).
- `backup`: `GET /v1/admin/backup` downloads a consistent snapshot as
  `application/octet-stream` with `Content-Disposition: attachment`. Its
  format is the implementation's, named by `X-Backup-Format`; a server
  SHOULD send `X-Content-SHA256` (hex) so the client can verify it.

## 10. Versioning and compatibility

- The protocol has a **major version**, `"1"` here. It appears in
  `/v1/meta` `version`, in the discovery document and in every path
  (`/v1/`).
- Within a major version, revisions are **additive only**: new optional
  operations, new features, new optional request parameters, new response
  members, new error codes. A revision MUST NOT remove or rename anything,
  change a type, tighten a limit a client relies on, or change the meaning
  of an existing value. Clients MUST therefore ignore what they do not
  know (§4.2).
- A change that breaks this rule needs a new major version, with paths
  under `/v2/`. A server MAY serve several major versions at once; the
  discovery document lists each.
- **Deprecation.** Something to be removed is first marked deprecated in a
  revision of the current major version (and `deprecated: true` in the
  OpenAPI description). It keeps working until the next major version,
  which MAY remove it.
- Revisions are recorded in [`CHANGELOG.md`](../CHANGELOG.md). While the
  status is Draft, version 1 itself may still change; the changelog says
  how.
- The admin API has its own major version (`capabilities.version`) under
  the same rules.

## 11. Security considerations

- **Transport.** Use HTTPS. The admin token is a bearer credential: anyone
  who sees it is the operator. Servers refuse admin requests over plain
  HTTP (§9.2); clients MUST NOT send the token over plain HTTP to another
  machine.
- **Admin token handling.** Store only a hash on the server (§9.1), keep the
  token out of URLs, logs and shell history where possible (environment
  variables or a file readable only by the operator), and rotate it when
  in doubt. The admin API has no CORS, so a web page cannot call it
  through a visitor's browser.
- **Client ids are capabilities.** Whoever has a post's client id can delete
  it. Servers MUST NOT disclose client ids (§5.9) and SHOULD store them only
  as a keyed hash (HMAC-SHA256 with a per-server random secret is
  RECOMMENDED), so that a leaked database does not let anyone delete posts
  on another server.
- **Addresses.** Servers that use client network addresses (rate limits,
  presence) SHOULD keep only a keyed hash (HMAC) of them, never the raw
  address (§12).
- **Forwarded headers.** `X-Forwarded-For` and similar headers can be
  forged. A server MUST use them only from proxies the operator trusts;
  otherwise rate limits and presence can be evaded or polluted.
- **Rate limits** (§5.7) are the main defence against flooding; they are
  not a spam filter.
- **Untrusted text.** Post text, author and tag names are arbitrary user
  input. A UI MUST render them as text (no HTML), and SHOULD treat URLs in
  them with care (allow only `http:` / `https:` links, `rel="noopener
  noreferrer"`). Servers MUST NOT rely on the UI for this.
- **Discovery** is public and contains only URLs; it is not a place for
  anything secret.

## 12. Privacy considerations

- kssw 1 collects no account data. A post is anonymous unless the poster
  types an author name.
- A server SHOULD NOT store raw IP addresses or raw client ids at all; a
  keyed hash is enough for rate limits, presence and "is this mine?".
  Presence data MUST be dropped after it stops counting (§8.2).
- The participant count is an aggregate number; it is the only audience
  figure the protocol exposes.
- Deleting a post (by its poster or an admin) hides its text, tags and
  author from the client API; servers keep them for moderation (the admin
  API shows them) unless the operator purges them. Operators SHOULD say so
  in their board's terms.
- Analytics, if an operator wants them, live outside the protocol (§1.1)
  and fall under the operator's own policy.

## 13. References

- [RFC 2119] Key words for use in RFCs to Indicate Requirement Levels. <https://www.rfc-editor.org/rfc/rfc2119>
- [RFC 8174] Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words. <https://www.rfc-editor.org/rfc/rfc8174>
- [RFC 3339] Date and Time on the Internet: Timestamps. <https://www.rfc-editor.org/rfc/rfc3339>
- [RFC 3986] Uniform Resource Identifier (URI): Generic Syntax. <https://www.rfc-editor.org/rfc/rfc3986>
- [RFC 6750] The OAuth 2.0 Authorization Framework: Bearer Token Usage. <https://www.rfc-editor.org/rfc/rfc6750>
- [RFC 8259] The JavaScript Object Notation (JSON) Data Interchange Format. <https://www.rfc-editor.org/rfc/rfc8259>
- [RFC 8615] Well-Known Uniform Resource Identifiers (URIs). <https://www.rfc-editor.org/rfc/rfc8615>
- [RFC 9110] HTTP Semantics. <https://www.rfc-editor.org/rfc/rfc9110>
- [Fetch] WHATWG Fetch Standard (CORS). <https://fetch.spec.whatwg.org/>
- [SemVer] Semantic Versioning 2.0.0. <https://semver.org/>
- [OpenAPI] OpenAPI Specification 3.0.3. <https://spec.openapis.org/oas/v3.0.3>

## Appendix A. Differences from the 6umi.net API

kssw derives from the API of [6umi.net](https://6umi.net), which predates
it and is not a kssw server (it has no `/v1/meta`). A UI that wants to work
with both can tell them apart by `/v1/meta` `protocol`. Informative:

| 6umi.net API | kssw 1 |
|---|---|
| no `/v1/meta` | `/v1/meta` with `protocol`, `version`, `profile`, `impl`, `impl_version`, `features` |
| `POST /v1/access_log` `{session_id, …}` | `POST /v1/presence` `{}` (feature `presence`) |
| tag object `{id: <text>, …}` | `{name, …}` |
| `GET /v1/tags?ids=` | `GET /v1/tags?names=` |
| `POST /v1/tags` `{id}` | `{name}` (feature `tag_create`) |
| errors `{detail}` | `{detail, code}` |
| post members `meta`, `translations`, `client_id`, `user_uid` | not part of kssw |
| author added as a tag, `#tags` extracted from text | stored exactly as sent |

The conformance suite marks tests where the two deliberately differ
(`diverges`).
