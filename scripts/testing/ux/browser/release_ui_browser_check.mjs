import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  classifyBrowserFinding,
  summarizeStability
} from "../../quality/browser/finding_stability.mjs";
import { groupFindingsByRootCause } from "../../quality/browser/root_cause_groups.mjs";

const manifestUrl = new URL("./ui_release_manifest.json", import.meta.url);

export const DEFAULT_MANIFEST = JSON.parse(
  readFileSync(manifestUrl, "utf8")
);

const delay = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

const retryControllerDeadline = async (operation, attempts = 3) => {
  let lastError = null;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      if (!/deadline|timed out/i.test(String(error)) || attempt === attempts) {
        throw error;
      }
      await delay(100);
    }
  }
  throw lastError;
};

const safeName = (value) => value.replace(/[^a-z0-9-]+/gi, "-").toLowerCase();

const accessibilitySnapshot = (tab) =>
  tab.playwright.locator("html").evaluate(() => {
    const visible = (element) => {
      const style = window.getComputedStyle(element);
      const rectangle = element.getBoundingClientRect();
      return (
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        rectangle.width > 0 &&
        rectangle.height > 0
      );
    };
    const describe = (element) =>
      element.id ||
      element.getAttribute("name") ||
      element.getAttribute("aria-label") ||
      element.tagName.toLowerCase();
    const allIds = Array.from(document.querySelectorAll("[id]"), (item) => item.id);
    const duplicateIds = Array.from(
      new Set(allIds.filter((id, index) => allIds.indexOf(id) !== index))
    ).sort();
    const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6"))
      .filter(visible)
      .map((heading) => Number(heading.tagName.slice(1)));
    const headingSkips = headings
      .map((level, index) => ({ from: headings[index - 1], to: level }))
      .filter((item, index) => index > 0 && item.to > item.from + 1);
    const controls = Array.from(
      document.querySelectorAll("a[href],button,input,select,textarea,[tabindex]")
    ).filter(visible);
    const clippedControls = controls
      .filter((element) => {
        const rectangle = element.getBoundingClientRect();
        const inVerticalViewport =
          rectangle.bottom > 0 && rectangle.top < window.innerHeight;
        return (
          inVerticalViewport &&
          (rectangle.left < -1 || rectangle.right > window.innerWidth + 1)
        );
      })
      .slice(0, 20)
      .map(describe);
    const unlabeledControls = Array.from(
      document.querySelectorAll("input:not([type='hidden']),select,textarea")
    )
      .filter(visible)
      .filter((element) => {
        const id = element.id;
        return !(
          element.getAttribute("aria-label") ||
          element.getAttribute("aria-labelledby") ||
          (id && document.querySelector(`label[for='${CSS.escape(id)}']`)) ||
          element.closest("label")
        );
      })
      .map(describe);
    const missingImageAlt = Array.from(document.querySelectorAll("img"))
      .filter((image) => !image.hasAttribute("alt"))
      .slice(0, 20)
      .map((image) => image.getAttribute("src") || "img");
    const failedImages = Array.from(document.images)
      .filter((image) => image.complete && image.naturalWidth === 0)
      .slice(0, 20)
      .map((image) => image.currentSrc || image.src);
    const failedStylesheets = Array.from(
      document.querySelectorAll("link[rel='stylesheet']")
    )
      .filter((link) => !link.getAttribute("href"))
      .slice(0, 20)
      .map(() => "stylesheet without href");
    const resourceFailures =
      window.performance &&
      typeof window.performance.getEntriesByType === "function"
        ? window.performance
            .getEntriesByType("resource")
            .filter((entry) => Number(entry.responseStatus || 0) >= 400)
            .slice(0, 20)
            .map((entry) => ({ name: entry.name, status: entry.responseStatus }))
        : [];
    const fixedOrSticky = Array.from(document.querySelectorAll("body *"))
      .filter(visible)
      .filter((element) => {
        const position = window.getComputedStyle(element).position;
        return position === "fixed" || position === "sticky";
      });
    const coveredTargets = controls
      .concat(Array.from(document.querySelectorAll("h1,h2,h3")).filter(visible))
      .filter((element) => {
        const rectangle = element.getBoundingClientRect();
        if (
          rectangle.bottom <= 0 ||
          rectangle.top >= window.innerHeight ||
          rectangle.right <= 0 ||
          rectangle.left >= window.innerWidth
        ) {
          return false;
        }
        const x = Math.max(0, Math.min(window.innerWidth - 1, rectangle.left + rectangle.width / 2));
        const y = Math.max(0, Math.min(window.innerHeight - 1, rectangle.top + rectangle.height / 2));
        const covering = document.elementFromPoint(x, y);
        return fixedOrSticky.some(
          (overlay) => overlay !== element && overlay.contains(covering) && !overlay.contains(element)
        );
      })
      .slice(0, 20)
      .map(describe);
    return {
      duplicateIds,
      failedImages,
      failedStylesheets,
      resourceFailures,
      clippedControls,
      coveredTargets,
      focusableControls: controls.filter(
        (element) => !element.hasAttribute("disabled") && element.tabIndex >= 0
      ).length,
      headingSkips,
      h1Count: headings.filter((level) => level === 1).length,
      landmarks: {
        main: document.querySelectorAll("main,[role='main']").length,
        navigation: document.querySelectorAll("nav,[role='navigation']").length,
        footer: document.querySelectorAll("footer,[role='contentinfo']").length
      },
      missingImageAlt,
      unlabeledControls,
      viewport: {
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth
      }
    };
  });

const focusedElementState = (tab) =>
  tab.playwright.locator("html").evaluate(() => {
    const active = document.activeElement;
    if (!active || active === document.body || active === document.documentElement) {
      return {
        identity: "body",
        interactive: false,
        selector: "body",
        visibleIndicator: false
      };
    }
    const style = window.getComputedStyle(active);
    const tag = active.tagName.toLowerCase();
    const selector = active.id
      ? `#${active.id}`
      : active.hasAttribute("data-bs-mobile-tools-edge")
        ? "[data-bs-mobile-tools-edge]"
        : active.hasAttribute("data-bs-mobile-tools-close")
          ? "[data-bs-mobile-tools-close]"
          : active.matches("button.navbar-toggler")
            ? "button.navbar-toggler"
            : `${tag}${active.getAttribute("href") ? `[href='${active.getAttribute("href")}']` : ""}`;
    const identity =
      active.id ||
      active.getAttribute("data-bs-analysis-choice") ||
      active.getAttribute("aria-label") ||
      active.textContent.trim().replace(/\s+/g, " ").slice(0, 80) ||
      tag;
    const visibleIndicator =
      active.matches(":focus-visible") &&
      ((style.outlineStyle !== "none" && Number.parseFloat(style.outlineWidth) > 0) ||
        style.boxShadow !== "none" ||
        (Number.parseFloat(style.borderWidth) > 0 &&
          style.borderColor !== "rgba(0, 0, 0, 0)"));
    return {
      identity,
      interactive: active.matches(
        "a[href],button,input,select,textarea,[tabindex]:not([tabindex='-1'])"
      ),
      selector,
      tag,
      role: active.getAttribute("role"),
      href: active.getAttribute("href"),
      visibleIndicator
    };
  });

