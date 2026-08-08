(function () {
  "use strict";

  const MANIFEST_ROUTE = "/assets/bs-research-sequence.json";

  function normalizeRoute(value) {
    let route = String(value || "").trim();
    try {
      route = new URL(route, "https://bs.invalid/").pathname;
      route = decodeURI(route);
    } catch (_error) {
      route = route.split(/[?#]/, 1)[0];
    }
    route = route.replace(/\\/g, "/").replace(/\/{2,}/g, "/");
    route = route.replace(/\/index\.html$/i, "/");
    if (!route.startsWith("/")) {
      route = "/" + route;
    }
    return route;
  }

  function articlesFromManifest(manifest) {
    if (
      !manifest ||
      manifest.schema_version !== 1 ||
      !Array.isArray(manifest.articles)
    ) {
      return [];
    }
    return manifest.articles;
  }

  function findCurrentArticle(manifest, pathname) {
    const route = normalizeRoute(pathname);
    return (
      articlesFromManifest(manifest).find(function (article) {
        return normalizeRoute(article.route) === route;
      }) || null
    );
  }

  function nextArticle(manifest, article) {
    if (!article || !article.next_route) {
      return null;
    }
    const candidate = findCurrentArticle(manifest, article.next_route);
    if (
      !candidate ||
      candidate.sequence_index !== article.sequence_index + 1 ||
      normalizeRoute(candidate.previous_route) !== normalizeRoute(article.route)
    ) {
      return null;
    }
    return candidate;
  }

  function idPrefixForArticle(route) {
    const slug = normalizeRoute(route)
      .replace(/^\/research\//, "")
      .replace(/\.html$/i, "")
      .replace(/[^a-z0-9]+/gi, "-")
      .replace(/^-|-$/g, "")
      .toLocaleLowerCase();
    return "bs-research-scroll-" + (slug || "article") + "-";
  }

  function captureArticleToc(toc, articleUrl) {
    if (!toc) {
      return null;
    }
    const clone = toc.cloneNode(true);
    clone
      .querySelectorAll("[data-bs-toc-toggle-divider]")
      .forEach(function (divider) {
        divider.remove();
      });
    clone.querySelectorAll("a[href]").forEach(function (link) {
      try {
        const target = new URL(link.getAttribute("href"), articleUrl);
        const current = new URL(articleUrl);
        if (
          target.origin === current.origin &&
          target.pathname === current.pathname &&
          target.hash
        ) {
          link.setAttribute("href", target.hash);
        }
      } catch (_error) {
        // Leave malformed links untouched; the rendered-site audit reports them.
      }
    });
    return clone.querySelector('a[href^="#"]') ? clone : null;
  }

  function createMarker(article) {
    const marker = document.createElement("span");
    marker.className = "bs-research-scroll-marker";
    marker.dataset.bsResearchScrollMarker = article.route;
    marker.setAttribute("aria-hidden", "true");
    return marker;
  }

  function createDivider(article) {
    const divider = document.createElement("section");
    divider.className = "bs-research-scroll-divider";
    divider.setAttribute("aria-label", "Next research article");
    const label = document.createElement("span");
    label.textContent = "Continue reading";
    const title = document.createElement("strong");
    title.textContent = article.title;
    divider.append(label, title);
    return divider;
  }

  function createEndState() {
    const end = document.createElement("p");
    end.className = "bs-research-scroll-end";
    end.dataset.bsResearchScrollEnd = "";
    end.textContent = "You have reached the end of the Research articles.";
    return end;
  }

  function initializeContinuousResearch() {
    if (
      !document.body ||
      !document.body.classList.contains("bs-research-article") ||
      !("IntersectionObserver" in window)
    ) {
      return;
    }
    const main = document.getElementById("quarto-document-content");
    const shared = window.BSLearnScroll;
    if (
      !main ||
      !shared ||
      typeof shared.rewriteIdReferences !== "function" ||
      typeof shared.rewriteResourceUrls !== "function"
    ) {
      return;
    }

    fetch(MANIFEST_ROUTE, { credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Research sequence failed to load");
        }
        return response.json();
      })
      .then(function (manifest) {
        const current = findCurrentArticle(manifest, window.location.pathname);
        if (!current) {
          return;
        }

        const loadedRoutes = new Set([normalizeRoute(current.route)]);
        const records = [];
        const initialTocElement = shared.findPrimaryToc(document);
        const initialToc = captureArticleToc(
          initialTocElement,
          window.location.href
        );
        const initialMarker = createMarker(current);
        main.insertBefore(initialMarker, main.firstChild);
        records.push({
          article: current,
          marker: initialMarker,
          toc: initialToc
        });
        let activeIndex = 0;
        let observer = null;

        function synchronizeActiveArticle() {
          const readingLine = Math.max(96, window.innerHeight * 0.28);
          let nextIndex = 0;
          records.forEach(function (record, index) {
            if (record.marker.getBoundingClientRect().top <= readingLine) {
              nextIndex = index;
            }
          });
          if (nextIndex === activeIndex) {
            return;
          }
          activeIndex = nextIndex;
          const globalToc = shared.findPrimaryToc(document);
          shared.replaceTocContents(globalToc, records[activeIndex].toc);
          if (globalToc) {
            const firstLink = globalToc.querySelector("a.nav-link");
            if (firstLink) {
              firstLink.classList.add("active");
            }
          }
        }

        window.addEventListener("scroll", synchronizeActiveArticle, {
          passive: true
        });

        function addSentinel(article) {
          const following = nextArticle(manifest, article);
          if (!following) {
            main.appendChild(createEndState());
            return;
          }
          const sentinel = document.createElement("div");
          sentinel.className = "bs-research-scroll-sentinel";
          sentinel.dataset.bsResearchScrollSentinel = following.route;
          sentinel.setAttribute("aria-live", "polite");
          main.appendChild(sentinel);

          function loadNext() {
            const normalized = normalizeRoute(following.route);
            if (loadedRoutes.has(normalized)) {
              return;
            }
            loadedRoutes.add(normalized);
            if (observer) {
              observer.disconnect();
              observer = null;
            }
            sentinel.classList.add("is-loading");
            sentinel.textContent = "Loading the next Research article\u2026";

            const requestUrl = new URL(following.route, window.location.origin);
            fetch(requestUrl.href, { credentials: "same-origin" })
              .then(function (response) {
                if (!response.ok) {
                  throw new Error("Next Research article failed to load");
                }
                const finalUrl = new URL(response.url);
                if (
                  finalUrl.origin !== window.location.origin ||
                  normalizeRoute(finalUrl.pathname) !== normalized
                ) {
                  throw new Error("Next Research article redirected");
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
                if (
                  !nextMain ||
                  !nextDocument.body.classList.contains("bs-research-article")
                ) {
                  throw new Error("Next Research content was not found");
                }
                const nextTocElement = shared.findPrimaryToc(nextDocument);
                const nextToc = captureArticleToc(
                  nextTocElement,
                  result.finalUrl.href
                );
                nextMain
                  .querySelectorAll(
                    "script, style, link[rel='stylesheet'], " +
                      "[data-bs-term-lookup], #bs-research-taxonomy-source, " +
                      ".bs-post-taxonomy, .quarto-categories"
                  )
                  .forEach(function (element) {
                    element.remove();
                  });

                const prefix = idPrefixForArticle(following.route);
                const idMap = shared.rewriteIdReferences(nextMain, prefix);
                if (nextToc) {
                  shared.rewriteIdReferences(nextToc, prefix, idMap);
                }
                shared.rewriteResourceUrls(nextMain, result.finalUrl.href);

                const marker = createMarker(following);
                const fragment = document.createDocumentFragment();
                fragment.appendChild(marker);
                fragment.appendChild(createDivider(following));
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
                records.push({
                  article: following,
                  marker: marker,
                  toc: nextToc
                });
                addSentinel(following);
                synchronizeActiveArticle();
              })
              .catch(function () {
                loadedRoutes.delete(normalized);
                sentinel.classList.remove("is-loading");
                sentinel.replaceChildren();
                const message = document.createElement("p");
                message.textContent =
                  "The next Research article could not be loaded.";
                const retry = document.createElement("button");
                retry.type = "button";
                retry.className = "bs-button-outline";
                retry.textContent = "Try again";
                retry.addEventListener("click", loadNext);
                sentinel.append(message, retry);
              });
          }

          observer = new IntersectionObserver(
            function (entries) {
              if (entries.some(function (entry) {
                return entry.isIntersecting;
              })) {
                loadNext();
              }
            },
            { rootMargin: "0px 0px 320px 0px" }
          );
          observer.observe(sentinel);
        }

        addSentinel(current);
      })
      .catch(function () {
        // A standalone Research article remains usable without the sequence.
      });
  }

  const publicApi = {
    articlesFromManifest: articlesFromManifest,
    captureArticleToc: captureArticleToc,
    findCurrentArticle: findCurrentArticle,
    idPrefixForArticle: idPrefixForArticle,
    nextArticle: nextArticle,
    normalizeRoute: normalizeRoute
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = publicApi;
  }

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", initializeContinuousResearch);
  }
})();
