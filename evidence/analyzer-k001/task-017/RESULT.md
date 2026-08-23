# Analyzer K001 Task 017 bounded implementation evidence

Status: BLOCKED

The current website is a static GitHub Pages deployment and has no deployable
application runtime for the production request/status/result gateway. The
accepted Node bridge requires a server-held secret and is not safe to call
directly from a public browser. No development SSH route was promoted.

The maximum safe bounded portion is implemented and tested:

- exact `bms-analysis-submission-v2` request fields with GNU / 1-ply allowlists,
  a 2,048-byte limit, complete GNUID validation, strict unknown-field rejection,
  and no executable/command/path/token surface;
- fixed HTTPS request, status, and result routes with validated Node keys;
- separate loopback-only development and reviewed production transports;
- strict public response envelopes, fixed public-safe errors, private-detail
  rejection, exact-origin CORS helpers, and a no-secret runtime config;
- Node-produced analysis-view delivery directly into the existing shared
  Results Viewer without a D1 or Parquet dependency;
- a fail-closed rendered public page: disabled form, controlled `unavailable`
  state, zero API requests, and zero browser/console errors.

Browser protocol proof observed queued, running, complete, cache-hit reuse, the
same Node key on identical submissions, existing-key lookup, one shared Results
Viewer, eight checker candidates, and zero transport submissions for invalid
input. This was a protocol/integration double; it ran no engine.

Validation:

- focused production/adapter Python: 19/19 PASS;
- production/shared-viewer JavaScript: PASS;
- production protocol browser proof: PASS, zero page/console errors;
- complete Quarto render: PASS, 28/28 pages;
- rendered static audit: PASS, 29 pages, zero findings;
- full JavaScript set: PASS;
- full Python set: 228 run, 224 PASS, one accepted historical
  publication-identity scanner failure, three environment/negative-control
  skips;
- quick gate: JavaScript PASS; Python has the same accepted historical scanner
  failure after all Task 017 tests pass;
- `git diff --check`: PASS.

Live server native analysis was not run. Task 016's accepted proof remains the
live baseline; Task 017 has no deployed production gateway through which a new
live public proof could safely run. No golden, Corpus, Canonical, D1, Parquet,
or benchmark state was mutated.

Remaining dependency: Project Coordinator/Task Manager must commission a named
HTTPS runtime/deployment owner and capacity-based abuse-control policy, then
independently accept and deploy the gateway before the public config can be
enabled.

`CONTROL_TOWER_RECONCILIATION_PENDING`