const focusSnapshot = async (tab, { mobile }) => {
  const keyboardSeed = await visibleLocator(
    tab.playwright.locator(
      "a[href],button,input,select,textarea,[tabindex]:not([tabindex='-1'])"
    )
  );
  if (keyboardSeed) {
    await keyboardSeed.press("Shift+Tab");
  }
  const pressFocused = async (key) => {
    const focused = tab.playwright.locator(":focus");
    if ((await focused.count()) !== 1) {
      return false;
    }
    await focused.press(key);
    return true;
  };
  const pageFeatures = await tab.playwright.locator("html").evaluate(() => ({
    mobileDrawerPresent: Boolean(
      document.querySelector("[data-bs-mobile-tools-edge]")
    ),
    mobileNavigationPresent: Boolean(document.querySelector("button.navbar-toggler")),
    skipLinkPresent: Boolean(
      Array.from(document.querySelectorAll("a[href^='#']")).find((link) =>
        /skip/i.test(link.textContent || "")
      )
    )
  }));
  const reached = [];
  const missingIndicators = [];
  let mobileNavigation = null;
  let mobileDrawer = null;
  let skipLink = null;
  for (let index = 0; index < 20; index += 1) {
    await pressFocused("Tab");
    const state = await focusedElementState(tab);
    reached.push({ order: index + 1, ...state });
    if (state.interactive && !state.visibleIndicator) {
      missingIndicators.push(state.identity);
    }
    if (mobile && state.selector === "button.navbar-toggler" && !mobileNavigation) {
      await pressFocused("Enter");
      await delay(100);
      const opened = await tab.playwright.locator("html").evaluate(() => ({
        expanded:
          document.querySelector("button.navbar-toggler")?.getAttribute("aria-expanded") ||
          null,
        menuVisible: Boolean(
          document.querySelector("#navbarCollapse")?.getClientRects().length
        )
      }));
      await pressFocused("Tab");
      const menuFocus = await focusedElementState(tab);
      await pressFocused("Escape");
      await delay(100);
      const returned = await focusedElementState(tab);
      mobileNavigation = { opened, menuFocus, returned };
    }
    if (
      mobile &&
      state.selector === "[data-bs-mobile-tools-edge]" &&
      !mobileDrawer
    ) {
      await pressFocused("Enter");
      await delay(100);
      const opened = await tab.playwright.locator("html").evaluate(() => ({
        expanded:
          document
            .querySelector("[data-bs-mobile-tools-edge]")
            ?.getAttribute("aria-expanded") || null,
        drawerVisible: Boolean(
          document
            .querySelector("[data-bs-mobile-tools-drawer]")
            ?.getClientRects().length
        )
      }));
      await pressFocused("Tab");
      const drawerFocus = await focusedElementState(tab);
      await pressFocused("Escape");
      await delay(100);
      const returned = await focusedElementState(tab);
      mobileDrawer = { opened, drawerFocus, returned };
    }
    if (!skipLink && state.href?.startsWith("#") && /skip/i.test(state.identity)) {
      await pressFocused("Enter");
      await delay(100);
      skipLink = {
        trigger: state,
        destination: await focusedElementState(tab),
        url: await tab.url()
      };
    }
  }
  const interactiveReached = reached.filter((item) => item.interactive);
  const identities = interactiveReached.map((item) => item.selector);
  const trapDetected = identities.some(
    (identity, index) =>
      index >= 2 &&
      identities[index - 1] === identity &&
      identities[index - 2] === identity
  );
  return {
    reached,
    interactiveReached: interactiveReached.length,
    distinct: new Set(identities).size,
    meaningfulOrder: identities.length >= 2 && new Set(identities).size >= 2,
    trapDetected,
    missingIndicators: Array.from(new Set(missingIndicators)).sort(),
    pageFeatures,
    mobileNavigation,
    mobileDrawer,
    skipLink
  };
};

const visibleLocator = async (locator) => {
  const count = await locator.count();
  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index);
    if (await candidate.isVisible()) {
      return candidate;
    }
  }
  return null;
};

const clickInPlace = async (tab, locator) => {
  const point = await locator.evaluate((element) => {
    const rectangle = element.getBoundingClientRect();
    return {
      x: rectangle.left + rectangle.width / 2,
      y: rectangle.top + rectangle.height / 2
    };
  });
  await tab.cua.click(point);
};

const pagePosition = (tab) =>
  retryControllerDeadline(() => tab.playwright.evaluate(
    () => ({
      clientHeight: document.documentElement.clientHeight,
      clientWidth: document.documentElement.clientWidth,
      scrollHeight: document.documentElement.scrollHeight,
      scrollWidth: document.documentElement.scrollWidth,
      scrollY: window.scrollY
    }),
    undefined,
    { timeoutMs: 10000 }
  ));

export const EXPECTED_CONTINUOUS_APPEND_COUNT = 1;

export const continuousConfigForPage = (page) => {
  if (page.kind === "learn-lesson") {
    return {
      markerSelector: ".bs-learn-scroll-lesson-marker",
      routeAttribute: "data-bs-learn-scroll-lesson-route",
      sentinelSelector: ".bs-learn-scroll-sentinel",
      endSelector: "[data-bs-learn-scroll-end]",
      namespace: "bs-learn-scroll-"
    };
  }
  if (page.kind === "research-article") {
    return {
      markerSelector: ".bs-research-scroll-marker",
      routeAttribute: "data-bs-research-scroll-marker",
      sentinelSelector: ".bs-research-scroll-sentinel",
      endSelector: ".bs-research-scroll-end",
      namespace: "bs-research-scroll-"
    };
  }
  return null;
};

const waitForLocatorVisibility = async (
  locator,
  expectedVisible,
  attempts = 20
) => {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const visible = Boolean(await visibleLocator(locator));
    if (visible === expectedVisible) {
      return true;
    }
    if (attempt < attempts) {
      await delay(50);
    }
  }
  return false;
};

