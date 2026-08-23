# Analyzer production request boundary v1

## Hosting gate result

The website cannot currently host a production request gateway. On 2026-08-23,
the live repository reported GitHub Pages `build_type: legacy`, HTTPS enforced,
and publishing from the root of `gh-pages`. The checked-in release command also
uses `quarto publish gh-pages`. There is no checked-in application-runtime or
API deployment workflow.

GitHub Pages serves the static browser client but cannot execute the bounded
server-side request/status/result protocol. The accepted Node PHP bridge is not
a public-browser substitute: it requires a server-held bearer secret and does
not provide the complete public analysis-view result boundary. A secret cannot
be embedded in this repository or sent to every browser.

Consequently the public production configuration remains deliberately disabled.
This task does not wrap, proxy, rename, or expose the development SSH route.

## Frozen public protocol

The gateway-neutral v1 boundary is:

```text
POST /v1/analyzer/requests
GET  /v1/analyzer/requests/{sha256-analysis-key}/status
GET  /v1/analyzer/requests/{sha256-analysis-key}/result
```

The POST body is the exact bounded Node submission schema
`bms-analysis-submission-v2`. It permits only:

- engine `gnu`;
- analysis setting `1ply`;
- decision `checker` or `cube`;
- a complete `gnuid` position;
- two integer dice from 1 through 6 for checker, or `null` for cube.

The maximum encoded body is 2,048 bytes. All request and nested position fields
are exact; unknown fields are rejected. There are no command, executable,
argument, shell, path, URL, token, report, rollout, GNU control, or Sage fields.
The browser and gateway do not compute an analysis key. Node returns its
deterministic `sha256-…` key and remains the only computation-identity,
deduplication, queue, lifecycle, execution, cache, and result authority.

The strict protocol types are in
`contracts/analyzer-public-api-v1.schema.json`. Executable gateway-neutral
validation is in `scripts/analyzer_public_contract.py`.

### Submission response

`bms-analyzer-public-submit-v1` contains exactly `schema_version`,
`analysis_key`, `status`, and `cache_hit`. Status is `queued`, `running`, or
`complete`.

### Status response

`bms-analyzer-public-status-v1` contains exactly `schema_version`,
`analysis_key`, `status`, and `cache_hit`. The gateway projects Node's public
lifecycle without creating another lifecycle store. Polling an unknown or
malformed key fails closed.

### Result response

`bms-analyzer-public-result-v1` contains exactly `schema_version`,
`analysis_key`, `status: complete`, and Node's `bms-node-analysis-view-v0`.
Both keys must match. The browser passes the analysis view to the existing
shared Results Viewer.

The gateway must make this response available directly from the finalized Node
result. It must not wait for Corpus, Canonical Parquet, DuckDB, D1, or a later
serving/index projection. An existing accepted result uses the same status and
result interface; a later D1 lookup projection may satisfy that lookup without
becoming factual or computation authority.

## Public error and information boundary

The client displays only allowlisted, stable error codes and fixed messages.
Unknown codes, unreadable bodies, network failures, and unexpected response
fields collapse to `service_unavailable`. Raw server messages are ignored.
Public responses must never contain stack traces, SSH/control-hop information,
hostnames, filesystem paths, credentials, tokens, commands, or engine output.

The production client constructs every URL from a reviewed HTTPS origin, the
fixed API base path, and a validated analysis key. It rejects credentials,
ports, query strings, fragments, paths in the configured origin, loopback,
`.local`, and RFC 1918 IPv4 hosts. Fetches use `credentials: omit`; the config
has no authentication or secret field.

## Origin and abuse gate

A production gateway must allow the exact site origin
`https://backgammonsimplified.github.io`, emit `Vary: Origin`, accept only GET,
POST, and OPTIONS, accept only the `Content-Type` request header, and reject
other origins. Wildcard origin plus credentials is not allowed.

Rate/quota control is intentionally not invented in the static client. Before
enabling the configuration, Project Coordinator/Task Manager must commission:

1. a named owner for an Internet-facing HTTPS application runtime that can
   reach the authoritative server Node without exposing a shell/control channel;
2. a capacity-based public rate/quota policy and operational monitoring owner;
3. exact origin handling, TLS, public error mapping, request-size enforcement,
   and runtime-only secret delivery;
4. Node worker/service orchestration for accepted queued work;
5. an independently accepted deployment and rollback procedure.

No authentication requirement has been selected by current product authority.
If a future architecture selects authentication, that is a separate reviewed
product/security decision; it must not expose Node's internal bridge secret to
the browser.

## Development/production separation

`scripts/analyzer_local_preview.py` and its optional SSH control route remain
loopback-only development infrastructure. The browser selects those endpoints
only when its hostname is `127.0.0.1`, `localhost`, or IPv6 loopback. A public
origin loads `site/data/analyzer-production-gateway-v1.json`; because no gateway
runtime is commissioned, the reviewed configuration has `enabled: false`, a
null gateway origin, and no secrets. The form stays disabled with a controlled
availability message.

Enabling the file is not itself a deployment procedure. It may occur only after
the missing runtime/owner gates above and independent Task 017 acceptance are
satisfied. Task 017 performs no public deployment.

## Non-ownership record

- D1 implementation: none.
- Fresh-result D1/Parquet dependency: none.
- Analyzer durable job/result cache: none.
- Analyzer request identity or deduplication authority: none.
- Browser or laptop engine execution: none.
- Canonical, Corpus, benchmark, or golden mutation: none.
- Control Tower mutation: none (`CONTROL_TOWER_RECONCILIATION_PENDING`).
