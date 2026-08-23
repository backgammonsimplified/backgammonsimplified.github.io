# Development layout

This directory reserves a clear home for future developer workflows. Existing
development and release scripts remain in `scripts/`, including
`preview-site.sh`, `bs-build-and-publish.sh`, and Windows helper scripts.

Target layout: `scripts/dev/preview/`, `scripts/dev/build/`, and
`scripts/dev/release/`. Do not relocate an active script until its callers,
documentation, and release checks are migrated in one scoped change.

## Analyzer server-backed prototype

`scripts/preview-analyzer-local.sh` keeps the browser on a loopback-only,
same-origin development adapter. By default it retains the local Task 011 Node
mode. To exercise an accepted server Node capability, set
`BS_ANALYZER_SERVER_CONFIG` to an operator-local JSON file before starting the
preview. Never commit that file.

The configuration uses the server-transport v1 schema declared by the adapter.
It supplies fixed token arrays for the operator-owned control command, accepted
Node CLI, and niced worker observer; absolute Node-owned runtime/public/view
roots; the accepted profile manifest; Node authority; and optional accepted
completed lookup roots. Command tokens and paths reject whitespace and shell
syntax. Browser request fields are sent to Node only on stdin and never become
remote command text.

The worker observer is a development proof harness, not another worker. It
launches exactly one accepted Node CLI worker and observes Node's public status
transitions so short-lived `running` states remain visible over a higher-latency
control route. It has no engine, parser, identity, queue, cache, cancellation,
or result-publication logic. Do not present this SSH transport as a production
API, and do not put credentials, headers, or private keys in its configuration.