const continuousStateSnapshot = (tab, config) =>
  retryControllerDeadline(() => tab.playwright.locator("#quarto-document-content").evaluate((_root, stateConfig) => {
    const markers = Array.from(
      document.querySelectorAll(stateConfig.markerSelector)
    );
    const loadedPageOrder = markers.map((marker) =>
      marker.getAttribute(stateConfig.routeAttribute)
    );
    const appendedPages = markers.slice(1).map((marker, index) => {
      const ids = [];
      let node = marker.nextElementSibling;
      const nextMarker = markers[index + 2] || null;
      while (node && node !== nextMarker && !node.matches(stateConfig.sentinelSelector)) {
        if (node.id) {
          ids.push(node.id);
        }
        node.querySelectorAll("[id]").forEach((element) => ids.push(element.id));
        node = node.nextElementSibling;
      }
      return {
        route: marker.getAttribute(stateConfig.routeAttribute),
        containerIds: Array.from(new Set(ids)).sort()
      };
    });
    const sentinel = document.querySelector(stateConfig.sentinelSelector);
    const endAvailable = Boolean(document.querySelector(stateConfig.endSelector));
    let historyState = null;
    try {
      historyState = JSON.parse(JSON.stringify(window.history?.state ?? null));
    } catch (_error) {
      historyState = "unserializable";
    }
    return {
      documentIdentity: {
        bodyClasses: Array.from(document.body.classList).sort(),
        h1: document.querySelector("h1")?.textContent?.trim() || null,
        route: window.location.pathname
      },
      loadedPageOrder,
      appendedPages,
      markerCount: markers.length,
      sentinel: sentinel
        ? {
            available: true,
            loading: sentinel.classList.contains("is-loading"),
            route:
              sentinel.getAttribute("data-bs-learn-scroll-sentinel") ||
              sentinel.getAttribute("data-bs-research-scroll-sentinel")
          }
        : { available: false, loading: false, route: null },
      completionSignal: Boolean(
        endAvailable || (sentinel && !sentinel.classList.contains("is-loading"))
      ),
      endAvailable,
      scrollPosition: {
        clientHeight: document.documentElement.clientHeight,
        scrollHeight: document.documentElement.scrollHeight,
        scrollY: window.scrollY
      },
      url: window.location.href,
      history: {
        length: window.history?.length ?? null,
        state: historyState
      }
    };
  }, config, { timeoutMs: 10000 }));

const waitForContinuousState = async (
  tab,
  config,
  predicate,
  timeoutMs = 10000
) => {
  const started = Date.now();
  let state = await continuousStateSnapshot(tab, config);
  while (!predicate(state) && Date.now() - started < timeoutMs) {
    await delay(100);
    state = await continuousStateSnapshot(tab, config);
  }
  return {
    state,
    timeoutReason: predicate(state)
      ? null
      : `expected continuous state was not reached within ${timeoutMs}ms`
  };
};

const scrollTo = async (tab, position) => {
  const current = await pagePosition(tab);
  const target = Number.isSafeInteger(position)
    ? Math.min(position, current.scrollHeight)
    : current.scrollHeight;
  await tab.cua.scroll({
    x: Math.max(1, Math.min(100, current.clientWidth - 1)),
    y: Math.max(1, Math.min(100, current.clientHeight - 1)),
    scrollX: 0,
    scrollY: target - current.scrollY
  });
  await delay(120);
};

const countVisible = async (locator) => {
  const count = await locator.count();
  let visible = 0;
  for (let index = 0; index < count; index += 1) {
    if (await locator.nth(index).isVisible()) {
      visible += 1;
    }
  }
  return visible;
};

const duplicateIds = (tab, rootSelector = "html") =>
  tab.playwright.locator(rootSelector).evaluate((root) => {
    const counts = new Map();
    root.querySelectorAll("[id]").forEach((element) => {
      if (element.closest(".quarto-sidebar-toggle-contents")) {
        return;
      }
      counts.set(element.id, (counts.get(element.id) || 0) + 1);
    });
    return Array.from(counts)
      .filter((entry) => entry[1] > 1)
      .map((entry) => entry[0])
      .sort();
  });

const interactWithLookup = async (
  tab,
  check,
  context,
  desktop,
  openAtTopOnly = false
) => {
  if (desktop) {
    const openLookup = await visibleLocator(
      tab.playwright.locator("[data-bs-term-lookup]")
    );
    check(
      Boolean(openLookup),
      context,
      "desktop term lookup is open at the top of the page"
    );
    if (openAtTopOnly) {
      return;
    }
  }
  await scrollTo(tab, 1400);
  await delay(700);
  await scrollTo(tab, 900);
  await delay(700);
  const toggle = await visibleLocator(
    tab.playwright.locator(
      "[data-bs-site-term-toggle], [data-bs-mobile-term-toggle]"
    )
  );
  if (!toggle) {
    check(false, context, "term lookup reveal control is missing");
    return;
  }
  check(
    (await toggle.getAttribute("aria-expanded")) === "false",
    context,
    "term lookup is initially collapsed"
  );
  const before = (await pagePosition(tab)).scrollY;
  await clickInPlace(tab, toggle);
  await delay(250);
  const afterOpen = (await pagePosition(tab)).scrollY;
  check(
    Math.abs(afterOpen - before) <= 32,
    context,
    "opening term lookup preserves scroll position " +
      `(before=${before}, after=${afterOpen})`
  );
  const close = await visibleLocator(
    tab.playwright.locator(".bs-term-lookup-close")
  );
  if (close) {
    await clickInPlace(tab, close);
    await delay(250);
  }
};

const interactWithMobileDrawer = async (tab, check, context) => {
  const edge = await visibleLocator(
    tab.playwright.locator("[data-bs-mobile-tools-edge]")
  );
  check(Boolean(edge), context, "mobile page-tools edge bar is visible");
  if (!edge) {
    return;
  }
  check(
    (await edge.textContent()).trim() === "",
    context,
    "mobile edge bar has no arrow or visible label"
  );
  await edge.click();
  const drawer = await visibleLocator(
    tab.playwright.locator("[data-bs-mobile-tools-drawer]")
  );
  check(Boolean(drawer), context, "mobile page-tools drawer opens");
  if (!drawer) {
    return;
  }
  check(
    (await countVisible(drawer.locator("a[href]"))) >= 1,
    context,
    "mobile drawer contains visible table-of-contents links"
  );
  check(
    (await drawer.locator("[data-bs-term-lookup]").count()) === 0,
    context,
    "mobile drawer omits the compact term search"
  );
  const close = drawer.locator("[data-bs-mobile-tools-close]");
  await close.click();
  check(
    (await edge.getAttribute("aria-expanded")) === "false",
    context,
    "mobile page-tools drawer closes"
  );
};

const interactWithMobileNavigation = async (tab, check, context) => {
  const toggle = tab.playwright.locator("button.navbar-toggler");
  const count = await toggle.count();
  check(count === 1, context, "mobile navigation has one menu toggle");
  if (count !== 1) {
    return;
  }
  await clickInPlace(tab, toggle);
  check(
    (await toggle.getAttribute("aria-expanded")) === "true",
    context,
    "mobile navigation menu opens"
  );
  const menu = tab.playwright.locator("#navbarCollapse");
  check(
    (await menu.count()) === 1 && (await menu.isVisible()),
    context,
    "mobile navigation links are visible"
  );
  await clickInPlace(tab, toggle);
  check(
    (await toggle.getAttribute("aria-expanded")) === "false",
    context,
    "mobile navigation menu closes"
  );
};

