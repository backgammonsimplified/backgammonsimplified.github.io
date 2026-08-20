const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 390, height: 844 }
];

const CHECKER_KEY =
  "sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d";
const CUBE_KEY =
  "sha256-1217f65d4a2c203e2370edb860ffaba81090a42f69d2a5fb56f5cceb64389e01";
export const CANONICAL_LESSON_ANALYSIS_SOURCE =
  "/data/analyzer-node-k001-lesson-preview.json";
export const CHECKER_CANDIDATE_IDS = [
  "cebe056b9fba14bb3a4fd58aa8f3e3d5430d98045ff21850c994bd24add37745",
  "44f91cbe042d6b615184f62d32d59337e3a35f709b875f11958bfdc2bf421477",
  "2940ef714c8cff1a3895543725738b43d64264c425968c3448c0a251a0e1542d",
  "5fd8fc14885e320a36c7769bf3127c2662c3d9f3164418872c7696be426460c8",
  "3c03cda00d76d9fbb7acc6d54dc78d2079fee4c1f10c946e4b2f3b8866a0027b",
  "09806fcf119b0f5742865fd64f987cecc00a28338b429a89a8098aacca864cf0",
  "6a2d4cbf49af863c3ca425061a616d836ef10e80429714fba0829180d2ec5837",
  "96d18ebbdcf54e9eb07265464db5b9e2100c5c0c6ae6c46e90a8a3a2258862d2"
];
export const CUBE_ACTION_IDS = {
  noDouble: "b0b5a1bdb5eebe7e4dd2ead2e48b22827ff870401381fe21a6f4d3eb0308e1ad",
  take: "5134e196c229cf5b7b36ce230fe26eedbb75ab8e1851010d6316008c233cfa0f",
  pass: "7ace038e9967b27f4c954b1a9b813f991f963e054e3994d6796d3cfd4c27a936"
};

export const LESSON_ANALYSIS_ROUTES = {
  cube: "/learn/cube/what-the-cube-is-asking.html",
  checker: "/learn/cube/why-is-25-percent-the-basic-take-point.html"
};

const delay = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

const componentSnapshot = (tab) =>
  tab.playwright.locator("html").evaluate(() => {
    const ids = Array.from(
      document.querySelectorAll(".bs-lesson-analysis [id]")
    ).map((element) => element.id);
    return {
      componentErrors: document.querySelectorAll(".bs-analysis-error").length,
      duplicateComponentIds: Array.from(
        new Set(ids.filter((id, index) => ids.indexOf(id) !== index))
      ),
      overflow:
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth
    };
  });

const consoleErrors = async (tab) => {
  const logs = await tab.dev.logs();
  return logs.filter((entry) =>
    /(TypeError|ReferenceError|Uncaught|console\.error)/i.test(
      typeof entry === "string" ? entry : JSON.stringify(entry)
    )
  );
};

export const summarizeLessonAnalysisReport = (report) => ({
  passed: report.failures.length === 0,
  checks: report.checks,
  failures: report.failures.length,
  pages: report.pages,
  durationMs: report.durationMs
});

