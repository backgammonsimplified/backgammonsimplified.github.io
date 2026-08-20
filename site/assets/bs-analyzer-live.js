(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.BMSAnalyzerLive = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const GNU_ID = /^[A-Za-z0-9+/]{14}:[A-Za-z0-9+/]{12}$/;
  const SUBMIT_URL = "/__bs_local_analysis/submit";
  const STATUS_ROOT = "/__bs_local_analysis/status/";

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
      gnuid: gnuid,
      decision: decision,
      dice: dice,
      engine: "gnu",
      analysis_setting: "1ply"
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
    const response = await fetch(url, options);
    let payload;
    try {
      payload = await response.json();
    } catch (_error) {
      throw new Error("The local analysis adapter returned an unreadable response.");
    }
    if (!response.ok || payload.ok === false) {
      const detail = payload.error && payload.error.message;
      const error = new Error(detail || "The local analysis adapter rejected the request.");
      error.code = payload.error && payload.error.code;
      throw error;
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

  function wait(milliseconds) {
    return new Promise(function (resolve) {
      setTimeout(resolve, milliseconds);
    });
  }

  async function pollUntilComplete(surface, analysisKey, options) {
    const interval = (options && options.pollInterval) || 250;
    const load = (options && options.fetchJson) || fetchJson;
    const render =
      (options && options.renderNodeAnalysisView) ||
      (globalThis.BMSAnalysisResults &&
        globalThis.BMSAnalysisResults.renderNodeAnalysisView);
    const results = surface.querySelector("[data-bs-analyzer-results]");
    for (;;) {
      const payload = await load(
        STATUS_ROOT + encodeURIComponent(analysisKey),
        { credentials: "same-origin" }
      );
      if (payload.status === "complete") {
        if (!payload.analysis_view || typeof render !== "function") {
          throw new Error("The shared Results Viewer could not mount the completed analysis.");
        }
        render(results, payload.analysis_view, {});
        setState(
          surface,
          "complete",
          options && options.cacheHit
            ? "Complete. Node reused the existing result."
            : "Complete. The Node result is shown below.",
          analysisKey
        );
        return payload;
      }
      if (["failed", "timed_out", "unsupported", "configuration_mismatch"].includes(payload.status)) {
        const error = new Error(
          (payload.error && payload.error.message) ||
            "The Node analysis did not complete."
        );
        error.code = payload.status;
        throw error;
      }
      setState(surface, "running", "GNU 1-ply analysis is running locally.", analysisKey);
      await wait(interval);
    }
  }

  async function submitSurface(surface, options) {
    const form = surface.querySelector("[data-bs-analyzer-form]");
    const button = form.querySelector('button[type="submit"]');
    const results = surface.querySelector("[data-bs-analyzer-results]");
    const load = (options && options.fetchJson) || fetchJson;
    setState(surface, "validating", "Checking the complete GNUID and decision input.");
    let request;
    try {
      request = formInput(form);
    } catch (error) {
      setState(surface, "invalid", error.message);
      return { ok: false, error: error };
    }

    button.disabled = true;
    results.replaceChildren();
    try {
      setState(surface, "starting", "Submitting to the local Node capability.");
      const submitted = await load(SUBMIT_URL, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request)
      });
      if (submitted.cache_hit) {
        setState(
          surface,
          "cache-hit",
          "Node found the completed analysis and skipped engine execution.",
          submitted.analysis_key
        );
      } else {
        setState(
          surface,
          "running",
          "Node accepted the request; GNU 1-ply analysis is running locally.",
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
        error.code === "unsupported_capability" || error.code === "unsupported"
          ? "unsupported"
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
    form.addEventListener("change", function (event) {
      if (event.target && event.target.name === "decision") {
        decisionChanged(form);
      }
    });
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      submitSurface(surface, options);
    });
    decisionChanged(form);
    setState(surface, "idle", "Enter a complete GNUID to begin.");
    return { submit: function () { return submitSurface(surface, options); } };
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
    GNU_ID: GNU_ID,
    STATUS_ROOT: STATUS_ROOT,
    SUBMIT_URL: SUBMIT_URL,
    decisionChanged: decisionChanged,
    fetchJson: fetchJson,
    mount: mount,
    mountAll: mountAll,
    normalizeInput: normalizeInput,
    pollUntilComplete: pollUntilComplete,
    setState: setState,
    submitSurface: submitSurface
  };
});
