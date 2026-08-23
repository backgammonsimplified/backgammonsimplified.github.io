(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.BMSAnalyzerLive = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const REQUEST_SCHEMA = "bms-analysis-submission-v2";
  const CONFIG_SCHEMA = "bms-analyzer-gateway-config-v1";
  const SUBMIT_RESPONSE_SCHEMA = "bms-analyzer-public-submit-v1";
  const STATUS_RESPONSE_SCHEMA = "bms-analyzer-public-status-v1";
  const RESULT_RESPONSE_SCHEMA = "bms-analyzer-public-result-v1";
  const NODE_VIEW_SCHEMA = "bms-node-analysis-view-v0";
  const CONFIG_URL = "/data/analyzer-production-gateway-v1.json";
  const API_BASE_PATH = "/v1/analyzer";
  const MAX_REQUEST_BYTES = 2048;
  const GNU_ID = /^[A-Za-z0-9+/]{14}:[A-Za-z0-9+/]{12}$/;
  const ANALYSIS_KEY = /^sha256-[0-9a-f]{64}$/;
  const PUBLIC_STATES = [
    "queued",
    "running",
    "complete",
    "cancelled",
    "failed",
    "timed_out",
    "unsupported",
    "configuration_mismatch"
  ];
  const FAILURE_STATES = [
    "failed",
    "timed_out",
    "unsupported",
    "configuration_mismatch",
    "cancelled"
  ];
  const PUBLIC_ERROR_MESSAGES = {
    malformed_request: "The analysis request is invalid.",
    request_too_large: "The analysis request is too large.",
    unsupported_capability: "That analysis capability is not available.",
    unknown_analysis: "That analysis request was not found.",
    rate_limited: "Too many analysis requests. Try again later.",
    cancelled: "The analysis request was cancelled.",
    failed: "The analysis could not be completed.",
    timed_out: "The analysis timed out.",
    unsupported: "That analysis capability is not available.",
    configuration_mismatch: "The analysis service is temporarily unavailable.",
    node_unavailable: "The analysis service is temporarily unavailable.",
    service_unavailable: "The analysis service is temporarily unavailable."
  };
  const DEVELOPMENT_ENDPOINTS = {
    submit: "/__bs_local_analysis/submit",
    statusRoot: "/__bs_local_analysis/status/",
    lookupRoot: "/__bs_local_analysis/lookup/"
  };

  function analyzerError(code) {
    const safeCode = Object.prototype.hasOwnProperty.call(PUBLIC_ERROR_MESSAGES, code)
      ? code
      : "service_unavailable";
    const error = new Error(PUBLIC_ERROR_MESSAGES[safeCode]);
    error.code = safeCode;
    return error;
  }

  function exactKeys(value, expected, label) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw analyzerError("service_unavailable");
    }
    const actual = Object.keys(value).sort();
    const wanted = expected.slice().sort();
    if (actual.length !== wanted.length || actual.some(function (key, index) {
      return key !== wanted[index];
    })) {
      const error = analyzerError("service_unavailable");
      error.contract = label;
      throw error;
    }
  }

  function normalizeInput(value) {
    const decision = String(value.decision || "").trim().toLowerCase();
    const gnuid = String(value.gnuid || "").trim();
    if (!GNU_ID.test(gnuid)) {
      throw new Error(
        "Enter a complete GNU Position ID and Match ID separated by a colon."
      );
    }
    if (decision !== "checker" && decision !== "cube") {
      throw new Error("Choose a checker or cube decision.");
    }
    let dice = null;
    if (decision === "checker") {
      dice = [Number(value.die1), Number(value.die2)];
      if (
        dice.some(function (die) {
          return !Number.isInteger(die) || die < 1 || die > 6;
        })
      ) {
        throw new Error("Checker analysis requires two dice values from 1 to 6.");
      }
    }
    return {
      schema_version: REQUEST_SCHEMA,
      engine: "gnu",
      decision_type: decision,
      analysis_setting: "1ply",
      position: { format: "gnuid", id: gnuid },
      dice: dice
    };
  }

  function formInput(form) {
    const data = new FormData(form);
    return normalizeInput({
      gnuid: data.get("gnuid"),
      decision: data.get("decision"),
      die1: data.get("die1"),
      die2: data.get("die2")
    });
  }

  async function fetchJson(url, options) {
    let response;
    try {
      response = await fetch(url, options);
    } catch (_error) {
      throw analyzerError("service_unavailable");
    }
    let payload;
    try {
      payload = await response.json();
    } catch (_error) {
      throw analyzerError("service_unavailable");
    }
    if (!response.ok || payload.ok === false || payload.error) {
      const code = payload && payload.error && payload.error.code;
      throw analyzerError(code);
    }
    return payload;
  }

  function setState(surface, state, message, analysisKey) {
    surface.dataset.bsAnalyzerState = state;
    const label = surface.querySelector("[data-bs-analyzer-state-label]");
    const detail = surface.querySelector("[data-bs-analyzer-state-detail]");
    const key = surface.querySelector("[data-bs-analyzer-key]");
    if (label) label.textContent = state.replace(/-/g, " ");
    if (detail) detail.textContent = message;
    if (key) {
      key.textContent = analysisKey ? "Analysis key: " + analysisKey : "";
      key.hidden = !analysisKey;
    }
  }

  function decisionChanged(form) {
    const decision = form.querySelector('input[name="decision"]:checked');
    const checker = decision && decision.value === "checker";
    form.querySelectorAll("[data-bs-checker-die]").forEach(function (input) {
      input.disabled = !checker;
      input.required = checker;
    });
    const group = form.querySelector("[data-bs-checker-dice]");
    if (group) group.hidden = !checker;
  }

  function validateAnalysisKey(value) {
    const key = String(value || "").trim();
    if (!ANALYSIS_KEY.test(key)) {
      const error = new Error("The server analysis key is invalid.");
      error.code = "malformed_request";
      throw error;
    }
    return key;
  }

  function validateSubmitResponse(value) {
    exactKeys(value, ["schema_version", "analysis_key", "status", "cache_hit"], "submit");
    if (
      value.schema_version !== SUBMIT_RESPONSE_SCHEMA ||
      !ANALYSIS_KEY.test(value.analysis_key) ||
      !["queued", "running", "complete"].includes(value.status) ||
      typeof value.cache_hit !== "boolean"
    ) {
      throw analyzerError("service_unavailable");
    }
    return value;
  }

  function validateStatusResponse(value, expectedKey) {
    exactKeys(value, ["schema_version", "analysis_key", "status", "cache_hit"], "status");
    if (
      value.schema_version !== STATUS_RESPONSE_SCHEMA ||
      value.analysis_key !== expectedKey ||
      !PUBLIC_STATES.includes(value.status) ||
      typeof value.cache_hit !== "boolean"
    ) {
      throw analyzerError("service_unavailable");
    }
    return value;
  }

  function rejectPrivateText(value) {
    if (Array.isArray(value)) {
      value.forEach(rejectPrivateText);
      return;
    }
    if (value && typeof value === "object") {
      Object.keys(value).forEach(function (key) {
        rejectPrivateText(value[key]);
      });
      return;
    }
    if (typeof value !== "string") return;
    if (
      /\bssh\b|traceback|authorization:|bearer\s|private key|\b[A-Za-z0-9.-]+\.(internal|local)\b/i.test(value) ||
      /^[A-Za-z]:[\\/]/.test(value) ||
      /^\/(home|srv|etc|var|tmp|opt|root|mnt)\//.test(value)
    ) {
      throw analyzerError("service_unavailable");
    }
  }

  function validateResultResponse(value, expectedKey) {
    exactKeys(value, ["schema_version", "analysis_key", "status", "analysis_view"], "result");
    if (
      value.schema_version !== RESULT_RESPONSE_SCHEMA ||
      value.analysis_key !== expectedKey ||
      value.status !== "complete" ||
      !value.analysis_view ||
      value.analysis_view.schema_version !== NODE_VIEW_SCHEMA ||
      value.analysis_view.analysis_key !== expectedKey
    ) {
      throw analyzerError("service_unavailable");
    }
    rejectPrivateText(value.analysis_view);
    return value;
  }

  function isLoopbackLocation(locationValue) {
    if (!locationValue) return false;
    const hostname = String(locationValue.hostname || "").toLowerCase();
    return ["127.0.0.1", "localhost", "::1", "[::1]"].includes(hostname);
  }

  function validatePublicOrigin(value, label) {
    let parsed;
    try {
      parsed = new URL(value);
    } catch (_error) {
      throw analyzerError("configuration_mismatch");
    }
    const hostname = parsed.hostname.toLowerCase();
    const privateHost =
      hostname === "localhost" ||
      hostname.endsWith(".local") ||
      hostname === "127.0.0.1" ||
      hostname === "::1" ||
      /^10\./.test(hostname) ||
      /^192\.168\./.test(hostname) ||
      /^172\.(1[6-9]|2[0-9]|3[01])\./.test(hostname);
    if (
      parsed.protocol !== "https:" ||
      parsed.username ||
      parsed.password ||
      parsed.port ||
      (parsed.pathname !== "/" && parsed.pathname !== "") ||
      parsed.search ||
      parsed.hash ||
      privateHost
    ) {
      const error = analyzerError("configuration_mismatch");
      error.contract = label;
      throw error;
    }
    return parsed.origin;
  }

  function validateGatewayConfig(value, locationValue) {
    exactKeys(
      value,
      [
        "schema_version",
        "enabled",
        "gateway_origin",
        "api_base_path",
        "allowed_site_origin",
        "max_request_bytes"
      ],
      "gateway config"
    );
    if (
      value.schema_version !== CONFIG_SCHEMA ||
      typeof value.enabled !== "boolean" ||
      value.api_base_path !== API_BASE_PATH ||
      value.max_request_bytes !== MAX_REQUEST_BYTES
    ) {
      throw analyzerError("configuration_mismatch");
    }
    const allowedSiteOrigin = validatePublicOrigin(
      value.allowed_site_origin,
      "allowed site origin"
    );
    if (locationValue && locationValue.origin !== allowedSiteOrigin) {
      throw analyzerError("configuration_mismatch");
    }
    if (!value.enabled) {
      if (value.gateway_origin !== null) {
        throw analyzerError("configuration_mismatch");
      }
      return Object.freeze({ enabled: false });
    }
    return Object.freeze({
      enabled: true,
      gatewayOrigin: validatePublicOrigin(value.gateway_origin, "gateway origin"),
      apiBasePath: API_BASE_PATH,
      maxRequestBytes: MAX_REQUEST_BYTES
    });
  }

  function mapDevelopmentStatus(value, key) {
    if (!value || value.analysis_key !== key || !PUBLIC_STATES.includes(value.status)) {
      throw analyzerError("service_unavailable");
    }
    return validateStatusResponse(
      {
        schema_version: STATUS_RESPONSE_SCHEMA,
        analysis_key: key,
        status: value.status,
        cache_hit: Boolean(value.cache_hit)
      },
      key
    );
  }

  function createDevelopmentTransport(locationValue) {
    if (!isLoopbackLocation(locationValue)) {
      throw analyzerError("configuration_mismatch");
    }
    return Object.freeze({
      kind: "loopback-development",
      async submit(request) {
        const raw = await fetchJson(DEVELOPMENT_ENDPOINTS.submit, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request)
        });
        return validateSubmitResponse({
          schema_version: SUBMIT_RESPONSE_SCHEMA,
          analysis_key: raw.analysis_key,
          status: raw.status,
          cache_hit: Boolean(raw.cache_hit)
        });
      },
      async status(analysisKey) {
        const key = validateAnalysisKey(analysisKey);
        const raw = await fetchJson(
          DEVELOPMENT_ENDPOINTS.statusRoot + encodeURIComponent(key),
          { credentials: "same-origin" }
        );
        return mapDevelopmentStatus(raw, key);
      },
      async lookup(analysisKey) {
        const key = validateAnalysisKey(analysisKey);
        const raw = await fetchJson(
          DEVELOPMENT_ENDPOINTS.lookupRoot + encodeURIComponent(key),
          { credentials: "same-origin" }
        );
        return mapDevelopmentStatus(raw, key);
      },
      async result(analysisKey) {
        const key = validateAnalysisKey(analysisKey);
        const raw = await fetchJson(
          DEVELOPMENT_ENDPOINTS.statusRoot + encodeURIComponent(key),
          { credentials: "same-origin" }
        );
        return validateResultResponse(
          {
            schema_version: RESULT_RESPONSE_SCHEMA,
            analysis_key: key,
            status: raw.status,
            analysis_view: raw.analysis_view
          },
          key
        );
      }
    });
  }

  function createProductionTransport(config) {
    if (!config || !config.enabled) {
      throw analyzerError("service_unavailable");
    }
    const base = config.gatewayOrigin + config.apiBasePath;
    return Object.freeze({
      kind: "production-https",
      async submit(request) {
        const body = JSON.stringify(request);
        if (new TextEncoder().encode(body).length > config.maxRequestBytes) {
          throw analyzerError("request_too_large");
        }
        return validateSubmitResponse(await fetchJson(base + "/requests", {
          method: "POST",
          mode: "cors",
          credentials: "omit",
          referrerPolicy: "strict-origin-when-cross-origin",
          headers: { "Content-Type": "application/json" },
          body: body
        }));
      },
      async status(analysisKey) {
        const key = validateAnalysisKey(analysisKey);
        const value = await fetchJson(
          base + "/requests/" + encodeURIComponent(key) + "/status",
          { mode: "cors", credentials: "omit", referrerPolicy: "strict-origin-when-cross-origin" }
        );
        return validateStatusResponse(value, key);
      },
      async lookup(analysisKey) {
        return this.status(analysisKey);
      },
      async result(analysisKey) {
        const key = validateAnalysisKey(analysisKey);
        const value = await fetchJson(
          base + "/requests/" + encodeURIComponent(key) + "/result",
          { mode: "cors", credentials: "omit", referrerPolicy: "strict-origin-when-cross-origin" }
        );
        return validateResultResponse(value, key);
      }
    });
  }

  async function resolveTransport(options) {
    const locationValue =
      (options && options.location) ||
      (typeof globalThis.location !== "undefined" ? globalThis.location : null);
    if (options && options.transport) return options.transport;
    if (isLoopbackLocation(locationValue)) {
      return createDevelopmentTransport(locationValue);
    }
    const load = (options && options.fetchConfig) || fetchJson;
    const config = validateGatewayConfig(
      await load(CONFIG_URL, { credentials: "same-origin", cache: "no-store" }),
      locationValue
    );
    return createProductionTransport(config);
  }

  function wait(milliseconds) {
    return new Promise(function (resolve) {
      setTimeout(resolve, milliseconds);
    });
  }

  async function pollUntilComplete(surface, analysisKey, options) {
    const interval = (options && options.pollInterval) || 250;
    const transport = options && options.transport;
    const render =
      (options && options.renderNodeAnalysisView) ||
      (globalThis.BMSAnalysisResults &&
        globalThis.BMSAnalysisResults.renderNodeAnalysisView);
    const results = surface.querySelector("[data-bs-analyzer-results]");
    if (!transport) throw analyzerError("service_unavailable");
    for (;;) {
      const payload = await transport.status(analysisKey);
      if (payload.status === "complete") {
        const completed = await transport.result(analysisKey);
        if (!completed.analysis_view || typeof render !== "function") {
          throw analyzerError("service_unavailable");
        }
        render(results, completed.analysis_view, {});
        setState(
          surface,
          "complete",
          options && options.existingLookup
            ? "Complete. The accepted Node result is shown below."
            : options && options.cacheHit
              ? "Complete. Node reused the existing result."
              : "Complete. The Node result is shown below.",
          analysisKey
        );
        return completed;
      }
      if (FAILURE_STATES.includes(payload.status)) {
        throw analyzerError(payload.status);
      }
      if (payload.status === "queued") {
        setState(surface, "queued", "The Node request is queued.", analysisKey);
      } else if (payload.status === "running") {
        setState(surface, "running", "GNU 1-ply analysis is running on Node.", analysisKey);
      } else {
        throw analyzerError("configuration_mismatch");
      }
      await wait(interval);
    }
  }

  async function loadAnalysisKey(surface, analysisKey, options) {
    const results = surface.querySelector("[data-bs-analyzer-results]");
    const transport = options && options.transport;
    let key;
    try {
      key = validateAnalysisKey(analysisKey);
    } catch (error) {
      setState(surface, "invalid", error.message);
      return { ok: false, error: error };
    }
    if (!transport) {
      const error = analyzerError("service_unavailable");
      setState(surface, "unavailable", error.message, key);
      return { ok: false, error: error };
    }
    results.replaceChildren();
    try {
      setState(surface, "looking-up", "Looking up the accepted Node result.", key);
      const payload = await transport.lookup(key);
      if (payload.status === "complete") {
        setState(surface, "already-complete", "Node found an already completed result.", key);
      }
      return await pollUntilComplete(
        surface,
        key,
        Object.assign({}, options || {}, { existingLookup: true })
      );
    } catch (error) {
      setState(
        surface,
        FAILURE_STATES.includes(error.code) ? error.code : "failed",
        error.message,
        key
      );
      return { ok: false, error: error };
    }
  }

  async function submitSurface(surface, options) {
    const form = surface.querySelector("[data-bs-analyzer-form]");
    const button = form.querySelector('button[type="submit"]');
    const results = surface.querySelector("[data-bs-analyzer-results]");
    const transport = options && options.transport;
    setState(surface, "validating", "Checking the complete GNUID and decision input.");
    let request;
    try {
      request = formInput(form);
    } catch (error) {
      setState(surface, "invalid", error.message);
      return { ok: false, error: error };
    }
    if (!transport) {
      const error = analyzerError("service_unavailable");
      setState(surface, "unavailable", error.message);
      return { ok: false, error: error };
    }

    button.disabled = true;
    results.replaceChildren();
    try {
      setState(surface, "submitting", "Looking up or submitting through the Node boundary.");
      const submitted = await transport.submit(request);
      if (submitted.cache_hit) {
        setState(
          surface,
          "cache-hit",
          "Node found the completed analysis and skipped engine execution.",
          submitted.analysis_key
        );
      } else if (submitted.status === "queued") {
        setState(
          surface,
          "queued",
          "Node accepted the request and placed it in its queue.",
          submitted.analysis_key
        );
      } else if (submitted.status === "running") {
        setState(
          surface,
          "running",
          "GNU 1-ply analysis is running on Node.",
          submitted.analysis_key
        );
      } else if (submitted.status === "complete") {
        setState(
          surface,
          "already-complete",
          "Node found an already completed result.",
          submitted.analysis_key
        );
      }
      return await pollUntilComplete(
        surface,
        submitted.analysis_key,
        Object.assign({}, options || {}, { cacheHit: submitted.cache_hit })
      );
    } catch (error) {
      setState(
        surface,
        error.code === "unsupported_capability"
          ? "unsupported"
          : FAILURE_STATES.includes(error.code)
            ? error.code
            : "failed",
        error.message
      );
      return { ok: false, error: error };
    } finally {
      button.disabled = false;
    }
  }

  function mount(surface, options) {
    const form = surface.querySelector("[data-bs-analyzer-form]");
    if (!form) return null;
    const button = form.querySelector('button[type="submit"]');
    let activeOptions = Object.assign({}, options || {});
    let transport = activeOptions.transport || null;
    let lookupStarted = false;

    function initialLookup(controller) {
      if (lookupStarted || typeof globalThis.location === "undefined") return;
      lookupStarted = true;
      const key = new URLSearchParams(globalThis.location.search).get("analysis_key");
      if (key) controller.lookup(key);
    }

    const controller = {
      ready: null,
      lookup: async function (key) {
        await controller.ready;
        return loadAnalysisKey(surface, key, activeOptions);
      },
      submit: async function () {
        await controller.ready;
        return submitSurface(surface, activeOptions);
      }
    };

    form.addEventListener("change", function (event) {
      if (event.target && event.target.name === "decision") {
        decisionChanged(form);
      }
    });
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      controller.submit();
    });
    decisionChanged(form);
    button.disabled = true;
    setState(surface, "configuring", "Checking the public Analyzer gateway.");
    controller.ready = (transport ? Promise.resolve(transport) : resolveTransport(activeOptions))
      .then(function (resolved) {
        transport = resolved;
        activeOptions.transport = resolved;
        button.disabled = false;
        setState(surface, "idle", "Enter a complete GNUID to begin.");
        initialLookup(controller);
        return resolved;
      })
      .catch(function (_error) {
        button.disabled = true;
        setState(
          surface,
          "unavailable",
          "Public analysis requests are unavailable until the production gateway is commissioned."
        );
        return null;
      });
    return controller;
  }

  function mountAll() {
    document.querySelectorAll("[data-bs-live-analyzer]").forEach(function (surface) {
      mount(surface);
    });
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", mountAll, { once: true });
    } else {
      mountAll();
    }
  }

  return {
    ANALYSIS_KEY: ANALYSIS_KEY,
    API_BASE_PATH: API_BASE_PATH,
    CONFIG_SCHEMA: CONFIG_SCHEMA,
    CONFIG_URL: CONFIG_URL,
    DEVELOPMENT_ENDPOINTS: DEVELOPMENT_ENDPOINTS,
    GNU_ID: GNU_ID,
    MAX_REQUEST_BYTES: MAX_REQUEST_BYTES,
    NODE_VIEW_SCHEMA: NODE_VIEW_SCHEMA,
    REQUEST_SCHEMA: REQUEST_SCHEMA,
    RESULT_RESPONSE_SCHEMA: RESULT_RESPONSE_SCHEMA,
    STATUS_RESPONSE_SCHEMA: STATUS_RESPONSE_SCHEMA,
    SUBMIT_RESPONSE_SCHEMA: SUBMIT_RESPONSE_SCHEMA,
    createDevelopmentTransport: createDevelopmentTransport,
    createProductionTransport: createProductionTransport,
    decisionChanged: decisionChanged,
    fetchJson: fetchJson,
    isLoopbackLocation: isLoopbackLocation,
    loadAnalysisKey: loadAnalysisKey,
    mount: mount,
    mountAll: mountAll,
    normalizeInput: normalizeInput,
    pollUntilComplete: pollUntilComplete,
    resolveTransport: resolveTransport,
    setState: setState,
    submitSurface: submitSurface,
    validateGatewayConfig: validateGatewayConfig,
    validateResultResponse: validateResultResponse,
    validateStatusResponse: validateStatusResponse,
    validateSubmitResponse: validateSubmitResponse
  };
});