export async function runLessonAnalysisBrowserChecks({
  browser,
  viewport,
  baseUrl
}) {
  if (!browser || !viewport || !baseUrl) {
    throw new Error("browser, viewport, and baseUrl are required");
  }
  const started = Date.now();
  const failures = [];
  let checks = 0;
  let pages = 0;
  const check = (condition, context, message) => {
    checks += 1;
    if (!condition) failures.push({ context, message });
  };
  const freshTab = async (viewportCase, route) => {
    await browser.tabs.finalize();
    const tab = await browser.tabs.new();
    await viewport.set({
      width: viewportCase.width,
      height: viewportCase.height
    });
    await tab.goto(new URL(route, baseUrl).href);
    await delay(900);
    pages += 1;
    return tab;
  };

  try {
    for (const viewportCase of VIEWPORTS) {
      const cubeContext = `${viewportCase.name}/cube`;
      const cubeTab = await freshTab(viewportCase, LESSON_ANALYSIS_ROUTES.cube);
      try {
        const host = cubeTab.playwright.locator("[data-bs-cube-decision]");
        check((await host.count()) === 1, cubeContext, "one real cube host mounts");
        const initial = await host.evaluate((element) => ({
          analysisId: element.querySelector("article")?.dataset.analysisId,
          analysisSource: element.dataset.bsAnalysisSrc,
          configuredAnalysisId: element.dataset.bsAnalysisId,
          actionIds: {
            noDouble: element.dataset.bsNoDoubleActionId,
            take: element.dataset.bsDoubleTakeActionId,
            pass: element.dataset.bsDoublePassActionId
          },
          image: element
            .querySelector(".bs-analysis-results-board-image")
            ?.getAttribute("src"),
          loaded: Boolean(
            element.querySelector(".bs-analysis-results-board-image")?.complete &&
              element.querySelector(".bs-analysis-results-board-image")
                ?.naturalWidth > 0
          )
        }));
        check(initial.analysisId === CUBE_KEY, cubeContext, "exact cube key mounts");
        check(
          initial.analysisSource === CANONICAL_LESSON_ANALYSIS_SOURCE &&
            initial.configuredAnalysisId === CUBE_KEY &&
            JSON.stringify(initial.actionIds) === JSON.stringify(CUBE_ACTION_IDS),
          cubeContext,
          "cube host retains exact Canonical source and action bindings"
        );
        check(
          initial.image === "/assets/positions/node-k001/cube/starting.svg" &&
            initial.loaded,
          cubeContext,
          "prepared cube board loads"
        );

        await host.locator("button[data-bs-analysis-choice='double']").click();
        check(
          await host.locator(".bs-analysis-responder").isVisible(),
          cubeContext,
          "lesson-owned Double choice reveals responder prompt"
        );
        check(
          (await host
            .locator(".bs-analysis-position .bs-analysis-results-board-image")
            .getAttribute("src")) ===
            "/assets/positions/node-k001/cube/responder.svg",
          cubeContext,
          "Double switches the prepared board to responder perspective"
        );
        await host.locator("button[data-bs-analysis-choice='take']").click();
        check(
          (await host
            .locator(
              ".bs-analysis-candidate-result .bs-analysis-results-board-image"
            )
            .getAttribute("src")) ===
            "/assets/positions/node-k001/cube/responder.svg",
          cubeContext,
          "Take retains the responder-perspective board"
        );
        await host.locator("button[data-bs-analysis-choice='pass']").click();
        check(
          (await host
            .locator(
              ".bs-analysis-candidate-result .bs-analysis-results-board-image"
            )
            .getAttribute("src")) ===
            "/assets/positions/node-k001/cube/responder.svg" &&
            (await host
              .locator(
                `button[data-bs-analysis-result-choice='${CUBE_ACTION_IDS.pass}']`
              )
              .getAttribute("aria-pressed")) === "true",
          cubeContext,
          "Pass uses the same responder-perspective board"
        );
        await host.locator("button[data-bs-analysis-choice='no-double']").click();
        check(
          !(await host.locator(".bs-analysis-responder").isVisible()) &&
            (await host
              .locator(
                ".bs-analysis-candidate-result .bs-analysis-results-board-image"
              )
              .getAttribute("src")) ===
              "/assets/positions/node-k001/cube/starting.svg" &&
            (await host
              .locator(
                `button[data-bs-analysis-result-choice='${CUBE_ACTION_IDS.noDouble}']`
              )
              .getAttribute("aria-pressed")) === "true",
          cubeContext,
          "No double stays out of the responder stage and uses the original perspective"
        );
        await host.locator("button[data-bs-analysis-choice='double']").click();
        await host.locator("button[data-bs-analysis-choice='take']").click();
        const revealed = await host.evaluate((element) => ({
          active: element
            .querySelector(
              "button[data-bs-analysis-result-choice][aria-pressed='true']"
            )
            ?.getAttribute("data-bs-analysis-result-choice"),
          actionCount: element.querySelectorAll(
            "button[data-bs-analysis-result-choice]"
          ).length,
          checkerDecision: Boolean(
            element.querySelector(".bs-analysis-results-checker-decision")
          ),
          comparison: Boolean(
            element.querySelector(".bs-analysis-results-comparison-table")
          ),
          shared: element
            .querySelector("[data-bs-shared-analysis-consumer='lesson']")
            ?.querySelector("[data-bs-shared-analysis-presentation]")
            ?.dataset.bsSharedAnalysisPresentation,
          text: element.textContent
        }));
        check(
          revealed.shared === "true" && revealed.active === CUBE_ACTION_IDS.take,
          cubeContext,
          "cube reveal invokes the shared viewer with Double, take active"
        );
        check(
          revealed.actionCount === 3 &&
            revealed.text.includes("Double, take") &&
            revealed.text.includes("+0.998") &&
            revealed.text.includes("Double, pass") &&
            revealed.text.includes("+1.000") &&
            revealed.text.includes("No double") &&
            revealed.text.includes("+0.638") &&
            revealed.text.includes("75.0%"),
          cubeContext,
          "cube source actions, equities, and probabilities remain visible"
        );
        check(
          !revealed.checkerDecision && !revealed.comparison,
          cubeContext,
          "cube remains free of checker comparison UI"
        );
        const cubePage = await componentSnapshot(cubeTab);
        check(cubePage.overflow <= 0, cubeContext, "cube page has no overflow");
        check(
          cubePage.duplicateComponentIds.length === 0,
          cubeContext,
          "cube component IDs remain unique"
        );
        check(
          cubePage.componentErrors === 0 &&
            (await consoleErrors(cubeTab)).length === 0,
          cubeContext,
          "cube page has no mount or console errors"
        );
      } catch (error) {
        failures.push({
          context: cubeContext,
          message: `browser helper error: ${String(error)}`
        });
      }

      const checkerContext = `${viewportCase.name}/checker`;
      const checkerTab = await freshTab(
        viewportCase,
        LESSON_ANALYSIS_ROUTES.checker
      );
      try {
        const host = checkerTab.playwright.locator("[data-bs-checker-decision]");
        const initial = await host.evaluate((element) => ({
          analysisId: element.querySelector("article")?.dataset.analysisId,
          analysisSource: element.dataset.bsAnalysisSrc,
          configuredAnalysisId: element.dataset.bsAnalysisId,
          choiceIds: Array.from(
            element.querySelectorAll(
              ":scope .bs-analysis-choice-row > [data-bs-analysis-choice]"
            )
          ).map((choice) => choice.dataset.bsAnalysisChoice),
          choices: element.querySelectorAll(
            ":scope .bs-analysis-choice-row > [data-bs-analysis-choice]"
          ).length,
          image: element
            .querySelector(".bs-analysis-results-board-image")
            ?.getAttribute("src")
        }));
        check(
          initial.analysisId === CHECKER_KEY &&
            initial.analysisSource === CANONICAL_LESSON_ANALYSIS_SOURCE &&
            initial.configuredAnalysisId === CHECKER_KEY &&
            initial.choices === 8 &&
            JSON.stringify(initial.choiceIds) ===
              JSON.stringify(CHECKER_CANDIDATE_IDS),
          checkerContext,
          "exact Canonical checker source/key exposes all eight ordered choices"
        );
        check(
          initial.image === "/assets/positions/node-k001/checker/starting.svg",
          checkerContext,
          "prepared checker starting board loads"
        );

        await host
          .locator(
            `button[data-bs-analysis-choice='${CHECKER_CANDIDATE_IDS[7]}']`
          )
          .click();
        const revealed = await host.evaluate((element) => ({
          active: element
            .querySelector(".bs-analysis-results-candidate.is-active")
            ?.dataset.bsAnalysisCandidateId,
          candidateCount: element.querySelectorAll(
            ".bs-analysis-results-candidate"
          ).length,
          comparison: Boolean(
            element.querySelector(".bs-analysis-results-comparison-table")
          ),
          image: element
            .querySelector(".bs-analysis-results-board-image")
            ?.getAttribute("src"),
          selectedBar: Boolean(
            element.querySelector(
              ".bs-analysis-results-decision-card--selected .bs-analysis-results-outcome-bar"
            )
          ),
          shared: element
            .querySelector("[data-bs-shared-analysis-consumer='lesson']")
            ?.querySelector("[data-bs-shared-analysis-presentation]")
            ?.dataset.bsSharedAnalysisPresentation,
          sticky: Boolean(
            element.querySelector(".bs-analysis-results-checker-decision")
          ),
          stickyHeight: element
            .querySelector(".bs-analysis-results-checker-decision")
            ?.getBoundingClientRect().height,
          viewportHeight: window.innerHeight
        }));
        check(
          revealed.shared === "true" &&
            revealed.candidateCount === 8 &&
            revealed.active === CHECKER_CANDIDATE_IDS[7],
          checkerContext,
          "checker reveal uses the shared viewer and preserves eight candidates"
        );
        check(
          revealed.image ===
            "/assets/positions/node-k001/checker/candidate-8.svg",
          checkerContext,
          "selected checker uses its supplied movement overlay"
        );
        check(
          revealed.sticky && revealed.comparison && revealed.selectedBar,
          checkerContext,
          "Task 005 top/selected comparison and probability bar remain available"
        );
        if (viewportCase.name === "mobile") {
          check(
            revealed.stickyHeight <= revealed.viewportHeight * 0.6,
            checkerContext,
            "mobile sticky checker surface leaves room for the candidate list"
          );
        }

        await host
          .locator(
            `[data-bs-analysis-candidate-id='${CHECKER_CANDIDATE_IDS[1]}'] > summary`
          )
          .click();
        await host
          .locator(
            `[data-bs-analysis-candidate-id='${CHECKER_CANDIDATE_IDS[2]}'] > summary`
          )
          .click();
        const disclosures = await host.evaluate((element) => ({
          active: element
            .querySelector(".bs-analysis-results-candidate.is-active")
            ?.dataset.bsAnalysisCandidateId,
          image: element
            .querySelector(".bs-analysis-results-board-image")
            ?.getAttribute("src"),
          open: Array.from(
            element.querySelectorAll(".bs-analysis-results-candidate[open]")
          ).map((candidate) => candidate.dataset.bsAnalysisCandidateId)
        }));
        check(
          disclosures.active === CHECKER_CANDIDATE_IDS[2] &&
            disclosures.image ===
              "/assets/positions/node-k001/checker/candidate-3.svg" &&
            disclosures.open.includes(CHECKER_CANDIDATE_IDS[0]) &&
            disclosures.open.includes(CHECKER_CANDIDATE_IDS[1]) &&
            disclosures.open.includes(CHECKER_CANDIDATE_IDS[2]) &&
            disclosures.open.includes(CHECKER_CANDIDATE_IDS[7]),
          checkerContext,
          "active movement board is independent of open candidate disclosures"
        );
        const checkerPage = await componentSnapshot(checkerTab);
        check(
          checkerPage.overflow <= 0,
          checkerContext,
          "checker page has no overflow"
        );
        check(
          checkerPage.duplicateComponentIds.length === 0,
          checkerContext,
          "checker component IDs remain unique"
        );
        check(
          checkerPage.componentErrors === 0 &&
            (await consoleErrors(checkerTab)).length === 0,
          checkerContext,
          "checker page has no mount or console errors"
        );
      } catch (error) {
        failures.push({
          context: checkerContext,
          message: `browser helper error: ${String(error)}`
        });
      }
    }
  } finally {
    await viewport.reset();
    await browser.tabs.finalize();
  }

  const report = {
    checks,
    failures,
    pages,
    durationMs: Date.now() - started
  };
  return {
    ...report,
    summary: summarizeLessonAnalysisReport(report)
  };
}
