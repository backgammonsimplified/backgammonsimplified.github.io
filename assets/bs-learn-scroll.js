(function () {
  "use strict";

  const MANIFEST_ROUTE = "/assets/bs-learn-sequence.json";
  let bootstrapToc = null;
  const ID_TOKEN_ATTRIBUTES = [
    "for",
    "aria-activedescendant",
    "aria-controls",
    "aria-describedby",
    "aria-details",
    "aria-errormessage",
    "aria-flowto",
    "aria-labelledby",
    "aria-owns",
    "data-answer-panel",
    "data-anchor-id",
    "form",
    "headers",
    "list"
  ];
  const ID_HASH_ATTRIBUTES = [
    "data-bs-target",
    "data-target",
    "data-scroll-target"
  ];
  const URL_ATTRIBUTES = ["href", "src", "poster", "data-src"];

  function normalizeRoute(pathname) {
    let route = String(pathname || "").trim();
    try {
      if (/^[a-z][a-z0-9+.-]*:\/\//i.test(route)) {
        route = new URL(route).pathname;
      }
      route = decodeURI(route);
    } catch (_error) {
      // Retain the supplied route when it cannot be decoded.
    }
    route = route.split(/[?#]/, 1)[0].replace(/\\/g, "/");
    route = (route.startsWith("/") ? route : "/" + route).replace(/\/{2,}/g, "/");
    route = route.replace(/\/index\.html$/i, "/");
    route = route.replace(/\.html\/+$/i, ".html");
    if (
      route.length > 1 &&
      !route.endsWith("/") &&
      !/\/[^/]+\.[a-z0-9]+$/i.test(route)
    ) {
      route += "/";
    }
    return route || "/";
  }

  function lessonsFromManifest(manifest) {
    if (
      !manifest ||
      manifest.schema_version !== 1 ||
      !Array.isArray(manifest.lessons)
    ) {
      return [];
    }
    return manifest.lessons;
  }

  function findCurrentLesson(manifest, pathname) {
    const route = normalizeRoute(pathname);
    return (
      lessonsFromManifest(manifest).find(function (lesson) {
        return normalizeRoute(lesson.route) === route;
      }) || null
    );
  }

  function nextLesson(manifest, lesson) {
    if (!lesson || !lesson.next_route) {
      return null;
    }
    const lessons = lessonsFromManifest(manifest);
    const candidate = findCurrentLesson(manifest, lesson.next_route);
    if (
      !candidate ||
      candidate.sequence_index !== lesson.sequence_index + 1 ||
      normalizeRoute(candidate.previous_route) !== normalizeRoute(lesson.route)
    ) {
      return null;
    }
    return lessons[candidate.sequence_index] === candidate ? candidate : null;
  }

  function isFinalLesson(manifest, lesson) {
    return Boolean(lesson && !nextLesson(manifest, lesson));
  }

  function laterLessonRoutes(manifest, pathname) {
    const lesson = findCurrentLesson(manifest, pathname);
    if (!lesson) {
      return [];
    }
    return lessonsFromManifest(manifest)
      .slice(lesson.sequence_index + 1)
      .map(function (candidate) {
        return normalizeRoute(candidate.route);
      });
  }

  function idPrefixForRoute(route) {
    const parts = normalizeRoute(route).split("/").filter(Boolean);
    if (parts[0] === "learn") {
      parts.shift();
    }
    const slug = (parts.join("-") || "lesson")
      .replace(/\.html$/i, "")
      .toLocaleLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
    return "bs-learn-scroll-" + (slug || "lesson") + "-";
  }

  function rewriteIdReferences(root, prefix, existingIdMap) {
    const idMap = existingIdMap || new Map();
    root.querySelectorAll("[id]").forEach(function (element) {
      const oldId = element.id;
      const newId = prefix + oldId;
      idMap.set(oldId, newId);
      element.id = newId;
    });

    root.querySelectorAll("*").forEach(function (element) {
      ID_TOKEN_ATTRIBUTES.forEach(function (attribute) {
        const value = element.getAttribute(attribute);
        if (!value) {
          return;
        }
        element.setAttribute(
          attribute,
          value
            .split(/\s+/)
            .map(function (id) {
              return idMap.get(id) || id;
            })
            .join(" ")
        );
      });

      ["href", "xlink:href"].forEach(function (attribute) {
        const href = element.getAttribute(attribute);
        if (href && href.startsWith("#") && href.length > 1) {
          const target = href.slice(1);
          if (idMap.has(target)) {
            element.setAttribute(attribute, "#" + idMap.get(target));
          }
        }
      });

      ID_HASH_ATTRIBUTES.forEach(function (attribute) {
        const target = element.getAttribute(attribute);
        if (target && target.startsWith("#") && idMap.has(target.slice(1))) {
          element.setAttribute(attribute, "#" + idMap.get(target.slice(1)));
        }
      });

      Array.from(element.attributes || []).forEach(function (attribute) {
        const rewritten = attribute.value.replace(
          /url\(\s*#([^)\s]+)\s*\)/g,
          function (match, id) {
            return idMap.has(id) ? "url(#" + idMap.get(id) + ")" : match;
          }
        );
        if (rewritten !== attribute.value) {
          element.setAttribute(attribute.name, rewritten);
        }
      });
    });
    return idMap;
  }

  function isSafeDataUrl(value) {
    return /^data:(?:image|audio|video|font)\/[a-z0-9.+-]+[;,]/i.test(value);
  }

  function resolveUrlValue(value, baseUrl) {
    const original = String(value || "").trim();
    if (!original) {
      return original;
    }
    if (/^javascript:/i.test(original)) {
      return null;
    }
    if (original.startsWith("#") || /^(?:mailto|tel):/i.test(original)) {
      return original;
    }
    if (/^data:/i.test(original)) {
      return isSafeDataUrl(original) ? original : null;
    }
    if (/^(?:https?:)?\/\//i.test(original)) {
      return original;
    }
    if (original.startsWith("/")) {
      return original;
    }
    try {
      return new URL(original, baseUrl).href;
    } catch (_error) {
      return null;
    }
  }

  function resolveSrcset(value, baseUrl) {
    const original = String(value || "").trim();
    if (!original || /^data:/i.test(original)) {
      return !original || isSafeDataUrl(original) ? original : "";
    }
    const candidates = original.split(",").map(function (candidate) {
      const match = candidate.trim().match(/^(\S+)(\s+.*)?$/);
      if (!match) {
        return "";
      }
      const resolved = resolveUrlValue(match[1], baseUrl);
      return resolved === null ? "" : resolved + (match[2] || "");
    });
    return candidates.filter(Boolean).join(", ");
  }

  function rewriteResourceUrls(root, baseUrl) {
    root.querySelectorAll("*").forEach(function (element) {
      Array.from(element.attributes || []).forEach(function (attribute) {
        if (/^on/i.test(attribute.name)) {
          element.removeAttribute(attribute.name);
        }
      });
      URL_ATTRIBUTES.forEach(function (attribute) {
        if (!element.hasAttribute(attribute)) {
          return;
        }
        const resolved = resolveUrlValue(element.getAttribute(attribute), baseUrl);
        if (resolved === null) {
          element.removeAttribute(attribute);
        } else {
          element.setAttribute(attribute, resolved);
        }
      });
      if (element.hasAttribute("srcset")) {
        element.setAttribute(
          "srcset",
          resolveSrcset(element.getAttribute("srcset"), baseUrl)
        );
      }
    });
  }

  function sameOriginUrl(route, origin) {
    try {
      const url = new URL(route, origin);
      return url.origin === origin ? url : null;
    } catch (_error) {
      return null;
    }
  }

  function createLoadedRouteTracker(initialRoute) {
    const loaded = new Set([normalizeRoute(initialRoute)]);
    const inFlight = new Set();
    return {
      canFetch: function (route) {
        const normalized = normalizeRoute(route);
        return (
          inFlight.size === 0 &&
          !loaded.has(normalized) &&
          !inFlight.has(normalized)
        );
      },
      start: function (route) {
        const normalized = normalizeRoute(route);
        if (!this.canFetch(normalized)) {
          return false;
        }
        inFlight.add(normalized);
        return true;
      },
      complete: function (route) {
        const normalized = normalizeRoute(route);
        inFlight.delete(normalized);
        loaded.add(normalized);
      },
      fail: function (route) {
        inFlight.delete(normalizeRoute(route));
      },
      isLoaded: function (route) {
        return loaded.has(normalizeRoute(route));
      },
      isInFlight: function (route) {
        return inFlight.has(normalizeRoute(route));
      }
    };
  }

  function readingLineForViewport(viewportHeight) {
    const height = Number(viewportHeight) || 0;
    return Math.max(72, Math.min(140, height * 0.18));
  }

  function selectActiveLessonIndex(
    markerTops,
    readingLine,
    previousIndex,
    direction,
    hysteresis
  ) {
    if (!Array.isArray(markerTops) || markerTops.length === 0) {
      return -1;
    }
    const lastIndex = markerTops.length - 1;
    const band = Number.isFinite(hysteresis) ? hysteresis : 28;
    let index = Number.isInteger(previousIndex)
      ? Math.max(0, Math.min(previousIndex, lastIndex))
      : 0;

    if (!direction) {
      index = 0;
      while (
        index < lastIndex &&
        markerTops[index + 1] <= readingLine
      ) {
        index += 1;
      }
      return index;
    }

    if (direction > 0) {
      while (
        index < lastIndex &&
        markerTops[index + 1] <= readingLine - band
      ) {
        index += 1;
      }
      return index;
    }

    while (
      index > 0 &&
      markerTops[index] > readingLine + band
    ) {
      index -= 1;
    }
    return index;
  }

  function sidebarRouteMatches(href, route, baseUrl) {
    try {
      return (
        normalizeRoute(new URL(href, baseUrl).pathname) ===
        normalizeRoute(route)
      );
    } catch (_error) {
      return false;
    }
  }

  function shouldExpandTrack(isExpanded, containsActiveLesson) {
    return Boolean(containsActiveLesson && !isExpanded);
  }

  function selectActiveHeadingIndex(headingTops, readingLine) {
    if (!Array.isArray(headingTops) || headingTops.length === 0) {
      return -1;
    }
    let index = 0;
    while (
      index + 1 < headingTops.length &&
      headingTops[index + 1] <= readingLine
    ) {
      index += 1;
    }
    return index;
  }

  function setActiveSidebar(sidebar, route, baseUrl) {
    if (!sidebar) {
      return null;
    }
    const links = Array.from(
      sidebar.querySelectorAll("a.sidebar-link[href]")
    );
    const activeLink =
      links.find(function (link) {
        return sidebarRouteMatches(
          link.getAttribute("href"),
          route,
          baseUrl
        );
      }) || null;
    if (!activeLink) {
      return null;
    }

    links.forEach(function (link) {
      link.classList.remove("active");
      link.removeAttribute("aria-current");
    });
    activeLink.classList.add("active");
    activeLink.setAttribute("aria-current", "page");

    const sectionList = activeLink.closest(".sidebar-section");
    const section = sectionList
      ? sectionList.closest(".sidebar-item-section")
      : null;
    const toggle = section
      ? section.querySelector(
          ":scope > .sidebar-item-container .sidebar-item-toggle"
        )
      : null;
    if (
      toggle &&
      shouldExpandTrack(
        toggle.getAttribute("aria-expanded") === "true",
        true
      )
    ) {
      toggle.click();
    }

    const sidebarRect = sidebar.getBoundingClientRect();
    const linkRect = activeLink.getBoundingClientRect();
    if (linkRect.top < sidebarRect.top) {
      sidebar.scrollTop -= sidebarRect.top - linkRect.top + 8;
    } else if (linkRect.bottom > sidebarRect.bottom) {
      sidebar.scrollTop += linkRect.bottom - sidebarRect.bottom + 8;
    }
    return activeLink;
  }

  function captureToc(toc) {
    if (!toc || !toc.querySelector('a[href^="#"]')) {
      return null;
    }
    const clone = toc.cloneNode(true);
    clone
      .querySelectorAll("[data-bs-toc-toggle-divider]")
      .forEach(function (divider) {
        divider.remove();
      });
    clone.querySelectorAll(".active").forEach(function (element) {
      element.classList.remove("active");
    });
    return clone;
  }

  function tocHashTargets(toc) {
    if (!toc) {
      return [];
    }
    return Array.from(toc.querySelectorAll('a[href^="#"]')).map(
      function (link) {
        return link.getAttribute("href");
      }
    );
  }

  function headingIdsFromToc(toc) {
    return tocHashTargets(toc)
      .filter(function (target) {
        return target.length > 1;
      })
      .map(function (target) {
        return target.slice(1);
      });
  }

  function replaceTocContents(globalToc, storedToc) {
    if (!globalToc) {
      return false;
    }
    const headingToggle = globalToc.querySelector(
      "[data-bs-toc-heading-toggle]"
    );
    const toggleDivider = headingToggle
      ? headingToggle.closest("[data-bs-toc-toggle-divider]")
      : null;
    const controlledLinksId = headingToggle
      ? headingToggle.getAttribute("aria-controls")
      : "";
    if (!storedToc || !storedToc.querySelector('a[href^="#"]')) {
      globalToc.replaceChildren();
      globalToc.hidden = true;
      globalToc.setAttribute("aria-hidden", "true");
      return false;
    }
    const children = Array.from(storedToc.childNodes).map(function (node) {
      return node.cloneNode(true);
    });
    globalToc.replaceChildren.apply(globalToc, children);
    const tocLinks = globalToc.querySelector(":scope > ul");
    if (headingToggle && tocLinks) {
      if (controlledLinksId) {
        tocLinks.id = controlledLinksId;
      }
      globalToc.appendChild(toggleDivider || headingToggle);
    }
    globalToc.hidden = false;
    globalToc.removeAttribute("aria-hidden");
    return true;
  }

  function createLessonMarker(lesson) {
    const marker = document.createElement("section");
    marker.className = "bs-learn-scroll-lesson-marker";
    marker.dataset.bsLearnScrollLessonRoute = lesson.route;
    marker.setAttribute("aria-hidden", "true");
    return marker;
  }

  function createLessonRecord(lesson, sectionElement, headingIds, toc) {
    return {
      route: normalizeRoute(lesson.route),
      title: String(lesson.title || ""),
      trackId: String(lesson.track_id || ""),
      trackTitle: String(lesson.track_title || ""),
      sectionElement: sectionElement,
      headingIds: Array.from(headingIds || []),
      toc: toc,
      sequencePosition: Number(lesson.sequence_index)
    };
  }

  function startsNewTrack(lesson) {
    return Boolean(lesson && lesson.next_starts_new_track);
  }

  function errorStateForLesson(lesson) {
    return {
      message: "The next lesson could not be loaded.",
      route: lesson ? normalizeRoute(lesson.route) : ""
    };
  }

  function createDivider(lesson, fetchedTitle, trackBoundary) {
    const divider = document.createElement("section");
    const label = document.createElement("span");
    const title = document.createElement("strong");
    const track = document.createElement("span");
    const visibleTitle = fetchedTitle || lesson.title;

    divider.className = "bs-learn-scroll-divider";
    if (trackBoundary) {
      divider.classList.add("is-track-boundary");
    }
    divider.dataset.bsLearnScrollDivider = lesson.route;
    divider.setAttribute("aria-label", "Next lesson: " + visibleTitle);
    label.className = "bs-learn-scroll-divider-label";
    label.textContent = trackBoundary ? "Next track" : "Next lesson";
    title.className = "bs-learn-scroll-divider-title";
    title.textContent = visibleTitle;
    track.className = "bs-learn-scroll-divider-track";
    track.textContent = lesson.track_title;
    divider.append(label, title, track);
    return divider;
  }

  function createEndState() {
    const end = document.createElement("section");
    const message = document.createElement("p");
    const link = document.createElement("a");
    end.className = "bs-learn-scroll-end";
    end.dataset.bsLearnScrollEnd = "";
    message.textContent = "You have reached the end of the current lessons.";
    link.href = "/learn/";
    link.textContent = "Return to Learn Home";
    end.append(message, link);
    return end;
  }

  function createErrorState(lesson, retry) {
    const state = errorStateForLesson(lesson);
    const container = document.createElement("div");
    const message = document.createElement("p");
    const link = document.createElement("a");
    const button = document.createElement("button");

    container.className = "bs-learn-scroll-error";
    container.setAttribute("role", "status");
    container.setAttribute("aria-live", "polite");
    message.textContent = state.message + " ";
    link.href = state.route;
    link.textContent = "Open it as a normal page.";
    button.type = "button";
    button.className = "bs-button-outline bs-learn-scroll-retry";
    button.textContent = "Retry";
    button.addEventListener("click", retry, { once: true });
    message.appendChild(link);
    container.append(message, button);
    return container;
  }

  function findPrimaryToc(root) {
    if (!root || typeof root.getElementById !== "function") {
      return null;
    }
    const candidates =
      typeof root.querySelectorAll === "function"
        ? Array.from(root.querySelectorAll("#TOC"))
        : [root.getElementById("TOC")].filter(Boolean);
    const populatedCandidates = candidates.filter(function (toc) {
      return (
        toc &&
        typeof toc.querySelector === "function" &&
        Boolean(toc.querySelector('a[href^="#"]'))
      );
    });
    const preferredCandidates =
      populatedCandidates.length > 0 ? populatedCandidates : candidates;
    function isLaidOut(element) {
      return (
        element &&
        typeof element.getClientRects === "function" &&
        element.getClientRects().length > 0
      );
    }
    return (
      preferredCandidates.find(function (toc) {
        return isLaidOut(toc) || isLaidOut(toc.parentElement);
      }) ||
      preferredCandidates.find(function (toc) {
        return (
          !toc.hidden &&
          toc.getAttribute("aria-hidden") !== "true"
        );
      }) ||
      preferredCandidates[0] ||
      null
    );
  }

  function waitForPrimaryToc(root, attempts) {
    const remainingAttempts =
      Number.isFinite(attempts) ? Math.max(0, attempts) : 24;
    return new Promise(function (resolve) {
      function check(remaining) {
        const toc = findPrimaryToc(root);
        if (
          (toc &&
            typeof toc.querySelector === "function" &&
            toc.querySelector('a[href^="#"]')) ||
          remaining <= 0 ||
          typeof window.requestAnimationFrame !== "function"
        ) {
          resolve(toc);
          return;
        }
        window.requestAnimationFrame(function () {
          check(remaining - 1);
        });
      }
      check(remainingAttempts);
    });
  }

  function initializeContinuousLearn() {
    if (
      !document.body ||
      !document.body.classList.contains("bs-learn-article") ||
      document.body.classList.contains("bs-learn-track-index") ||
      !("IntersectionObserver" in window) ||
      !document.getElementById("quarto-document-content")
    ) {
      return;
    }

    fetch(MANIFEST_ROUTE, { credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Learn sequence failed to load");
        }
        return response.json();
      })
      .then(function (manifest) {
        if (bootstrapToc) {
          return {
            initialTocElement: findPrimaryToc(document),
            manifest: manifest
          };
        }
        return waitForPrimaryToc(document).then(function (initialTocElement) {
          return {
            initialTocElement: initialTocElement,
            manifest: manifest
          };
        });
      })
      .then(function (initialState) {
        const manifest = initialState.manifest;
        const main = document.getElementById("quarto-document-content");
        const current = findCurrentLesson(manifest, window.location.pathname);
        if (!main || !current) {
          return;
        }

        const tracker = createLoadedRouteTracker(current.route);
        const sidebar = document.getElementById("quarto-sidebar");
        const initialTocElement =
          initialState.initialTocElement || findPrimaryToc(document);
        const lessonRecords = [];
        const initialToc =
          captureToc(initialTocElement) ||
          (bootstrapToc ? bootstrapToc.cloneNode(true) : null);
        const initialHeadingIds = headingIdsFromToc(initialToc);
        const initialMarker = createLessonMarker(current);
        main.insertBefore(initialMarker, main.firstChild);
        lessonRecords.push(
          createLessonRecord(
            current,
            initialMarker,
            initialHeadingIds,
            initialToc
          )
        );

        let observer = null;
        let activeLessonIndex = 0;
        let lastScrollY = window.scrollY;
        let pendingDirection = 0;
        let activeUpdateScheduled = false;
        let contentResizeObserver = null;

        function activeTocElement() {
          return findPrimaryToc(document) || initialTocElement;
        }

        function updateActiveTocHeading(record, readingLine) {
          const globalToc = activeTocElement();
          if (!globalToc || !record) {
            return;
          }
          const headings = record.headingIds
            .map(function (id) {
              return document.getElementById(id);
            })
            .filter(Boolean);
          const headingIndex = selectActiveHeadingIndex(
            headings.map(function (heading) {
              return heading.getBoundingClientRect().top;
            }),
            readingLine
          );
          globalToc.querySelectorAll("a.nav-link.active").forEach(
            function (link) {
              link.classList.remove("active");
            }
          );
          if (headingIndex < 0) {
            return;
          }
          const target = "#" + headings[headingIndex].id;
          const matchingLink = Array.from(
            globalToc.querySelectorAll('a[href^="#"]')
          ).find(function (link) {
            return (
              link.getAttribute("href") === target ||
              link.getAttribute("data-scroll-target") === target
            );
          });
          if (matchingLink) {
            matchingLink.classList.add("active");
          }
        }

        function synchronizeActiveLesson(record) {
          setActiveSidebar(sidebar, record.route, window.location.href);
          replaceTocContents(activeTocElement(), record.toc);
          updateActiveTocHeading(
            record,
            readingLineForViewport(window.innerHeight)
          );
        }

        function updateActiveLesson(direction) {
          const readingLine = readingLineForViewport(window.innerHeight);
          const nextIndex = selectActiveLessonIndex(
            lessonRecords.map(function (record) {
              return record.sectionElement.getBoundingClientRect().top;
            }),
            readingLine,
            activeLessonIndex,
            direction,
            28
          );
          if (nextIndex >= 0 && nextIndex !== activeLessonIndex) {
            activeLessonIndex = nextIndex;
            synchronizeActiveLesson(lessonRecords[activeLessonIndex]);
          } else {
            updateActiveTocHeading(
              lessonRecords[activeLessonIndex],
              readingLine
            );
          }
        }

        function scheduleActiveLessonUpdate(direction) {
          pendingDirection = direction || pendingDirection;
          if (activeUpdateScheduled) {
            return;
          }
          activeUpdateScheduled = true;
          window.requestAnimationFrame(function () {
            activeUpdateScheduled = false;
            const directionToApply = pendingDirection;
            pendingDirection = 0;
            updateActiveLesson(directionToApply);
          });
        }

        window.addEventListener(
          "scroll",
          function () {
            const nextScrollY = window.scrollY;
            const direction =
              nextScrollY > lastScrollY + 1
                ? 1
                : nextScrollY < lastScrollY - 1
                  ? -1
                  : 0;
            lastScrollY = nextScrollY;
            scheduleActiveLessonUpdate(direction);
          },
          { passive: true }
        );
        window.addEventListener("resize", function () {
          scheduleActiveLessonUpdate(0);
        });
        main.addEventListener(
          "toggle",
          function () {
            scheduleActiveLessonUpdate(0);
          },
          true
        );
        if ("ResizeObserver" in window) {
          contentResizeObserver = new ResizeObserver(function () {
            scheduleActiveLessonUpdate(0);
          });
          contentResizeObserver.observe(main);
        }
        synchronizeActiveLesson(lessonRecords[0]);

        function showEndState() {
          if (!main.querySelector("[data-bs-learn-scroll-end]")) {
            main.appendChild(createEndState());
          }
        }

        function addSentinel(currentLesson) {
          const followingLesson = nextLesson(manifest, currentLesson);
          if (!followingLesson) {
            showEndState();
            return;
          }

          const sentinel = document.createElement("div");
          sentinel.className = "bs-learn-scroll-sentinel";
          sentinel.dataset.bsLearnScrollSentinel = followingLesson.route;
          sentinel.setAttribute("aria-live", "polite");
          main.appendChild(sentinel);

          function attemptLoad() {
            const requestUrl = sameOriginUrl(
              followingLesson.route,
              window.location.origin
            );
            if (
              !requestUrl ||
              !findCurrentLesson(manifest, requestUrl.pathname) ||
              !tracker.start(followingLesson.route)
            ) {
              return;
            }

            if (observer) {
              observer.disconnect();
              observer = null;
            }
            sentinel.classList.add("is-loading");
            sentinel.textContent = "Loading the next lesson\u2026";

            fetch(requestUrl.href, { credentials: "same-origin" })
              .then(function (response) {
                if (!response.ok) {
                  throw new Error("Next lesson failed to load");
                }
                const finalUrl = sameOriginUrl(response.url, window.location.origin);
                if (
                  !finalUrl ||
                  normalizeRoute(finalUrl.pathname) !==
                    normalizeRoute(followingLesson.route)
                ) {
                  throw new Error("Next lesson redirected unexpectedly");
                }
                return response.text().then(function (html) {
                  return { html: html, finalUrl: finalUrl };
                });
              })
              .then(function (result) {
                const nextDocument = new DOMParser().parseFromString(
                  result.html,
                  "text/html"
                );
                const nextMain = nextDocument.getElementById(
                  "quarto-document-content"
                );
                const nextToc = findPrimaryToc(nextDocument);
                if (
                  !nextMain ||
                  !nextDocument.body ||
                  !nextDocument.body.classList.contains("bs-learn-article")
                ) {
                  throw new Error("Next lesson content was not found");
                }

                const heading = nextMain.querySelector("h1");
                const fetchedTitle = heading ? heading.textContent.trim() : "";
                if (!fetchedTitle) {
                  throw new Error("Next lesson title was not found");
                }

                nextMain
                  .querySelectorAll(
                    "script, style, link[rel='stylesheet'], " +
                      "[data-bs-term-lookup], [data-bs-lesson-track-nav], " +
                      ".quarto-title-breadcrumbs, .quarto-categories"
                  )
                  .forEach(function (element) {
                    element.remove();
                  });
                nextMain.querySelectorAll(".column-margin").forEach(
                  function (margin) {
                    margin.classList.add("bs-learn-scroll-inline-margin");
                  }
                );

                const prefix = idPrefixForRoute(followingLesson.route);
                const headingIdMap = rewriteIdReferences(nextMain, prefix);
                if (nextToc) {
                  rewriteIdReferences(nextToc, prefix, headingIdMap);
                }
                rewriteResourceUrls(nextMain, result.finalUrl.href);
                const storedNextToc = captureToc(nextToc);
                const headingIds = headingIdsFromToc(storedNextToc);
                const header = nextMain.querySelector(".quarto-title-block");
                if (header) {
                  header.dataset.bsLearnScrollLesson = followingLesson.route;
                }

                const marker = createLessonMarker(followingLesson);
                const fragment = document.createDocumentFragment();
                fragment.appendChild(marker);
                fragment.appendChild(
                  createDivider(
                    followingLesson,
                    fetchedTitle,
                    startsNewTrack(currentLesson)
                  )
                );
                Array.from(nextMain.children).forEach(function (child) {
                  fragment.appendChild(document.importNode(child, true));
                });
                if (
                  window.BSLearn &&
                  typeof window.BSLearn.mountLesson === "function"
                ) {
                  window.BSLearn.mountLesson(fragment);
                }
                sentinel.replaceWith(fragment);
                lessonRecords.push(
                  createLessonRecord(
                    Object.assign({}, followingLesson, {
                      title: fetchedTitle
                    }),
                    marker,
                    headingIds,
                    storedNextToc
                  )
                );
                tracker.complete(followingLesson.route);
                addSentinel(followingLesson);
                scheduleActiveLessonUpdate(1);
              })
              .catch(function () {
                tracker.fail(followingLesson.route);
                sentinel.classList.remove("is-loading");
                sentinel.replaceChildren(
                  createErrorState(followingLesson, attemptLoad)
                );
              });
          }

          observer = new IntersectionObserver(
            function (entries) {
              if (
                entries.some(function (entry) {
                  return entry.isIntersecting;
                })
              ) {
                attemptLoad();
              }
            },
            { rootMargin: "0px 0px 320px 0px" }
          );
          observer.observe(sentinel);
        }

        addSentinel(current);
      })
      .catch(function () {
        // A standalone lesson remains fully usable when the sequence is unavailable.
      });
  }

  const publicApi = {
    captureToc: captureToc,
    createLessonRecord: createLessonRecord,
    createLoadedRouteTracker: createLoadedRouteTracker,
    errorStateForLesson: errorStateForLesson,
    findCurrentLesson: findCurrentLesson,
    findPrimaryToc: findPrimaryToc,
    headingIdsFromToc: headingIdsFromToc,
    idPrefixForRoute: idPrefixForRoute,
    isFinalLesson: isFinalLesson,
    laterLessonRoutes: laterLessonRoutes,
    nextLesson: nextLesson,
    normalizeRoute: normalizeRoute,
    readingLineForViewport: readingLineForViewport,
    replaceTocContents: replaceTocContents,
    waitForPrimaryToc: waitForPrimaryToc,
    resolveSrcset: resolveSrcset,
    resolveUrlValue: resolveUrlValue,
    rewriteIdReferences: rewriteIdReferences,
    rewriteResourceUrls: rewriteResourceUrls,
    sameOriginUrl: sameOriginUrl,
    selectActiveHeadingIndex: selectActiveHeadingIndex,
    selectActiveLessonIndex: selectActiveLessonIndex,
    setActiveSidebar: setActiveSidebar,
    shouldExpandTrack: shouldExpandTrack,
    sidebarRouteMatches: sidebarRouteMatches,
    tocHashTargets: tocHashTargets,
    startsNewTrack: startsNewTrack
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = publicApi;
  }

  if (typeof window !== "undefined") {
    window.BSLearnScroll = Object.assign(
      window.BSLearnScroll || {},
      publicApi
    );
  }

  if (typeof document !== "undefined") {
    bootstrapToc = captureToc(findPrimaryToc(document));
    document.addEventListener("DOMContentLoaded", initializeContinuousLearn);
  }
})();
