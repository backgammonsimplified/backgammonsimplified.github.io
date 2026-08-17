(function () {
  "use strict";

  const FIXTURE_SCHEMA = "bs-lesson-analysis-fixture-v1";
  const FIRST_ACTIONS = ["double", "roll"];
  const RESPONSES = ["pass", "take"];
  const fixtureRequests = new Map();
  let instanceCounter = 0;

  function sharedAnalysis() {
    if (
      typeof globalThis !== "undefined" &&
      globalThis.BMSAnalysisResults
    ) {
      return globalThis.BMSAnalysisResults;
    }
    if (typeof module === "object" && module.exports) {
      return require("./bs-analysis-results.js");
    }
    throw new Error("The shared analysis presentation is unavailable.");
  }

  function cleanToken(value) {
    return (
      String(value || "component")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") || "component"
    );
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
      normalizedAction === "double" && accepted && actionData.responder
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
    return (
      !hasIdentity ||
      Boolean(
        candidate &&
          candidate.position_id === fixture.position_id &&
          candidate.state_hash === fixture.state_hash &&
          candidate.analysis_id === fixture.analysis_id
      )
    );
  }

  function validateFixtureDocument(data) {
    if (!data || data.schema_version !== FIXTURE_SCHEMA) {
      throw new Error("Unsupported lesson analysis fixture schema.");
    }
    if (!data.fixture_status || !data.fixture_status.message || !data.asset_root) {
      throw new Error("Lesson analysis fixture requires status and asset root.");
    }
    return data;
  }

  function loadFixtures(url) {
    if (!fixtureRequests.has(url)) {
      fixtureRequests.set(
        url,
        fetch(url, { credentials: "same-origin" })
          .then(function (response) {
            if (!response.ok) {
              throw new Error("Lesson analysis fixtures failed to load.");
            }
            return response.json();
          })
          .then(validateFixtureDocument)
      );
    }
    return fixtureRequests.get(url);
  }

  function element(tagName, className, text) {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
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
    return { content: content, details: details, summary: summary };
  }

  function boardFor(image, assetRoot, className) {
    const figure = element("figure", className || "bs-analysis-position");
    const board = element("div", "bs-analysis-results-board");
    sharedAnalysis().renderBoard(board, {
      image: assetUrl(assetRoot, image.image),
      alt: optionalText(image.alt || image.image_alt, "Fixture position")
    });
    figure.appendChild(board);
    return { figure: figure, board: board };
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

  function lessonProbabilities(probabilities) {
    if (!probabilities) return null;
    const win = probabilities.win;
    const lose =
      probabilities.lose === null || probabilities.lose === undefined
        ? Number.isFinite(Number(win))
          ? 1 - Number(win)
          : null
        : probabilities.lose;
    return {
      win: win,
      win_gammon_or_better:
        probabilities.win_gammon_or_better !== undefined
          ? probabilities.win_gammon_or_better
          : probabilities.win_gammon,
      win_backgammon: probabilities.win_backgammon,
      lose: lose,
      lose_gammon_or_worse:
        probabilities.lose_gammon_or_worse !== undefined
          ? probabilities.lose_gammon_or_worse
          : probabilities.lose_gammon,
      lose_backgammon: probabilities.lose_backgammon
    };
  }

  function sharedMetadata(fixture) {
    return {
      engine: fixture.analysis && fixture.analysis.engine,
      engine_version: null,
      source_family: fixture.source_kind,
      parser: "lesson-analysis-fixture-adapter-v1",
      provenance: fixture.analysis_id || "Lesson fixture",
      recommendation: fixture.recommendation,
      analysis_settings: {
        requested: null,
        effective: fixture.analysis && fixture.analysis.setting
      }
    };
  }

  function checkerViewModel(fixture, fixtures) {
    return {
      id: fixture.analysis_id || fixture.position_id || "lesson-checker-analysis",
      analysis_kind: "checker",
      title: fixture.title,
      subtitle: fixture.prompt,
      fixture: true,
      original_board: {
        image: assetUrl(fixtures.asset_root, fixture.initial.image),
        alt: fixture.initial.alt
      },
      context: { score: null, cube: null, dice: null, decision: "Checker play" },
      metadata: sharedMetadata(fixture),
      probabilities: null,
      candidates: fixture.candidates.map(function (candidate, index) {
        if (!checkerCandidateIdentityMatches(fixture, candidate)) {
          throw new Error("Checker candidate identity does not match its fixture.");
        }
        return {
          id: candidate.id,
          source_order: index + 1,
          display_rank: candidate.rank,
          move: candidate.move || candidate.label,
          evaluation: optionalText(
            fixture.analysis && fixture.analysis.setting,
            "Fixture evaluation"
          ),
          value: { label: "Equity", value: candidate.equity },
          difference_from_best:
            candidate.equity_loss === null || candidate.equity_loss === undefined
              ? null
              : -Number(candidate.equity_loss),
          probabilities: lessonProbabilities(candidate.winning_probabilities),
          move_board: {
            image: assetUrl(fixtures.asset_root, candidate.image),
            alt: candidate.image_alt
          },
          resulting_position_id: candidate.resulting_position_id,
          details: candidate.explanation
        };
      }),
      warnings: [fixtures.fixture_status.message],
      limitations: [
        optionalText(
          fixture.analysis && fixture.analysis.explanation,
          "No additional lesson analysis explanation was supplied."
        )
      ]
    };
  }

  function cubeViewModel(analysis, image, fixture, fixtures, idSuffix) {
    const equities = (analysis && analysis.equities) || {};
    const probabilities = lessonProbabilities(
      analysis && analysis.winning_probabilities
    );
    return {
      id: cleanToken(fixture.title + "-" + idSuffix),
      analysis_kind: "cube",
      title: fixture.title,
      subtitle: analysis && analysis.explanation,
      fixture: true,
      original_board: {
        image: assetUrl(fixtures.asset_root, image.image),
        alt: image.alt
      },
      context: { score: null, cube: null, dice: null, decision: "Cube decision" },
      metadata: {
        engine: "Fixture only",
        engine_version: null,
        source_family: fixtures.fixture_status.kind,
        parser: "lesson-analysis-fixture-adapter-v1",
        provenance: "Lesson fixture",
        recommendation: analysis && analysis.recommendation,
        analysis_settings: { requested: null, effective: null }
      },
      probabilities: probabilities,
      actions: Object.entries(equities).map(function (entry) {
        return {
          id: entry[0],
          label: humanize(entry[0]),
          normalized_action: entry[0],
          supported: true,
          value: { label: "Equity", value: entry[1] },
          probabilities: probabilities,
          details: analysis && analysis.explanation
        };
      }),
      warnings: [fixtures.fixture_status.message],
      limitations: []
    };
  }

  function matchingActionId(model, educationalChoice) {
    const exact = model.actions.find(function (action) {
      return action.id === educationalChoice;
    });
    if (exact) return exact.id;
    const prefixed = model.actions.find(function (action) {
      return action.id.indexOf(educationalChoice + "_") === 0;
    });
    return prefixed ? prefixed.id : null;
  }

  function appendSharedDisclosure(parent, id, model, activeId, summaryText) {
    const section = disclosure(
      id,
      summaryText || "Show analysis",
      "bs-analysis-disclosure bs-analysis-disclosure--nested"
    );
    const host = element("div", "bs-lesson-shared-analysis");
    host.dataset.bsSharedAnalysisConsumer = "lesson";
    section.content.appendChild(host);
    sharedAnalysis().renderPresentation(host, model, {
      initialActiveId: activeId,
      showMore: true
    });
    parent.appendChild(section.details);
    return section;
  }

  function acceptedAnalysisChoice(model, choiceId) {
    const choices = model
      ? model.analysis_kind === "checker"
        ? model.candidates
        : model.actions
      : null;
    if (!Array.isArray(choices)) {
      throw new Error("Accepted lesson analysis does not define choices.");
    }
    const choice = choices.find(function (item) {
      return item && item.id === choiceId;
    });
    if (!choice) {
      throw new Error("Accepted lesson analysis does not define the selected choice.");
    }
    return choice;
  }

  function acceptedLessonArticle(host, model, kind) {
    if (!model || model.analysis_kind !== kind) {
      throw new Error("Accepted lesson analysis has the wrong decision type.");
    }
    const instanceId = nextInstanceId(kind, model.id);
    const article = element(
      "article",
      "bs-lesson-analysis bs-" + kind + "-analysis"
    );
    const heading = element(
      "h3",
      "bs-analysis-title",
      host.dataset.bsLessonTitle || model.title
    );
    const position = element("figure", "bs-analysis-position");
    const board = element("div", "bs-analysis-results-board");
    const prompt = element(
      "p",
      "bs-analysis-prompt",
      host.dataset.bsLessonPrompt || model.subtitle
    );
    const status = element(
      "p",
      "bs-analysis-choice-status",
      kind === "checker"
        ? "Choose a move to reveal the accepted analysis."
        : "Choose the cube action you would make."
    );
    const result = element("div", "bs-analysis-candidate-result");

    heading.id = instanceId + "-title";
    article.setAttribute("aria-labelledby", heading.id);
    article.dataset.bsAnalysisInstance = instanceId;
    article.dataset.analysisId = model.id;
    sharedAnalysis().renderBoard(board, model.original_board);
    position.appendChild(board);
    status.setAttribute("aria-live", "polite");
    result.hidden = true;
    result.dataset.bsSharedAnalysisConsumer = "lesson";

    return {
      article: article,
      heading: heading,
      instanceId: instanceId,
      position: position,
      prompt: prompt,
      result: result,
      status: status
    };
  }

  function revealAcceptedAnalysis(parts, model, choiceId) {
    const choice = acceptedAnalysisChoice(model, choiceId);
    sharedAnalysis().renderPresentation(parts.result, model, {
      initialActiveId: choice.id,
      showMore: true
    });
    parts.position.hidden = true;
    parts.result.hidden = false;
    return choice;
  }

  function mountAcceptedChecker(host, model) {
    const parts = acceptedLessonArticle(host, model, "checker");
    const group = element("div", "bs-analysis-choice-row");

    group.setAttribute("role", "group");
    group.setAttribute("aria-label", parts.prompt.textContent);
    model.candidates.forEach(function (candidate) {
      const button = choiceButton(candidate.move, candidate.id);
      button.addEventListener("click", function () {
        const selected = revealAcceptedAnalysis(parts, model, candidate.id);
        setPressed(group, selected.id);
        parts.status.textContent =
          selected.move + " selected. The accepted analysis is revealed.";
      });
      group.appendChild(button);
    });

    parts.article.append(
      parts.heading,
      parts.position,
      parts.prompt,
      group,
      parts.status,
      parts.result
    );
    host.replaceChildren(parts.article);
  }

  function mountAcceptedCube(host, model) {
    const parts = acceptedLessonArticle(host, model, "cube");
    const firstGroup = element("div", "bs-analysis-choice-row");
    const response = element("section", "bs-analysis-responder");
    const responseHeading = element(
      "h4",
      "bs-analysis-responder-title",
      "Responder decision"
    );
    const responsePrompt = element(
      "p",
      "bs-analysis-prompt",
      "If the cube is doubled, should the responder take or pass?"
    );
    const responseGroup = element("div", "bs-analysis-choice-row");
    const doubleButton = choiceButton("Double", "double");
    const noDoubleButton = choiceButton("No double", "no-double");
    const takeButton = choiceButton("Take", "take");
    const passButton = choiceButton("Pass", "pass");
    const actionIds = {
      noDouble: host.dataset.bsNoDoubleActionId,
      take: host.dataset.bsDoubleTakeActionId,
      pass: host.dataset.bsDoublePassActionId
    };

    Object.values(actionIds).forEach(function (actionId) {
      acceptedAnalysisChoice(model, actionId);
    });
    firstGroup.setAttribute("role", "group");
    firstGroup.setAttribute("aria-label", parts.prompt.textContent);
    firstGroup.append(doubleButton, noDoubleButton);
    response.hidden = true;
    responseHeading.id = parts.instanceId + "-responder-title";
    response.setAttribute("aria-labelledby", responseHeading.id);
    responseGroup.setAttribute("role", "group");
    responseGroup.setAttribute("aria-label", responsePrompt.textContent);
    responseGroup.append(takeButton, passButton);
    response.append(responseHeading, responsePrompt, responseGroup);

    function revealCubeChoice(actionId, lessonChoice) {
      const selected = revealAcceptedAnalysis(parts, model, actionId);
      parts.status.textContent =
        lessonChoice + " selected. The accepted cube analysis is revealed.";
      return selected;
    }

    doubleButton.addEventListener("click", function () {
      setPressed(firstGroup, "double");
      setPressed(responseGroup, "");
      response.hidden = false;
      parts.result.hidden = true;
      parts.position.hidden = false;
      parts.status.textContent =
        "Double selected. Now choose the responder's action.";
    });
    noDoubleButton.addEventListener("click", function () {
      setPressed(firstGroup, "no-double");
      response.hidden = true;
      revealCubeChoice(actionIds.noDouble, "No double");
    });
    takeButton.addEventListener("click", function () {
      setPressed(responseGroup, "take");
      revealCubeChoice(actionIds.take, "Double, take");
    });
    passButton.addEventListener("click", function () {
      setPressed(responseGroup, "pass");
      revealCubeChoice(actionIds.pass, "Double, pass");
    });

    parts.article.append(
      parts.heading,
      parts.position,
      parts.prompt,
      firstGroup,
      response,
      parts.status,
      parts.result
    );
    host.replaceChildren(parts.article);
  }

  function mountCube(host, fixtures, fixtureId) {
    const fixture = fixtures.cube_cases && fixtures.cube_cases[fixtureId];
    if (!fixture) throw new Error("Unknown cube lesson fixture: " + fixtureId);

    const instanceId = nextInstanceId("cube", fixtureId);
    const article = element("article", "bs-lesson-analysis bs-cube-analysis");
    const heading = element("h3", "bs-analysis-title", fixture.title);
    const initialFigure = boardFor(fixture.initial, fixtures.asset_root);
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

    function renderResponse(response) {
      const state = cubeDecisionState(fixture, "double", response);
      const responseAnswer = article.querySelector(
        "#" + instanceId + "-response-answer"
      );
      const responseGroup = article.querySelector("[data-bs-cube-response-group]");
      if (!responseAnswer || !responseGroup) return;
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
        element("p", "bs-analysis-answer-summary", state.responseData.summary)
      );
      const model = cubeViewModel(
        state.responseData.analysis,
        { image: state.responder.image, alt: state.responder.alt },
        fixture,
        fixtures,
        "response-" + response
      );
      appendSharedDisclosure(
        responseContent,
        instanceId + "-response-analysis",
        model,
        matchingActionId(model, response),
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
        element("p", "bs-analysis-answer-summary", state.actionData.summary)
      );

      if (state.actionData.analysis) {
        const model = cubeViewModel(
          state.actionData.analysis,
          fixture.initial,
          fixture,
          fixtures,
          "first-" + action
        );
        appendSharedDisclosure(
          firstAnswer.content,
          instanceId + "-first-analysis",
          model,
          matchingActionId(model, action),
          "Show first-decision analysis"
        );
      }

      if (state.responder) {
        const responderSection = element("section", "bs-analysis-responder");
        const responderHeading = element(
          "h4",
          "bs-analysis-responder-title",
          "Responder decision"
        );
        const responderFigure = boardFor(
          { image: state.responder.image, alt: state.responder.alt },
          fixtures.asset_root,
          "bs-analysis-position bs-analysis-position--responder"
        );
        const responderPrompt = element(
          "p",
          "bs-analysis-prompt",
          state.responder.prompt
        );
        const responseGroup = element("div", "bs-analysis-choice-row");
        const passButton = choiceButton("Pass", "pass");
        const takeButton = choiceButton("Take", "take");
        const responseAnswer = disclosure(
          instanceId + "-response-answer",
          "Response answer",
          "bs-analysis-disclosure bs-analysis-answer bs-analysis-answer--response"
        );

        responderHeading.id = instanceId + "-responder-title";
        responderSection.setAttribute("aria-labelledby", responderHeading.id);
        responseGroup.dataset.bsCubeResponseGroup = "";
        responseGroup.setAttribute("role", "group");
        responseGroup.setAttribute("aria-label", state.responder.prompt);
        responseGroup.append(passButton, takeButton);
        responseAnswer.details.hidden = true;
        passButton.addEventListener("click", function () {
          renderResponse("pass");
        });
        takeButton.addEventListener("click", function () {
          renderResponse("take");
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

  function mountChecker(host, fixtures, fixtureId) {
    const fixture = fixtures.checker_cases && fixtures.checker_cases[fixtureId];
    if (!fixture) throw new Error("Unknown checker lesson fixture: " + fixtureId);

    const instanceId = nextInstanceId("checker", fixtureId);
    const article = element("article", "bs-lesson-analysis bs-checker-analysis");
    const heading = element("h3", "bs-analysis-title", fixture.title);
    const position = boardFor(fixture.initial, fixtures.asset_root);
    const prompt = element("p", "bs-analysis-prompt", fixture.prompt);
    const group = element("div", "bs-analysis-choice-row");
    const status = element(
      "p",
      "bs-analysis-choice-status",
      "Choose a supplied candidate to reveal the shared analysis."
    );
    const result = element("div", "bs-analysis-candidate-result");
    const model = checkerViewModel(fixture, fixtures);

    heading.id = instanceId + "-title";
    article.setAttribute("aria-labelledby", heading.id);
    article.dataset.bsAnalysisInstance = instanceId;
    article.dataset.positionId = optionalText(fixture.position_id, "");
    article.dataset.stateHash = optionalText(fixture.state_hash, "");
    article.dataset.analysisId = optionalText(fixture.analysis_id, "");
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", fixture.prompt);
    status.setAttribute("aria-live", "polite");
    result.hidden = true;
    result.dataset.bsSharedAnalysisConsumer = "lesson";

    fixture.candidates.forEach(function (candidate) {
      const button = choiceButton(candidate.label, candidate.id);
      button.addEventListener("click", function () {
        const selected = checkerCandidateState(fixture, candidate.id);
        if (!checkerCandidateIdentityMatches(fixture, selected)) {
          throw new Error("Checker candidate identity does not match its fixture.");
        }
        setPressed(group, candidate.id);
        sharedAnalysis().renderPresentation(result, model, {
          initialActiveId: selected.id,
          showMore: true
        });
        position.figure.hidden = true;
        result.hidden = false;
        status.textContent =
          selected.label + " selected. The shared candidate analysis is revealed.";
      });
      group.appendChild(button);
    });

    article.append(heading, position.figure, prompt, group, status, result);
    host.replaceChildren(article);
  }

  function showMountError(host, error) {
    const message = element(
      "p",
      "bs-analysis-error",
      "This lesson analysis could not be loaded."
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
    const analysisUrl = host.dataset.bsAnalysisSrc;
    const analysisId = host.dataset.bsAnalysisId;
    if (analysisUrl || analysisId) {
      if (!analysisUrl || !analysisId) {
        showMountError(host, new Error("Analysis source and ID are required."));
        return Promise.resolve();
      }
      host.setAttribute("aria-busy", "true");
      return sharedAnalysis()
        .fixtureLoader(analysisUrl)(analysisId)
        .then(function (payload) {
          if (host.hasAttribute("data-bs-cube-decision")) {
            mountAcceptedCube(host, payload.analysis);
          } else if (host.hasAttribute("data-bs-checker-decision")) {
            mountAcceptedChecker(host, payload.analysis);
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
    if (!rootElement) return [];
    const selector = "[data-bs-cube-decision], [data-bs-checker-decision]";
    const hosts = [];
    if (typeof rootElement.matches === "function" && rootElement.matches(selector)) {
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
    acceptedAnalysisChoice: acceptedAnalysisChoice,
    assetUrl: assetUrl,
    checkerCandidateIdentityMatches: checkerCandidateIdentityMatches,
    checkerCandidateState: checkerCandidateState,
    checkerViewModel: checkerViewModel,
    cubeDecisionState: cubeDecisionState,
    cubeViewModel: cubeViewModel,
    lessonProbabilities: lessonProbabilities,
    matchingActionId: matchingActionId,
    mount: mount,
    mountAcceptedChecker: mountAcceptedChecker,
    mountAcceptedCube: mountAcceptedCube,
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
