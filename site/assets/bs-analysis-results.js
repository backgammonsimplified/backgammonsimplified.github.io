(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.BMSAnalysisResults = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const FIXTURE_SCHEMA = "bs-analysis-results-viewer-fixture-v1";
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

  function probabilityComparisonRows(topProbabilities, selectedProbabilities) {
    return PROBABILITY_COMPARISON_ROWS.map(function (definition) {
      const top = numericProbability(
        topProbabilities && topProbabilities[definition[0]]
      );
      const selected = numericProbability(
        selectedProbabilities && selectedProbabilities[definition[0]]
      );
      const difference = top === null || selected === null ? null : selected - top;
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
    if (!model || model.fixture !== true) {
      throw new Error("Analysis viewer record is not marked as a fixture-page record.");
    }
    if (
      !model.id ||
      !model.title ||
      !["checker", "cube"].includes(model.analysis_kind)
    ) {
      throw new Error("Malformed analysis viewer fixture.");
    }
    if (!model.original_board || !model.original_board.image) {
      throw new Error("Analysis viewer fixture is missing its original board asset.");
    }
    if (model.analysis_kind === "checker" && !Array.isArray(model.candidates)) {
      throw new Error("Checker analysis fixture must define candidates.");
    }
    if (model.analysis_kind === "cube" && !Array.isArray(model.actions)) {
      throw new Error("Cube analysis fixture must define actions.");
    }
    return model;
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

  function candidateSummary(candidate) {
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
    return body;
  }

  function showCheckerCandidate(candidate, board, originalBoard, status) {
    const boardView = candidate.move_board || originalBoard;
    renderBoard(
      board,
      boardView,
      "Move-overlay board not supplied for this candidate"
    );
    status.textContent = candidate.move_board
      ? "Showing the starting position with " + optionalText(candidate.move, "candidate") + " overlaid."
      : "Move overlay unavailable for " + optionalText(candidate.move, "candidate") + "; showing the original position.";
  }

  function checkerMoveCard(candidate, label, modifier) {
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
    card.append(heading, identity, outcomePanel(candidate && candidate.probabilities));
    return card;
  }

  function probabilityComparisonTable(topCandidate, selectedCandidate) {
    const table = element("table", "bs-analysis-results-comparison-table");
    const caption = element(
      "caption",
      "bs-analysis-results-comparison-caption",
      "Top move versus selected move probabilities"
    );
    const head = element("thead", "");
    const headerRow = element("tr", "");
    const body = element("tbody", "");
    const outcomeHeader = element("th", "", "Outcome");
    const topHeader = element("th", "", "Top move");
    const selectedHeader = element("th", "", "Selected move");
    outcomeHeader.scope = "col";
    topHeader.scope = "col";
    selectedHeader.scope = "col";
    headerRow.append(outcomeHeader, topHeader, selectedHeader);
    head.appendChild(headerRow);

    probabilityComparisonRows(
      topCandidate && topCandidate.probabilities,
      selectedCandidate && selectedCandidate.probabilities
    ).forEach(function (row) {
      const tableRow = element("tr", "");
      const label = element("th", "", row.label);
      const top = element("td", "", row.topDisplay);
      const selected = element("td", "");
      label.scope = "row";
      top.dataset.label = "Top move";
      selected.dataset.label = "Selected move";
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

  function showCheckerDecision(decision, topCandidate, selectedCandidate) {
    decision.replaceChildren(checkerMoveCard(topCandidate, "Top move", "top"));
    if (!selectedCandidate || selectedCandidate.id === topCandidate.id) return;

    const selected = element("div", "bs-analysis-results-selected-comparison");
    selected.append(
      checkerMoveCard(selectedCandidate, "Selected move", "selected"),
      probabilityComparisonTable(topCandidate, selectedCandidate)
    );
    decision.appendChild(selected);
  }

  function setActiveCheckerCandidate(
    choiceGroup,
    candidate,
    board,
    originalBoard,
    status,
    decision,
    topCandidate
  ) {
    choiceGroup
      .querySelectorAll("[data-bs-analysis-candidate-id]")
      .forEach(function (details) {
        const active = details.dataset.bsAnalysisCandidateId === candidate.id;
        details.classList.toggle("is-active", active);
        const summary = details.querySelector(":scope > summary");
        if (summary) summary.setAttribute("aria-current", active ? "true" : "false");
      });
    showCheckerCandidate(candidate, board, originalBoard, status);
    showCheckerDecision(decision, topCandidate, candidate);
  }

  function renderChecker(model, board, choiceGroup, status, decision, options) {
    const candidatesById = new Map();
    const topCandidate =
      model.candidates.find(function (candidate) {
        return Number(candidate.display_rank) === 1;
      }) || model.candidates[0];
    model.candidates.forEach(function (candidate) {
      const details = element("details", "bs-analysis-results-candidate");
      details.dataset.bsAnalysisCandidateId = candidate.id;
      const summary = candidateSummary(candidate);
      details.append(summary, candidateDetails(candidate));
      candidatesById.set(candidate.id, { candidate: candidate, details: details });
      summary.addEventListener("click", function () {
        setActiveCheckerCandidate(
          choiceGroup,
          candidate,
          board,
          model.original_board,
          status,
          decision,
          topCandidate
        );
      });
      choiceGroup.appendChild(details);
      if (candidate.id === topCandidate.id) {
        details.open = true;
      }
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
        board,
        model.original_board,
        status,
        decision,
        topCandidate
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
          board,
          model.original_board,
          status,
          decision,
          topCandidate
        );
        return true;
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

  function renderCube(model, board, choiceGroup, status, options) {
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
        secondary,
        trailing,
        action.id,
        action.supported
      );
      button.addEventListener("click", function () {
        activate(action);
      });
      actionsById.set(action.id, action);
      choiceGroup.appendChild(button);
    });
    choiceGroup.appendChild(actionDetail);

    if (options && options.initialActiveId && actionsById.has(options.initialActiveId)) {
      activate(actionsById.get(options.initialActiveId));
    }

    return {
      activate: function (actionId) {
        const action = actionsById.get(actionId);
        if (!action) return false;
        activate(action);
        return true;
      }
    };
  }

  function buildPresentation(model, options) {
    const presentation = element("div", "bs-analysis-results-presentation");
    const shell = element("div", "bs-analysis-results-shell");
    const boardSection = element("section", "bs-analysis-results-board-section");
    const boardHeading = element(
      "h3",
      "bs-analysis-results-section-title",
      "Position"
    );
    const board = element("div", "bs-analysis-results-board");
    const analysisSection = element("section", "bs-analysis-results-main");
    const choicesHeading = element(
      "h3",
      "bs-analysis-results-section-title",
      model.analysis_kind === "checker" ? "Moves" : "Cube actions"
    );
    const choiceGroup = element("div", "bs-analysis-results-choices");
    const checkerDecision = element(
      "section",
      "bs-analysis-results-checker-summary"
    );
    const status = element(
      "p",
      "bs-analysis-results-choice-status",
      model.analysis_kind === "checker"
        ? "The top move is open. Opening another move keeps previous analysis open."
        : "Choose an action to inspect its supplied details."
    );
    const more = element("details", "bs-analysis-results-more");
    const moreSummary = element("summary", "", "More information");
    const moreContent = element("div", "bs-analysis-results-more-content");

    presentation.dataset.bsSharedAnalysisPresentation = "true";
    choiceGroup.setAttribute("role", "group");
    choiceGroup.setAttribute(
      "aria-label",
      model.analysis_kind === "checker"
        ? "Displayed checker candidates"
        : "Cube actions"
    );
    status.setAttribute("aria-live", "polite");
    renderBoard(
      board,
      (options && options.boardOverride) || model.original_board
    );

    let controls;
    if (model.analysis_kind === "checker") {
      checkerDecision.setAttribute("aria-label", "Checker move comparison");
      controls = renderChecker(
        model,
        board,
        choiceGroup,
        status,
        checkerDecision,
        options
      );
    } else {
      controls = renderCube(model, board, choiceGroup, status, options);
    }

    boardSection.append(boardHeading, board);
    analysisSection.append(choicesHeading, choiceGroup, status);

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
      decisionSurface.append(boardSection, checkerDecision);
      presentation.append(decisionSurface, analysisSection);
    } else {
      shell.append(boardSection, analysisSection);
      presentation.appendChild(shell);
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
    analysisFromDocument,
    candidateMetrics,
    exclusiveOutcomeSegments,
    fixtureLoader,
    formatNumber,
    formatProbability,
    mount,
    mountAll,
    outcomeSummaryItems,
    probabilityComparisonRows,
    renderBoard,
    renderPresentation,
    setActiveCheckerCandidate,
    validateAnalysisModel,
    validateFixtureDocument
  };
});
