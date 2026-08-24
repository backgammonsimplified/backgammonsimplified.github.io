(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.BMSAnalysisResults = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const FIXTURE_SCHEMA = "bs-analysis-results-viewer-fixture-v1";
  const NODE_ANALYSIS_VIEW_SCHEMA = "b" + "ms-node-analysis-view-v0";
  const FIXTURE_KINDS = new Set([
    "synthetic",
    "retained-analysis",
    "canonical-analysis"
  ]);
  const requestCache = new Map();
  const OUTCOME_SEGMENTS = [
    ["win_backgammon", "Win backgammon", "win-bg"],
    ["win_gammon", "Win gammon", "win-gammon"],
    ["win_single", "Win single", "win-single"],
    ["lose_single", "Lose single", "lose-single"],
    ["lose_gammon", "Lose gammon", "lose-gammon"],
    ["lose_backgammon", "Lose backgammon", "lose-bg"]
  ];
  const PROBABILITY_COMPARISON_ROWS = [
    ["win", "Win"],
    ["win_gammon_or_better", "Win gammon or better"],
    ["win_backgammon", "Win backgammon"],
    ["lose", "Lose"],
    ["lose_gammon_or_worse", "Lose gammon or worse"],
    ["lose_backgammon", "Lose backgammon"]
  ];
  const HADD_HEADS = ["q_win", "q_wg", "q_wbg", "q_lg", "q_lbg"];
  const HADD_ARCHITECTURE = "ridge-ranking-hadd-value-explanation-sidecar-v1";
  const HADD_PERSPECTIVE = "normalized_static_post_move_next_player_on_roll";

  function optionalText(value, fallback) {
    return value === null || value === undefined || value === ""
      ? fallback || "Not supplied"
      : String(value);
  }

  function formatNumber(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "Not supplied";
    }
    const number = Number(value);
    return (number >= 0 ? "+" : "") + number.toFixed(3);
  }

  function formatProbability(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "Not supplied";
    }
    return (Number(value) * 100).toFixed(1) + "%";
  }

  function formatComparisonPercent(value, signed) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "Not supplied";
    }
    const percentage = Number(value) * 100;
    const rounded = Math.abs(percentage) < 0.05 ? 0 : percentage;
    const text = rounded.toFixed(1).replace(/\.0$/, "") + "%";
    return signed && rounded >= 0 ? "+" + text : text;
  }

  function numericProbability(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return null;
    }
    const number = Number(value);
    return number >= 0 && number <= 1 ? number : null;
  }

  function probabilityComparisonRows(
    topProbabilities,
    selectedProbabilities,
    preparedDifferences
  ) {
    return PROBABILITY_COMPARISON_ROWS.map(function (definition) {
      const top = numericProbability(
        topProbabilities && topProbabilities[definition[0]]
      );
      const selected = numericProbability(
        selectedProbabilities && selectedProbabilities[definition[0]]
      );
      const prepared =
        preparedDifferences &&
        preparedDifferences[definition[0]] !== null &&
        preparedDifferences[definition[0]] !== undefined &&
        !Number.isNaN(Number(preparedDifferences[definition[0]]))
          ? Number(preparedDifferences[definition[0]])
          : null;
      const difference =
        prepared !== null
          ? prepared
          : top === null || selected === null
            ? null
            : selected - top;
      return {
        key: definition[0],
        label: definition[1],
        top: top,
        selected: selected,
        difference: difference,
        topDisplay: formatComparisonPercent(top, false),
        selectedDisplay: formatComparisonPercent(selected, false),
        differenceDisplay:
          difference === null ? null : formatComparisonPercent(difference, true)
      };
    });
  }

  function approximatelyOne(value) {
    return Math.abs(value - 1) <= 0.002;
  }

  function exclusiveOutcomeSegments(probabilities) {
    if (!probabilities) {
      return {
        status: "missing",
        segments: [],
        message: "Outcome probabilities not supplied"
      };
    }

    const win = numericProbability(probabilities.win);
    const lose = numericProbability(probabilities.lose);
    if (win === null || lose === null) {
      return {
        status: "missing",
        segments: [],
        message: "Win and loss probabilities are required for the outcome bar"
      };
    }
    if (!approximatelyOne(win + lose)) {
      return {
        status: "invalid",
        segments: [],
        message: "Supplied win and loss probabilities are inconsistent"
      };
    }

    const winGammonOrBetter = numericProbability(
      probabilities.win_gammon_or_better
    );
    const winBackgammon = numericProbability(probabilities.win_backgammon);
    const loseGammonOrWorse = numericProbability(
      probabilities.lose_gammon_or_worse
    );
    const loseBackgammon = numericProbability(probabilities.lose_backgammon);
    const completeBreakdown = [
      winGammonOrBetter,
      winBackgammon,
      loseGammonOrWorse,
      loseBackgammon
    ].every((value) => value !== null);

    if (!completeBreakdown) {
      return {
        status: "partial",
        segments: [
          { key: "win", label: "Win", tone: "win-total", value: win },
          { key: "lose", label: "Lose", tone: "lose-total", value: lose }
        ],
        message: "Gammon and backgammon breakdown not supplied"
      };
    }

    if (
      winBackgammon > winGammonOrBetter ||
      winGammonOrBetter > win ||
      loseBackgammon > loseGammonOrWorse ||
      loseGammonOrWorse > lose
    ) {
      return {
        status: "invalid",
        segments: [],
        message: "Supplied cumulative outcome probabilities are inconsistent"
      };
    }

    const values = {
      win_backgammon: winBackgammon,
      win_gammon: winGammonOrBetter - winBackgammon,
      win_single: win - winGammonOrBetter,
      lose_single: lose - loseGammonOrWorse,
      lose_gammon: loseGammonOrWorse - loseBackgammon,
      lose_backgammon: loseBackgammon
    };

    return {
      status: "complete",
      segments: OUTCOME_SEGMENTS.map(function (definition) {
        return {
          key: definition[0],
          label: definition[1],
          tone: definition[2],
          value: values[definition[0]]
        };
      }),
      message:
        "Segment widths are display-only differences from the supplied cumulative probabilities"
    };
  }

  function outcomeSummaryItems(probabilities) {
    if (!probabilities) {
      return [
        ["Win", null, "win"],
        ["Gammon", null, "win"],
        ["Backgammon", null, "win"],
        ["Lose gammon", null, "lose"],
        ["Lose backgammon", null, "lose"]
      ];
    }
    return [
      ["Win", numericProbability(probabilities.win), "win"],
      [
        "Gammon",
        numericProbability(probabilities.win_gammon_or_better),
        "win"
      ],
      ["Backgammon", numericProbability(probabilities.win_backgammon), "win"],
      [
        "Lose gammon",
        numericProbability(probabilities.lose_gammon_or_worse),
        "lose"
      ],
      [
        "Lose backgammon",
        numericProbability(probabilities.lose_backgammon),
        "lose"
      ]
    ];
  }

  function validateFixtureDocument(document) {
    if (!document || document.schema_version !== FIXTURE_SCHEMA) {
      throw new Error("Unsupported analysis viewer fixture schema.");
    }
    if (
      !document.fixture_status ||
      !FIXTURE_KINDS.has(document.fixture_status.kind) ||
      !document.fixture_status.label ||
      !document.fixture_status.message ||
      !document.analyses ||
      typeof document.analyses !== "object"
    ) {
      throw new Error("Analysis viewer fixture has an unsupported fixture status.");
    }
    return document;
  }

  function validateAnalysisModel(model) {
    const liveNodeModel =
      model &&
      model.fixture === false &&
      model.source_schema === NODE_ANALYSIS_VIEW_SCHEMA;
    if (!model || (model.fixture !== true && !liveNodeModel)) {
      throw new Error("Analysis viewer record has an unsupported presentation source.");
    }
    if (
      !model.id ||
      !model.title ||
      !["checker", "cube"].includes(model.analysis_kind)
    ) {
      throw new Error("Malformed analysis viewer fixture.");
    }
    if (model.fixture === true && (!model.original_board || !model.original_board.image)) {
      throw new Error("Analysis viewer fixture is missing its original board asset.");
    }
    if (
      model.analysis_kind === "checker" &&
      (!Array.isArray(model.candidates) || model.candidates.length === 0)
    ) {
      throw new Error("Checker analysis fixture must define candidates.");
    }
    if (
      model.analysis_kind === "cube" &&
      (!Array.isArray(model.actions) || model.actions.length === 0)
    ) {
      throw new Error("Cube analysis fixture must define actions.");
    }
    return model;
  }

  function validateNodeAnalysisView(view) {
    if (!view || view.schema_version !== NODE_ANALYSIS_VIEW_SCHEMA) {
      throw new Error("Unsupported Node analysis-view schema.");
    }
    if (
      !view.analysis_key ||
      !["checker", "cube"].includes(view.analysis_kind) ||
      !view.source_request ||
      !view.source_request.position ||
      view.source_request.position.format !== "gnuid" ||
      !view.source_request.position.id ||
      !view.engine ||
      !view.recommendation
    ) {
      throw new Error("Malformed Node analysis view.");
    }
    if (
      view.analysis_kind === "checker" &&
      (!view.checker || !Array.isArray(view.checker.candidates))
    ) {
      throw new Error("Node checker analysis view has no candidates.");
    }
    if (
      view.analysis_kind === "cube" &&
      (!view.cube || !Array.isArray(view.cube.actions))
    ) {
      throw new Error("Node cube analysis view has no actions.");
    }
    return view;
  }

  function nodeProbabilities(probabilities) {
    if (!probabilities) return null;
    return {
      win: probabilities.win,
      win_gammon_or_better: probabilities.win_gammon,
      win_backgammon: probabilities.win_backgammon,
      lose: probabilities.lose,
      lose_gammon_or_worse: probabilities.lose_gammon,
      lose_backgammon: probabilities.lose_backgammon
    };
  }

  function nodeProbabilityDifferences(probabilities) {
    return nodeProbabilities(probabilities);
  }

  function nodeSettingsText(view) {
    const requested = (view.settings && view.settings.requested) || {};
    const effective = (view.settings && view.settings.effective) || {};
    return {
      requested: [
        requested.analysis_setting,
        requested.decision_type,
        requested.report_mode
      ]
        .filter(Boolean)
        .join(", "),
      effective: [
        effective.actual_evaluation_type,
        effective.evaluation_plies === null ||
        effective.evaluation_plies === undefined
          ? null
          : effective.evaluation_plies + "-ply",
        effective.cubeful === null || effective.cubeful === undefined
          ? null
          : "cubeful=" + effective.cubeful,
        effective.pruning === null || effective.pruning === undefined
          ? null
          : "pruning=" + effective.pruning
      ]
        .filter(Boolean)
        .join(", ")
    };
  }

  function analysisModelFromNodeView(view) {
    validateNodeAnalysisView(view);
    const request = view.source_request;
    const provenance = view.producer_provenance || {};
    const parser = provenance.parser || {};
    const settings = nodeSettingsText(view);
    const dice = request.dice;
    const model = {
      id: view.analysis_key,
      analysis_kind: view.analysis_kind,
      title:
        view.analysis_kind === "checker"
          ? "GNU checker analysis"
          : "GNU cube analysis",
      subtitle: request.position.id,
      fixture: false,
      source_schema: view.schema_version,
      original_board: null,
      original_position_id: request.position.id,
      recommended_id: view.recommendation.id,
      context: {
        score: null,
        cube: null,
        dice: Array.isArray(dice) ? dice.join("-") : null,
        decision: view.analysis_kind
      },
      metadata: {
        engine: view.engine.name,
        engine_version: view.engine.version,
        source_family: "backgammon-node live analysis",
        parser: parser.identity,
        provenance:
          "analysis " +
          view.analysis_key +
          "; producer " +
          optionalText(provenance.producer_identity_sha256),
        analysis_settings: settings,
        recommendation:
          view.analysis_kind === "checker"
            ? view.recommendation.notation
            : view.recommendation.label
      },
      probabilities: nodeProbabilities(view.probabilities),
      warnings: Array.isArray(view.warnings) ? view.warnings.slice() : [],
      limitations: Array.isArray(view.limitations)
        ? view.limitations.slice()
        : []
    };

    if (view.analysis_kind === "checker") {
      model.played_move = view.played_move;
      model.candidates = view.checker.candidates.map(function (candidate) {
        const evaluation = candidate.evaluation || {};
        return {
          id: candidate.id,
          source_order: candidate.source_order,
          display_rank: candidate.display_order,
          move: candidate.notation,
          evaluation: [
            evaluation.type,
            evaluation.ply === null || evaluation.ply === undefined
              ? null
              : evaluation.ply + "-ply"
          ]
            .filter(Boolean)
            .join(", "),
          actual_ply: evaluation.ply,
          value: candidate.value,
          difference_from_best: candidate.difference_from_best,
          probabilities: nodeProbabilities(candidate.probabilities),
          move_board: null,
          result_board: null,
          resulting_position_id: candidate.resulting_position_id,
          structured_movements: Array.isArray(candidate.movement_steps)
            ? candidate.movement_steps.slice()
            : [],
          comparison_to_recommended: {
            rank_difference: null,
            value_difference: candidate.difference_from_best,
            probability_differences: nodeProbabilityDifferences(
              candidate.probability_differences_from_best
            )
          },
          preview: {
            status: "unavailable",
            kind: null,
            movement_steps: Array.isArray(candidate.movement_steps)
              ? candidate.movement_steps.slice()
              : [],
            resulting_position_id: candidate.resulting_position_id,
            message:
              "This Node analysis view does not supply a verified movement or resulting-board asset. No candidate board was inferred."
          },
          details:
            "Candidate facts come from the normalized Node analysis view; no move-overlay asset was supplied."
        };
      });
    } else {
      model.actions = view.cube.actions.map(function (action) {
        return {
          id: action.id,
          label: action.label,
          normalized_action: action.normalized_action,
          supported: action.supported !== false,
          value: action.value,
          probabilities: nodeProbabilities(action.probabilities),
          display_rank: action.display_order,
          actual_ply:
            view.cube.actual_ply === null || view.cube.actual_ply === undefined
              ? null
              : view.cube.actual_ply,
          comparison_to_recommended: null,
          details:
            "Action facts come from the normalized Node analysis view."
        };
      });
      model.actions.forEach(function (action) {
        action.is_recommended = action.id === model.recommended_id;
      });
    }
    return validateAnalysisModel(model);
  }

  function renderNodeAnalysisView(host, view, options) {
    const model = analysisModelFromNodeView(view);
    host.dataset.bsNodeAnalysisView = "true";
    host.dataset.bsAnalysisKey = model.id;
    return renderPresentation(host, model, options || {});
  }

  function analysisFromDocument(document, id) {
    validateFixtureDocument(document);
    const model = document.analyses[id];
    if (!model) {
      throw new Error("Unknown analysis fixture ID: " + id);
    }
    return {
      fixtureStatus: document.fixture_status,
      analysis: validateAnalysisModel(model)
    };
  }

  function fixtureLoader(url) {
    return async function loadAnalysis(id) {
      if (!requestCache.has(url)) {
        requestCache.set(
          url,
          fetch(url, { credentials: "same-origin" })
            .then(function (response) {
              if (!response.ok) {
                throw new Error("Analysis fixture data failed to load.");
              }
              return response.json();
            })
            .then(validateFixtureDocument)
        );
      }
      return analysisFromDocument(await requestCache.get(url), id);
    };
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function definitionList(rows, className) {
    const list = element("dl", className || "bs-analysis-results-meta");
    rows.forEach(function (row) {
      list.append(element("dt", "", row[0]), element("dd", "", row[1]));
    });
    return list;
  }

  function renderBoard(container, board, fallbackText) {
    container.replaceChildren();
    if (board && typeof board.render === "function") {
      const rendered = board.render();
      if (rendered) {
        rendered.classList && rendered.classList.add("bs-analysis-results-board-rendered");
        rendered.setAttribute && rendered.setAttribute("role", "img");
        rendered.setAttribute && rendered.setAttribute(
          "aria-label",
          optionalText(board.alt, "Analyzed backgammon position")
        );
        rendered.setAttribute && rendered.setAttribute("inert", "");
        container.appendChild(rendered);
        return;
      }
    }
    if (!board || !board.image) {
      const missing = element(
        "div",
        "bs-analysis-results-board-missing",
        fallbackText || "Board not available"
      );
      missing.setAttribute("role", "status");
      container.appendChild(missing);
      return;
    }
    const image = element("img", "bs-analysis-results-board-image");
    image.src = board.image;
    image.alt = optionalText(board.alt, "Backgammon position");
    image.width = 1200;
    image.height = 910;
    image.loading = "eager";
    image.decoding = "async";
    image.addEventListener(
      "error",
      function () {
        renderBoard(container, null, "Board asset could not be loaded");
      },
      { once: true }
    );
    container.appendChild(image);
  }

  function copyText(value, status, label) {
    const text =
      value === null || value === undefined || value === "" ? "" : String(value);
    if (!text) return Promise.resolve(false);
    const announce = function () {
      if (status) status.textContent = (label || "Identifier") + " copied.";
      return true;
    };
    if (
      typeof navigator !== "undefined" &&
      navigator.clipboard &&
      typeof navigator.clipboard.writeText === "function"
    ) {
      return navigator.clipboard.writeText(text).then(announce, function () {
        if (status) status.textContent = "Copy failed. Select the identifier and copy it manually.";
        return false;
      });
    }
    if (status) status.textContent = "Clipboard access is unavailable. Select the identifier and copy it manually.";
    return Promise.resolve(false);
  }

  function outcomePanel(probabilities) {
    const result = exclusiveOutcomeSegments(probabilities);
    const panel = element("section", "bs-analysis-results-outcomes");
    panel.setAttribute("aria-label", "Outcome probabilities");

    const summary = element("div", "bs-analysis-results-outcome-summary");
    outcomeSummaryItems(probabilities).forEach(function (item) {
      const field = element(
        "span",
        "bs-analysis-results-outcome-summary-item bs-analysis-results-outcome-summary-item--" +
          item[2]
      );
      field.append(
        element("span", "bs-analysis-results-outcome-summary-label", item[0] + ":"),
        element(
          "span",
          "bs-analysis-results-outcome-summary-value",
          formatProbability(item[1])
        )
      );
      summary.appendChild(field);
    });
    panel.appendChild(summary);

    if (result.status === "missing" || result.status === "invalid") {
      const unavailable = element(
        "div",
        "bs-analysis-results-outcome-unavailable",
        result.message
      );
      unavailable.setAttribute(
        "role",
        result.status === "invalid" ? "alert" : "status"
      );
      panel.appendChild(unavailable);
      return panel;
    }

    const bar = element("div", "bs-analysis-results-outcome-bar");
    bar.setAttribute("role", "img");
    bar.setAttribute(
      "aria-label",
      result.segments
        .map(function (segment) {
          return segment.label + " " + formatProbability(segment.value);
        })
        .join(", ")
    );
    result.segments.forEach(function (segment) {
      const part = element(
        "span",
        "bs-analysis-results-outcome-segment bs-analysis-results-outcome-segment--" +
          segment.tone
      );
      part.style.width = segment.value * 100 + "%";
      part.title = segment.label + ": " + formatProbability(segment.value);
      bar.appendChild(part);
    });
    panel.appendChild(bar);

    if (result.status === "partial") {
      panel.appendChild(
        element("p", "bs-analysis-results-outcome-note", result.message)
      );
    }
    return panel;
  }

  function contextRows(context) {
    return [
      ["Score", optionalText(context && context.score)],
      ["Cube", optionalText(context && context.cube)],
      ["Dice", optionalText(context && context.dice)],
      ["Decision", optionalText(context && context.decision)]
    ];
  }

  function metadataRows(metadata) {
    const settings = (metadata && metadata.analysis_settings) || {};
    const rows = [
      ["Engine", optionalText(metadata && metadata.engine)],
      ["Engine version", optionalText(metadata && metadata.engine_version)],
      ["Source family", optionalText(metadata && metadata.source_family)],
      ["Requested settings", optionalText(settings.requested)],
      ["Effective settings", optionalText(settings.effective)],
      ["Parser / adapter", optionalText(metadata && metadata.parser)],
      ["Provenance", optionalText(metadata && metadata.provenance)]
    ];
    if (metadata && metadata.played_move !== undefined) {
      rows.push(["Played move", optionalText(metadata.played_move)]);
    }
    if (metadata && metadata.recommendation !== undefined) {
      rows.push(["Recommendation", optionalText(metadata.recommendation)]);
    }
    return rows;
  }

  function listSection(title, values, className) {
    const section = element(
      "section",
      className || "bs-analysis-results-note-section"
    );
    section.appendChild(element("h4", "", title));
    if (!Array.isArray(values) || values.length === 0) {
      section.appendChild(
        element("p", "bs-analysis-results-empty", "None supplied")
      );
      return section;
    }
    const list = element("ul", "");
    values.forEach(function (value) {
      list.appendChild(element("li", "", value));
    });
    section.appendChild(list);
    return section;
  }

  function candidateMetrics(candidate) {
    return {
      equity:
        candidate && candidate.value
          ? formatNumber(candidate.value.value)
          : "Not supplied",
      versusBest: formatNumber(candidate && candidate.difference_from_best)
    };
  }

  function recommendedCheckerCandidate(model) {
    return (
      model.candidates.find(function (candidate) {
        return model.recommended_id && candidate.id === model.recommended_id;
      }) ||
      model.candidates.find(function (candidate) {
        return (
          model.metadata &&
          model.metadata.recommendation &&
          candidate.move === model.metadata.recommendation
        );
      }) ||
      model.candidates.find(function (candidate) {
        return Number(candidate.display_rank) === 1;
      }) ||
      model.candidates[0]
    );
  }

  function candidateSummary(candidate, isRecommended) {
    const summary = element("summary", "bs-analysis-results-candidate-summary");
    summary.dataset.bsAnalysisResultChoice = candidate.id;
    summary.setAttribute("aria-current", "false");

    const identity = element("span", "bs-analysis-results-candidate-identity");
    const depth = element(
      "span",
      "bs-analysis-results-candidate-depth",
      optionalText(candidate.evaluation, "Evaluation not supplied")
    );
    const selectedIndicator = element(
      "span",
      "bs-analysis-results-candidate-selected",
      "Selected"
    );
    selectedIndicator.setAttribute("aria-hidden", "true");
    depth.appendChild(selectedIndicator);
    if (isRecommended) {
      const recommended = element(
        "span",
        "bs-analysis-results-recommended-badge",
        "Engine recommended"
      );
      recommended.setAttribute("aria-label", "Engine-recommended candidate");
      depth.appendChild(recommended);
    }
    identity.append(
      element(
        "span",
        "bs-analysis-results-candidate-rank",
        candidate.display_rank ? "#" + candidate.display_rank : "-"
      ),
      element(
        "span",
        "bs-analysis-results-candidate-move",
        optionalText(candidate.move, "Unnamed candidate")
      ),
      depth
    );

    const metrics = candidateMetrics(candidate);
    const metricGroup = element("span", "bs-analysis-results-candidate-metrics");
    const equity = element("span", "bs-analysis-results-candidate-metric");
    equity.append(
      element("span", "bs-analysis-results-candidate-metric-label", "Equity"),
      element("span", "bs-analysis-results-candidate-metric-value", metrics.equity)
    );
    const versusBest = element("span", "bs-analysis-results-candidate-metric");
    versusBest.append(
      element("span", "bs-analysis-results-candidate-metric-label", "vs best"),
      element(
        "span",
        "bs-analysis-results-candidate-metric-value",
        metrics.versusBest
      )
    );
    metricGroup.append(equity, versusBest);
    summary.append(identity, metricGroup);
    return summary;
  }

  function candidateDetails(candidate) {
    const body = element("div", "bs-analysis-results-candidate-body");
    body.appendChild(outcomePanel(candidate.probabilities));
    body.appendChild(
      element(
        "p",
        "bs-analysis-results-candidate-detail",
        optionalText(candidate.details)
      )
    );
    if (candidate.resulting_position_id) {
      const identity = element("p", "bs-analysis-results-candidate-identity-fact");
      identity.append(
        element("strong", "", "Result identity: "),
        element("code", "", candidate.resulting_position_id)
      );
      body.appendChild(identity);
    }
    return body;
  }

  function movementLocation(value) {
    if (value === null || value === undefined) return "unknown";
    if (String(value).toLowerCase() === "off") return "off";
    if (String(value).toLowerCase() === "bar") return "bar";
    return "point " + String(value);
  }

  function movementFacts(candidate, container, status) {
    container.replaceChildren();
    container.appendChild(
      element("h4", "bs-analysis-results-preview-facts-title", "Prepared candidate facts")
    );
    const movements = Array.isArray(candidate.structured_movements)
      ? candidate.structured_movements
      : candidate.preview && Array.isArray(candidate.preview.movement_steps)
        ? candidate.preview.movement_steps
        : [];
    if (movements.length) {
      const list = element("ol", "bs-analysis-results-movement-steps");
      movements.forEach(function (movement) {
        const die =
          movement.die === null || movement.die === undefined
            ? "die not supplied"
            : "die " + movement.die;
        list.appendChild(
          element(
            "li",
            "",
            movementLocation(movement.from) +
              " to " +
              movementLocation(movement.to) +
              " (" +
              die +
              ")"
          )
        );
      });
      container.appendChild(list);
    } else {
      container.appendChild(
        element(
          "p",
          "bs-analysis-results-preview-note",
          candidate.move_board
            ? "A verified combined movement/result board is available; atomic movement steps were not supplied."
            : "Structured movement steps were not supplied."
        )
      );
    }
    if (candidate.resulting_position_id) {
      const identity = element("div", "bs-analysis-results-result-identity");
      const value = element("code", "", candidate.resulting_position_id);
      const copy = element("button", "bs-button bs-analysis-results-copy", "Copy result ID");
      copy.type = "button";
      copy.addEventListener("click", function () {
        copyText(candidate.resulting_position_id, status, "Result identifier");
      });
      identity.append(
        element("span", "", "Result identity"),
        value,
        copy
      );
      container.appendChild(identity);
    } else {
      container.appendChild(
        element(
          "p",
          "bs-analysis-results-preview-note",
          "A resulting-position identity was not supplied."
        )
      );
    }
    if (!candidate.move_board && !candidate.result_board) {
      const unavailable = element(
        "p",
        "bs-analysis-results-preview-unavailable",
        (candidate.preview && candidate.preview.message) ||
          "A verified candidate board was not supplied. The original position is shown; no resulting board was inferred."
      );
      unavailable.setAttribute("role", "status");
      container.appendChild(unavailable);
    }
  }

  function checkerBoardExplorer(board, toolbar, facts, originalBoard, status) {
    let activeCandidate = null;
    let mode = "original";
    const original = element("button", "bs-button", "Original");
    const movement = element("button", "bs-button", "Movement + result");
    const result = element("button", "bs-button", "Result");
    [original, movement, result].forEach(function (button) {
      button.type = "button";
      button.setAttribute("aria-pressed", "false");
    });
    original.dataset.bsPreviewMode = "original";
    movement.dataset.bsPreviewMode = "movement";
    result.dataset.bsPreviewMode = "result";
    toolbar.append(original, movement, result);

    function boardForMode() {
      if (!activeCandidate || mode === "original") return originalBoard;
      if (mode === "result") return activeCandidate.result_board;
      return activeCandidate.move_board;
    }

    function refresh(message) {
      [original, movement, result].forEach(function (button) {
        button.setAttribute(
          "aria-pressed",
          button.dataset.bsPreviewMode === mode ? "true" : "false"
        );
      });
      renderBoard(
        board,
        boardForMode(),
        mode === "original"
          ? "Original analyzed board is unavailable"
          : "Prepared candidate board is unavailable"
      );
      if (message) status.textContent = message;
    }

    function setMode(nextMode) {
      if (nextMode === "movement" && (!activeCandidate || !activeCandidate.move_board)) {
        return false;
      }
      if (nextMode === "result" && (!activeCandidate || !activeCandidate.result_board)) {
        return false;
      }
      mode = nextMode;
      refresh(
        nextMode === "original"
          ? "Showing the original analyzed position."
          : nextMode === "movement"
            ? "Showing the prepared movement overlay and resulting checker state for " +
              optionalText(activeCandidate.move, "the selected candidate") + "."
            : "Showing the prepared resulting board for " +
              optionalText(activeCandidate.move, "the selected candidate") + "."
      );
      return true;
    }

    original.addEventListener("click", function () { setMode("original"); });
    movement.addEventListener("click", function () { setMode("movement"); });
    result.addEventListener("click", function () { setMode("result"); });

    return {
      setCandidate: function (candidate) {
        activeCandidate = candidate;
        movement.hidden = !candidate.move_board;
        result.hidden = !candidate.result_board;
        movement.textContent = candidate.result_board
          ? "Movement overlay"
          : "Movement + result";
        mode = candidate.move_board
          ? "movement"
          : candidate.result_board
            ? "result"
            : "original";
        movementFacts(candidate, facts, status);
        refresh(
          candidate.move_board || candidate.result_board
            ? "Selected " + optionalText(candidate.move, "candidate") + ". Prepared candidate board shown."
            : "Selected " + optionalText(candidate.move, "candidate") + ". Candidate board unavailable; original position shown."
        );
      },
      setMode: setMode,
      getMode: function () { return mode; }
    };
  }

  function checkerMoveCard(candidate, label, modifier, comparison) {
    const card = element(
      "section",
      "bs-analysis-results-decision-card bs-analysis-results-decision-card--" +
        modifier
    );
    const heading = element("div", "bs-analysis-results-decision-card-heading");
    const identity = element("div", "bs-analysis-results-decision-card-identity");
    const metrics = candidateMetrics(candidate);
    heading.append(
      element("span", "bs-analysis-results-decision-label", label),
      element(
        "span",
        "bs-analysis-results-decision-rank",
        candidate && candidate.display_rank
          ? "Rank " + candidate.display_rank
          : "Rank not supplied"
      )
    );
    identity.append(
      element(
        "strong",
        "bs-analysis-results-decision-move",
        optionalText(candidate && candidate.move, "Unnamed candidate")
      ),
      element(
        "span",
        "bs-analysis-results-decision-equity",
        "Equity " + metrics.equity
      )
    );
    const facts = definitionList(
      [
        ["Evaluation", optionalText(candidate && candidate.evaluation)],
        [
          "vs recommended",
          comparison && comparison.value_difference !== null && comparison.value_difference !== undefined
            ? formatNumber(comparison.value_difference)
            : modifier === "top"
              ? "+0.000"
              : optionalText(candidate && candidate.difference_from_best)
        ]
      ],
      "bs-analysis-results-decision-facts"
    );
    card.append(
      heading,
      identity,
      facts,
      outcomePanel(candidate && candidate.probabilities)
    );
    return card;
  }

  function probabilityComparisonTable(
    topCandidate,
    selectedCandidate,
    itemKind,
    preparedDifferences
  ) {
    const table = element("table", "bs-analysis-results-comparison-table");
    const caption = element(
      "caption",
      "bs-analysis-results-comparison-caption",
      "Recommended versus selected " + (itemKind || "candidate") + " probabilities"
    );
    const head = element("thead", "");
    const headerRow = element("tr", "");
    const body = element("tbody", "");
    const outcomeHeader = element("th", "", "Outcome");
    const topHeader = element("th", "", "Recommended");
    const selectedHeader = element("th", "", "Selected");
    outcomeHeader.scope = "col";
    topHeader.scope = "col";
    selectedHeader.scope = "col";
    headerRow.append(outcomeHeader, topHeader, selectedHeader);
    head.appendChild(headerRow);

    probabilityComparisonRows(
      topCandidate && topCandidate.probabilities,
      selectedCandidate && selectedCandidate.probabilities,
      preparedDifferences ||
      (selectedCandidate &&
        selectedCandidate.comparison_to_recommended &&
        selectedCandidate.comparison_to_recommended.probability_differences)
    ).forEach(function (row) {
      const tableRow = element("tr", "");
      const label = element("th", "", row.label);
      const top = element("td", "", row.topDisplay);
      const selected = element("td", "");
      label.scope = "row";
      top.dataset.label = "Recommended";
      selected.dataset.label = "Selected";
      selected.appendChild(
        element("span", "bs-analysis-results-comparison-value", row.selectedDisplay)
      );
      if (row.differenceDisplay !== null) {
        selected.appendChild(
          element(
            "span",
            "bs-analysis-results-comparison-difference",
            " (" + row.differenceDisplay + ")"
          )
        );
      }
      tableRow.append(label, top, selected);
      body.appendChild(tableRow);
    });
    table.append(caption, head, body);
    return table;
  }

  function usablePreparedHadd(model) {
    const hadd = model && model.hadd;
    if (
      !hadd ||
      hadd.status !== "available" ||
      hadd.selected_architecture !== HADD_ARCHITECTURE ||
      hadd.position_perspective !== HADD_PERSPECTIVE ||
      !hadd.authority ||
      hadd.authority.hadd_ranking_authorized !== false ||
      hadd.authority.calculated_cubeful !== "CUBEFUL_CALCULATION_AUTHORITY_BLOCKED" ||
      !hadd.model ||
      !hadd.feature_system ||
      !Array.isArray(hadd.ab_explanations)
    ) {
      return null;
    }
    const complete = model.candidates.every(function (candidate) {
      const facts = candidate.hadd_derived_facts;
      return (
        facts &&
        facts.position_id === candidate.resulting_position_id &&
        facts.position_perspective === HADD_PERSPECTIVE &&
        facts.probabilities &&
        Number.isFinite(Number(facts.probability_derived_cubeless)) &&
        facts.conditional_logit_evidence &&
        JSON.stringify(facts.conditional_logit_evidence.heads) === JSON.stringify(HADD_HEADS) &&
        facts.conditional_logit_evidence.additive_scale === "conditional_logit_only"
      );
    });
    return complete ? hadd : null;
  }

  function haddCandidateCard(candidate, label) {
    const facts = candidate.hadd_derived_facts;
    const card = element("section", "bs-analysis-results-hadd-card");
    card.append(
      element("span", "bs-analysis-results-decision-label", label),
      element("strong", "bs-analysis-results-hadd-move", optionalText(candidate.move)),
      definitionList(
        [
          ["HADD value", formatNumber(facts.probability_derived_cubeless)],
          ["Position perspective", "next player on roll"]
        ],
        "bs-analysis-results-hadd-facts"
      ),
      element("h5", "bs-analysis-results-hadd-probability-title", "HADD probabilities"),
      outcomePanel(facts.probabilities)
    );
    return card;
  }

  function orientedHaddExplanation(hadd, candidateA, candidateB) {
    for (const explanation of hadd.ab_explanations) {
      if (
        explanation.candidate_a_id === candidateA.id &&
        explanation.candidate_b_id === candidateB.id &&
        explanation.difference_order === "A-minus-B"
      ) {
        return { explanation: explanation, multiplier: 1 };
      }
      if (
        explanation.candidate_a_id === candidateB.id &&
        explanation.candidate_b_id === candidateA.id &&
        explanation.difference_order === "A-minus-B"
      ) {
        return { explanation: explanation, multiplier: -1 };
      }
    }
    return null;
  }

  function haddContributionTable(oriented) {
    const details = element("details", "bs-analysis-results-hadd-explanation");
    const changed = oriented.explanation.per_feature_conditional_logit_difference.filter(
      function (row) {
        return row.conditional_logit_contributions.some(function (value) {
          return value !== 0;
        });
      }
    );
    details.appendChild(
      element(
        "summary",
        "bs-analysis-results-hadd-explanation-summary",
        "Why the resulting positions differ according to HADD (" +
          changed.length +
          " changed features)"
      )
    );
    const intro = element(
      "p",
      "bs-analysis-results-hadd-explanation-note",
      "Each row is an exact conditional-logit contribution difference in selected-minus-recommended (A-minus-B) order. Unchanged features cancel to exact zero and are omitted."
    );
    const logitDifferences = definitionList(
      HADD_HEADS.map(function (head, index) {
        return [
          head + " exact difference",
          formatNumber(
            oriented.multiplier *
              oriented.explanation.conditional_logit_difference[index]
          )
        ];
      }),
      "bs-analysis-results-hadd-facts"
    );
    const tableWrap = element("div", "bs-analysis-results-hadd-table-wrap");
    const table = element("table", "bs-analysis-results-comparison-table bs-analysis-results-hadd-table");
    const caption = element(
      "caption",
      "bs-analysis-results-comparison-caption",
      "Exact selected-minus-recommended conditional-logit feature contributions"
    );
    const head = element("thead", "");
    const header = element("tr", "");
    header.appendChild(element("th", "", "Feature"));
    HADD_HEADS.forEach(function (name) {
      header.appendChild(element("th", "", name));
    });
    head.appendChild(header);
    const body = element("tbody", "");
    changed.forEach(function (row) {
      const tr = element("tr", "");
      const label = element("th", "", row.feature_id.replaceAll("_", " "));
      label.scope = "row";
      tr.appendChild(label);
      row.conditional_logit_contributions.forEach(function (value) {
        tr.appendChild(element("td", "", formatNumber(oriented.multiplier * value)));
      });
      body.appendChild(tr);
    });
    table.append(caption, head, body);
    tableWrap.appendChild(table);
    details.append(intro, logitDifferences, tableWrap);
    return details;
  }

  function haddComparisonPanel(model, topCandidate, selectedCandidate) {
    const hadd = usablePreparedHadd(model);
    if (!hadd || !topCandidate || !selectedCandidate) return null;
    const panel = element("section", "bs-analysis-results-hadd");
    panel.setAttribute("aria-label", "HADD derived resulting-position facts");
    panel.append(
      element("h4", "bs-analysis-results-hadd-title", "HADD derived resulting-position facts"),
      element(
        "p",
        "bs-analysis-results-hadd-authority",
        "The engine recommendation above is native factual output. Pairwise Ridge remains the sole Explainer ranking authority where surfaced. HADD did not select either candidate; it supplies model-derived resulting-position probabilities, cubeless value, and conditional-logit explanation evidence."
      )
    );
    const cards = element("div", "bs-analysis-results-hadd-cards");
    cards.appendChild(haddCandidateCard(topCandidate, "Recommended candidate result"));
    if (selectedCandidate.id !== topCandidate.id) {
      cards.appendChild(haddCandidateCard(selectedCandidate, "Selected candidate result"));
    }
    panel.appendChild(cards);
    if (selectedCandidate.id !== topCandidate.id) {
      const oriented = orientedHaddExplanation(hadd, selectedCandidate, topCandidate);
      if (oriented) {
        const preparedProbabilityDifferences = {};
        Object.keys(oriented.explanation.probability_differences).forEach(
          function (key) {
            preparedProbabilityDifferences[key] =
              oriented.multiplier *
              oriented.explanation.probability_differences[key];
          }
        );
        preparedProbabilityDifferences.lose =
          selectedCandidate.hadd_derived_facts.probabilities.lose -
          topCandidate.hadd_derived_facts.probabilities.lose;
        panel.append(
          element(
            "p",
            "bs-analysis-results-hadd-output-difference",
            "Selected-minus-recommended HADD value difference: " +
              formatNumber(
                oriented.multiplier *
                  oriented.explanation.probability_derived_cubeless_difference
              )
          ),
          probabilityComparisonTable(
            { probabilities: topCandidate.hadd_derived_facts.probabilities },
            { probabilities: selectedCandidate.hadd_derived_facts.probabilities },
            "HADD resulting-position",
            preparedProbabilityDifferences
          ),
          haddContributionTable(oriented)
        );
      }
      panel.appendChild(
        element(
          "p",
          "bs-analysis-results-hadd-nonlinear-note",
          "Probability and HADD value differences are nonlinear outputs after the sigmoid and probability hierarchy. They are separate from the additive conditional-logit feature evidence and do not have a simple additive feature decomposition."
        )
      );
    }
    panel.appendChild(
      element(
        "p",
        "bs-analysis-results-hadd-model",
        "HADD model " + optionalText(hadd.model.source_model_id) +
          "; runtime " + optionalText(hadd.model.runtime_id) +
          "; feature system " + optionalText(hadd.feature_system.feature_set_identity) + "."
      )
    );
    return panel;
  }

  function showCheckerDecision(
    decision,
    topCandidate,
    selectedCandidate,
    model,
    haddDecision
  ) {
    decision.replaceChildren(
      checkerMoveCard(topCandidate, "Recommended candidate", "top", {
        value_difference: 0
      })
    );
    if (!selectedCandidate) return;

    const hadd = haddComparisonPanel(model, topCandidate, selectedCandidate);
    if (haddDecision) {
      haddDecision.replaceChildren();
      if (hadd) haddDecision.appendChild(hadd);
    }
    if (selectedCandidate.id === topCandidate.id) {
      return;
    }

    const selected = element("div", "bs-analysis-results-selected-comparison");
    selected.append(
      checkerMoveCard(
        selectedCandidate,
        "Selected candidate",
        "selected",
        selectedCandidate.comparison_to_recommended
      ),
      probabilityComparisonTable(topCandidate, selectedCandidate)
    );
    decision.appendChild(selected);
  }

  function setActiveCheckerCandidate(
    choiceGroup,
    candidate,
    boardExplorer,
    status,
    decision,
    topCandidate,
    model,
    haddDecision
  ) {
    choiceGroup
      .querySelectorAll("[data-bs-analysis-candidate-id]")
      .forEach(function (details) {
        const active = details.dataset.bsAnalysisCandidateId === candidate.id;
        details.classList.toggle("is-active", active);
        const summary = details.querySelector(":scope > summary");
        if (summary) summary.setAttribute("aria-current", active ? "true" : "false");
      });
    boardExplorer.setCandidate(candidate);
    showCheckerDecision(decision, topCandidate, candidate, model, haddDecision);
  }

  function renderChecker(
    model,
    choiceGroup,
    status,
    decision,
    haddDecision,
    boardExplorer,
    options
  ) {
    const candidatesById = new Map();
    const summaries = [];
    const topCandidate = recommendedCheckerCandidate(model);
    model.candidates.forEach(function (candidate) {
      const details = element("details", "bs-analysis-results-candidate");
      details.dataset.bsAnalysisCandidateId = candidate.id;
      const summary = candidateSummary(candidate, candidate.id === topCandidate.id);
      details.append(summary, candidateDetails(candidate));
      candidatesById.set(candidate.id, { candidate: candidate, details: details });
      summaries.push(summary);
      summary.addEventListener("click", function () {
        setActiveCheckerCandidate(
          choiceGroup,
          candidate,
          boardExplorer,
          status,
          decision,
          topCandidate,
          model,
          haddDecision
        );
      });
      choiceGroup.appendChild(details);
      if (candidate.id === topCandidate.id) {
        details.open = true;
      }
    });

    summaries.forEach(function (summary, index) {
      summary.addEventListener("keydown", function (event) {
        let next = null;
        if (["ArrowDown", "ArrowRight"].includes(event.key)) {
          next = (index + 1) % summaries.length;
        } else if (["ArrowUp", "ArrowLeft"].includes(event.key)) {
          next = (index - 1 + summaries.length) % summaries.length;
        } else if (event.key === "Home") {
          next = 0;
        } else if (event.key === "End") {
          next = summaries.length - 1;
        }
        if (next === null) return;
        event.preventDefault();
        const target = model.candidates[next];
        summaries[next].focus();
        candidatesById.get(target.id).details.open = true;
        setActiveCheckerCandidate(
          choiceGroup,
          target,
          boardExplorer,
          status,
          decision,
          topCandidate,
          model,
          haddDecision
        );
      });
    });

    if (topCandidate) {
      const requested =
        options && options.initialActiveId
          ? candidatesById.get(options.initialActiveId)
          : null;
      const active = requested || candidatesById.get(topCandidate.id);
      if (requested) requested.details.open = true;
      setActiveCheckerCandidate(
        choiceGroup,
        active.candidate,
        boardExplorer,
        status,
        decision,
        topCandidate,
        model,
        haddDecision
      );
    } else {
      decision.appendChild(
        element("p", "bs-analysis-results-empty", "No checker moves supplied")
      );
    }

    return {
      activate: function (candidateId, activateOptions) {
        const selected = candidatesById.get(candidateId);
        if (!selected) return false;
        if (!activateOptions || activateOptions.open !== false) {
          selected.details.open = true;
        }
        setActiveCheckerCandidate(
          choiceGroup,
          selected.candidate,
          boardExplorer,
          status,
          decision,
          topCandidate,
          model,
          haddDecision
        );
        return true;
      },
      reset: function () {
        return this.activate(topCandidate.id);
      },
      setPreviewMode: boardExplorer.setMode,
      getPreviewMode: boardExplorer.getMode,
      getActiveId: function () {
        const active = Array.from(
          choiceGroup.querySelectorAll("[data-bs-analysis-candidate-id]")
        ).find(function (details) {
          return details.classList.contains("is-active");
        });
        return active ? active.dataset.bsAnalysisCandidateId : null;
      }
    };
  }

  function selectionButton(primary, secondary, trailing, id, supported) {
    const button = element("button", "bs-analysis-results-choice");
    button.type = "button";
    button.dataset.bsAnalysisResultChoice = id;
    button.setAttribute("aria-pressed", "false");
    if (supported === false) button.classList.add("is-unsupported");

    const copy = element("span", "bs-analysis-results-choice-copy");
    copy.append(
      element("span", "bs-analysis-results-choice-primary", primary),
      element("span", "bs-analysis-results-choice-secondary", secondary)
    );
    button.append(
      copy,
      element("span", "bs-analysis-results-choice-value", trailing)
    );
    return button;
  }

  function setPressed(group, id) {
    group
      .querySelectorAll("[data-bs-analysis-result-choice]")
      .forEach(function (button) {
        if (button.tagName === "BUTTON") {
          button.setAttribute(
            "aria-pressed",
            button.dataset.bsAnalysisResultChoice === id ? "true" : "false"
          );
        }
      });
  }

  function recommendedCubeAction(model) {
    return (
      model.actions.find(function (action) {
        return model.recommended_id && action.id === model.recommended_id;
      }) ||
      model.actions.find(function (action) {
        return (
          model.metadata &&
          model.metadata.recommendation &&
          action.label === model.metadata.recommendation
        );
      }) ||
      model.actions.find(function (action) {
        return Number(action.display_rank) === 1;
      }) ||
      model.actions[0]
    );
  }

  function cubeActionCard(action, label, modifier) {
    const card = element(
      "section",
      "bs-analysis-results-decision-card bs-analysis-results-decision-card--" + modifier
    );
    const heading = element("div", "bs-analysis-results-decision-card-heading");
    heading.append(
      element("span", "bs-analysis-results-decision-label", label),
      element(
        "span",
        "bs-analysis-results-decision-rank",
        action && action.display_rank ? "Rank " + action.display_rank : "Rank not supplied"
      )
    );
    const identity = element("div", "bs-analysis-results-decision-card-identity");
    identity.append(
      element(
        "strong",
        "bs-analysis-results-decision-move",
        optionalText(action && action.label, "Unnamed cube action")
      ),
      element(
        "span",
        "bs-analysis-results-decision-equity",
        "Value " + (action && action.value ? formatNumber(action.value.value) : "Not supplied")
      )
    );
    card.append(
      heading,
      identity,
      definitionList(
        [
          ["Action", optionalText(action && action.normalized_action)],
          [
            "vs recommended",
            action &&
            action.comparison_to_recommended &&
            action.comparison_to_recommended.value_difference !== null &&
            action.comparison_to_recommended.value_difference !== undefined
              ? formatNumber(action.comparison_to_recommended.value_difference)
              : modifier === "top"
                ? "+0.000"
                : "Not supplied"
          ]
        ],
        "bs-analysis-results-decision-facts"
      )
    );
    return card;
  }

  function showCubeDecision(decision, recommended, selected, probabilities) {
    decision.replaceChildren(cubeActionCard(recommended, "Recommended action", "top"));
    if (!selected || selected.id === recommended.id) return;
    const comparison = element("div", "bs-analysis-results-selected-comparison");
    comparison.appendChild(cubeActionCard(selected, "Selected action", "selected"));
    if (recommended.probabilities || selected.probabilities || probabilities) {
      comparison.appendChild(
        probabilityComparisonTable(
          Object.assign({}, recommended, {
            probabilities: recommended.probabilities || probabilities
          }),
          Object.assign({}, selected, {
            probabilities: selected.probabilities || probabilities
          }),
          "cube action"
        )
      );
    }
    decision.appendChild(comparison);
  }

  function renderCube(model, board, choiceGroup, status, decision, options) {
    const presentationBoard =
      (options && options.boardOverride) || model.original_board;
    const sharedOutcomes = element("div", "bs-analysis-results-cube-outcomes");
    const actionDetail = element(
      "p",
      "bs-analysis-results-action-detail",
      "Select an action to inspect its supplied explanation."
    );
    sharedOutcomes.appendChild(outcomePanel(model.probabilities));
    choiceGroup.appendChild(sharedOutcomes);
    const actionsById = new Map();
    const buttons = [];
    const recommended = recommendedCubeAction(model);

    function activate(action) {
      setPressed(choiceGroup, action.id);
      renderBoard(board, presentationBoard);
      sharedOutcomes.replaceChildren(
        outcomePanel(action.probabilities || model.probabilities)
      );
      status.textContent =
        action.supported === false
          ? action.label + " is intentionally unsupported in this fixture."
          : "Selected " + action.label + ".";
      actionDetail.textContent = optionalText(
        action.details,
        "No additional explanation was supplied for this action."
      );
      showCubeDecision(decision, recommended, action, model.probabilities);
    }

    model.actions.forEach(function (action) {
      const secondary =
        action.supported === false
          ? "Unsupported in this fixture"
          : optionalText(action.normalized_action, "Action");
      const trailing = action.value
        ? formatNumber(action.value.value)
        : "Not supplied";
      const button = selectionButton(
        action.label,
        action.id === recommended.id ? secondary + " · Engine recommended" : secondary,
        trailing,
        action.id,
        action.supported
      );
      button.addEventListener("click", function () {
        activate(action);
      });
      actionsById.set(action.id, action);
      buttons.push(button);
      choiceGroup.appendChild(button);
    });
    choiceGroup.appendChild(actionDetail);

    buttons.forEach(function (button, index) {
      button.addEventListener("keydown", function (event) {
        let next = null;
        if (["ArrowDown", "ArrowRight"].includes(event.key)) next = (index + 1) % buttons.length;
        else if (["ArrowUp", "ArrowLeft"].includes(event.key)) next = (index - 1 + buttons.length) % buttons.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = buttons.length - 1;
        if (next === null) return;
        event.preventDefault();
        buttons[next].focus();
        activate(model.actions[next]);
      });
    });

    const initial =
      options && options.initialActiveId && actionsById.has(options.initialActiveId)
        ? actionsById.get(options.initialActiveId)
        : recommended;
    if (initial) activate(initial);

    return {
      activate: function (actionId) {
        const action = actionsById.get(actionId);
        if (!action) return false;
        activate(action);
        return true;
      },
      reset: function () { return this.activate(recommended.id); },
      getActiveId: function () {
        const active = buttons.find(function (button) {
          return button.getAttribute("aria-pressed") === "true";
        });
        return active ? active.dataset.bsAnalysisResultChoice : null;
      }
    };
  }

  function buildPresentation(model, options) {
    const presentation = element("div", "bs-analysis-results-presentation");
    const explorerHeader = element("header", "bs-analysis-results-explorer-header");
    const explorerCopy = element("div", "bs-analysis-results-explorer-copy");
    const explorerActions = element("div", "bs-analysis-results-explorer-actions");
    const shell = element("div", "bs-analysis-results-shell");
    const boardSection = element("section", "bs-analysis-results-board-section");
    const boardHeading = element(
      "h3",
      "bs-analysis-results-section-title",
      "Candidate board"
    );
    const boardToolbar = element("div", "bs-analysis-results-preview-toolbar");
    const board = element("div", "bs-analysis-results-board");
    const previewFacts = element("section", "bs-analysis-results-preview-facts");
    const analysisSection = element("section", "bs-analysis-results-main");
    const choicesHeading = element(
      "h3",
      "bs-analysis-results-section-title",
      model.analysis_kind === "checker" ? "Moves" : "Cube actions"
    );
    const choiceGroup = element("div", "bs-analysis-results-choices");
    const decision = element(
      "section",
      "bs-analysis-results-checker-summary"
    );
    const haddDecision = element(
      "div",
      "bs-analysis-results-hadd-surface"
    );
    const status = element(
      "p",
      "bs-analysis-results-choice-status",
      model.analysis_kind === "checker"
        ? "The engine-recommended candidate is selected. Use arrow keys in the candidate list to compare alternatives."
        : "The engine-recommended action is selected. Use arrow keys to compare alternatives."
    );
    const more = element("details", "bs-analysis-results-more");
    const moreSummary = element("summary", "", "More information");
    const moreContent = element("div", "bs-analysis-results-more-content");

    presentation.dataset.bsSharedAnalysisPresentation = "true";
    presentation.dataset.bsResultExplorer = model.analysis_kind;
    explorerCopy.append(
      element("span", "bs-status-label", "RESULT EXPLORER"),
      element(
        "h2",
        "bs-analysis-results-explorer-title",
        model.analysis_kind === "checker"
          ? "Explore checker candidates"
          : "Explore cube actions"
      ),
      element(
        "p",
        "bs-analysis-results-explorer-intro",
        "The recommendation and comparisons below use supplied analysis facts only."
      )
    );
    const reset = element("button", "bs-button", "Reset to recommended");
    reset.type = "button";
    reset.dataset.bsResetComparison = "true";
    explorerActions.appendChild(reset);
    if (model.id) {
      const copyAnalysis = element("button", "bs-button", "Copy analysis ID");
      copyAnalysis.type = "button";
      copyAnalysis.addEventListener("click", function () {
        copyText(model.id, status, "Analysis identifier");
      });
      explorerActions.appendChild(copyAnalysis);
    }
    if (options && typeof options.onReturnToEditor === "function") {
      const edit = element("button", "bs-button bs-button-primary", "Edit original position");
      edit.type = "button";
      edit.dataset.bsReturnToEditor = "true";
      edit.addEventListener("click", function () {
        options.onReturnToEditor();
        status.textContent = "Returned to the original analyzed position in the editor. Edit and resubmit when ready.";
      });
      explorerActions.appendChild(edit);
    }
    explorerHeader.append(explorerCopy, explorerActions);
    choiceGroup.setAttribute("role", "group");
    choiceGroup.setAttribute(
      "aria-label",
      model.analysis_kind === "checker"
        ? "Displayed checker candidates"
        : "Cube actions"
    );
    status.setAttribute("aria-live", "polite");
    status.setAttribute("aria-atomic", "true");
    const originalBoard =
      (options && options.boardOverride) || model.original_board;
    renderBoard(board, originalBoard);

    let controls;
    if (model.analysis_kind === "checker") {
      decision.setAttribute("aria-label", "Checker candidate comparison");
      const boardExplorer = checkerBoardExplorer(
        board,
        boardToolbar,
        previewFacts,
        originalBoard,
        status
      );
      controls = renderChecker(
        model,
        choiceGroup,
        status,
        decision,
        haddDecision,
        boardExplorer,
        options
      );
    } else {
      decision.setAttribute("aria-label", "Cube action comparison");
      controls = renderCube(model, board, choiceGroup, status, decision, options);
    }
    reset.addEventListener("click", function () {
      if (controls && controls.reset) controls.reset();
      status.textContent = "Comparison reset to the engine recommendation.";
    });

    boardSection.append(boardHeading);
    if (model.analysis_kind === "checker") boardSection.appendChild(boardToolbar);
    boardSection.appendChild(board);
    if (model.analysis_kind === "checker") boardSection.appendChild(previewFacts);
    if (model.analysis_kind === "checker") {
      analysisSection.append(choicesHeading, choiceGroup, haddDecision, status);
    } else {
      analysisSection.append(decision, choicesHeading, choiceGroup, status);
    }

    if (!options || options.showMore !== false) {
      moreSummary.setAttribute("aria-label", "More information about this analysis");
      moreContent.append(
        element("h3", "bs-analysis-results-section-title", "Metadata"),
        definitionList(metadataRows(model.metadata)),
        listSection(
          "Warnings",
          model.warnings,
          "bs-analysis-results-warning-section"
        ),
        listSection(
          "Limitations",
          model.limitations,
          "bs-analysis-results-limitation-section"
        )
      );
      more.append(moreSummary, moreContent);
      analysisSection.appendChild(more);
    }

    if (model.analysis_kind === "checker") {
      const decisionSurface = element(
        "div",
        "bs-analysis-results-checker-decision"
      );
      decisionSurface.append(boardSection, decision);
      presentation.append(explorerHeader, decisionSurface, analysisSection);
    } else {
      shell.append(boardSection, analysisSection);
      presentation.append(explorerHeader, shell);
    }
    return { element: presentation, controls: controls };
  }

  function renderPresentation(host, model, options) {
    validateAnalysisModel(model);
    const result = buildPresentation(model, options || {});
    host.replaceChildren(result.element);
    return result.controls;
  }

  function render(host, payload) {
    const model = payload.analysis;
    const fixtureStatus = payload.fixtureStatus;
    const article = element("article", "bs-analysis-results-viewer");
    const header = element("header", "bs-analysis-results-header");
    const fixtureBadge = element(
      "span",
      "bs-status bs-status--warning",
      fixtureStatus.label
    );
    const title = element("h2", "bs-analysis-results-title", model.title);
    const subtitle = element(
      "p",
      "bs-analysis-results-subtitle",
      model.subtitle
    );
    const fixtureMessage = element(
      "p",
      "bs-analysis-results-fixture-message",
      fixtureStatus.message
    );
    const context = definitionList(
      contextRows(model.context),
      "bs-analysis-results-context"
    );
    const presentation = buildPresentation(model, {});

    article.dataset.bsAnalysisResultsInstance = model.id;
    fixtureBadge.title = fixtureStatus.message;
    header.append(fixtureBadge, title, subtitle, fixtureMessage, context);
    article.append(header, presentation.element);
    host.replaceChildren(article);
  }

  function renderError(host, error) {
    const panel = element("div", "bs-analysis-results-error");
    panel.setAttribute("role", "alert");
    panel.append(
      element("strong", "", "Analysis fixture unavailable"),
      element(
        "p",
        "",
        optionalText(error && error.message, "Unknown loader error")
      )
    );
    host.replaceChildren(panel);
  }

  async function mount(host) {
    const url = host.dataset.analysisFixtureUrl;
    const id = host.dataset.analysisId;
    if (!url || !id) {
      renderError(
        host,
        new Error("Analysis fixture host is missing its loader configuration.")
      );
      return;
    }
    try {
      const payload = await fixtureLoader(url)(id);
      render(host, payload);
    } catch (error) {
      renderError(host, error);
    }
  }

  function mountAll() {
    document.querySelectorAll("[data-bs-analysis-results]").forEach(mount);
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", mountAll, { once: true });
    } else {
      mountAll();
    }
  }

  return {
    FIXTURE_SCHEMA,
    NODE_ANALYSIS_VIEW_SCHEMA,
    analysisModelFromNodeView,
    analysisFromDocument,
    candidateMetrics,
    exclusiveOutcomeSegments,
    fixtureLoader,
    formatNumber,
    formatProbability,
    haddComparisonPanel,
    mount,
    mountAll,
    outcomeSummaryItems,
    probabilityComparisonRows,
    renderBoard,
    renderNodeAnalysisView,
    renderPresentation,
    setActiveCheckerCandidate,
    usablePreparedHadd,
    validateAnalysisModel,
    validateNodeAnalysisView,
    validateFixtureDocument
  };
});
