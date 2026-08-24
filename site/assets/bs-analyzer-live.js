(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.BMSAnalyzerLive = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const GNU_ID = /^[A-Za-z0-9+/]{14}:[A-Za-z0-9+/]{12}$/;
  const ANALYSIS_KEY = /^sha256-[0-9a-f]{64}$/;
  const SUBMIT_URL = "/__bs_local_analysis/submit";
  const STATUS_ROOT = "/__bs_local_analysis/status/";
  const LOOKUP_ROOT = "/__bs_local_analysis/lookup/";
  const FAILURE_STATES = [
    "failed",
    "timed_out",
    "unsupported",
    "configuration_mismatch",
    "cancelled"
  ];

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
      throw new Error("The Analyzer development adapter returned an unreadable response.");
    }
    if (!response.ok || payload.ok === false) {
      const detail = payload.error && payload.error.message;
      const error = new Error(detail || "The Analyzer development adapter rejected the request.");
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

  function originalBoardSnapshot(surface, gnuid) {
    const source = surface.querySelector(".bs-editor-board-shell");
    if (!source || typeof source.cloneNode !== "function") return null;
    const snapshot = source.cloneNode(true);
    snapshot.querySelectorAll("[id]").forEach(function (node) {
      node.removeAttribute("id");
    });
    snapshot.querySelectorAll("button,[tabindex],input,select,textarea").forEach(function (node) {
      node.setAttribute("tabindex", "-1");
      node.setAttribute("aria-hidden", "true");
    });
    snapshot.classList.add("bs-analysis-results-editor-snapshot");
    return {
      alt: "Original analyzed position " + gnuid,
      render: function () { return snapshot.cloneNode(true); }
    };
  }

  function returnToEditor(surface) {
    const form = surface.querySelector("[data-bs-analyzer-form]");
    if (!form) return;
    form.scrollIntoView({ behavior: "smooth", block: "start" });
    const focusTarget = form.querySelector("[data-bs-editor-board] [data-slot]") ||
      form.querySelector("button, input, select, textarea");
    if (focusTarget && typeof focusTarget.focus === "function") {
      focusTarget.focus({ preventScroll: true });
    }
  }

  function resultViewerOptions(surface, options) {
    return {
      boardOverride: options && options.originalBoardSnapshot,
      onReturnToEditor: function () { returnToEditor(surface); }
    };
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
        render(results, payload.analysis_view, resultViewerOptions(surface, options));
        setState(
          surface,
          "complete",
          options && options.existingLookup
            ? "Complete. The accepted server Node result is shown below."
            : options && options.cacheHit
              ? "Complete. Node reused the existing result."
              : "Complete. The server Node result is shown below.",
          analysisKey
        );
        return payload;
      }
      if (FAILURE_STATES.includes(payload.status)) {
        const error = new Error(
          (payload.error && payload.error.message) ||
            "The Node analysis did not complete."
        );
        error.code = payload.status;
        throw error;
      }
      if (payload.status === "queued") {
        setState(surface, "queued", "The server Node request is queued.", analysisKey);
      } else if (payload.status === "running") {
        setState(surface, "running", "GNU 1-ply analysis is running on the server Node.", analysisKey);
      } else {
        const error = new Error("The server Node returned an unsupported lifecycle state.");
        error.code = "configuration_mismatch";
        throw error;
      }
      await wait(interval);
    }
  }

  async function loadAnalysisKey(surface, analysisKey, options) {
    const key = String(analysisKey || "").trim();
    const results = surface.querySelector("[data-bs-analyzer-results]");
    const load = (options && options.fetchJson) || fetchJson;
    if (!ANALYSIS_KEY.test(key)) {
      const error = new Error("The server analysis key is invalid.");
      setState(surface, "invalid", error.message);
      return { ok: false, error: error };
    }
    results.replaceChildren();
    try {
      setState(surface, "looking-up", "Looking up the accepted server Node result.", key);
      const payload = await load(LOOKUP_ROOT + encodeURIComponent(key), {
        credentials: "same-origin"
      });
      if (payload.status === "complete") {
        setState(surface, "already-complete", "Node found an already completed server result.", key);
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
    const load = (options && options.fetchJson) || fetchJson;
    setState(surface, "validating", "Checking the complete GNUID and decision input.");
    let request;
    try {
      request = formInput(form);
    } catch (error) {
      setState(surface, "invalid", error.message);
      return { ok: false, error: error };
    }

    const boardSnapshot = originalBoardSnapshot(surface, request.gnuid);

    button.disabled = true;
    results.replaceChildren();
    try {
      setState(surface, "submitting", "Looking up or submitting through the server Node boundary.");
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
      } else if (submitted.status === "queued") {
        setState(
          surface,
          "queued",
          "Node accepted the request and placed it in the server queue.",
          submitted.analysis_key
        );
      } else if (submitted.status === "running") {
        setState(
          surface,
          "running",
          "GNU 1-ply analysis is running on the server Node.",
          submitted.analysis_key
        );
      } else if (submitted.status === "complete") {
        setState(
          surface,
          "already-complete",
          "Node found an already completed server result.",
          submitted.analysis_key
        );
      }
      return await pollUntilComplete(
        surface,
        submitted.analysis_key,
        Object.assign({}, options || {}, {
          cacheHit: submitted.cache_hit,
          originalBoardSnapshot: boardSnapshot
        })
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
    form.addEventListener("change", function (event) {
      if (event.target && event.target.name === "decision") {
        decisionChanged(form);
      }
    });
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      submitSurface(surface, options);
    });
    form.addEventListener("bs-position-editor-change", function () {
      if (surface.dataset.bsAnalyzerState === "complete") {
        setState(
          surface,
          "edited",
          "The editor has changed since the displayed analysis. Resubmit to analyze the edited position."
        );
      }
    });
    decisionChanged(form);
    setState(surface, "idle", "Edit the board and position facts, then analyze.");
    const controller = {
      lookup: function (key) { return loadAnalysisKey(surface, key, options); },
      submit: function () { return submitSurface(surface, options); }
    };
    if (typeof globalThis.location !== "undefined") {
      const key = new URLSearchParams(globalThis.location.search).get("analysis_key");
      if (key) controller.lookup(key);
    }
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
    GNU_ID: GNU_ID,
    LOOKUP_ROOT: LOOKUP_ROOT,
    STATUS_ROOT: STATUS_ROOT,
    SUBMIT_URL: SUBMIT_URL,
    decisionChanged: decisionChanged,
    fetchJson: fetchJson,
    loadAnalysisKey: loadAnalysisKey,
    mount: mount,
    mountAll: mountAll,
    normalizeInput: normalizeInput,
    originalBoardSnapshot: originalBoardSnapshot,
    pollUntilComplete: pollUntilComplete,
    resultViewerOptions: resultViewerOptions,
    returnToEditor: returnToEditor,
    setState: setState,
    submitSurface: submitSurface
  };
});
