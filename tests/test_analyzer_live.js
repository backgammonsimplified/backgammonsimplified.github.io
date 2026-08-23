const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const live = require("../site/assets/bs-analyzer-live.js");
const viewer = require("../site/assets/bs-analysis-results.js");
const root = path.resolve(__dirname, "..");

const checker = live.normalizeInput({
  gnuid: " 4HPwATDgc/ABMA:cAnqAAAAAAAE ",
  decision: "checker",
  die1: "4",
  die2: "2"
});
assert.deepEqual(checker, {
  schema_version: "bms-analysis-submission-v2",
  engine: "gnu",
  decision_type: "checker",
  analysis_setting: "1ply",
  position: { format: "gnuid", id: "4HPwATDgc/ABMA:cAnqAAAAAAAE" },
  dice: [4, 2]
});
assert.deepEqual(
  live.normalizeInput({
    gnuid: "4HPwATDgc/ABMA:cAngAAAAAAAE",
    decision: "cube",
    die1: "not-used",
    die2: "not-used"
  }).dice,
  null
);
assert.throws(
  () => live.normalizeInput({ gnuid: "4HPwATDgc/ABMA", decision: "cube" }),
  /complete GNU Position ID and Match ID/
);
assert.throws(
  () =>
    live.normalizeInput({
      gnuid: "4HPwATDgc/ABMA:cAnqAAAAAAAE",
      decision: "checker",
      die1: "0",
      die2: "7"
    }),
  /two dice values/
);

const checkerView = JSON.parse(
  fs.readFileSync(
    path.join(root, "tests/fixtures/node-k001-checker-analysis-view.json"),
    "utf8"
  )
);
const cubeView = JSON.parse(
  fs.readFileSync(
    path.join(root, "tests/fixtures/node-k001-cube-analysis-view.json"),
    "utf8"
  )
);
const checkerModel = viewer.analysisModelFromNodeView(checkerView);
const cubeModel = viewer.analysisModelFromNodeView(cubeView);

assert.equal(checkerModel.fixture, false);
assert.equal(checkerModel.source_schema, viewer.NODE_ANALYSIS_VIEW_SCHEMA);
assert.equal(checkerModel.analysis_kind, "checker");
assert.equal(checkerModel.original_board, null);
assert.equal(checkerModel.candidates.length, checkerView.checker.candidates.length);
assert.equal(checkerModel.candidates[0].move, checkerView.checker.candidates[0].notation);
assert.equal(checkerModel.metadata.parser, "gnu-text-parser-v1");
assert.equal(cubeModel.analysis_kind, "cube");
assert.equal(cubeModel.actions.length, cubeView.cube.actions.length);
assert.equal(cubeModel.actions[0].label, cubeView.cube.actions[0].label);
assert.equal(cubeModel.context.dice, null);
assert.throws(
  () => viewer.analysisModelFromNodeView({ schema_version: "invented-view-v1" }),
  /Unsupported Node analysis-view schema/
);

assert.match(checkerView.analysis_key, live.ANALYSIS_KEY);
assert.equal(live.DEVELOPMENT_ENDPOINTS.lookupRoot, "/__bs_local_analysis/lookup/");
assert.equal(live.MAX_REQUEST_BYTES, 2048);
assert.equal(live.isLoopbackLocation({ hostname: "127.0.0.1" }), true);
assert.equal(live.isLoopbackLocation({ hostname: "backgammonsimplified.github.io" }), false);

const publicLocation = {
  origin: "https://backgammonsimplified.github.io",
  hostname: "backgammonsimplified.github.io"
};
const disabled = live.validateGatewayConfig(
  {
    schema_version: live.CONFIG_SCHEMA,
    enabled: false,
    gateway_origin: null,
    api_base_path: live.API_BASE_PATH,
    allowed_site_origin: publicLocation.origin,
    max_request_bytes: live.MAX_REQUEST_BYTES
  },
  publicLocation
);
assert.equal(disabled.enabled, false);
const enabled = live.validateGatewayConfig(
  {
    schema_version: live.CONFIG_SCHEMA,
    enabled: true,
    gateway_origin: "https://analysis-api.example.org",
    api_base_path: live.API_BASE_PATH,
    allowed_site_origin: publicLocation.origin,
    max_request_bytes: live.MAX_REQUEST_BYTES
  },
  publicLocation
);
assert.equal(enabled.gatewayOrigin, "https://analysis-api.example.org");
assert.throws(
  () => live.validateGatewayConfig({
    schema_version: live.CONFIG_SCHEMA,
    enabled: true,
    gateway_origin: "http://private-node.internal:8080/private",
    api_base_path: live.API_BASE_PATH,
    allowed_site_origin: publicLocation.origin,
    max_request_bytes: live.MAX_REQUEST_BYTES
  }, publicLocation),
  /temporarily unavailable/
);
assert.throws(
  () => live.validateGatewayConfig({
    schema_version: live.CONFIG_SCHEMA,
    enabled: false,
    gateway_origin: null,
    api_base_path: live.API_BASE_PATH,
    allowed_site_origin: publicLocation.origin,
    max_request_bytes: live.MAX_REQUEST_BYTES,
    token: "must-never-be-a-browser-field"
  }, publicLocation),
  /temporarily unavailable/
);

function fakeSurface() {
  const label = { textContent: "" };
  const detail = { textContent: "" };
  const key = { textContent: "", hidden: true };
  const results = { replaceChildren() {} };
  return {
    dataset: {},
    detail: detail,
    querySelector(selector) {
      return {
        "[data-bs-analyzer-state-label]": label,
        "[data-bs-analyzer-state-detail]": detail,
        "[data-bs-analyzer-key]": key,
        "[data-bs-analyzer-results]": results
      }[selector];
    }
  };
}

