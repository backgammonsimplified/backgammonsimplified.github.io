import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  DEFAULT_MANIFEST,
  summarizeReport
} from "../scripts/release_ui_browser_check.mjs";

const helperSource = readFileSync(
  new URL("../scripts/release_ui_browser_check.mjs", import.meta.url),
  "utf8"
);
const canonicalHelperSource = readFileSync(
  new URL(
    "../scripts/testing/ux/browser/release_ui_browser_check.mjs",
    import.meta.url
  ),
  "utf8"
);

assert.equal(DEFAULT_MANIFEST.version, 2);
assert.deepEqual(
  DEFAULT_MANIFEST.viewports.map((item) => item.name),
  [
    "desktop-1440",
    "laptop-1280",
    "tablet-1024",
    "mobile-390",
    "small-mobile-320"
  ]
);
assert.ok(DEFAULT_MANIFEST.pages.some((page) => page.id === "home"));
assert.deepEqual(
  DEFAULT_MANIFEST.pages.find((page) => page.id === "analyze")
    .required_markers,
  ["data-bs-live-analyzer"]
);
assert.deepEqual(
  DEFAULT_MANIFEST.pages.find((page) => page.id === "cube-lesson")
    .required_markers,
  ["data-bs-cube-decision"]
);
assert.equal(
  DEFAULT_MANIFEST.pages.filter(
    (page) => page.kind === "edge-scroll-fixture"
  ).length,
  0
);

assert.deepEqual(
  summarizeReport({
    pages: 4,
    checks: 20,
    failures: [],
    consoleMessages: [],
    durationMs: 100
  }),
  {
    passed: true,
    pages: 4,
    checks: 20,
    failures: 0,
    consoleMessages: 0,
    durationMs: 100
  }
);

assert.equal(
  summarizeReport({
    pages: 1,
    checks: 2,
    failures: [{ context: "mobile/home", message: "overflow" }],
    consoleMessages: ["error"],
    durationMs: 50
  }).passed,
  false
);

assert.ok(
  helperSource.includes("TOC rail collapse also hides the lesson track")
);
assert.ok(
  helperSource.includes("restoring the TOC rail also restores the lesson track")
);
assert.ok(
  /waitForLocatorVisibility\(lessonTrack,\s*false\)/.test(
    canonicalHelperSource
  )
);
assert.ok(
  /waitForLocatorVisibility\(lessonTrack,\s*true\)/.test(
    canonicalHelperSource
  )
);
assert.ok(canonicalHelperSource.includes("checksByContext[context]"));
assert.ok(canonicalHelperSource.includes("interactive analyzer form is present"));
assert.ok(canonicalHelperSource.includes("analyzer shared results mount is present"));
assert.ok(!canonicalHelperSource.includes("#bs-position-preview-frame"));
assert.ok(!helperSource.includes("[data-bs-lesson-track-toggle]"));
assert.match(
  helperSource,
  /await scrollTo\(tab, 1400\);[\s\S]*await scrollTo\(tab, 900\);/
);
assert.ok(
  helperSource.includes('tab.playwright.locator(".bs-term-lookup-close")')
);

console.log("UI release browser helper tests passed");
