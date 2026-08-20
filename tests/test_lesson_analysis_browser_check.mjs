import assert from "node:assert/strict";

import {
  CANONICAL_LESSON_ANALYSIS_SOURCE,
  CHECKER_CANDIDATE_IDS,
  CUBE_ACTION_IDS,
  LESSON_ANALYSIS_ROUTES,
  summarizeLessonAnalysisReport
} from "../scripts/lesson_analysis_browser_check.mjs";

assert.equal(
  CANONICAL_LESSON_ANALYSIS_SOURCE,
  "/data/analyzer-node-k001-lesson-preview.json"
);

assert.deepEqual(CUBE_ACTION_IDS, {
  noDouble: "b0b5a1bdb5eebe7e4dd2ead2e48b22827ff870401381fe21a6f4d3eb0308e1ad",
  take: "5134e196c229cf5b7b36ce230fe26eedbb75ab8e1851010d6316008c233cfa0f",
  pass: "7ace038e9967b27f4c954b1a9b813f991f963e054e3994d6796d3cfd4c27a936"
});

assert.deepEqual(CHECKER_CANDIDATE_IDS, [
  "cebe056b9fba14bb3a4fd58aa8f3e3d5430d98045ff21850c994bd24add37745",
  "44f91cbe042d6b615184f62d32d59337e3a35f709b875f11958bfdc2bf421477",
  "2940ef714c8cff1a3895543725738b43d64264c425968c3448c0a251a0e1542d",
  "5fd8fc14885e320a36c7769bf3127c2662c3d9f3164418872c7696be426460c8",
  "3c03cda00d76d9fbb7acc6d54dc78d2079fee4c1f10c946e4b2f3b8866a0027b",
  "09806fcf119b0f5742865fd64f987cecc00a28338b429a89a8098aacca864cf0",
  "6a2d4cbf49af863c3ca425061a616d836ef10e80429714fba0829180d2ec5837",
  "96d18ebbdcf54e9eb07265464db5b9e2100c5c0c6ae6c46e90a8a3a2258862d2"
]);

assert.deepEqual(LESSON_ANALYSIS_ROUTES, {
  cube: "/learn/cube/what-the-cube-is-asking.html",
  checker: "/learn/cube/why-is-25-percent-the-basic-take-point.html"
});

assert.deepEqual(
  summarizeLessonAnalysisReport({
    checks: 12,
    failures: [],
    pages: 4,
    durationMs: 250
  }),
  {
    passed: true,
    checks: 12,
    failures: 0,
    pages: 4,
    durationMs: 250
  }
);

assert.equal(
  summarizeLessonAnalysisReport({
    checks: 1,
    failures: [{ context: "mobile/cube", message: "overflow" }],
    pages: 1,
    durationMs: 50
  }).passed,
  false
);

console.log("lesson analysis browser helper tests passed");
