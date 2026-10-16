# Security policy

This repository is a specification (prose, OpenAPI descriptions and a test
suite); it runs nowhere by itself. Please report here:

- a flaw **in the protocol** that makes every conforming server or client
  unsafe (for example a rule that lets someone delete other people's posts,
  leak client ids, or reach the admin API without the token);
- a weakness in the security or privacy considerations (§11, §12 of
  [`spec/kssw.md`](spec/kssw.md)).

A bug in one implementation belongs to that implementation's repository
(the PHP reference implementation: [ks-sw-api](https://github.com/kimari-s/ks-sw-api)).

## How to report

1. **Preferred:** GitHub private vulnerability reporting — the
   repository's **Security** tab → **Report a vulnerability**.
2. **Fallback:** email **security@6umi.net** (the RFC 2142 `security@`
   mailbox).

Please do not open a public issue for an undisclosed vulnerability. We aim
to acknowledge a report within a week. There is no bug bounty.

## Supported versions

The current draft of protocol version 1 (`main`).