const interactWithGlossarySidebar = async (tab, check, context) => {
  const link = await visibleLocator(
    tab.playwright.locator("main .bs-inline-glossary[data-bs-glossary-slug]")
  );
  if (!link) {
    check(false, context, "inline glossary link is available for sidebar flow");
    return;
  }
  await link.click();
  const sidebar = tab.playwright.locator("[data-bs-glossary-sidebar]");
  check(
    (await sidebar.count()) === 1 && (await sidebar.isVisible()),
    context,
    "inline glossary link opens the definition sidebar"
  );
  const close = sidebar.locator("[data-bs-glossary-sidebar-close]");
  if ((await close.count()) === 1) {
    await close.click();
    check(!(await sidebar.isVisible()), context, "glossary definition sidebar closes");
  } else {
    check(false, context, "glossary definition sidebar has a close control");
  }
};

const interactWithToc = async (
  tab,
  check,
  context,
  desktop,
  collapseLessonTrack = false
) => {
  const toggleState = async () => {
    const toggle = await visibleLocator(
      tab.playwright.locator("[data-bs-toc-heading-toggle]")
    );
    return toggle
      ? {
          available: true,
          expanded: await toggle.getAttribute("aria-expanded")
        }
      : { available: false, expanded: null };
  };
  const clickToggle = async () => {
    const toggle = await visibleLocator(
      tab.playwright.locator("[data-bs-toc-heading-toggle]")
    );
    if (!toggle) {
      return false;
    }
    await toggle.click();
    return true;
  };
  const initial = await toggleState();
  if (!desktop) {
    check(!initial.available, context, "desktop TOC heading control stays hidden");
    return;
  }
  check(initial.available, context, "compact TOC heading control is visible");
  if (!initial.available) {
    return;
  }
  const lessonTrack = collapseLessonTrack
    ? await visibleLocator(
        tab.playwright.locator(".bs-lesson-track-content")
      )
    : null;
  if (collapseLessonTrack) {
    check(
      Boolean(lessonTrack),
      context,
      "lesson track is visible before collapsing the TOC rail"
    );
  }
  await clickToggle();
  const collapsed = await toggleState();
  check(
    collapsed.expanded === "false",
    context,
    "TOC links collapse"
  );
  check(
    collapsed.available,
    context,
    "TOC restore control remains available"
  );
  if (lessonTrack) {
    check(
      await waitForLocatorVisibility(lessonTrack, false),
      context,
      "TOC rail collapse also hides the lesson track"
    );
  }
  if (!collapsed.available) {
    return;
  }
  await clickToggle();
  const restored = await toggleState();
  check(
    restored.expanded === "true",
    context,
    "TOC links restore"
  );
  if (lessonTrack) {
    check(
      await waitForLocatorVisibility(lessonTrack, true),
      context,
      "restoring the TOC rail also restores the lesson track"
    );
  }
};

const interactWithLearnIndex = async (tab, check, context) => {
  const filters = tab.playwright.locator("[data-bs-learn-filters]");
  check((await filters.count()) === 1, context, "lesson filters exist");
  if ((await filters.count()) !== 1) {
    return;
  }
  check(
    (await filters.getAttribute("open")) === null,
    context,
    "lesson filters default collapsed"
  );
  await filters.locator(":scope > summary").click();
  check(
    (await filters.getAttribute("open")) !== null,
    context,
    "lesson filters expand"
  );
  const input = filters.locator("[data-bs-learn-search]");
  const items = tab.playwright.locator("[data-bs-learn-item]");
  const total = await items.count();
  await input.fill("What the Cube Is Really Asking");
  await delay(80);
  const visible = await countVisible(items);
  check(
    visible >= 1 && visible < total,
    context,
    "lesson search narrows the catalogue"
  );
  const clear = await visibleLocator(
    filters.locator("[data-bs-learn-clear]")
  );
  check(Boolean(clear), context, "lesson search exposes its clear control");
  if (clear) {
    await clear.click();
    check(
      (await countVisible(items)) === total,
      context,
      "clearing search restores lessons"
    );
  }
};

const interactWithRichFixture = async (tab, check, context) => {
  const summary = tab.playwright.locator(
    "details.bs-scroll-fixture-disclosure > summary"
  );
  check((await summary.count()) === 1, context, "rich disclosure exists");
  if ((await summary.count()) !== 1) {
    return;
  }
  await summary.click();
  check(
    (await tab.playwright.locator(".bs-scroll-fixture-svg").count()) === 2,
    context,
    "two SVG positions render"
  );
  const choices = tab.playwright.locator(
    ".bs-scroll-fixture-disclosure .bs-answer-choice"
  );
  check((await choices.count()) === 4, context, "four position choices render");
  const take = tab.playwright.getByRole("button", {
    name: "Take",
    exact: true
  });
  await take.click();
  check(
    (await take.getAttribute("aria-pressed")) === "true",
    context,
    "Take records its pressed state"
  );
  check(
    (await tab.playwright
      .locator("#bs-scroll-fixture-follow-up")
      .getAttribute("open")) !== null,
    context,
    "choice opens the nested explanation"
  );
};

const interactWithLessonAnalysisFixture = async (tab, check, context) => {
  const fixture = tab.playwright.locator("[data-bs-cube-decision]").nth(0);
  check(
    (await fixture.count()) === 1,
    context,
    "cube lesson analysis mounts"
  );
  if ((await fixture.count()) !== 1) {
    return;
  }
  const double = fixture.locator(
    "button[data-bs-analysis-choice='double']"
  );
  await double.click();
  check(
    (await double.getAttribute("aria-pressed")) === "true",
    context,
    "Double records its pressed state"
  );
  const take = fixture.locator(
    "button[data-bs-analysis-choice='take']"
  );
  check((await take.count()) === 1, context, "Double reveals Pass and Take");
  if ((await take.count()) === 1) {
    await take.click();
    check(
      (await take.getAttribute("aria-pressed")) === "true",
      context,
      "Take records its pressed state"
    );
  }
};

