(function () {
  "use strict";

  const FIXTURE_SCHEMA = "bs-lesson-analysis-fixture-v1";
  const FIRST_ACTIONS = ["double", "roll"];
  const RESPONSES = ["pass", "take"];
  const fixtureRequests = new Map();
  let instanceCounter = 0;

  function cleanToken(value) {
    return String(value || "component")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "component";
  }

  function nextInstanceId(kind, fixtureId) {
    instanceCounter += 1;
    return [
      "bs-analysis",
      cleanToken(kind),
      cleanToken(fixtureId),
      String(instanceCounter)
    ].join("-");
  }

  function resetInstanceCounter() {
    instanceCounter = 0;
  }

  function optionalText(value, fallback) {
    if (value === null || value === undefined || value === "") {
      return fallback || "Not supplied";
    }
    return String(value);
  }

  function formatEquity(value) {
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

  function humanize(value) {
    return String(value || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, function (letter) {
        return letter.toUpperCase();
      });
  }

  function assetUrl(assetRoot, assetName) {
    const value = optionalText(assetName, "");
    if (!value) {
      throw new Error("Lesson analysis fixture is missing an SVG asset name.");
    }
    if (/^(?:https?:)?\//.test(value)) {
      return value;
    }
    const root = optionalText(assetRoot, "").replace(/\/?$/, "/");
    if (!root || value.includes("..")) {
      throw new Error("Lesson analysis fixture has an unsafe SVG asset path.");
    }
    return root + value.replace(/^\/+/, "");
  }

  function cubeDecisionState(fixture, action, response) {
    const normalizedAction = String(action || "").toLowerCase();
    if (!FIRST_ACTIONS.includes(normalizedAction)) {
      throw new Error("Cube action must be Double or Roll.");
    }
    if (!fixture || !fixture.actions || !fixture.actions[normalizedAction]) {
      throw new Error("Cube fixture does not define the selected action.");
    }
    const actionData = fixture.actions[normalizedAction];
    const accepted =
      String(fixture.correct_first_action || "").toLowerCase() ===
      normalizedAction;
    const responder =
      normalizedAction === "double" &&
      accepted &&
      actionData.responder
        ? actionData.responder
        : null;
    let responseData = null;
    let responseAccepted = null;

    if (response !== null && response !== undefined) {
      const normalizedResponse = String(response).toLowerCase();
      if (!RESPONSES.includes(normalizedResponse)) {
        throw new Error("Cube response must be Pass or Take.");
      }
      if (
        !responder ||
        !responder.responses ||
        !responder.responses[normalizedResponse]
      ) {
        throw new Error("Cube fixture does not define the selected response.");
      }
      responseData = responder.responses[normalizedResponse];
      responseAccepted =
        String(responder.correct_response || "").toLowerCase() ===
        normalizedResponse;
    }

    return {
      action: normalizedAction,
      actionAccepted: accepted,
      actionData: actionData,
      responder: responder,
      responseAccepted: responseAccepted,
      responseData: responseData
    };
  }

  function checkerCandidateState(fixture, candidateId) {
    if (!fixture || !Array.isArray(fixture.candidates)) {
      throw new Error("Checker fixture must define candidate moves.");
    }
    const candidate = fixture.candidates.find(function (item) {
      return item && item.id === candidateId;
    });
    if (!candidate) {
      throw new Error("Checker fixture does not define the selected candidate.");
    }
    return candidate;
  }

  function checkerCandidateIdentityMatches(fixture, candidate) {
    const hasIdentity = Boolean(
      fixture && fixture.position_id && fixture.state_hash && fixture.analysis_id
    );
    return !hasIdentity || Boolean(
      candidate &&
      candidate.position_id === fixture.position_id &&
      candidate.state_hash === fixture.state_hash &&
      candidate.analysis_id === fixture.analysis_id
    );
  }

  function validateFixtureDocument(data) {
    if (!data || data.schema_version !== FIXTURE_SCHEMA) {
      throw new Error("Unsupported lesson analysis fixture schema.");
    }
    if (
      !data.fixture_status ||
      !data.fixture_status.message ||
      !data.asset_root
    ) {
      throw new Error("Lesson analysis fixture requires status and asset root.");
    }
    return data;
  }

  function loadFixtures(url) {
    if (!fixtureRequests.has(url)) {
      fixtureRequests.set(
        url,
        fetch(url, { credentials: "same-origin" }).then(function (response) {
          if (!response.ok) {
            throw new Error("Lesson analysis fixtures failed to load.");
          }
          return response.json();
        }).then(validateFixtureDocument)
      );
    }
    return fixtureRequests.get(url);
  }

  function element(tagName, className, text) {
    const node = document.createElement(tagName);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  function disclosure(id, summaryText, className) {
    const details = element("details", className || "bs-analysis-disclosure");
    const summary = element("summary", "", summaryText);
    const content = element("div", "bs-analysis-disclosure-content");
    details.id = id;
    content.id = id + "-content";
    summary.setAttribute("aria-controls", content.id);
    summary.setAttribute("aria-expanded", "false");
    details.addEventListener("toggle", function () {
      summary.setAttribute("aria-expanded", details.open ? "true" : "false");
    });
    details.append(summary, content);
    return {
      content: content,
      details: details,
      summary: summary
    };
  }

  function figureFor(image, assetRoot, className) {
    const figure = element("figure", className || "bs-analysis-position");
    const img = element("img", "bs-analysis-position-image");
    img.src = assetUrl(assetRoot, image.image);
    img.alt = optionalText(image.alt || image.image_alt, "Fixture position");
    img.width = 1200;
    img.height = 910;
    img.loading = "eager";
    img.decoding = "async";
    figure.appendChild(img);
    return { figure: figure, image: img };
  }

  function definitionList(rows, className) {
    const list = element("dl", className || "bs-analysis-metrics");
    rows.forEach(function (row) {
      list.append(
        element("dt", "", row[0]),
        element("dd", "", row[1])
      );
    });
    return list;
  }

  function analysisRows(analysis) {
    const rows = [
      ["Recommendation", optionalText(analysis && analysis.recommendation)]
    ];
    Object.entries((analysis && analysis.equities) || {}).forEach(
      function (entry) {
        rows.push(["Equity — " + humanize(entry[0]), formatEquity(entry[1])]);
      }
    );
    Object.entries((analysis && analysis.winning_probabilities) || {}).forEach(
      function (entry) {
        rows.push([
          "Probability — " + humanize(entry[0]),
          formatProbability(entry[1])
        ]);
      }
    );
    return rows;
  }

  function appendAnalysisDisclosure(
    parent,
    id,
    analysis,
    fixtureStatus,
    summaryText
  ) {
    const section = disclosure(
      id,
      summaryText || "Show fixture analysis",
      "bs-analysis-disclosure bs-analysis-disclosure--nested"
    );
    section.content.append(
      definitionList(analysisRows(analysis)),
      element(
        "p",
        "bs-analysis-explanation",
        optionalText(analysis && analysis.explanation)
      ),
      element(
        "p",
        "bs-analysis-fixture-note",
        fixtureStatus.message
      )
    );
    parent.appendChild(section.details);
    return section;
  }

  function choiceButton(label, value) {
    const button = element(
      "button",
      "bs-button-outline bs-analysis-choice",
      label
    );
    button.type = "button";
    button.dataset.bsAnalysisChoice = value;
    button.setAttribute("aria-pressed", "false");
    return button;
  }

  function setPressed(group, selected) {
    group
      .querySelectorAll("[data-bs-analysis-choice]")
      .forEach(function (button) {
        button.setAttribute(
          "aria-pressed",
          button.dataset.bsAnalysisChoice === selected ? "true" : "false"
        );
      });
  }

  function mountCube(host, fixtures, fixtureId) {
    const fixture = fixtures.cube_cases && fixtures.cube_cases[fixtureId];
    if (!fixture) {
      throw new Error("Unknown cube lesson fixture: " + fixtureId);
    }

    const instanceId = nextInstanceId("cube", fixtureId);
    const article = element("article", "bs-lesson-analysis bs-cube-analysis");
    const heading = element("h3", "bs-analysis-title", fixture.title);
    const initialFigure = figureFor(fixture.initial, fixtures.asset_root);
    const prompt = element("p", "bs-analysis-prompt", fixture.prompt);
    const group = element("div", "bs-analysis-choice-row");
    const status = element(
      "p",
      "bs-analysis-choice-status",
      "Choose Double or Roll to reveal the fixture answer."
    );
    const firstAnswer = disclosure(
      instanceId + "-first-answer",
      "Answer",
      "bs-analysis-disclosure bs-analysis-answer"
    );
    const doubleButton = choiceButton("Double", "double");
    const rollButton = choiceButton("Roll", "roll");

    heading.id = instanceId + "-title";
    article.setAttribute("aria-labelledby", heading.id);
    article.dataset.bsAnalysisInstance = instanceId;
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", fixture.prompt);
    group.append(doubleButton, rollButton);
    status.setAttribute("aria-live", "polite");
    firstAnswer.details.hidden = true;

    function renderResponse(responder, response) {
      const state = cubeDecisionState(fixture, "double", response);
      const responseAnswer = article.querySelector(
        "#" + instanceId + "-response-answer"
      );
      const responseGroup = article.querySelector(
        "[data-bs-cube-response-group]"
      );
      if (!responseAnswer || !responseGroup) {
        return;
      }
      setPressed(responseGroup, response);
      const responseSummary = responseAnswer.querySelector(":scope > summary");
      const responseContent = responseAnswer.querySelector(
        ":scope > .bs-analysis-disclosure-content"
      );
      responseSummary.textContent =
        humanize(response) +
        ": " +
        (state.responseAccepted ? "fixture answer" : "review the fixture answer");
      responseContent.replaceChildren(
        element(
          "p",
          "bs-analysis-answer-summary",
          state.responseData.summary
        )
      );
      appendAnalysisDisclosure(
        responseContent,
        instanceId + "-response-analysis",
        state.responseData.analysis,
        fixtures.fixture_status,
        "Show response analysis"
      );
      responseAnswer.hidden = false;
      responseAnswer.open = true;
      status.textContent =
        humanize(response) +
        " selected. " +
        (state.responseAccepted
          ? "This is the fixture response."
          : "Open the response analysis to compare it.");
    }

    function renderFirstAction(action) {
      const state = cubeDecisionState(fixture, action);
      setPressed(group, action);
      firstAnswer.summary.textContent =
        humanize(action) +
        ": " +
        (state.actionAccepted ? "fixture answer" : "review the fixture answer");
      firstAnswer.content.replaceChildren(
        element(
          "p",
          "bs-analysis-answer-summary",
          state.actionData.summary
        )
      );

      if (state.actionData.analysis) {
        appendAnalysisDisclosure(
          firstAnswer.content,
          instanceId + "-first-analysis",
          state.actionData.analysis,
          fixtures.fixture_status,
          "Show first-decision analysis"
        );
      }

      if (state.responder) {
        const responderSection = element(
          "section",
          "bs-analysis-responder"
        );
        const responderHeading = element(
          "h4",
          "bs-analysis-responder-title",
          "Responder decision"
        );
        const responderFigure = figureFor(
          {
            image: state.responder.image,
            alt: state.responder.alt
          },
          fixtures.asset_root,
          "bs-analysis-position bs-analysis-position--responder"
        );
        const responderPrompt = element(
          "p",
          "bs-analysis-prompt",
          state.responder.prompt
        );
        const responseGroup = element(
          "div",
          "bs-analysis-choice-row"
        );
        const passButton = choiceButton("Pass", "pass");
        const takeButton = choiceButton("Take", "take");
        const responseAnswer = disclosure(
          instanceId + "-response-answer",
          "Response answer",
          "bs-analysis-disclosure bs-analysis-answer bs-analysis-answer--response"
        );

        responderHeading.id = instanceId + "-responder-title";
        responderSection.setAttribute(
          "aria-labelledby",
          responderHeading.id
        );
        responseGroup.dataset.bsCubeResponseGroup = "";
        responseGroup.setAttribute("role", "group");
        responseGroup.setAttribute("aria-label", state.responder.prompt);
        responseGroup.append(passButton, takeButton);
        responseAnswer.details.hidden = true;
        passButton.addEventListener("click", function () {
          renderResponse(state.responder, "pass");
        });
        takeButton.addEventListener("click", function () {
          renderResponse(state.responder, "take");
        });
        responderSection.append(
          responderHeading,
          responderFigure.figure,
          responderPrompt,
          responseGroup,
          responseAnswer.details
        );
        firstAnswer.content.appendChild(responderSection);
      }

      firstAnswer.details.hidden = false;
      firstAnswer.details.open = true;
      status.textContent =
        humanize(action) +
        " selected. " +
        (state.actionAccepted
          ? "This is the fixture answer."
          : "Open the analysis to compare it.");
    }

    doubleButton.addEventListener("click", function () {
      renderFirstAction("double");
    });
    rollButton.addEventListener("click", function () {
      renderFirstAction("roll");
    });

    article.append(
      heading,
      initialFigure.figure,
      prompt,
      group,
      status,
      firstAnswer.details
    );
    host.replaceChildren(article);
  }

  function candidateMetricRows(candidate) {
    const rows = [
      ["Selected move", candidate.label],
      ["Rank", optionalText(candidate.rank)],
      ["Equity", formatEquity(candidate.equity)],
      ["Equity loss", formatEquity(candidate.equity_loss)]
    ];
    Object.entries(candidate.winning_probabilities || {}).forEach(
      function (entry) {
        rows.push([
          "Probability — " + humanize(entry[0]),
          formatProbability(entry[1])
        ]);
      }
    );
    return rows;
  }

  function mountChecker(host, fixtures, fixtureId) {
    const fixture = fixtures.checker_cases && fixtures.checker_cases[fixtureId];
    if (!fixture) {
      throw new Error("Unknown checker lesson fixture: " + fixtureId);
    }

    const instanceId = nextInstanceId("checker", fixtureId);
    const article = element(
      "article",
      "bs-lesson-analysis bs-checker-analysis"
    );
    const heading = element("h3", "bs-analysis-title", fixture.title);
    const position = figureFor(fixture.initial, fixtures.asset_root);
    const prompt = element("p", "bs-analysis-prompt", fixture.prompt);
    const group = element("div", "bs-analysis-choice-row");
    const status = element(
      "p",
      "bs-analysis-choice-status",
      "Choose a supplied candidate to update the position and metrics."
    );
    const metrics = element("div", "bs-analysis-candidate-result");

    heading.id = instanceId + "-title";
    article.setAttribute("aria-labelledby", heading.id);
    article.dataset.bsAnalysisInstance = instanceId;
    article.dataset.positionId = optionalText(fixture.position_id, "");
    article.dataset.stateHash = optionalText(fixture.state_hash, "");
    article.dataset.analysisId = optionalText(fixture.analysis_id, "");
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", fixture.prompt);
    status.setAttribute("aria-live", "polite");
    metrics.appendChild(
      element(
        "p",
        "bs-analysis-empty",
        "No candidate selected. The shared starting SVG remains visible."
      )
    );

    fixture.candidates.forEach(function (candidate) {
      const button = choiceButton(candidate.label, candidate.id);
      button.addEventListener("click", function () {
        const selected = checkerCandidateState(fixture, candidate.id);
        if (!checkerCandidateIdentityMatches(fixture, selected)) {
          throw new Error("Checker candidate identity does not match its fixture.");
        }
        setPressed(group, candidate.id);
        position.image.src = assetUrl(fixtures.asset_root, selected.image);
        position.image.alt = optionalText(
          selected.image_alt,
          selected.label + " fixture result"
        );
        metrics.replaceChildren(
          definitionList(candidateMetricRows(selected)),
          element(
            "p",
            "bs-analysis-explanation",
            optionalText(selected.explanation)
          )
        );
        status.textContent =
          selected.label +
          " selected. The supplied position and metrics are displayed.";
      });
      group.appendChild(button);
    });

    const engineAnalysis = disclosure(
      instanceId + "-engine-analysis",
      optionalText(
        fixture.analysis && fixture.analysis.label,
        "Show engine analysis"
      ),
      "bs-analysis-disclosure"
    );
    engineAnalysis.content.append(
      definitionList([
        ["Recommendation", optionalText(fixture.recommendation)],
        [
          "Engine",
          optionalText(fixture.analysis && fixture.analysis.engine)
        ],
        [
          "Setting",
          optionalText(fixture.analysis && fixture.analysis.setting)
        ]
      ]),
      element(
        "p",
        "bs-analysis-explanation",
        optionalText(fixture.analysis && fixture.analysis.explanation)
      ),
      element(
        "p",
        "bs-analysis-fixture-note",
        fixtures.fixture_status.message
      )
    );

    article.append(
      heading,
      position.figure,
      prompt,
      group,
      status,
      metrics,
      engineAnalysis.details
    );
    host.replaceChildren(article);
  }

  function showMountError(host, error) {
    const message = element(
      "p",
      "bs-analysis-error",
      "This lesson analysis fixture could not be loaded."
    );
    message.setAttribute("role", "alert");
    message.title = String(error && error.message ? error.message : error);
    host.replaceChildren(message);
  }

  function mountHost(host) {
    if (!host || host.dataset.bsAnalysisMounted === "true") {
      return Promise.resolve();
    }
    host.dataset.bsAnalysisMounted = "true";
    const url = host.dataset.bsFixtureSrc;
    const fixtureId = host.dataset.bsFixtureId;
    if (!url || !fixtureId) {
      showMountError(host, new Error("Fixture source and ID are required."));
      return Promise.resolve();
    }
    host.setAttribute("aria-busy", "true");
    return loadFixtures(url)
      .then(function (fixtures) {
        if (host.hasAttribute("data-bs-cube-decision")) {
          mountCube(host, fixtures, fixtureId);
        } else if (host.hasAttribute("data-bs-checker-decision")) {
          mountChecker(host, fixtures, fixtureId);
        } else {
          throw new Error("Unknown lesson analysis component type.");
        }
      })
      .catch(function (error) {
        showMountError(host, error);
      })
      .finally(function () {
        host.removeAttribute("aria-busy");
      });
  }

  function hostsIn(rootElement) {
    if (!rootElement) {
      return [];
    }
    const selector =
      "[data-bs-cube-decision], [data-bs-checker-decision]";
    const hosts = [];
    if (
      typeof rootElement.matches === "function" &&
      rootElement.matches(selector)
    ) {
      hosts.push(rootElement);
    }
    if (typeof rootElement.querySelectorAll === "function") {
      rootElement.querySelectorAll(selector).forEach(function (host) {
        hosts.push(host);
      });
    }
    return hosts;
  }

  function mount(rootElement) {
    return Promise.all(hostsIn(rootElement).map(mountHost));
  }

  function hookContinuousLessons() {
    if (
      typeof window === "undefined" ||
      !window.BSLearn ||
      typeof window.BSLearn.mountLesson !== "function" ||
      window.BSLearn.bsLessonAnalysisHooked
    ) {
      return;
    }
    const originalMount = window.BSLearn.mountLesson;
    window.BSLearn.mountLesson = function (rootElement) {
      const result = originalMount(rootElement);
      mount(rootElement);
      return result;
    };
    window.BSLearn.bsLessonAnalysisHooked = true;
  }

  const publicApi = {
    assetUrl: assetUrl,
    checkerCandidateIdentityMatches: checkerCandidateIdentityMatches,
    checkerCandidateState: checkerCandidateState,
    cubeDecisionState: cubeDecisionState,
    formatEquity: formatEquity,
    formatProbability: formatProbability,
    mount: mount,
    nextInstanceId: nextInstanceId,
    resetInstanceCounter: resetInstanceCounter,
    validateFixtureDocument: validateFixtureDocument
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = publicApi;
  }

  if (typeof window !== "undefined") {
    window.BSLessonAnalysis = Object.assign(
      window.BSLessonAnalysis || {},
      publicApi
    );
    hookContinuousLessons();
  }

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", function () {
      hookContinuousLessons();
      mount(document);
    });
  }
})();
