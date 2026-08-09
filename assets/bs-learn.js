(function () {
  "use strict";

  const DIFFICULTY_SELECTOR = "[data-bs-filter-difficulty]";
  const TRACK_SELECTOR = "[data-bs-filter-track]";
  const TERM_SELECTOR = "[data-bs-filter-term]";
  const LESSON_SELECTOR = "[data-bs-learn-item]";
  const GROUP_SELECTOR = "[data-bs-learn-group]";
  let glossaryLookupEntriesPromise = null;

  function parseList(value) {
    if (!value) {
      return [];
    }

    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch (_error) {
      return [];
    }
  }

  function matchesAny(values, selected) {
    return selected.length === 0 || selected.some(function (value) {
      return values.includes(value);
    });
  }

  function itemMatchesTaxonomy(item, difficulties, tracks) {
    return (
      matchesAny(item.difficulties, difficulties) &&
      matchesAny(item.tracks, tracks)
    );
  }

  function normalizeLearnSearch(value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^\p{L}\p{N}]+/gu, " ")
      .trim()
      .toLocaleLowerCase();
  }

  function isMobileDrawerSwipe(startX, startY, endX, endY) {
    const deltaX = endX - startX;
    const deltaY = endY - startY;
    return (
      startX <= 56 &&
      Math.abs(deltaX) >= 24 &&
      Math.abs(deltaX) > Math.abs(deltaY) * 1.25
    );
  }

  function lessonSearchRank(item, query) {
    const normalizedQuery = normalizeLearnSearch(query);
    if (!normalizedQuery) {
      return 0;
    }
    const primaryValues =
      item.primarySearchValues || item.searchValues || [];
    const bodyValues = item.bodySearchValues || [];
    if (
      primaryValues.some(function (value) {
        return normalizeLearnSearch(value).includes(normalizedQuery);
      })
    ) {
      return 1;
    }
    if (
      bodyValues.some(function (value) {
        return normalizeLearnSearch(value).includes(normalizedQuery);
      })
    ) {
      return 2;
    }
    return Number.POSITIVE_INFINITY;
  }

  function rankLessonItems(items, query) {
    return Array.from(items).sort(function (left, right) {
      const rankDifference =
        lessonSearchRank(left, query) - lessonSearchRank(right, query);
      if (rankDifference !== 0) {
        return rankDifference;
      }
      return left.originalIndex - right.originalIndex;
    });
  }

  function lessonGroupSearchRank(items, query) {
    return Array.from(items).reduce(function (best, item) {
      return Math.min(best, lessonSearchRank(item, query));
    }, Number.POSITIVE_INFINITY);
  }

  function itemMatchesLesson(item, query, difficulties, terms) {
    const matchesSearch = Number.isFinite(lessonSearchRank(item, query));
    return (
      matchesSearch &&
      matchesAny(item.difficulties, difficulties) &&
      matchesAny(item.terms, terms)
    );
  }

  function sortedValues(values) {
    return Array.from(values).sort(function (left, right) {
      return left.localeCompare(right);
    });
  }

  function normalizeLookupQuery(value) {
    return String(value || "").trim();
  }

  function isSamePageTocHref(href, currentHref) {
    const value = String(href || "").trim();
    if (!value) {
      return false;
    }
    if (value.startsWith("#")) {
      return value.length > 1;
    }
    try {
      const current = new URL(currentHref);
      const target = new URL(value, current);
      return (
        Boolean(target.hash) &&
        target.origin === current.origin &&
        target.pathname === current.pathname
      );
    } catch (_error) {
      return false;
    }
  }

  function tocHasHashLinks(toc) {
    if (!toc || typeof toc.querySelectorAll !== "function") {
      return false;
    }
    return Array.from(toc.querySelectorAll("a[href]")).some(function (link) {
      return isSamePageTocHref(
        link.getAttribute("href"),
        window.location.href
      );
    });
  }

  function lookupMatchRank(entry, query) {
    const normalizedQuery = normalizeLearnSearch(query);
    if (!normalizedQuery) {
      return Number.POSITIVE_INFINITY;
    }
    const compactQuery = normalizedQuery.replace(/\s+/g, "");
    const canonical = normalizeLearnSearch(entry.term);
    const aliases = Array.isArray(entry.aliases)
      ? entry.aliases.map(normalizeLearnSearch)
      : [];
    const compactCanonical = canonical.replace(/\s+/g, "");
    const compactAliases = aliases.map(function (alias) {
      return alias.replace(/\s+/g, "");
    });

    if (canonical === normalizedQuery) {
      return 1;
    }
    if (aliases.includes(normalizedQuery)) {
      return 2;
    }
    if (
      compactCanonical === compactQuery ||
      compactAliases.includes(compactQuery)
    ) {
      return 3;
    }
    if (canonical.startsWith(normalizedQuery)) {
      return 4;
    }
    if (aliases.some(function (alias) {
      return alias.startsWith(normalizedQuery);
    })) {
      return 5;
    }
    if (canonical.includes(normalizedQuery)) {
      return 6;
    }
    if (aliases.some(function (alias) {
      return alias.includes(normalizedQuery);
    })) {
      return 7;
    }
    if (
      compactCanonical.includes(compactQuery) ||
      compactAliases.some(function (alias) {
        return alias.includes(compactQuery);
      })
    ) {
      return 8;
    }
    const shortDefinition = normalizeLearnSearch(entry.short_definition);
    const fullDefinition = normalizeLearnSearch(entry.definition);
    if (shortDefinition.includes(normalizedQuery)) {
      return 9;
    }
    if (fullDefinition.includes(normalizedQuery)) {
      return 10;
    }
    return Number.POSITIVE_INFINITY;
  }

  function bestLookupEntry(entries, query) {
    return Array.from(entries || [])
      .map(function (entry, index) {
        return {
          entry: entry,
          index: index,
          rank: lookupMatchRank(entry, query)
        };
      })
      .filter(function (candidate) {
        return Number.isFinite(candidate.rank);
      })
      .sort(function (left, right) {
        if (left.rank !== right.rank) {
          return left.rank - right.rank;
        }
        const termComparison = String(left.entry.term).localeCompare(
          String(right.entry.term)
        );
        return termComparison || left.index - right.index;
      })
      .map(function (candidate) {
        return candidate.entry;
      })[0] || null;
  }

  function canonicalEntryBySlug(entries, slug) {
    return Array.from(entries || []).find(function (entry) {
      return String(entry.slug) === String(slug);
    }) || null;
  }

  function canonicalShortDefinition(entries, slug) {
    const entry = canonicalEntryBySlug(entries, slug);
    if (!entry || typeof entry.short_definition !== "string") {
      return null;
    }
    return entry.short_definition;
  }

  function loadGlossaryLookupEntries() {
    if (!glossaryLookupEntriesPromise) {
      glossaryLookupEntriesPromise = fetch(
        "/assets/bs-glossary-lookup.json",
        { credentials: "same-origin" }
      )
        .then(function (response) {
          if (!response.ok) {
            throw new Error("Glossary lookup data failed to load");
          }
          return response.json();
        })
        .then(function (data) {
          return Array.isArray(data.entries) ? data.entries : [];
        });
    }
    return glossaryLookupEntriesPromise;
  }

  function inlineGlossaryTooltipPosition(
    linkRectangle,
    tooltipRectangle,
    viewportWidth,
    viewportHeight
  ) {
    const margin = 12;
    const gap = 8;
    const maximumLeft = Math.max(
      margin,
      viewportWidth - tooltipRectangle.width - margin
    );
    const left = Math.max(
      margin,
      Math.min(linkRectangle.left, maximumLeft)
    );
    const below = linkRectangle.bottom + gap;
    const above = linkRectangle.top - gap - tooltipRectangle.height;
    const maximumTop = Math.max(
      margin,
      viewportHeight - tooltipRectangle.height - margin
    );
    let top = below;

    if (below + tooltipRectangle.height > viewportHeight - margin) {
      top = above >= margin ? above : maximumTop;
    }

    return {
      left: left,
      top: Math.max(margin, Math.min(top, maximumTop))
    };
  }

  function initializeInlineGlossary() {
    const links = Array.from(
      document.querySelectorAll(
        ".bs-inline-glossary[data-bs-glossary-slug]"
      )
    );
    if (links.length === 0) {
      return;
    }

    const tooltip = document.createElement("aside");
    tooltip.className = "bs-inline-glossary-tooltip";
    tooltip.id = "bs-inline-glossary-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.hidden = true;
    document.body.appendChild(tooltip);

    let activeLink = null;

    const positionTooltip = function (link) {
      const position = inlineGlossaryTooltipPosition(
        link.getBoundingClientRect(),
        tooltip.getBoundingClientRect(),
        window.innerWidth,
        window.innerHeight
      );
      tooltip.style.left = position.left + "px";
      tooltip.style.top = position.top + "px";
    };

    const hideTooltip = function (link) {
      if (activeLink !== link) {
        return;
      }
      activeLink = null;
      link.removeAttribute("aria-describedby");
      tooltip.hidden = true;
      tooltip.replaceChildren();
    };

    const showTooltip = function (link) {
      activeLink = link;
      const slug = link.dataset.bsGlossarySlug;
      loadGlossaryLookupEntries()
        .then(function (entries) {
          if (activeLink !== link) {
            return;
          }
          const entry = canonicalEntryBySlug(entries, slug);
          const summary = canonicalShortDefinition(entries, slug);
          if (!entry || !summary) {
            hideTooltip(link);
            return;
          }
          const heading = document.createElement("strong");
          heading.textContent = entry.term;
          const definition = document.createElement("span");
          definition.textContent = summary;
          const instruction = document.createElement("span");
          instruction.className = "bs-inline-glossary-tooltip-action";
          instruction.textContent = "Click for full definition";
          tooltip.replaceChildren(heading, definition, instruction);
          tooltip.hidden = false;
          link.setAttribute("aria-describedby", tooltip.id);
          positionTooltip(link);
        })
        .catch(function () {
          hideTooltip(link);
        });
    };

    links.forEach(function (link) {
      link.addEventListener("mouseenter", function () {
        showTooltip(link);
      });
      link.addEventListener("mouseleave", function () {
        hideTooltip(link);
      });
      link.addEventListener("focus", function () {
        showTooltip(link);
      });
      link.addEventListener("blur", function () {
        hideTooltip(link);
      });
      link.addEventListener("click", function (event) {
        event.preventDefault();
        hideTooltip(link);
        document.dispatchEvent(
          new CustomEvent("bs:open-glossary-term", {
            detail: { slug: link.dataset.bsGlossarySlug }
          })
        );
      });
    });

    const repositionActiveTooltip = function () {
      if (activeLink && !tooltip.hidden) {
        positionTooltip(activeLink);
      }
    };
    window.addEventListener("resize", repositionActiveTooltip);
    window.addEventListener("scroll", repositionActiveTooltip, {
      passive: true
    });
  }

  function setAllGroupsExpanded(groups, expanded) {
    groups.forEach(function (group) {
      group.open = expanded;
    });
  }

  function groupControlState(groups) {
    const visibleGroups = groups.filter(function (group) {
      return !group.hidden;
    });
    return {
      collapseDisabled:
        visibleGroups.length === 0 ||
        visibleGroups.every(function (group) {
          return !group.open;
        }),
      expandDisabled:
        visibleGroups.length === 0 ||
        visibleGroups.every(function (group) {
          return group.open;
        })
    };
  }

  function initializeLearnFilters() {
    const panel = document.querySelector("[data-bs-learn-filters]");
    const list = document.querySelector("[data-bs-learn-list]");

    if (!panel || !list) {
      return;
    }

    const items = Array.from(list.querySelectorAll(LESSON_SELECTOR)).map(
      function (element, originalIndex) {
        return {
          element: element,
          difficulties: parseList(element.dataset.bsDifficulties),
          track: element.dataset.bsTrack || "",
          terms: parseList(element.dataset.bsTerms),
          primarySearchValues: parseList(element.dataset.bsSearchPrimary),
          bodySearchValues: parseList(element.dataset.bsSearchBody),
          originalIndex: originalIndex,
          originalParent: element.parentElement
        };
      }
    );
    const groups = Array.from(list.querySelectorAll(GROUP_SELECTOR));
    const groupRecords = groups.map(function (group, originalIndex) {
      return {
        element: group,
        items: items.filter(function (item) {
          return group.contains(item.element);
        }),
        count: group.querySelector("[data-bs-learn-group-count]"),
        originalIndex: originalIndex
      };
    });
    const difficultyButtons = Array.from(
      panel.querySelectorAll(DIFFICULTY_SELECTOR)
    );
    const trackButtons = Array.from(panel.querySelectorAll(TRACK_SELECTOR));
    const termButtons = Array.from(panel.querySelectorAll(TERM_SELECTOR));
    const searchInput = panel.querySelector("[data-bs-learn-search]");
    const resultCount = panel.querySelector("[data-bs-learn-result-count]");
    const clearButton = panel.querySelector("[data-bs-learn-clear]");
    const emptyState = document.querySelector("[data-bs-learn-empty]");
    const collapseAll = document.querySelector("[data-bs-learn-collapse-all]");
    const expandAll = document.querySelector("[data-bs-learn-expand-all]");
    const selectedDifficulties = new Set();
    const selectedTerms = new Set();
    let selectedTrack = "";
    const parameters = new URLSearchParams(window.location.search);
    if (searchInput) {
      searchInput.value = parameters.get("search") || "";
    }

    parameters.getAll("difficulty").forEach(function (value) {
      if (
        difficultyButtons.some(function (button) {
          return button.dataset.bsFilterDifficulty === value;
        })
      ) {
        selectedDifficulties.add(value);
      }
    });
    parameters.getAll("track").forEach(function (value) {
      if (
        trackButtons.some(function (button) {
          return button.dataset.bsFilterTrack === value;
        })
      ) {
        selectedTrack = value;
      }
    });
    parameters.getAll("term").forEach(function (value) {
      if (
        termButtons.some(function (button) {
          return button.dataset.bsFilterTerm === value;
        })
      ) {
        selectedTerms.add(value);
      }
    });

    function setPressed(buttons, selected, datasetKey) {
      buttons.forEach(function (button) {
        const active = selected.has(button.dataset[datasetKey] || "");
        button.setAttribute("aria-pressed", active ? "true" : "false");
        button.classList.toggle("is-active", active);
      });
    }

    function updateUrl() {
      const next = new URL(window.location.href);
      next.searchParams.delete("difficulty");
      next.searchParams.delete("track");
      next.searchParams.delete("term");
      next.searchParams.delete("search");
      const query = searchInput ? searchInput.value.trim() : "";
      if (query) {
        next.searchParams.set("search", query);
      }
      sortedValues(selectedDifficulties).forEach(function (value) {
        next.searchParams.append("difficulty", value);
      });
      if (selectedTrack) {
        next.searchParams.set("track", selectedTrack);
      }
      sortedValues(selectedTerms).forEach(function (value) {
        next.searchParams.append("term", value);
      });
      window.history.replaceState({}, "", next);
    }

    function updateGroupControls() {
      const state = groupControlState(groups);
      if (collapseAll) {
        collapseAll.disabled = state.collapseDisabled;
      }
      if (expandAll) {
        expandAll.disabled = state.expandDisabled;
      }
    }

    function updateCounts() {
      const query = searchInput ? searchInput.value : "";
      const difficulties = sortedValues(selectedDifficulties);
      const terms = sortedValues(selectedTerms);
      difficultyButtons.forEach(function (button) {
        const value = button.dataset.bsFilterDifficulty || "";
        const count = items.filter(function (item) {
          return (
            item.difficulties.includes(value) &&
            itemMatchesLesson(item, query, [], terms)
          );
        }).length;
        const countElement = button.querySelector(".bs-learn-filter-count");
        if (countElement) {
          countElement.textContent = "\u00d7" + count;
        }
        button.disabled =
          count === 0 && !selectedDifficulties.has(value);
      });

      trackButtons.forEach(function (button) {
        const value = button.dataset.bsFilterTrack || "";
        const count = items.filter(function (item) {
          return (
            item.track === value &&
            itemMatchesLesson(item, query, difficulties, terms)
          );
        }).length;
        const countElement = button.querySelector(".bs-learn-filter-count");
        if (countElement) {
          countElement.textContent = "\u00d7" + count;
        }
        button.disabled = false;
      });

      termButtons.forEach(function (button) {
        const value = button.dataset.bsFilterTerm || "";
        const count = items.filter(function (item) {
          return (
            item.terms.includes(value) &&
            itemMatchesLesson(item, query, difficulties, [])
          );
        }).length;
        const countElement = button.querySelector(".bs-learn-filter-count");
        if (countElement) {
          countElement.textContent = "\u00d7" + count;
        }
        button.disabled = count === 0 && !selectedTerms.has(value);
      });
    }

    function applyFilters(options) {
      const shouldUpdateUrl = !options || options.updateUrl !== false;
      const difficulties = sortedValues(selectedDifficulties);
      const terms = sortedValues(selectedTerms);
      const query = searchInput ? searchInput.value : "";
      let visibleCount = 0;

      items.forEach(function (item) {
        const visible = itemMatchesLesson(
          item,
          query,
          difficulties,
          terms
        );
        item.element.hidden = !visible;
        if (visible) {
          visibleCount += 1;
        }
      });

      groupRecords.forEach(function (groupRecord) {
        const groupVisibleCount = groupRecord.items.filter(function (item) {
          return !item.element.hidden;
        }).length;
        const totalCount = Number(
          groupRecord.element.dataset.bsTotalLessons || "0"
        );
        groupRecord.element.hidden =
          totalCount > 0 && groupVisibleCount === 0;
        if (groupRecord.count) {
          groupRecord.count.textContent =
            groupVisibleCount +
            (groupVisibleCount === 1 ? " lesson" : " lessons");
        }
      });

      const groupParent = groups[0] ? groups[0].parentElement : null;
      if (groupParent) {
        Array.from(groupRecords)
          .sort(function (left, right) {
            const leftRank = lessonGroupSearchRank(
              left.items,
              query
            );
            const rightRank = lessonGroupSearchRank(
              right.items,
              query
            );
            return (
              leftRank - rightRank ||
              left.originalIndex - right.originalIndex
            );
          })
          .forEach(function (groupRecord) {
            groupParent.appendChild(groupRecord.element);
          });
      }

      setPressed(
        difficultyButtons,
        selectedDifficulties,
        "bsFilterDifficulty"
      );
      setPressed(
        trackButtons,
        new Set(selectedTrack ? [selectedTrack] : []),
        "bsFilterTrack"
      );
      setPressed(termButtons, selectedTerms, "bsFilterTerm");
      updateCounts();

      if (selectedTrack) {
        groups.forEach(function (group) {
          group.open = group.dataset.bsTrackId === selectedTrack;
        });
      }
      updateGroupControls();

      if (resultCount) {
        resultCount.textContent =
          "Showing " +
          visibleCount +
          (visibleCount === 1 ? " lesson." : " lessons.");
      }
      if (emptyState) {
        emptyState.hidden = visibleCount !== 0 || items.length === 0;
      }
      if (clearButton) {
        clearButton.hidden =
          selectedDifficulties.size === 0 &&
          selectedTrack === "" &&
          selectedTerms.size === 0 &&
          normalizeLearnSearch(query).length === 0;
      }
      if (shouldUpdateUrl) {
        updateUrl();
      }
    }

    function toggleSelection(set, value) {
      if (set.has(value)) {
        set.delete(value);
      } else {
        set.add(value);
      }
    }

    panel.addEventListener("click", function (event) {
      const difficultyButton = event.target.closest(DIFFICULTY_SELECTOR);
      const trackButton = event.target.closest(TRACK_SELECTOR);
      const termButton = event.target.closest(TERM_SELECTOR);
      const clear = event.target.closest("[data-bs-learn-clear]");

      if (difficultyButton) {
        toggleSelection(
          selectedDifficulties,
          difficultyButton.dataset.bsFilterDifficulty || ""
        );
        applyFilters();
        return;
      }
      if (trackButton) {
        const value = trackButton.dataset.bsFilterTrack || "";
        selectedTrack = selectedTrack === value ? "" : value;
        if (!selectedTrack) {
          setAllGroupsExpanded(groups, true);
        }
        applyFilters();
        return;
      }
      if (termButton) {
        toggleSelection(
          selectedTerms,
          termButton.dataset.bsFilterTerm || ""
        );
        applyFilters();
        return;
      }
      if (clear) {
        selectedDifficulties.clear();
        selectedTerms.clear();
        selectedTrack = "";
        setAllGroupsExpanded(groups, true);
        if (searchInput) {
          searchInput.value = "";
        }
        applyFilters();
      }
    });

    if (searchInput) {
      searchInput.addEventListener("input", function () {
        applyFilters();
      });
    }

    list.addEventListener("click", function (event) {
      if (event.target.closest(".bs-learn-catalogue-link")) {
        event.stopPropagation();
      }
    });

    if (collapseAll) {
      collapseAll.addEventListener("click", function () {
        selectedTrack = "";
        setAllGroupsExpanded(groups, false);
        setPressed(trackButtons, new Set(), "bsFilterTrack");
        updateGroupControls();
        updateUrl();
      });
    }
    if (expandAll) {
      expandAll.addEventListener("click", function () {
        selectedTrack = "";
        setAllGroupsExpanded(groups, true);
        setPressed(trackButtons, new Set(), "bsFilterTrack");
        updateGroupControls();
        updateUrl();
      });
    }
    groups.forEach(function (group) {
      group.addEventListener("toggle", updateGroupControls);
    });

    applyFilters({ updateUrl: false });
  }

  function initializeLearnSidebarControls() {
    const sidebar = document.getElementById("quarto-sidebar");
    const menu = sidebar
      ? sidebar.querySelector(".sidebar-menu-container")
      : null;
    const sections = sidebar
      ? Array.from(sidebar.querySelectorAll(".sidebar-item-section"))
      : [];
    if (!menu || sections.length === 0) {
      return;
    }

    const controls = document.createElement("div");
    controls.className = "bs-learn-sidebar-actions";
    controls.setAttribute("role", "group");
    controls.setAttribute("aria-label", "Learn sidebar sections");
    controls.innerHTML =
      '<button type="button" data-bs-sidebar-collapse-all>Collapse all</button>' +
      '<button type="button" data-bs-sidebar-expand-all>Expand all</button>';
    menu.prepend(controls);
    const collapse = controls.querySelector("[data-bs-sidebar-collapse-all]");
    const expand = controls.querySelector("[data-bs-sidebar-expand-all]");

    function toggles() {
      return sections
        .map(function (section) {
          return section.querySelector(
            ":scope > .sidebar-item-container .sidebar-item-toggle"
          );
        })
        .filter(Boolean);
    }

    function setExpanded(expanded) {
      toggles().forEach(function (toggle) {
        const isExpanded = toggle.getAttribute("aria-expanded") === "true";
        if (isExpanded !== expanded) {
          toggle.click();
        }
      });
      update();
    }

    function update() {
      const states = toggles().map(function (toggle) {
        return toggle.getAttribute("aria-expanded") === "true";
      });
      if (collapse) {
        collapse.disabled = states.every(function (state) {
          return !state;
        });
      }
      if (expand) {
        expand.disabled = states.every(Boolean);
      }
    }

    if (collapse) {
      collapse.addEventListener("click", function () {
        setExpanded(false);
      });
    }
    if (expand) {
      expand.addEventListener("click", function () {
        setExpanded(true);
      });
    }
    toggles().forEach(function (toggle) {
      toggle.addEventListener("click", function () {
        window.setTimeout(update, 0);
      });
    });
    update();
  }

  function placeLessonTrackLinks() {
    document
      .querySelectorAll("[data-bs-lesson-taxonomy]")
      .forEach(function (taxonomy) {
        const trackNav = taxonomy.querySelector(
          "[data-bs-lesson-track-nav]"
        );

        if (!trackNav) {
          return;
        }

        const desktopQuery = window.matchMedia("(min-width: 992px)");
        const lessonPage =
          document.body.classList.contains("bs-learn-article") &&
          !document.body.classList.contains("bs-learn-track-index");
        let trackContent = null;

        if (lessonPage) {
          trackContent = document.createElement("div");
          trackContent.className = "bs-lesson-track-content";
          trackContent.id = "bs-lesson-track-content";
          while (trackNav.firstChild) {
            trackContent.appendChild(trackNav.firstChild);
          }
          trackNav.appendChild(trackContent);
        }

        function place() {
          const wide = desktopQuery.matches;
          const sidebar = document.getElementById("quarto-margin-sidebar");
          const toc = sidebar ? sidebar.querySelector("#TOC") : null;
          const desktopRailActive = lessonPage && wide && Boolean(sidebar);

          if (wide && sidebar) {
            let anchor = toc;
            while (
              anchor &&
              anchor.parentElement &&
              anchor.parentElement !== sidebar
            ) {
              anchor = anchor.parentElement;
            }
            if (anchor) {
              sidebar.insertBefore(trackNav, anchor);
            } else {
              sidebar.prepend(trackNav);
            }
          } else {
            taxonomy.appendChild(trackNav);
          }
          if (trackContent) {
            const collapsed =
              desktopRailActive &&
              sidebar.classList.contains("bs-toc-collapsed");
            trackContent.hidden = collapsed;
            trackNav.classList.toggle(
              "bs-lesson-track-collapsed",
              collapsed
            );
          }
        }

        place();
        desktopQuery.addEventListener("change", place);
      });
  }

  function placeLessonRightRailCards() {
    const lessonPage =
      document.body.classList.contains("bs-learn-article") &&
      !document.body.classList.contains("bs-learn-track-index");
    if (!lessonPage) {
      return;
    }

    const placements = Array.from(
      document.querySelectorAll(".column-margin .bs-right-rail-card")
    ).map(function (card) {
      return {
        card: card,
        margin: card.closest(".column-margin"),
        nextSibling: card.nextSibling,
        source: card.parentElement
      };
    });
    if (!placements.length) {
      return;
    }

    const desktopQuery = window.matchMedia("(min-width: 992px)");

    function place() {
      const sidebar = document.getElementById("quarto-margin-sidebar");
      const useSidebar = desktopQuery.matches && Boolean(sidebar);

      placements.forEach(function (placement) {
        if (useSidebar) {
          sidebar.appendChild(placement.card);
          placement.margin.hidden = true;
          placement.card.classList.add("bs-right-rail-card--stacked");
          return;
        }

        placement.margin.hidden = false;
        if (
          placement.nextSibling &&
          placement.nextSibling.parentNode === placement.source
        ) {
          placement.source.insertBefore(
            placement.card,
            placement.nextSibling
          );
        } else {
          placement.source.appendChild(placement.card);
        }
        placement.card.classList.remove("bs-right-rail-card--stacked");
      });
    }

    place();
    desktopQuery.addEventListener("change", place);
  }

  function isMainSiteIndex() {
    const path = window.location.pathname.replace(/\/index\.html$/, "/");
    return path === "/";
  }

  function createTermLookup() {
    const lookup = document.createElement("aside");
    lookup.className = "bs-term-lookup";
    lookup.id = "bs-term-lookup-panel";
    lookup.dataset.bsTermLookup = "";
    lookup.hidden = true;
    lookup.innerHTML =
      '<div class="bs-term-lookup-heading">' +
      "<strong>Look Up a Term</strong>" +
      '<button type="button" class="bs-term-lookup-close" ' +
      'data-bs-term-lookup-close aria-controls="bs-term-lookup-panel" ' +
      'aria-expanded="true" aria-label="Collapse term lookup">' +
      '<span aria-hidden="true">&rarr;</span></button>' +
      "</div>" +
      '<form action="/glossary/" method="get" data-bs-term-lookup-form>' +
      '<label class="visually-hidden" for="bs-term-lookup-input">' +
      "Term or alias</label>" +
      '<div class="bs-term-lookup-controls">' +
      '<input id="bs-term-lookup-input" name="q" type="search" required ' +
      'autocomplete="off" spellcheck="false" ' +
      'placeholder="Enter Term">' +
      '<button type="submit">Search</button>' +
      "</div></form>" +
      '<div class="bs-term-lookup-result" data-bs-term-lookup-result ' +
      'aria-live="polite" hidden></div>';
    return lookup;
  }

  function renderLookupResult(container, entry, query) {
    container.replaceChildren();
    container.hidden = false;

    if (!entry) {
      const message = document.createElement("p");
      message.textContent = "No matching glossary term was found.";
      const fullSearch = document.createElement("a");
      fullSearch.className = "bs-term-lookup-full";
      fullSearch.href =
        "/glossary/?q=" + encodeURIComponent(query);
      fullSearch.textContent = "Search the Full Glossary \u2192";
      container.append(message, fullSearch);
      return;
    }

    const heading = document.createElement("h3");
    heading.textContent = entry.term;
    heading.tabIndex = -1;
    container.appendChild(heading);

    if (Array.isArray(entry.aliases) && entry.aliases.length > 0) {
      const aliases = document.createElement("p");
      aliases.className = "bs-term-lookup-aliases";
      aliases.textContent = "Otherwise known as: " + entry.aliases.join(", ");
      container.appendChild(aliases);
    }

    const shortDefinition = document.createElement("p");
    shortDefinition.className = "bs-term-lookup-short-definition";
    shortDefinition.textContent = entry.short_definition;
    container.appendChild(shortDefinition);

    const definition = document.createElement("p");
    definition.className = "bs-term-lookup-definition";
    definition.textContent = entry.definition;
    container.appendChild(definition);

    if (Array.isArray(entry.categories) && entry.categories.length > 0) {
      const categories = document.createElement("p");
      categories.className = "bs-term-lookup-categories";
      categories.textContent =
        (entry.categories.length === 1 ? "Category: " : "Categories: ") +
        entry.categories.join(", ");
      container.appendChild(categories);
    }

    const resolvedRelated = Array.isArray(entry.related_terms)
      ? entry.related_terms.filter(function (related) {
          return related && related.slug;
        })
      : [];
    if (resolvedRelated.length > 0) {
      const relatedTermsHeading = document.createElement("p");
      relatedTermsHeading.className = "bs-term-lookup-related-heading";
      relatedTermsHeading.textContent = "Related terms";
      const relatedTermsList = document.createElement("ul");
      relatedTermsList.className = "bs-term-lookup-related";
      resolvedRelated.forEach(function (related) {
        const item = document.createElement("li");
        const button = document.createElement("button");
        button.type = "button";
        button.className = "bs-term-lookup-related-term";
        button.dataset.bsTermLookupRelated = related.slug;
        button.textContent = related.term;
        item.appendChild(button);
        relatedTermsList.appendChild(item);
      });
      container.append(relatedTermsHeading, relatedTermsList);
    }

    if (
      Array.isArray(entry.related_lessons) &&
      entry.related_lessons.length > 0
    ) {
      const relatedHeading = document.createElement("p");
      relatedHeading.className = "bs-term-lookup-related-heading";
      relatedHeading.textContent = "Related lessons";
      const relatedList = document.createElement("ul");
      relatedList.className = "bs-term-lookup-related";
      entry.related_lessons.forEach(function (lesson) {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = lesson.route;
        link.textContent = lesson.title;
        item.appendChild(link);
        relatedList.appendChild(item);
      });
      container.append(relatedHeading, relatedList);
    }

    const fullEntry = document.createElement("a");
    fullEntry.className = "bs-term-lookup-full";
    fullEntry.href = "/glossary/#" + encodeURIComponent(entry.slug);
    fullEntry.textContent = "Go to glossary entry";
    container.appendChild(fullEntry);
  }

  function initializeTermLookup() {
    const glossaryIndexPage = document.body.classList.contains(
      "bs-glossary-index"
    );
    const lookupDisabled =
      isMainSiteIndex() ||
      document.body.classList.contains("bs-learn-index") ||
      document.body.classList.contains("bs-learn-track-index") ||
      document.body.classList.contains("bs-analyze-page") ||
      document.body.classList.contains("bs-match-predictor-page");
    const glossarySearch = document.querySelector(
      "[data-bs-glossary-search]"
    );
    const lookupCandidates = lookupDisabled
      ? []
      : Array.from(document.querySelectorAll("[data-bs-term-lookup]"));
    let lookup =
      lookupCandidates.find(function (candidate) {
        return !candidate.closest(".quarto-sidebar-toggle-contents");
      }) || lookupCandidates[0] || null;
    if (
      !lookupDisabled &&
      !lookup &&
      (!glossarySearch || glossaryIndexPage)
    ) {
      lookup = createTermLookup();
    }
    if (lookup) {
      lookup.classList.add("bs-term-lookup--site");
      lookup.id = lookup.id || "bs-term-lookup-panel";
      lookup.hidden = true;
    }
    const engineBenchmarkPage = document.body.classList.contains(
      "bs-engine-benchmark-page"
    );
    const refinedRightRailPage =
      (document.body.classList.contains("bs-learn-article") &&
        !document.body.classList.contains("bs-learn-track-index")) ||
      document.body.classList.contains("bs-research-article") ||
      engineBenchmarkPage;

    const tools = document.createElement("div");
    tools.className = "bs-site-tools";
    tools.setAttribute("role", "group");
    tools.setAttribute("aria-label", "Page tools");
    tools.innerHTML =
      '<button type="button" class="bs-term-lookup-reveal" ' +
      'data-bs-site-term-toggle aria-controls="bs-term-lookup-panel" ' +
      'aria-expanded="false" aria-label="Open term lookup">' +
      '<span aria-hidden="true">&larr;</span> Term Search</button>' +
      (refinedRightRailPage
        ? ""
        : '<button type="button" class="bs-toc-toggle" ' +
          'data-bs-toc-toggle aria-controls="TOC" aria-expanded="true" ' +
          'aria-label="Collapse table of contents" hidden>Collapse TOC</button>' +
          '<button type="button" class="bs-margin-sidebar-toggle" ' +
          'data-bs-margin-sidebar-toggle aria-controls="quarto-margin-sidebar" ' +
          'aria-expanded="true" aria-label="Collapse all right sidebar content" hidden>' +
          'Collapse All <span aria-hidden="true">&#9652;</span></button>') +
      '<button type="button" class="bs-site-back-to-top" ' +
      'data-bs-site-back-to-top hidden>Back to top ' +
      '<span aria-hidden="true">\u25b4</span></button>';

    let termToggle = tools.querySelector("[data-bs-site-term-toggle]");
    const tocToggle = tools.querySelector("[data-bs-toc-toggle]");
    const marginSidebarToggle = tools.querySelector(
      "[data-bs-margin-sidebar-toggle]"
    );
    const backToTop = tools.querySelector("[data-bs-site-back-to-top]");
    if (termToggle && !lookup && !glossarySearch) {
      termToggle.remove();
      termToggle = null;
    }
    const form = lookup
      ? lookup.querySelector("[data-bs-term-lookup-form]")
      : null;
    const input = form ? form.querySelector('input[name="q"]') : null;
    const result = lookup
      ? lookup.querySelector("[data-bs-term-lookup-result]")
      : null;
    const close = lookup
      ? lookup.querySelector("[data-bs-term-lookup-close]")
      : null;
    const desktopQuery = window.matchMedia("(min-width: 992px)");
    let marginSidebar =
      document.querySelector(
        "#quarto-margin-sidebar:not(.quarto-sidebar-toggle-contents)"
      ) || document.getElementById("quarto-margin-sidebar");
    let toc = null;
    let tocHeadingToggle = null;
    let tocObserver = null;
    let tocCloneObserver = null;
    const boundTocHeadingToggles = new WeakSet();
    let desktopCollapsed = !refinedRightRailPage;
    let tocCollapsed = false;
    let marginSidebarCollapsed = false;
    let rightRailScrollCollapsed = false;
    let lastRightRailScrollY = window.scrollY;
    let lastGlossaryScrollY = window.scrollY;
    let suppressRightRailAutoCollapse = false;
    let mobileDrawerOpen = false;
    let mobileTouchStart = null;
    let mobileDrawer = null;
    let mobileDrawerEdge = null;
    let mobileDrawerBackdrop = null;
    let mobileDrawerToc = null;

    if (refinedRightRailPage) {
      mobileDrawerEdge = document.createElement("button");
      mobileDrawerEdge.type = "button";
      mobileDrawerEdge.className = "bs-mobile-tools-edge";
      mobileDrawerEdge.dataset.bsMobileToolsEdge = "";
      mobileDrawerEdge.setAttribute("aria-controls", "bs-mobile-tools-drawer");
      mobileDrawerEdge.setAttribute("aria-expanded", "false");
      mobileDrawerEdge.setAttribute(
        "aria-label",
        "Open table of contents"
      );

      mobileDrawer = document.createElement("aside");
      mobileDrawer.id = "bs-mobile-tools-drawer";
      mobileDrawer.className = "bs-mobile-tools-drawer";
      mobileDrawer.dataset.bsMobileToolsDrawer = "";
      mobileDrawer.setAttribute("aria-label", "Page contents");
      mobileDrawer.setAttribute("aria-hidden", "true");
      mobileDrawer.innerHTML =
        '<div class="bs-mobile-tools-heading">' +
        "<strong>Page tools</strong>" +
        '<button type="button" data-bs-mobile-tools-close>Close</button>' +
        "</div>" +
        '<nav class="bs-mobile-tools-toc" aria-label="On this page" ' +
        "data-bs-mobile-tools-toc></nav>";
      mobileDrawerToc = mobileDrawer.querySelector(
        "[data-bs-mobile-tools-toc]"
      );

      mobileDrawerBackdrop = document.createElement("button");
      mobileDrawerBackdrop.type = "button";
      mobileDrawerBackdrop.className = "bs-mobile-tools-backdrop";
      mobileDrawerBackdrop.dataset.bsMobileToolsBackdrop = "";
      mobileDrawerBackdrop.setAttribute("aria-label", "Close page tools");
      mobileDrawerBackdrop.hidden = true;
      document.body.append(
        mobileDrawerBackdrop,
        mobileDrawer,
        mobileDrawerEdge
      );
    }

    const preservePagePosition = function (callback) {
      const scrollX = window.scrollX;
      const scrollY = window.scrollY;
      const restore = function () {
        window.scrollTo(scrollX, scrollY);
      };
      callback();
      restore();
      window.requestAnimationFrame(function () {
        restore();
        window.requestAnimationFrame(restore);
      });
      window.setTimeout(restore, 60);
      window.setTimeout(restore, 180);
    };

    const activateTocHeadingToggle = function (clickedToggle) {
        tocHeadingToggle = clickedToggle;
        toc = clickedToggle.closest("#TOC") || toc;
        marginSidebar =
          clickedToggle.closest("#quarto-margin-sidebar") || marginSidebar;
        suppressRightRailAutoCollapse = true;
        const visiblyCollapsed =
          clickedToggle.getAttribute("aria-expanded") === "false";
        if (visiblyCollapsed) {
          rightRailScrollCollapsed = false;
          tocCollapsed = false;
        } else {
          tocCollapsed = !tocCollapsed;
        }
        if (marginSidebar) {
          marginSidebar.classList.remove(
            "bs-refined-right-rail-scroll-collapsed"
          );
        }
        preservePagePosition(function () {
          updateToc();
          positionRefinedRightTools();
          document
            .querySelectorAll("[data-bs-lesson-track-nav]")
            .forEach(function (trackNav) {
              const trackContent = trackNav.querySelector(
                ".bs-lesson-track-content"
              );
              if (trackContent) {
                trackContent.hidden = tocCollapsed;
                trackNav.classList.toggle(
                  "bs-lesson-track-collapsed",
                  tocCollapsed
                );
              }
            });
        });
        window.setTimeout(function () {
          lastRightRailScrollY = window.scrollY;
          suppressRightRailAutoCollapse = false;
        }, 220);
    };

    const bindTocHeadingToggle = function (toggle) {
      if (!toggle || boundTocHeadingToggles.has(toggle)) {
        return;
      }
      boundTocHeadingToggles.add(toggle);
      toggle.dataset.bsTocToggleBound = "true";
      toggle.addEventListener("click", function () {
        activateTocHeadingToggle(toggle);
      });
    };

    const placeTocHeadingToggleBeforeLinks = function (toggle) {
      if (!toc || !toggle) {
        return;
      }
      let divider = toggle.closest(".bs-toc-toggle-divider");
      if (!divider) {
        divider = document.createElement("div");
        divider.className = "bs-toc-toggle-divider";
        divider.dataset.bsTocToggleDivider = "";
        toggle.replaceWith(divider);
        divider.appendChild(toggle);
      }
      const tocLinks = toc.querySelector(":scope > ul");
      if (
        tocLinks &&
        (divider.parentElement !== toc ||
          divider.nextElementSibling !== tocLinks)
      ) {
        toc.insertBefore(divider, tocLinks);
      }
    };

    const mountTocHeadingToggle = function () {
      if (!refinedRightRailPage) {
        return false;
      }
      const tocCandidates = Array.from(document.querySelectorAll("#TOC"));
      toc =
        (marginSidebar
          ? tocCandidates.find(function (candidate) {
              return marginSidebar.contains(candidate) && tocHasHashLinks(candidate);
            })
          : null) ||
        tocCandidates.find(tocHasHashLinks) ||
        (marginSidebar ? marginSidebar.querySelector("#TOC") : null);
      if (!toc || !tocHasHashLinks(toc)) {
        return false;
      }
      const existingToggle = toc.querySelector(
        "[data-bs-toc-heading-toggle]"
      );
      if (existingToggle) {
        tocHeadingToggle = existingToggle;
        bindTocHeadingToggle(tocHeadingToggle);
        placeTocHeadingToggleBeforeLinks(tocHeadingToggle);
        return true;
      }
      const tocLinks = toc.querySelector(":scope > ul");
      if (tocLinks) {
        tocLinks.id = tocLinks.id || "bs-toc-links";
        tocHeadingToggle = document.createElement("button");
        tocHeadingToggle.type = "button";
        tocHeadingToggle.className = "bs-toc-heading-toggle";
        tocHeadingToggle.dataset.bsTocHeadingToggle = "";
        tocHeadingToggle.setAttribute("aria-controls", tocLinks.id);
        tocHeadingToggle.hidden = true;
        bindTocHeadingToggle(tocHeadingToggle);
        const divider = document.createElement("div");
        divider.className = "bs-toc-toggle-divider";
        divider.dataset.bsTocToggleDivider = "";
        divider.appendChild(tocHeadingToggle);
        toc.insertBefore(divider, tocLinks);
        return true;
      }
      return false;
    };
    mountTocHeadingToggle();

    if (lookup && refinedRightRailPage) {
      const formElement = lookup.querySelector("[data-bs-term-lookup-form]");
      if (formElement && !lookup.querySelector(".bs-term-lookup-browse")) {
        const browseGlossary = document.createElement("a");
        browseGlossary.className = "bs-term-lookup-browse";
        browseGlossary.href = "/glossary/";
        browseGlossary.textContent = "Browse the full glossary";
        formElement.insertAdjacentElement("afterend", browseGlossary);
      }
    }

    if (lookup) {
      tools.insertBefore(lookup, marginSidebarToggle || backToTop);
    }

    const inDesktopSidebar = function () {
      return desktopQuery.matches && Boolean(marginSidebar);
    };

    const inRefinedRightRail = function () {
      return inDesktopSidebar() && refinedRightRailPage;
    };

    const inEditorialDock = function () {
      return (
        desktopQuery.matches &&
        !marginSidebar &&
        document.body.classList.contains("bs-research-index")
      );
    };

    const inDesktopDock = function () {
      return inDesktopSidebar() || inEditorialDock();
    };

    const refreshMobileDrawerToc = function () {
      if (!mobileDrawerToc) {
        return;
      }
      const sourceToc = Array.from(document.querySelectorAll("#TOC")).find(
        tocHasHashLinks
      );
      mobileDrawerToc.replaceChildren();
      if (!sourceToc) {
        mobileDrawerToc.hidden = true;
        return;
      }
      const sourceLinks = sourceToc.querySelector(":scope > ul");
      if (!sourceLinks) {
        mobileDrawerToc.hidden = true;
        return;
      }
      const heading = document.createElement("strong");
      heading.className = "bs-mobile-tools-toc-title";
      heading.textContent = "On this page";
      const links = sourceLinks.cloneNode(true);
      links.removeAttribute("id");
      [links]
        .concat(Array.from(links.querySelectorAll(".collapse, .collapsing")))
        .forEach(function (list) {
          list.classList.remove("collapse", "collapsing", "show");
          list.removeAttribute("hidden");
        });
      links.querySelectorAll("[id]").forEach(function (element) {
        element.removeAttribute("id");
      });
      links.querySelectorAll("[aria-controls]").forEach(function (element) {
        element.removeAttribute("aria-controls");
      });
      mobileDrawerToc.append(heading, links);
      mobileDrawerToc.hidden = false;
    };

    const setMobileDrawerOpen = function (expanded, options) {
      if (!mobileDrawer || !mobileDrawerEdge || !mobileDrawerBackdrop) {
        return;
      }
      mobileDrawerOpen = expanded;
      if (expanded) {
        refreshMobileDrawerToc();
      }
      mobileDrawer.classList.toggle("bs-mobile-tools-drawer--open", expanded);
      mobileDrawer.setAttribute("aria-hidden", expanded ? "false" : "true");
      mobileDrawerEdge.setAttribute(
        "aria-expanded",
        expanded ? "true" : "false"
      );
      mobileDrawerBackdrop.hidden = !expanded;
      document.body.classList.toggle("bs-mobile-tools-open", expanded);
      if (expanded && (!options || options.focus !== false)) {
        const target = mobileDrawer.querySelector(
          "a[href], [data-bs-mobile-tools-close]"
        );
        if (target) {
          target.focus({ preventScroll: true });
        }
      }
    };

    if (mobileDrawerEdge && mobileDrawer && mobileDrawerBackdrop) {
      mobileDrawerEdge.addEventListener("click", function () {
        setMobileDrawerOpen(true);
      });
      mobileDrawerBackdrop.addEventListener("click", function () {
        setMobileDrawerOpen(false);
      });
      const drawerClose = mobileDrawer.querySelector(
        "[data-bs-mobile-tools-close]"
      );
      if (drawerClose) {
        drawerClose.addEventListener("click", function () {
          setMobileDrawerOpen(false);
          mobileDrawerEdge.focus();
        });
      }
      mobileDrawer.addEventListener("click", function (event) {
        if (event.target.closest("a[href^='#']")) {
          setMobileDrawerOpen(false);
        }
      });
      document.addEventListener(
        "touchstart",
        function (event) {
          if (
            desktopQuery.matches ||
            mobileDrawerOpen ||
            event.touches.length !== 1
          ) {
            mobileTouchStart = null;
            return;
          }
          const touch = event.touches[0];
          mobileTouchStart =
            touch.clientX <= 56
              ? { x: touch.clientX, y: touch.clientY }
              : null;
        },
        { passive: true }
      );
      document.addEventListener(
        "touchend",
        function (event) {
          if (
            !mobileTouchStart ||
            desktopQuery.matches ||
            event.changedTouches.length !== 1
          ) {
            mobileTouchStart = null;
            return;
          }
          const touch = event.changedTouches[0];
          if (
            isMobileDrawerSwipe(
              mobileTouchStart.x,
              mobileTouchStart.y,
              touch.clientX,
              touch.clientY
            )
          ) {
            setMobileDrawerOpen(true);
          }
          mobileTouchStart = null;
        },
        { passive: true }
      );
    }

    const open = function (options) {
      const settings = options || {};
      const focusInput = settings.focusInput !== false;
      if (glossarySearch && !lookup) {
        glossarySearch.scrollIntoView({ behavior: "smooth", block: "center" });
        glossarySearch.focus();
        return;
      }
      if (!lookup) {
        return;
      }
      if (inDesktopDock()) {
        desktopCollapsed = false;
      }
      lookup.hidden = false;
      if (termToggle) {
        termToggle.hidden = true;
      }
      if (close) {
        close.setAttribute("aria-expanded", "true");
      }
      document.body.classList.add("bs-term-lookup-open");
      document
        .querySelectorAll("[data-bs-site-term-toggle]")
        .forEach(function (button) {
          button.setAttribute("aria-expanded", "true");
        });
      if (input && focusInput && desktopQuery.matches) {
        input.focus({ preventScroll: true });
      }
    };

    const closeLookup = function (options) {
      const settings = options || {};
      if (!lookup) {
        return;
      }
      if (settings.rememberDesktop && inDesktopDock()) {
        desktopCollapsed = true;
      }
      lookup.hidden = true;
      if (termToggle) {
        termToggle.hidden = false;
      }
      if (close) {
        close.setAttribute("aria-expanded", "false");
      }
      document.body.classList.remove("bs-term-lookup-open");
      document
        .querySelectorAll("[data-bs-site-term-toggle]")
        .forEach(function (button) {
          button.setAttribute("aria-expanded", "false");
        });
      if (settings.returnFocus && termToggle && !termToggle.hidden) {
        termToggle.focus();
      }
    };

    const hideLookupOnMobile = function () {
      if (lookup) {
        if (lookup.parentElement !== tools) {
          tools.insertBefore(lookup, marginSidebarToggle || backToTop);
        }
        lookup.classList.remove("bs-term-lookup--floating");
        lookup.hidden = true;
      }
      if (termToggle) {
        termToggle.hidden = true;
        termToggle.setAttribute("aria-expanded", "false");
      }
      if (close) {
        close.setAttribute("aria-expanded", "false");
      }
      document.body.classList.remove("bs-term-lookup-open");
    };

    const updateMarginSidebar = function () {
      if (!marginSidebar || !marginSidebarToggle) {
        return;
      }
      if (inRefinedRightRail()) {
        marginSidebarCollapsed = false;
        marginSidebar.classList.remove("bs-margin-sidebar-collapsed");
        marginSidebarToggle.hidden = true;
        return;
      }
      const collapsed = inDesktopSidebar() && marginSidebarCollapsed;
      marginSidebar.classList.toggle(
        "bs-margin-sidebar-collapsed",
        collapsed
      );
      marginSidebarToggle.hidden = !inDesktopSidebar();
      marginSidebarToggle.setAttribute(
        "aria-expanded",
        collapsed ? "false" : "true"
      );
      marginSidebarToggle.setAttribute(
        "aria-label",
        collapsed
          ? "Expand all right sidebar content"
          : "Collapse all right sidebar content"
      );
      marginSidebarToggle.innerHTML = collapsed
        ? 'Expand All <span aria-hidden="true">&#9662;</span>'
        : 'Collapse All <span aria-hidden="true">&#9652;</span>';
    };

    const updateToc = function () {
      if (!marginSidebar || (!tocToggle && !tocHeadingToggle)) {
        return;
      }
      const refined = inRefinedRightRail() && Boolean(tocHeadingToggle);
      marginSidebar.classList.toggle("bs-refined-right-rail", refined);
      if (refined) {
        const effectivelyCollapsed =
          tocCollapsed || rightRailScrollCollapsed;
        marginSidebar.classList.toggle(
          "bs-toc-collapsed",
          effectivelyCollapsed
        );
        if (tocToggle) {
          tocToggle.hidden = true;
        }
        tocHeadingToggle.hidden = false;
        tocHeadingToggle.setAttribute(
          "aria-expanded",
          effectivelyCollapsed ? "false" : "true"
        );
        tocHeadingToggle.setAttribute(
          "aria-label",
          effectivelyCollapsed
            ? "Expand table of contents"
            : "Collapse table of contents"
        );
        tocHeadingToggle.textContent = engineBenchmarkPage
          ? effectivelyCollapsed
            ? "Expand TOC"
            : "Collapse TOC"
          : effectivelyCollapsed
            ? "Table of Contents \u25be"
            : "\u25b4";
        return;
      }
      if (tocHeadingToggle) {
        tocHeadingToggle.hidden = true;
      }
      if (!tocToggle) {
        return;
      }
      const available = inDesktopSidebar() && Boolean(toc);
      const collapsed = available && tocCollapsed;
      marginSidebar.classList.toggle("bs-toc-collapsed", collapsed);
      tocToggle.hidden = !available;
      tocToggle.setAttribute(
        "aria-expanded",
        collapsed ? "false" : "true"
      );
      tocToggle.setAttribute(
        "aria-label",
        collapsed ? "Expand table of contents" : "Collapse table of contents"
      );
      tocToggle.textContent = collapsed ? "Expand TOC" : "Collapse TOC";
    };

    const positionRefinedRightTools = function () {
      if (!inRefinedRightRail()) {
        tools.style.removeProperty("--bs-refined-tools-left");
        tools.style.removeProperty("--bs-refined-tools-width");
        tools.style.removeProperty("--bs-refined-tools-top");
        if (backToTop) {
          backToTop.style.removeProperty("--bs-refined-tools-right");
        }
        return;
      }
      const sidebarBounds = marginSidebar.getBoundingClientRect();
      const viewportWidth = document.documentElement.clientWidth;
      const toolsWidth = Math.min(
        sidebarBounds.width * 3,
        viewportWidth - 32
      );
      const tocBounds =
        toc && toc.getClientRects().length > 0
          ? toc.getBoundingClientRect()
          : sidebarBounds;
      tools.style.setProperty(
        "--bs-refined-tools-left",
        Math.max(16, sidebarBounds.right - toolsWidth) + "px"
      );
      tools.style.setProperty(
        "--bs-refined-tools-width",
        toolsWidth + "px"
      );
      tools.style.setProperty(
        "--bs-refined-tools-top",
        Math.max(sidebarBounds.top, tocBounds.bottom) + 4 + "px"
      );
      if (backToTop) {
        backToTop.style.setProperty(
          "--bs-refined-tools-right",
          Math.max(8, viewportWidth - sidebarBounds.right) + "px"
        );
      }
    };

    const placeRefinedBackToTop = function () {
      if (!backToTop) {
        return;
      }
      const refined = inRefinedRightRail();
      backToTop.classList.toggle("bs-refined-back-to-top", refined);
      if (refined) {
        document.body.appendChild(backToTop);
      } else if (backToTop.parentElement !== tools) {
        tools.appendChild(backToTop);
      }
    };

    const updateRightRailForScroll = function () {
      if (!marginSidebar || !inRefinedRightRail()) {
        rightRailScrollCollapsed = false;
        if (marginSidebar) {
          marginSidebar.classList.remove(
            "bs-refined-right-rail-scroll-collapsed"
          );
        }
        lastRightRailScrollY = window.scrollY;
        return;
      }

      const currentScrollY = window.scrollY;
      if (suppressRightRailAutoCollapse) {
        rightRailScrollCollapsed = false;
        marginSidebar.classList.remove(
          "bs-refined-right-rail-scroll-collapsed"
        );
        lastRightRailScrollY = currentScrollY;
        return;
      }
      if (currentScrollY <= 32) {
        rightRailScrollCollapsed = false;
      } else if (Math.abs(currentScrollY - lastRightRailScrollY) > 6) {
        rightRailScrollCollapsed = currentScrollY > lastRightRailScrollY;
      }
      marginSidebar.classList.toggle(
        "bs-refined-right-rail-scroll-collapsed",
        rightRailScrollCollapsed
      );
      updateToc();
      positionRefinedRightTools();
      if (Math.abs(currentScrollY - lastRightRailScrollY) > 6) {
        lastRightRailScrollY = currentScrollY;
      }
    };

    const placeTools = function () {
      if (inDesktopSidebar()) {
        setMobileDrawerOpen(false, { focus: false });
        if (lookup && lookup.parentElement !== tools) {
          tools.insertBefore(lookup, marginSidebarToggle || backToTop);
        }
        tools.classList.add("bs-site-tools--sidebar");
        tools.classList.remove("bs-site-tools--editorial-dock");
        tools.classList.remove("bs-site-tools--floating");
        if (lookup) {
          lookup.classList.remove("bs-term-lookup--floating");
        }
        if (inRefinedRightRail()) {
          document.body.appendChild(tools);
        } else {
          let tocAnchor = toc;
          while (
            tocAnchor &&
            tocAnchor.parentElement &&
            tocAnchor.parentElement !== marginSidebar
          ) {
            tocAnchor = tocAnchor.parentElement;
          }
          if (tocAnchor && tocAnchor.parentElement === marginSidebar) {
            marginSidebar.insertBefore(tools, tocAnchor.nextSibling);
          } else {
            marginSidebar.appendChild(tools);
          }
        }
        if (lookup && !desktopCollapsed) {
          open({ focusInput: false });
        } else if (lookup) {
          closeLookup();
        }
      } else if (inEditorialDock()) {
        setMobileDrawerOpen(false, { focus: false });
        if (lookup && lookup.parentElement !== tools) {
          tools.insertBefore(lookup, marginSidebarToggle || backToTop);
        }
        tools.classList.add(
          "bs-site-tools--sidebar",
          "bs-site-tools--editorial-dock"
        );
        tools.classList.remove("bs-site-tools--floating");
        if (lookup) {
          lookup.classList.remove("bs-term-lookup--floating");
        }
        document.body.appendChild(tools);
        if (lookup && !desktopCollapsed) {
          open({ focusInput: false });
        } else if (lookup) {
          closeLookup();
        }
      } else if (refinedRightRailPage && mobileDrawer) {
        tools.classList.remove("bs-site-tools--sidebar");
        tools.classList.remove("bs-site-tools--editorial-dock");
        tools.classList.add("bs-site-tools--floating");
        document.body.appendChild(tools);
        hideLookupOnMobile();
        refreshMobileDrawerToc();
      } else {
        tools.classList.remove("bs-site-tools--sidebar");
        tools.classList.remove("bs-site-tools--editorial-dock");
        tools.classList.add("bs-site-tools--floating");
        document.body.appendChild(tools);
        if (desktopQuery.matches && lookup) {
          lookup.classList.add("bs-term-lookup--floating");
          closeLookup();
        } else {
          hideLookupOnMobile();
        }
      }
      updateToc();
      updateMarginSidebar();
      placeRefinedBackToTop();
      positionRefinedRightTools();
      updateRightRailForScroll();
    };

    if (
      refinedRightRailPage &&
      !tocHeadingToggle &&
      marginSidebar &&
      "MutationObserver" in window
    ) {
      tocObserver = new MutationObserver(function () {
        if (mountTocHeadingToggle()) {
          tocObserver.disconnect();
          tocObserver = null;
          updateToc();
        }
      });
      tocObserver.observe(marginSidebar, {
        childList: true,
        subtree: true
      });
    }
    if (refinedRightRailPage && "MutationObserver" in window) {
      tocCloneObserver = new MutationObserver(function () {
        document
          .querySelectorAll("[data-bs-toc-heading-toggle]")
          .forEach(bindTocHeadingToggle);
        positionRefinedRightTools();
      });
      tocCloneObserver.observe(document.body, {
        childList: true,
        subtree: true
      });
      document
        .querySelectorAll("[data-bs-toc-heading-toggle]")
        .forEach(bindTocHeadingToggle);
    }

    if (termToggle) {
      termToggle.addEventListener("click", function () {
        preservePagePosition(function () {
          open();
        });
      });
    }
    if (close) {
      close.addEventListener("click", function () {
        preservePagePosition(function () {
          closeLookup({ rememberDesktop: true, returnFocus: true });
        });
      });
    }
    if (marginSidebarToggle) {
      marginSidebarToggle.addEventListener("click", function () {
        marginSidebarCollapsed = !marginSidebarCollapsed;
        updateMarginSidebar();
      });
    }
    if (tocToggle) {
      tocToggle.addEventListener("click", function () {
        tocCollapsed = !tocCollapsed;
        updateToc();
      });
    }
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && mobileDrawerOpen) {
        setMobileDrawerOpen(false);
        if (mobileDrawerEdge) {
          mobileDrawerEdge.focus();
        }
        return;
      }
      if (
        event.key === "Escape" &&
        lookup &&
        !lookup.hidden &&
        !inRefinedRightRail()
      ) {
        preservePagePosition(function () {
          closeLookup({ rememberDesktop: true, returnFocus: true });
        });
      }
    });

    placeTools();
    desktopQuery.addEventListener("change", placeTools);
    window.addEventListener("resize", positionRefinedRightTools, {
      passive: true
    });
    window.addEventListener("scroll", positionRefinedRightTools, {
      passive: true
    });
    window.addEventListener("load", positionRefinedRightTools, { once: true });
    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(positionRefinedRightTools);
    });

    const updateLookupForScroll = function () {
      if (!lookup || !inRefinedRightRail()) {
        return;
      }
      if (suppressRightRailAutoCollapse) {
        return;
      }
      if (window.scrollY <= 32) {
        if (lookup.hidden) {
          open({ focusInput: false });
        }
      } else if (!lookup.hidden) {
        closeLookup();
      }
    };
    if (refinedRightRailPage) {
      window.addEventListener("scroll", updateLookupForScroll, {
        passive: true
      });
      window.addEventListener("scroll", updateRightRailForScroll, {
        passive: true
      });
      updateLookupForScroll();
    }
    const updateGlossaryLookupForScroll = function () {
      if (!glossaryIndexPage || !lookup) {
        return;
      }
      const currentScrollY = window.scrollY;
      if (Math.abs(currentScrollY - lastGlossaryScrollY) > 4) {
        if (!lookup.hidden) {
          closeLookup();
        }
        lastGlossaryScrollY = currentScrollY;
      }
    };
    if (glossaryIndexPage) {
      window.addEventListener("scroll", updateGlossaryLookupForScroll, {
        passive: true
      });
    }

    if (form && input && result) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        const query = normalizeLookupQuery(input.value);
        if (!query) {
          input.focus();
          return;
        }
        input.value = query;
        result.hidden = false;
        result.textContent = "Looking up\u2026";
        loadGlossaryLookupEntries()
          .then(function (entries) {
            renderLookupResult(
              result,
              bestLookupEntry(entries, query),
              query
            );
          })
          .catch(function () {
            window.location.href =
              "/glossary/?q=" + encodeURIComponent(query);
          });
      });
    }

    if (result) {
      result.addEventListener("click", function (event) {
        const target =
          event.target && typeof event.target.closest === "function"
            ? event.target.closest("[data-bs-term-lookup-related]")
            : null;
        if (!target || !result.contains(target)) {
          return;
        }
        const slug = target.dataset.bsTermLookupRelated;
        if (!slug) {
          return;
        }
        event.preventDefault();
        document.dispatchEvent(
          new CustomEvent("bs:open-glossary-term", {
            detail: { slug: slug, focusResult: true }
          })
        );
      });
    }

    document.addEventListener("bs:open-glossary-term", function (event) {
      const slug = event && event.detail ? event.detail.slug : "";
      if (!slug || !lookup || !result) {
        return;
      }
      if (!desktopQuery.matches) {
        window.location.href =
          "/glossary/#" + encodeURIComponent(slug);
        return;
      }
      suppressRightRailAutoCollapse = true;
      rightRailScrollCollapsed = false;
      if (marginSidebar) {
        marginSidebar.classList.remove(
          "bs-refined-right-rail-scroll-collapsed"
        );
      }
      preservePagePosition(function () {
        open({ focusInput: false });
      });
      result.hidden = false;
      result.textContent = "Looking up\u2026";
      loadGlossaryLookupEntries()
        .then(function (entries) {
          const entry = canonicalEntryBySlug(entries, slug);
          if (entry && input) {
            input.value = entry.term;
          }
          renderLookupResult(result, entry, entry ? entry.term : slug);
          if (entry && event.detail.focusResult) {
            const heading = result.querySelector("h3");
            if (heading) {
              heading.focus({ preventScroll: true });
            }
          }
        })
        .catch(function () {
          window.location.href =
            "/glossary/#" + encodeURIComponent(slug);
        });
      window.setTimeout(function () {
        lastRightRailScrollY = window.scrollY;
        suppressRightRailAutoCollapse = false;
      }, 220);
    });

    const legacyBackToTop = document.querySelector(
      "[data-bs-glossary-back-to-top]"
    );
    if (legacyBackToTop) {
      legacyBackToTop.remove();
    }
    const updateBackToTop = function () {
      if (backToTop) {
        backToTop.hidden = window.scrollY <= window.innerHeight;
      }
    };
    if (backToTop) {
      backToTop.addEventListener("click", function () {
        const reducedMotion = window.matchMedia(
          "(prefers-reduced-motion: reduce)"
        ).matches;
        window.scrollTo({
          top: 0,
          behavior: reducedMotion ? "auto" : "smooth"
        });
      });
      window.addEventListener("scroll", updateBackToTop, { passive: true });
      window.addEventListener("resize", updateBackToTop);
      updateBackToTop();
    }

    return {
      open: function () {
        if (!desktopQuery.matches) {
          return;
        }
        preservePagePosition(function () {
          open();
        });
      }
    };
  }

  function initializeMobileLessonBar() {
    if (
      !document.body.classList.contains("bs-learn-article") ||
      document.body.classList.contains("bs-learn-index") ||
      document.body.classList.contains("bs-learn-track-index")
    ) {
      return;
    }
    const bar = document.querySelector(
      ".quarto-secondary-nav .container-fluid"
    );
    if (!bar) {
      return;
    }
    const indexToggle = bar.querySelector(".quarto-btn-toggle");
    const breadcrumbs = bar.querySelector(".quarto-page-breadcrumbs");
    const filler = bar.querySelector("a.flex-grow-1");
    if (!indexToggle) {
      return;
    }

    indexToggle.classList.add("bs-mobile-lesson-index-toggle");
    indexToggle.setAttribute("aria-label", "Expand Lesson Index");
    const label = document.createElement("span");
    label.className = "bs-mobile-lesson-index-label";
    label.textContent = "\u2190 Expand Lesson Index";
    indexToggle.appendChild(label);
    if (breadcrumbs) {
      breadcrumbs.classList.add("bs-mobile-lesson-breadcrumbs");
    }
    if (filler) {
      filler.classList.add("bs-mobile-lesson-filler");
    }
  }

  function initializeLearnLeftSidebarToggle() {
    const learnPage =
      document.body.classList.contains("bs-learn-article") ||
      document.body.classList.contains("bs-learn-index") ||
      document.body.classList.contains("bs-learn-track-index");
    const sidebar = document.getElementById("quarto-sidebar");
    if (!learnPage || !sidebar) {
      return;
    }

    const desktopQuery = window.matchMedia("(min-width: 992px)");
    const keepExpandedWhileScrolling =
      document.body.classList.contains("bs-learn-index") ||
      document.body.classList.contains("bs-learn-track-index");
    const sidebarScroller =
      sidebar.querySelector(".sidebar-menu-container") || sidebar;
    const pageHeader = document.getElementById("quarto-header");
    const toggle = document.createElement("button");
    let collapsed = false;
    let lastScrollY = window.scrollY;
    let lastSidebarScrollTop = sidebarScroller.scrollTop;
    let scrollingDown = false;
    let pageScrollingDown = false;
    let autoCollapsePending = window.scrollY <= 32;
    toggle.type = "button";
    toggle.className = "bs-learn-left-sidebar-toggle";
    toggle.dataset.bsLearnLeftSidebarToggle = "";
    toggle.setAttribute("aria-controls", sidebar.id);
    document.body.appendChild(toggle);

    const positionExpandedToggle = function () {
      const sidebarRight = sidebar.getBoundingClientRect().right;
      toggle.style.left =
        Math.max(8, sidebarRight - toggle.offsetWidth - 24) + "px";
    };

    const updateVisibility = function () {
      const navbarHidden = Boolean(
        pageHeader && pageHeader.classList.contains("headroom--unpinned")
      );
      toggle.classList.toggle(
        "bs-learn-left-sidebar-toggle--nav-hidden",
        desktopQuery.matches &&
          window.scrollY > 32 &&
          (pageScrollingDown || navbarHidden)
      );
      toggle.hidden =
        !desktopQuery.matches ||
        (!collapsed &&
          !keepExpandedWhileScrolling &&
          scrollingDown &&
          (window.scrollY > 32 || sidebarScroller.scrollTop > 4));
      if (!toggle.hidden && !collapsed) {
        positionExpandedToggle();
      }
    };

    const update = function () {
      const active = desktopQuery.matches && collapsed;
      sidebar.hidden = active;
      document.body.classList.toggle("bs-learn-left-sidebar-collapsed", active);
      updateVisibility();
      toggle.setAttribute("aria-expanded", active ? "false" : "true");
      toggle.setAttribute(
        "aria-label",
        active ? "Show Learn table of contents" : "Hide Learn table of contents"
      );
      toggle.textContent = active ? "\u2192 Show Lessons" : "\u2190 Hide";
      if (active) {
        toggle.style.left = "0.5rem";
      } else {
        positionExpandedToggle();
      }
    };

    toggle.addEventListener("click", function () {
      collapsed = !collapsed;
      update();
    });
    window.addEventListener("resize", update);
    window.addEventListener(
      "scroll",
      function () {
        const currentScrollY = window.scrollY;
        if (currentScrollY <= 32) {
          autoCollapsePending = true;
          if (!keepExpandedWhileScrolling && collapsed) {
            collapsed = false;
            pageScrollingDown = false;
            scrollingDown = false;
            lastScrollY = currentScrollY;
            update();
            return;
          }
        }
        if (Math.abs(currentScrollY - lastScrollY) > 4) {
          pageScrollingDown = currentScrollY > lastScrollY;
          scrollingDown = pageScrollingDown;
          lastScrollY = currentScrollY;
          if (
            !keepExpandedWhileScrolling &&
            autoCollapsePending &&
            scrollingDown &&
            currentScrollY > 32
          ) {
            autoCollapsePending = false;
            if (!collapsed) {
              collapsed = true;
              update();
              return;
            }
          }
          updateVisibility();
        }
      },
      { passive: true }
    );
    sidebarScroller.addEventListener(
      "scroll",
      function () {
        const currentScrollTop = sidebarScroller.scrollTop;
        if (Math.abs(currentScrollTop - lastSidebarScrollTop) > 4) {
          scrollingDown = currentScrollTop > lastSidebarScrollTop;
          lastSidebarScrollTop = currentScrollTop;
          updateVisibility();
        }
      },
      { passive: true }
    );
    if (pageHeader && "MutationObserver" in window) {
      new MutationObserver(updateVisibility).observe(pageHeader, {
        attributes: true,
        attributeFilter: ["class"]
      });
    }
    if ("ResizeObserver" in window) {
      new ResizeObserver(function () {
        if (!toggle.hidden && !collapsed) {
          positionExpandedToggle();
        }
      }).observe(sidebar);
    }
    desktopQuery.addEventListener("change", update);
    update();
  }

  function findIdWithinRoot(root, id) {
    return (
      Array.from(root.querySelectorAll("[id]")).find(function (element) {
        return element.id === id;
      }) || null
    );
  }

  function initializeAnswerChoices(root) {
    root.querySelectorAll(".bs-decision-prompt").forEach(function (prompt) {
      if (prompt.dataset.bsAnswerChoicesMounted === "true") {
        return;
      }
      prompt.dataset.bsAnswerChoicesMounted = "true";
      const panelId = prompt.dataset.answerPanel;
      const panel = panelId ? findIdWithinRoot(root, panelId) : null;
      const buttons = Array.from(
        prompt.querySelectorAll(".bs-answer-choice")
      );
      const status = prompt.querySelector(".bs-choice-status");

      buttons.forEach(function (button) {
        button.addEventListener("click", function () {
          buttons.forEach(function (candidate) {
            candidate.setAttribute("aria-pressed", "false");
            candidate.classList.remove("is-selected");
          });

          button.setAttribute("aria-pressed", "true");
          button.classList.add("is-selected");

          if (status) {
            status.textContent =
              "Selected: " +
              button.textContent.trim() +
              ". The working answer is open below; correctness remains unverified.";
          }

          if (panel && panel.tagName === "DETAILS") {
            panel.open = true;
          }
        });
      });
    });
  }

  function initializeLazyAnalyzerFrames(root) {
    root
      .querySelectorAll("details.bs-analyzer-embed")
      .forEach(function (details) {
        if (details.dataset.bsLazyAnalyzerMounted === "true") {
          return;
        }
        details.dataset.bsLazyAnalyzerMounted = "true";
        details.addEventListener("toggle", function () {
          if (!details.open) {
            return;
          }

          const iframe = details.querySelector("iframe[data-src]");

          if (!iframe || iframe.getAttribute("src")) {
            return;
          }

          const source = iframe.dataset.src;

          if (!source) {
            return;
          }

          const status = details.querySelector(".bs-analyzer-status");

          if (status) {
            status.textContent = "Loading the analyzer…";
          }

          iframe.addEventListener(
            "load",
            function () {
              if (status) {
                status.textContent = "Analyzer loaded.";
              }
            },
            { once: true }
          );

          iframe.setAttribute("src", source);
          iframe.removeAttribute("data-src");
        });
      });
  }

  function mountLesson(rootElement) {
    if (
      !rootElement ||
      typeof rootElement.querySelectorAll !== "function"
    ) {
      return;
    }
    initializeAnswerChoices(rootElement);
    initializeLazyAnalyzerFrames(rootElement);
  }

  const publicApi = {
    bestLookupEntry: bestLookupEntry,
    canonicalEntryBySlug: canonicalEntryBySlug,
    canonicalShortDefinition: canonicalShortDefinition,
    groupControlState: groupControlState,
    inlineGlossaryTooltipPosition: inlineGlossaryTooltipPosition,
    isMobileDrawerSwipe: isMobileDrawerSwipe,
    isSamePageTocHref: isSamePageTocHref,
    itemMatchesLesson: itemMatchesLesson,
    lessonSearchRank: lessonSearchRank,
    lessonGroupSearchRank: lessonGroupSearchRank,
    itemMatchesTaxonomy: itemMatchesTaxonomy,
    matchesAny: matchesAny,
    normalizeLearnSearch: normalizeLearnSearch,
    normalizeLookupQuery: normalizeLookupQuery,
    lookupMatchRank: lookupMatchRank,
    mountLesson: mountLesson,
    parseList: parseList,
    rankLessonItems: rankLessonItems,
    setAllGroupsExpanded: setAllGroupsExpanded
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = publicApi;
  }

  if (typeof window !== "undefined") {
    window.BSLearn = Object.assign(window.BSLearn || {}, publicApi);
  }

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", function () {
      if (document.documentElement.dataset.bsLearnInitialized === "true") {
        return;
      }
      document.documentElement.dataset.bsLearnInitialized = "true";
      initializeLearnFilters();
      initializeLearnSidebarControls();
      initializeInlineGlossary();
      initializeTermLookup();
      initializeMobileLessonBar();
      initializeLearnLeftSidebarToggle();
      placeLessonTrackLinks();
      placeLessonRightRailCards();
      mountLesson(document);
    });
  }
})();