const interactWithEdgeFixture = async (tab, check, context) => {
  const fixture = tab.playwright.locator("[data-bs-ui-edge-fixture]");
  check((await fixture.count()) === 1, context, "edge fixture renders once");
  if ((await fixture.count()) !== 1) {
    return;
  }
  const longChoice = tab.playwright.getByRole("button", {
    name: "Keep playing with this unusually long choice label",
    exact: true
  });
  await longChoice.click();
  check(
    (await longChoice.getAttribute("aria-pressed")) === "true",
    context,
    "long action label remains clickable"
  );
  const panel = tab.playwright.locator("#bs-ui-edge-response");
  check(
    (await panel.getAttribute("open")) !== null,
    context,
    "edge layout panel opens"
  );
  const region = tab.playwright.locator(".bs-ui-edge-scroll-region");
  const regionMetrics = await region.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth
  }));
  check(
    regionMetrics.scrollWidth > regionMetrics.clientWidth,
    context,
    "wide table is contained in its own scroll region"
  );
  await tab.playwright
    .locator('a[href="#bs-ui-edge-anchor"]')
    .click();
  check(
    (await tab.url()).endsWith("#bs-ui-edge-anchor"),
    context,
    "fixture anchor navigation works"
  );
};

const interactWithGlossary = async (tab, check, context) => {
  const input = tab.playwright.locator("[data-bs-glossary-search]");
  check((await input.count()) === 1, context, "glossary search exists");
  if ((await input.count()) !== 1) {
    return;
  }
  const entries = tab.playwright.locator("[data-bs-glossary-entry]");
  const total = await entries.count();
  await input.fill("active builder");
  await delay(100);
  const visible = await countVisible(entries);
  check(
    visible >= 1 && visible < total,
    context,
    "glossary search narrows full definitions"
  );
  const clear = await visibleLocator(
    tab.playwright.locator("[data-bs-glossary-clear]")
  );
  if (clear) {
    await clear.click();
    check(
      (await countVisible(entries)) === total,
      context,
      "glossary clear restores full definitions"
    );
  } else {
    check(false, context, "glossary clear control is missing");
  }
  const trackFilter = tab.playwright.locator(
    "[data-bs-glossary-filter-track='Doubling Cube']"
  );
  check((await trackFilter.count()) === 1, context, "glossary track filter exists");
  if ((await trackFilter.count()) === 1) {
    await clickInPlace(tab, trackFilter);
    check(
      (await trackFilter.getAttribute("aria-pressed")) === "true" &&
        (await countVisible(entries)) < total,
      context,
      "glossary track filter narrows definitions"
    );
    await clickInPlace(tab, trackFilter);
  }
  await tab.goto(new URL("#active-builder", await tab.url()).href);
  check(
    (await tab.url()).endsWith("#active-builder") &&
      (await tab.playwright.locator("#active-builder").getAttribute("open")) !== null,
    context,
    "glossary anchor opens the requested definition"
  );
};

const runPageInteraction = async ({
  tab,
  page,
  viewport,
  check
}) => {
  const context = `${viewport.name}/${page.id}`;
  const desktop = viewport.width >= 992;
  if (!desktop) {
    await interactWithMobileNavigation(tab, check, context);
  }
  if (page.kind === "learn-index") {
    await interactWithLearnIndex(tab, check, context);
  }
  if (page.kind === "learn-lesson") {
    await interactWithToc(tab, check, context, desktop, true);
    if (desktop) {
      await interactWithLookup(tab, check, context, desktop);
    } else {
      await interactWithMobileDrawer(tab, check, context);
    }
    if ((page.required_markers || []).includes("data-bs-cube-decision")) {
      await interactWithLessonAnalysisFixture(tab, check, context);
    }
    await interactWithGlossarySidebar(tab, check, context);
  }
  if (page.kind === "rich-scroll-fixture") {
    await interactWithRichFixture(tab, check, context);
  }
  if (page.kind === "edge-scroll-fixture") {
    await interactWithEdgeFixture(tab, check, context);
  }
  if (page.kind === "research-article") {
    await interactWithToc(tab, check, context, desktop);
    if (desktop) {
      await interactWithLookup(tab, check, context, desktop, true);
    } else {
      await interactWithMobileDrawer(tab, check, context);
    }
    await interactWithGlossarySidebar(tab, check, context);
  }
  if (page.kind === "glossary") {
    await interactWithGlossary(tab, check, context);
  }
};

const clickThroughNavigation = async ({
  tab,
  browser,
  viewport,
  desktop,
  baseUrl,
  check
}) => {
  await tab.goto(new URL("/about.html", baseUrl).href);
  await delay(250);
  const learnLink = await visibleLocator(
    tab.playwright.getByRole("link", { name: "Learn", exact: true })
  );
  check(Boolean(learnLink), "desktop/click-through", "Learn nav link is visible");
  if (!learnLink) {
    return;
  }
  await learnLink.click();
  await delay(300);
  check(
    new URL(await tab.url()).pathname === "/learn/",
    "desktop/click-through",
    "navbar click reaches Learn"
  );
  let cubeTab = tab;
  if (browser) {
    cubeTab = await browser.tabs.new();
    await viewport.set({ width: desktop.width, height: desktop.height });
    await cubeTab.goto(new URL("/learn/", baseUrl).href);
    await delay(300);
  }
  const cubeLink = await visibleLocator(
    cubeTab.playwright.getByRole("link", {
      name: "The Doubling Cube",
      exact: true
    })
  );
  check(Boolean(cubeLink), "desktop/click-through", "Cube track link is visible");
  if (!cubeLink) {
    return cubeTab;
  }
  await cubeLink.click();
  await delay(300);
  check(
    new URL(await cubeTab.url()).pathname === "/learn/cube/",
    "desktop/click-through",
    "Learn click reaches the Cube track"
  );
  return cubeTab;
};

export const summarizeReport = (report) => ({
  passed: report.failures.length === 0,
  pages: report.pages,
  checks: report.checks,
  failures: report.failures.length,
  consoleMessages: report.consoleMessages.length,
  durationMs: report.durationMs
});