(async function () {
  const originalFetch = global.fetch;
  const surface = fakeSurface();
  const states = [];
  const payloads = ["queued", "running", "complete"];
  const transport = {
    async status(key) {
      states.push(surface.dataset.bsAnalyzerState);
      return {
        schema_version: live.STATUS_RESPONSE_SCHEMA,
        analysis_key: key,
        status: payloads.shift(),
        cache_hit: false
      };
    },
    async result(key) {
      return {
        schema_version: live.RESULT_RESPONSE_SCHEMA,
        analysis_key: key,
        status: "complete",
        analysis_view: checkerView
      };
    }
  };
  live.setState(surface, "queued", "queued");
  await live.pollUntilComplete(surface, checkerView.analysis_key, {
    pollInterval: 1,
    transport: transport,
    renderNodeAnalysisView: function (_target, value) {
      assert.equal(value.analysis_key, checkerView.analysis_key);
    }
  });
  assert.deepEqual(states, ["queued", "queued", "running"]);
  assert.equal(surface.dataset.bsAnalyzerState, "complete");

  const lookupSurface = fakeSurface();
  const lookupStates = [];
  const lookupTransport = {
    async lookup(key) {
      lookupStates.push(lookupSurface.dataset.bsAnalyzerState);
      return {
        schema_version: live.STATUS_RESPONSE_SCHEMA,
        analysis_key: key,
        status: "complete",
        cache_hit: true
      };
    },
    async status(key) {
      lookupStates.push(lookupSurface.dataset.bsAnalyzerState);
      return {
        schema_version: live.STATUS_RESPONSE_SCHEMA,
        analysis_key: key,
        status: "complete",
        cache_hit: true
      };
    },
    async result(key) {
      return {
        schema_version: live.RESULT_RESPONSE_SCHEMA,
        analysis_key: key,
        status: "complete",
        analysis_view: checkerView
      };
    }
  };
  await live.loadAnalysisKey(lookupSurface, checkerView.analysis_key, {
    pollInterval: 1,
    transport: lookupTransport,
    renderNodeAnalysisView: function () {}
  });
  assert.deepEqual(lookupStates, ["looking-up", "already-complete"]);
  assert.equal(lookupSurface.dataset.bsAnalyzerState, "complete");

  assert.throws(
    () => live.validateSubmitResponse({
      schema_version: live.SUBMIT_RESPONSE_SCHEMA,
      analysis_key: checkerView.analysis_key,
      status: "queued",
      cache_hit: false,
      private_path: "/srv/node/private"
    }),
    /temporarily unavailable/
  );
  assert.throws(
    () => live.validateResultResponse({
      schema_version: live.RESULT_RESPONSE_SCHEMA,
      analysis_key: checkerView.analysis_key,
      status: "complete",
      analysis_view: Object.assign({}, checkerView, {
        warning: "Traceback from ssh private-node.internal at /srv/private/result.json"
      })
    }, checkerView.analysis_key),
    /temporarily unavailable/
  );

  const calls = [];
  global.fetch = async function (url, options) {
    calls.push({ url: url, options: options });
    let payload;
    if (url.endsWith("/requests")) {
      payload = {
        schema_version: live.SUBMIT_RESPONSE_SCHEMA,
        analysis_key: checkerView.analysis_key,
        status: "complete",
        cache_hit: true
      };
    } else if (url.endsWith("/status")) {
      payload = {
        schema_version: live.STATUS_RESPONSE_SCHEMA,
        analysis_key: checkerView.analysis_key,
        status: "complete",
        cache_hit: true
      };
    } else {
      payload = {
        schema_version: live.RESULT_RESPONSE_SCHEMA,
        analysis_key: checkerView.analysis_key,
        status: "complete",
        analysis_view: checkerView
      };
    }
    return { ok: true, async json() { return payload; } };
  };
  const production = live.createProductionTransport(enabled);
  await production.submit(checker);
  await production.status(checkerView.analysis_key);
  await production.result(checkerView.analysis_key);
  assert.deepEqual(calls.map((call) => call.url), [
    "https://analysis-api.example.org/v1/analyzer/requests",
    "https://analysis-api.example.org/v1/analyzer/requests/" + checkerView.analysis_key + "/status",
    "https://analysis-api.example.org/v1/analyzer/requests/" + checkerView.analysis_key + "/result"
  ]);
  assert.equal(calls.every((call) => call.options.credentials === "omit"), true);
  assert.deepEqual(Object.keys(calls[0].options.headers), ["Content-Type"]);
  await assert.rejects(production.status("../../etc/passwd"), /analysis key is invalid/);

  global.fetch = async function () {
    return {
      ok: false,
      async json() {
        return {
          error: {
            code: "bridge_failure",
            message: "ssh private-node.internal /srv/private Traceback"
          }
        };
      }
    };
  };
  await assert.rejects(
    live.fetchJson("https://analysis-api.example.org/v1/analyzer/requests", {}),
    function (error) {
      assert.equal(error.code, "service_unavailable");
      assert.doesNotMatch(error.message, /ssh|private-node|srv|Traceback/i);
      return true;
    }
  );
  global.fetch = originalFetch;

  console.log("Analyzer production protocol, lifecycle, and shared-viewer mapping passed");
})().catch(function (error) {
  console.error(error);
  process.exitCode = 1;
});
