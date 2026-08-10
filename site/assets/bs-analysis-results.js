(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.BMSAnalysisResults = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const FIXTURE_SCHEMA = "bs-analysis-results-viewer-fixture-v1";
  const requestCache = new Map();
  const OUTCOME_SEGMENTS = [
    ["win_backgammon", "Win backgammon", "win-bg"],
    ["win_gammon", "Win gammon", "win-gammon"],
    ["win_single", "Win single", "win-single"],
    ["lose_single", "Lose single", "lose-single"],
    ["lose_gammon", "Lose gammon", "lose-gammon"],
    ["lose_backgammon", "Lose backgammon", "lose-bg"]
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

  function numericProbability(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return null;
    }
    const number = Number(value);
    return number >= 0 && number <= 1 ? number : null;
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

  function validateFixtureDocument(document) {
    if (!document || document.schema_version !== FIXTURE_SCHEMA) {
      throw new Error("Unsupported analysis viewer fixture schema.");
    }
    if (
      !document.fixture_status ||
      document.fixture_status.kind !== "synthetic" ||
      !document.fixture_status.label ||
      !document.fixture_status.message ||
      !document.analyses ||
      typeof document.analyses !== "object"
    ) {
      throw new Error("Analysis viewer fixtures must be explicitly synthetic.");
    }
    return document;
  }

  function validateAnalysisModel(model) {
    if (!model || model.fixture !== true) {
      throw new Error("Analysis viewer fixture is not marked synthetic.");
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
        fallbackText || "Result board not available"
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

    const headline = element("div", "bs-analysis-results-outcome-headline");
    headline.append(
      element(
        "span",
        "bs-analysis-results-outcome-total bs-analysis-results-outcome-total--win",
        "Win " + formatProbability(probabilities && probabilities.win)
      ),
      element(
        "span",
        "bs-analysis-results-outcome-total bs-analysis-results-outcome-total--lose",
        "Lose " + formatProbability(probabilities && probabilities.lose)
      )
    );
    panel.appendChild(headline);

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

    const legend = element("div", "bs-analysis-results-outcome-legend");
    result.segments.forEach(function (segment) {
      const item = element("span", "bs-analysis-results-outcome-key");
      const swatch = element(
        "span",
        "bs-analysis-results-outcome-swatch bs-analysis-results-outcome-swatch--" +
          segment.tone
      );
      swatch.setAttribute("aria-hidden", "true");
      item.append(
        swatch,
        element("span", "bs-analysis-results-outcome-key-label", segment.label),
        element(
          "span",
          "bs-analysis-results-outcome-key-value",
          formatProbability(segment.value)
        )
      );
      legend.appendChild(item);
    });
    panel.appendChild(legend);

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
    return [
      ["Engine", optionalText(metadata && metadata.engine)],
      ["Engine version", optionalText(metadata && metadata.engine_version)],
      ["Requested settings", optionalText(settings.requested)],
      ["Effective settings", optionalText(settings.effective)],
      ["Parser / adapter", optionalText(metadata && metadata.parser)],
      ["Provenance", optionalText(metadata && metadata.provenance)]
    ];
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

  function selectedValue(value) {
    if (!value) return "Not supplied";
    return optionalText(value.label, "Value") + ": " + formatNumber(value.value);
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
        button.setAttribute(
          "aria-pressed",
          button.dataset.bsAnalysisResultChoice === id ? "true" : "false"
        );
      });
  }

  function renderChecker(
    model,
    board,
    summary,
    outcomes,
    choiceGroup,
    status
  ) {
    model.candidates.forEach(function (candidate) {
      const primary = [
        candidate.display_rank ? "#" + candidate.display_rank : null,
        candidate.move || "Unnamed candidate"
      ]
        .filter(Boolean)
        .join("  ");
      const secondary = [
        candidate.evaluation || "Evaluation not supplied",
        candidate.difference_from_best === null ||
        candidate.difference_from_best === undefined
          ? "Δ not supplied"
          : "Δ " + formatNumber(candidate.difference_from_best)
      ].join(" · ");
      const trailing = candidate.value
        ? formatNumber(candidate.value.value)
        : "Not supplied";
      const button = selectionButton(
        primary,
        secondary,
        trailing,
        candidate.id,
        true
      );
      button.addEventListener("click", function () {
        setPressed(choiceGroup, candidate.id);
        renderBoard(
          board,
          candidate.result_board,
          "Result board not supplied for this candidate"
        );
        summary.replaceChildren(
          definitionList(
            [
              ["Selected candidate", optionalText(candidate.move)],
              ["Display rank", optionalText(candidate.display_rank)],
              ["Evaluation", optionalText(candidate.evaluation)],
              ["Value", selectedValue(candidate.value)],
              [
                "Difference from best",
                formatNumber(candidate.difference_from_best)
              ],
              ["Detail", optionalText(candidate.details)]
            ],
            "bs-analysis-results-selection-meta"
          )
        );
        outcomes.replaceChildren(outcomePanel(candidate.probabilities));
        status.textContent =
          "Selected " + optionalText(candidate.move, "candidate") + ".";
      });
      choiceGroup.appendChild(button);
    });
  }

  function renderCube(
    model,
    board,
    summary,
    outcomes,
    choiceGroup,
    status
  ) {
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
        setPressed(choiceGroup, action.id);
        renderBoard(board, model.original_board);
        summary.replaceChildren(
          definitionList(
            [
              ["Selected action", optionalText(action.label)],
              ["Normalized label", optionalText(action.normalized_action)],
              [
                "Support",
                action.supported === false
                  ? "Unsupported in this fixture"
                  : "Supported fixture action"
              ],
              ["Value", selectedValue(action.value)],
              ["Detail", optionalText(action.details)]
            ],
            "bs-analysis-results-selection-meta"
          )
        );
        outcomes.replaceChildren(
          outcomePanel(action.probabilities || model.probabilities)
        );
        status.textContent =
          action.supported === false
            ? action.label + " is intentionally unsupported in this fixture."
            : "Selected " + action.label + ".";
      });
      choiceGroup.appendChild(button);
    });
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
    const shell = element("div", "bs-analysis-results-shell");
    const boardColumn = element("div", "bs-analysis-results-board-column");
    const boardHeading = element(
      "h3",
      "bs-analysis-results-section-title",
      "Position"
    );
    const board = element("div", "bs-analysis-results-board");
    const resultsColumn = element("div", "bs-analysis-results-main");
    const outcomeHeading = element(
      "h3",
      "bs-analysis-results-section-title",
      "Winning chances"
    );
    const outcomes = element("div", "");
    const choicesHeading = element(
      "h3",
      "bs-analysis-results-section-title",
      model.analysis_kind === "checker" ? "Moves" : "Cube actions"
    );
    const choiceGroup = element("div", "bs-analysis-results-choices");
    const status = element(
      "p",
      "bs-analysis-results-choice-status",
      "Choose an item to inspect its supplied details."
    );
    const summary = element("div", "bs-analysis-results-selection-summary");
    const more = element("details", "bs-analysis-results-more");
    const moreSummary = element("summary", "", "More information");
    const moreContent = element("div", "bs-analysis-results-more-content");

    article.dataset.bsAnalysisResultsInstance = model.id;
    fixtureBadge.title = "Fixture data is synthetic";
    choiceGroup.setAttribute("role", "group");
    choiceGroup.setAttribute(
      "aria-label",
      model.analysis_kind === "checker"
        ? "Displayed checker candidates"
        : "Cube actions"
    );
    status.setAttribute("aria-live", "polite");
    renderBoard(board, model.original_board);
    outcomes.appendChild(outcomePanel(model.probabilities));
    moreSummary.setAttribute(
      "aria-label",
      "More information about this synthetic analysis fixture"
    );
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

    if (model.analysis_kind === "checker") {
      renderChecker(
        model,
        board,
        summary,
        outcomes,
        choiceGroup,
        status
      );
    } else {
      renderCube(model, board, summary, outcomes, choiceGroup, status);
    }

    header.append(fixtureBadge, title, subtitle, fixtureMessage, context);
    boardColumn.append(boardHeading, board);
    resultsColumn.append(
      outcomeHeading,
      outcomes,
      choicesHeading,
      choiceGroup,
      status,
      summary,
      more
    );
    shell.append(boardColumn, resultsColumn);
    article.append(header, shell);
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
    exclusiveOutcomeSegments,
    fixtureLoader,
    formatNumber,
    formatProbability,
    mount,
    mountAll,
    validateAnalysisModel,
    validateFixtureDocument
  };
});