export async function runReleaseUiChecks({
  browser,
  tab,
  viewport,
  baseUrl,
  manifest = DEFAULT_MANIFEST,
  screenshotDir = null
}) {
  if ((!browser && !tab) || !viewport || !baseUrl) {
    throw new Error("browser or tab, plus viewport and baseUrl, are required");
  }
  const started = Date.now();
  const failures = [];
  const consoleMessages = [];
  const consoleSeen = new Set();
  const limitations = [];
  const continuousLoading = [];
  const focusTraversal = [];
  const interactionStates = [];
  const screenshots = [];
  let failureScreenshots = 0;
  let checks = 0;
  const checksByContext = {};
  let pages = 0;
  const executedPageContexts = [];
  const check = (condition, context, message, metadata = {}) => {
    checks += 1;
    checksByContext[context] = (checksByContext[context] || 0) + 1;
    if (!condition) {
      failures.push({ context, message, ...metadata });
    }
  };
  const acquireTab = async () => {
    if (!browser) {
      return tab;
    }
    await browser.tabs.finalize();
    return browser.tabs.new();
  };
  const collectConsole = async (activeTab, context) => {
    try {
      const logs = await activeTab.dev.logs();
      for (const entry of logs) {
        const text =
          typeof entry === "string" ? entry : JSON.stringify(entry);
        if (consoleSeen.has(text)) {
          continue;
        }
        consoleSeen.add(text);
        consoleMessages.push(text);
        if (/(TypeError|ReferenceError|Uncaught|console\.error)/i.test(text)) {
          failures.push({ context, message: text });
        }
      }
    } catch (error) {
      failures.push({
        context,
        message: `could not read console logs: ${String(error)}`
      });
    }
  };
  const saveScreenshot = async (activeTab, viewportCase, page, kind) => {
    if (!screenshotDir) {
      return;
    }
    if (
      kind === "failure" &&
      failureScreenshots >= (manifest.failure_screenshot_limit || 30)
    ) {
      return;
    }
    const fileName = `${safeName(viewportCase.name)}-${safeName(page.id)}${
      kind === "failure" ? `-failure-${failureScreenshots + 1}` : ""
    }.png`;
    const relativePath = `screenshots/browser/${fileName}`;
    try {
      mkdirSync(screenshotDir, { recursive: true });
      writeFileSync(join(screenshotDir, fileName), await activeTab.screenshot({ fullPage: false }));
      screenshots.push({ kind, page: page.id, route: page.route, viewport: viewportCase.name, path: relativePath });
      if (kind === "failure") {
        failureScreenshots += 1;
      }
    } catch (error) {
      failures.push({
        context: `${viewportCase.name}/${page.id}/screenshot`,
        message: `could not save ${kind} screenshot: ${String(error)}`,
        category: "test-infrastructure"
      });
    }
  };

  try {
    for (const viewportCase of manifest.viewports) {
      await viewport.set({
        width: viewportCase.width,
        height: viewportCase.height
      });
      for (const page of manifest.pages) {
        const context = `${viewportCase.name}/${page.id}`;
        pages += 1;
        executedPageContexts.push(context);
        const activeTab = await acquireTab();
        const failureCountBeforePage = failures.length;
        const continuousConfig = continuousConfigForPage(page);
        let initialContinuousState = null;
        let phase = "navigation";
        try {
          await viewport.set({
            width: viewportCase.width,
            height: viewportCase.height
          });
          await activeTab.goto(new URL(page.route, baseUrl).href);
          await activeTab.playwright.waitForLoadState({
            state: "domcontentloaded",
            timeoutMs: 30000
          });
          await scrollTo(activeTab, 0);
          await delay(500);

          if (continuousConfig) {
            phase = "continuous loading initialization";
            const initialized = await waitForContinuousState(
              activeTab,
              continuousConfig,
              (state) =>
                state.markerCount === 1 &&
                state.sentinel.available &&
                !state.sentinel.loading
            );
            initialContinuousState = initialized.state;
            check(
              initialized.timeoutReason === null,
              context,
              initialized.timeoutReason || "continuous loading initialization is ready"
            );
            check(
              initialContinuousState.documentIdentity.route === page.route,
              context,
              `continuous loading starts on the expected route: ${initialContinuousState.documentIdentity.route}`
            );
            check(
              Boolean(initialContinuousState.documentIdentity.h1),
              context,
              "continuous loading records the initial document identity"
            );
            check(
              initialContinuousState.appendedPages.length === 0,
              context,
              `continuous loading starts before appended pages (actual=${initialContinuousState.appendedPages.length})`
            );
          }

          phase = "landmarks and initial layout";
          const audit = await accessibilitySnapshot(activeTab);
          check(audit.landmarks.main === 1, context, "page has one main landmark");
          check(audit.landmarks.navigation >= 1, context, "page has a navigation landmark");
          check(audit.landmarks.footer >= 1, context, "page has a footer landmark");
          check(audit.h1Count === 1, context, "page has exactly one visible H1");
          check(audit.headingSkips.length === 0, context, "heading levels do not skip");
          check(audit.duplicateIds.length === 0, context, `initial IDs are unique${
            audit.duplicateIds.length ? `: ${audit.duplicateIds.join(", ")}` : ""
          }`);
          check(audit.unlabeledControls.length === 0, context, `form controls have labels${
            audit.unlabeledControls.length ? `: ${audit.unlabeledControls.join(", ")}` : ""
          }`);
          check(audit.missingImageAlt.length === 0, context, `images provide alt attributes${
            audit.missingImageAlt.length ? `: ${audit.missingImageAlt.join(", ")}` : ""
          }`);
          check(audit.failedImages.length === 0, context, `required images load${
            audit.failedImages.length ? `: ${audit.failedImages.join(", ")}` : ""
          }`);
          check(audit.failedStylesheets.length === 0, context, `required stylesheets load${
            audit.failedStylesheets.length ? `: ${audit.failedStylesheets.join(", ")}` : ""
          }`);
          check(audit.resourceFailures.length === 0, context, `required resources avoid HTTP failures${
            audit.resourceFailures.length ? `: ${JSON.stringify(audit.resourceFailures)}` : ""
          }`);
          check(audit.clippedControls.length === 0, context, `visible controls are not horizontally clipped${
            audit.clippedControls.length ? `: ${audit.clippedControls.join(", ")}` : ""
          }`);
          check(audit.coveredTargets.length === 0, context, `fixed or sticky elements do not cover controls or headings${
            audit.coveredTargets.length ? `: ${audit.coveredTargets.join(", ")}` : ""
          }`);
          const initialMetrics = await pagePosition(activeTab);
          check(
            initialMetrics.scrollWidth <= initialMetrics.clientWidth + 1,
            context,
            "page has no horizontal overflow"
          );
          for (const marker of page.required_markers || []) {
            const markerPresent = await activeTab.playwright.locator("html").evaluate(
              (root, requiredMarker) => {
                if (requiredMarker.startsWith("data-")) {
                  return Boolean(root.querySelector(`[${requiredMarker}]`));
                }
                if (requiredMarker.startsWith("bs-")) {
                  return Boolean(
                    root.querySelector(`.${requiredMarker}, #${requiredMarker}`)
                  );
                }
                return root.textContent.includes(requiredMarker);
              },
              marker
            );
            check(markerPresent, context, `required marker is present: ${marker}`);
          }
          if (page.kind === "analyzer") {
            check(
              (await activeTab.playwright.locator("[data-bs-live-analyzer]").count()) === 1,
              context,
              "interactive analyzer form is present"
            );
            check(
              (await activeTab.playwright.locator("#bs-analyzer-gnuid").count()) === 1,
              context,
              "analyzer complete GNUID input is present"
            );
            check(
              (await activeTab.playwright.locator("[data-bs-analysis-results]").count()) === 1,
              context,
              "analyzer shared results mount is present"
            );
          }
          if (page.kind === "match-predictor") {
            check(
              (await activeTab.playwright.locator(".bs-dashboard-frame iframe").count()) === 1,
              context,
              "Match Predictor iframe container is present without requiring iframe success"
            );
          }
          const focus = await focusSnapshot(activeTab, {
            mobile: viewportCase.width < 992
          });
          focusTraversal.push({ context, ...focus });
          check(
            focus.interactiveReached > 0,
            context,
            focus.interactiveReached > 0
              ? "keyboard traversal reaches an interactive element"
              : "keyboard traversal incomplete: no interactive element received focus",
            focus.interactiveReached > 0
              ? {}
              : { category: "test-infrastructure", incomplete: true }
          );
          check(
            audit.focusableControls < 2 || focus.meaningfulOrder,
            context,
            `keyboard focus follows a meaningful order: ${focus.reached
              .filter((item) => item.interactive)
              .map((item) => item.selector)
              .join(" -> ")}`
          );
          check(
            !focus.trapDetected,
            context,
            "keyboard traversal has no obvious focus trap"
          );
          check(
            focus.missingIndicators.length === 0,
            context,
            `sampled keyboard focus has a visible indicator${
              focus.missingIndicators.length ? `: ${focus.missingIndicators.join(", ")}` : ""
            }`
          );
          if (viewportCase.width < 992 && focus.pageFeatures.mobileNavigationPresent) {
            check(
              Boolean(focus.mobileNavigation),
              context,
              "keyboard traversal reaches the mobile-navigation toggle"
            );
            if (focus.mobileNavigation) {
              check(
                focus.mobileNavigation.opened.expanded === "true" &&
                  focus.mobileNavigation.opened.menuVisible,
                context,
                "keyboard activation opens mobile navigation"
              );
              check(
                focus.mobileNavigation.menuFocus.interactive,
                context,
                `mobile-navigation focus enters an interactive item: ${focus.mobileNavigation.menuFocus.selector}`
              );
              check(
                focus.mobileNavigation.returned.selector === "button.navbar-toggler",
                context,
                `mobile-navigation focus returns after closing: ${focus.mobileNavigation.returned.selector}`
              );
            }
          }
          if (viewportCase.width < 992 && focus.pageFeatures.mobileDrawerPresent) {
            check(
              Boolean(focus.mobileDrawer),
              context,
              "keyboard traversal reaches the mobile page-tools drawer"
            );
            if (focus.mobileDrawer) {
              check(
                focus.mobileDrawer.opened.expanded === "true" &&
                  focus.mobileDrawer.opened.drawerVisible,
                context,
                "keyboard activation opens the mobile page-tools drawer"
              );
              check(
                focus.mobileDrawer.drawerFocus.interactive,
                context,
                `mobile drawer receives focus: ${focus.mobileDrawer.drawerFocus.selector}`
              );
              check(
                focus.mobileDrawer.returned.selector ===
                  "[data-bs-mobile-tools-edge]",
                context,
                `mobile drawer returns focus after closing: ${focus.mobileDrawer.returned.selector}`
              );
            }
          }
          if (focus.pageFeatures.skipLinkPresent) {
            check(
              Boolean(focus.skipLink),
              context,
              "keyboard traversal reaches and activates the skip link"
            );
            if (focus.skipLink) {
              check(
                focus.skipLink.destination.selector !== "body",
                context,
                `skip link moves focus to its target: ${focus.skipLink.destination.selector}`
              );
            }
          }
          if (
            (manifest.baseline_screenshot_route_ids || []).includes(page.id) &&
            (manifest.baseline_screenshot_viewport_names || []).includes(viewportCase.name)
          ) {
            await saveScreenshot(activeTab, viewportCase, page, "baseline");
          }

          phase = "page interactions";
          await runPageInteraction({
            tab: activeTab,
            page,
            viewport: viewportCase,
            check
          });

          if (continuousConfig) {
            const postInteractionUrl = await activeTab.url();
            const routePreserved =
              new URL(postInteractionUrl).pathname === page.route;
            check(
              routePreserved,
              context,
              `page interactions preserve the continuous-loading route: ${postInteractionUrl}`
            );
            phase = "continuous loading state reset";
            await activeTab.goto(new URL(page.route, baseUrl).href);
            await activeTab.playwright.waitForLoadState({
              state: "domcontentloaded",
              timeoutMs: 30000
            });
            await scrollTo(activeTab, 0);
            await delay(500);
            const resetState = await waitForContinuousState(
              activeTab,
              continuousConfig,
              (state) =>
                state.markerCount === 1 &&
                state.appendedPages.length === 0 &&
                state.sentinel.available &&
                !state.sentinel.loading
            );
            initialContinuousState = resetState.state;
            check(
              resetState.timeoutReason === null,
              context,
              resetState.timeoutReason ||
                "continuous loading reset reaches a fresh initial state"
            );
            interactionStates.push({
              context,
              initialRoute: page.route,
              postInteractionUrl,
              routePreserved,
              resetDocumentIdentity: initialContinuousState.documentIdentity,
              resetLoadedPageOrder: initialContinuousState.loadedPageOrder,
              resetTimeoutReason: resetState.timeoutReason
            });
          }

          phase = "middle scroll";
          if (page.kind !== "research-article") {
            await scrollTo(
              activeTab,
              Math.floor(initialMetrics.scrollHeight / 2)
            );
          }
          const continuousPage = Boolean(continuousConfig);
          const markerSelector =
            page.kind === "research-article"
              ? ".bs-research-scroll-marker"
              : ".bs-learn-scroll-lesson-marker";
          const markersBeforeScroll = continuousPage
            ? initialContinuousState.markerCount
            : 0;
          phase = "bottom scroll and continuous loading";
          await scrollTo(activeTab, Number.MAX_SAFE_INTEGER);
          await delay(continuousPage ? 100 : 180);
          let bottomMetrics = await pagePosition(activeTab);
          if (continuousPage) {
            const completed = await waitForContinuousState(
              activeTab,
              continuousConfig,
              (state) =>
                state.markerCount ===
                  markersBeforeScroll + EXPECTED_CONTINUOUS_APPEND_COUNT &&
                state.completionSignal
            );
            const finalState = completed.state;
            const markersAfterScroll = finalState.markerCount;
            const actualAppendedPageCount =
              markersAfterScroll - markersBeforeScroll;
            check(
              completed.timeoutReason === null,
              context,
              completed.timeoutReason || "continuous loading reached its completion signal"
            );
            check(
              actualAppendedPageCount === EXPECTED_CONTINUOUS_APPEND_COUNT,
              context,
              page.kind === "research-article"
                ? `continuous scrolling appends exactly one Research article (expected=${EXPECTED_CONTINUOUS_APPEND_COUNT}, actual=${actualAppendedPageCount})`
                : `continuous scrolling appends exactly one lesson (expected=${EXPECTED_CONTINUOUS_APPEND_COUNT}, actual=${actualAppendedPageCount})`
            );
            check(
              finalState.loadedPageOrder.length === markersAfterScroll &&
                new Set(finalState.loadedPageOrder).size === markersAfterScroll,
              context,
              `continuous loading records unique loaded-page order: ${finalState.loadedPageOrder.join(" -> ")}`
            );
            check(
              finalState.appendedPages.every((item) => Boolean(item.route)),
              context,
              `continuous loading records each appended page identity: ${finalState.appendedPages.map((item) => item.route).join(", ")}`
            );
            const namespacedContainerIds = finalState.appendedPages.flatMap(
              (item) => item.containerIds
            );
            check(
              namespacedContainerIds.length > 0 &&
                namespacedContainerIds.every((id) =>
                  id.startsWith(continuousConfig.namespace)
                ),
              context,
              `appended container IDs are namespaced: ${namespacedContainerIds.join(", ")}`
            );
            check(
              finalState.url === initialContinuousState.url,
              context,
              `continuous loading preserves the final URL: ${finalState.url}`
            );
            check(
              finalState.history.length === initialContinuousState.history.length &&
                JSON.stringify(finalState.history.state) ===
                  JSON.stringify(initialContinuousState.history.state),
              context,
              "continuous loading preserves browser history state"
            );
            check(
              finalState.scrollPosition.scrollY > 0,
              context,
              `continuous loading records the final scroll position: ${finalState.scrollPosition.scrollY}`
            );
            continuousLoading.push({
              context,
              initialRoute: page.route,
              initialDocumentIdentity: initialContinuousState.documentIdentity,
              expectedAppendedPageCount: EXPECTED_CONTINUOUS_APPEND_COUNT,
              actualAppendedPageCount,
              appendedPages: finalState.appendedPages,
              loadedPageOrder: finalState.loadedPageOrder,
              loadingCompletionSignal: finalState.completionSignal,
              scrollTrigger: "browser wheel scroll to document bottom",
              finalScrollPosition: finalState.scrollPosition,
              namespacedContainerIds,
              finalUrl: finalState.url,
              browserHistoryState: finalState.history,
              timeoutReason: completed.timeoutReason
            });
            await delay(400);
            const navigationState = await activeTab.playwright
              .locator("html")
              .evaluate(() => ({
                activeSidebarLinks: document.querySelectorAll(
                  "#quarto-sidebar a.active[href]"
                ).length,
                activeTocLinks: document.querySelectorAll(
                  "#TOC a.nav-link.active"
                ).length,
                tocLinks: document.querySelectorAll("#TOC a[href]").length
              }));
            if (page.kind.includes("scroll-fixture")) {
              check(
                navigationState.activeSidebarLinks >= 1,
                context,
                "continuous scrolling keeps an active lesson in the sidebar"
              );
            }
            check(
              navigationState.tocLinks >= 1 &&
                navigationState.activeTocLinks >= 1,
              context,
              "continuous scrolling keeps an active populated TOC"
            );
            bottomMetrics = await pagePosition(activeTab);
          }
          if (bottomMetrics.scrollHeight > bottomMetrics.clientHeight + 1) {
            check(
              bottomMetrics.scrollY > 0,
              context,
              "page scrolls toward the bottom"
            );
          }
          check(
            bottomMetrics.scrollWidth <= bottomMetrics.clientWidth + 1,
            context,
            "page remains free of horizontal overflow after interactions"
          );
          phase = "duplicate ID audit";
          const duplicates = await duplicateIds(
            activeTab,
            page.kind === "research-article"
              ? "#quarto-document-content"
              : "html"
          );
          check(
            duplicates.length === 0,
            context,
            duplicates.length
              ? `duplicate IDs after scrolling: ${duplicates.join(", ")}`
              : "IDs remain unique after scrolling"
          );

          phase = "back-to-top control";
          const backToTop = await visibleLocator(
            activeTab.playwright.locator(
              "[data-bs-site-back-to-top], [data-bs-glossary-back-to-top]"
            )
          );
          if (
            backToTop &&
            bottomMetrics.scrollY > 0 &&
            page.kind !== "research-article"
          ) {
            await clickInPlace(activeTab, backToTop);
            await delay(1200);
            check(
              (await pagePosition(activeTab)).scrollY <= 80,
              context,
              "back-to-top returns near the page start"
            );
          }
        } catch (error) {
          failures.push({
            context,
            message: `browser helper error during ${phase}: ${String(error)}`,
            category: "test-infrastructure"
          });
        } finally {
          await collectConsole(activeTab, `${context}/console`);
          if (failures.length > failureCountBeforePage) {
            await saveScreenshot(activeTab, viewportCase, page, "failure");
          }
        }
      }
    }

    const desktop = manifest.viewports.find(
      (item) => item.width >= 992
    );
    if (desktop) {
      const clickTab = await acquireTab();
      let finalClickTab = clickTab;
      try {
        await viewport.set({ width: desktop.width, height: desktop.height });
        finalClickTab =
          (await clickThroughNavigation({
            tab: clickTab,
            browser,
            viewport,
            desktop,
            baseUrl,
            check
          })) || clickTab;
      } catch (error) {
        failures.push({
          context: "desktop/click-through",
          message: `browser helper error: ${String(error)}`
        });
      } finally {
        await collectConsole(clickTab, "desktop/click-through/console");
        if (finalClickTab !== clickTab) {
          await collectConsole(
            finalClickTab,
            "desktop/click-through-cube/console"
          );
        }
      }
    }
  } finally {
    await viewport.reset();
    if (browser) {
      await browser.tabs.finalize();
    }
  }

  const findings = failures.map((failure) => {
    const [viewportName, pageId] = failure.context.split("/");
    const page = manifest.pages.find((item) => item.id === pageId);
    const viewportCase = manifest.viewports.find(
      (item) => item.name === viewportName
    );
    const screenshot = screenshots.find(
      (item) =>
        item.kind === "failure" &&
        item.viewport === viewportName &&
        item.page === pageId
    );
    return classifyBrowserFinding({
      failure,
      page,
      viewport: viewportCase,
      screenshot
    });
  });
  const report = {
    version: manifest.version,
    comparisonContractVersion: 2,
    baseUrl,
    pages,
    checks,
    checksByContext,
    coverage: {
      routeIds: manifest.pages.map((page) => page.id),
      viewportNames: manifest.viewports.map((item) => item.name),
      expectedPageCount: manifest.pages.length * manifest.viewports.length,
      executedPageContexts,
      complete:
        executedPageContexts.length ===
        manifest.pages.length * manifest.viewports.length
    },
    failures,
    findings,
    stabilitySummary: summarizeStability(findings),
    rootCauseGroups: groupFindingsByRootCause(findings),
    limitations,
    continuousLoading,
    focusTraversal,
    interactionStates,
    consoleMessages,
    screenshots,
    durationMs: Date.now() - started
  };
  return {
    ...report,
    summary: summarizeReport(report)
  };
}
