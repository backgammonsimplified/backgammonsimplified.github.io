---

# Authoring Guide

This private guide explains where the site lives, how the navigation is wired, and how to copy the page components Marty wants to keep. The examples here are fixture-driven and intentionally editable.

## Where Things Live

| Area | Path | Notes |
|---|---|---|
| Homepage | `site/index.qmd` | Public landing page and homepage playground |
| Learn | `site/learn/index.qmd` | Curriculum landing page and lesson patterns |
| Glossary | `site/glossary/index.qmd` | One searchable page containing every canonical term |
| Custom 404 | `site/404.qmd` | Root not-found page and recovery links |
| Analyze | `site/analyze/index.qmd` | Static analyzer entry page and Shiny companion |
| Engine Benchmark | `site/engine-benchmark/index.qmd` | Stable benchmark hub and method overview |
| Sage vs GNU report | `site/engine-benchmark/sage-vs-gnu-stage1/index.qmd` | Preliminary study report beneath the benchmark hub |
| About | `site/about.qmd` | Project purpose and site-level identity |
| Legacy post fixtures | `site/posts/**` | Fixture-only examples; not a publication surface |
| Shared CSS | `site/assets/` | Layout, color, and component styling |

## Navigation

Edit `site/_quarto.yml` to change the navbar. The current public navigation is:

`Learn | Analyze | Match Predictor | Engine Benchmark | Research | Glossary | About | Search`

`Practice`, `Positions`, and the old `Blog` surface stay out of the primary navbar.

## Learn Sidebar

The Learn sidebar is generated into `site/_learn-navigation.yml`. Do not edit
that file or add a second manual Learn sidebar to `site/_quarto.yml`.
Track-index and lesson front matter define the hierarchy and order.

## Learn Catalogue

The Learn index, each track index, and the Learn sidebar are three generated
views of the same curriculum metadata. The Learn index provides search,
difficulty filters, and track focus. Each track index provides search,
difficulty filters, and term filters.

A track index declares a stable ID and its top-level order:

```yaml
---
title: "The Doubling Cube"
description: "Lessons about cube action, take points, market losers, and cube timing."
sidebar: learn
learn-track-index: doubling-cube
learn-track-order: 2
page-layout: full
body-classes: "bs-learn-article bs-learn-track-index"
toc: false
term-lookup: false
lesson-taxonomy: false
---

{{< include _lesson-index.html >}}
```

Every lesson then names exactly one primary track and its order within that
track. Running the generator updates `site/_learn-navigation.yml`,
`site/learn/_lesson-catalogue.html`, and every track's `_lesson-index.html`.
The Roman numerals are derived from the numeric order metadata and never
belong in titles.

## Learn Lesson Taxonomy

Every file under `site/learn/` that represents a lesson must declare `categories`, `tags`, and `terms`.

Allowed difficulty categories:

- `Beginner`
- `Intermediate`
- `Advanced`

Allowed learning-track tags:

- `Doubling Cube`
- `Checker Play`
- `Opening Play`
- `Match Play`
- `Endgames`
- `Engines and Analysis`

Use YAML lists even when selecting one value. Multiple difficulties or tracks mean the lesson is appropriate to each selected value. `terms` must contain canonical glossary slugs only; never use an alias slug. Related glossary links are generated only from this explicit metadata.

A complete lesson header looks like:

```yaml
---
title: "Why Is 25% the Basic Take Point When a Double Is Offered?"
description: "Learn the simplified comparison between taking and passing."
sidebar: learn
learn-track: doubling-cube
learn-order: 1
categories:
  - Beginner
  - Intermediate
tags:
  - Doubling Cube
terms:
  - take-point
  - equity
body-classes: bs-learn-article
---
```

The generated canonical-slug and stable-anchor reference is [learn-glossary-terms.md](learn-glossary-terms.md). Regenerate the Learn catalogue, glossary entries fragment, and that authoring reference with:

```powershell
python scripts/learn_glossary.py generate
python scripts/learn_glossary.py validate
```

Do not add glossary relationships by scanning lesson prose. A keyword scan may be used as an authoring warning, but the public relationship must remain explicit in `terms`.

`learn-track` must match a `learn-track-index` ID. `learn-order` must be a
unique, contiguous positive integer within that track. The generator uses
those two fields as the single curriculum sequence for the global Learn index,
the relevant track index, and the sidebar.

## Single-Page Glossary

The glossary has one public route:

```text
/glossary/
```

Do not create a directory or page for an individual term. Every canonical term
is an expandable entry in the initial HTML on the glossary page. Link to a term
with its stable canonical anchor:

```text
/glossary/#prime
/glossary/#take-point
```

Use canonical slugs in Learn and Research `terms` metadata. Aliases remain
inside their canonical data entry and search resolves them to the canonical
anchor; aliases never receive separate pages, redirects, or visible duplicate
entries. Related Learn and Research content is driven only by explicit
canonical `terms` metadata.

`site/404.qmd` is the source for the root `404.html` page. Keep its recovery
links to Home, Learn, Backgammon Glossary, and Research. It must
remain a normal content page without redirect code.

## Legacy Post Fixtures

The old `site/posts/**` examples remain explicitly registered as `fixture` routes. They are excluded from indexing, sitemap, RSS, and primary navigation. New Learn, Research, and benchmark content belongs under its public section and must use the page-publication registry instead of reviving a separate blog surface.

## Updates RSS

`site/updates/index.qmd` produces the combined `/updates/index.xml` feed. An
eligible Learn article, Research article, study, or benchmark report must live
under its public section, have a real ISO publication `date`, and explicitly
set `published: true`. The feed sorts those sources in reverse chronological
order. Do not mark landings, drafts, hidden or planned pages, or private fixture
posts as published feed items.

The controlled route entry in `site/_publication.yml` must also have
`status: published`. Source validation rejects either half of a contradictory
combination: `published: true` on a preliminary, draft, or fixture route, or a
feed-eligible article/report marked `status: published` without the explicit
source switch and date. Landing pages use the controlled `published` route
status for indexing but never set `published: true`, because they are not dated
Updates items.

## Page Publication Status

`site/_publication.yml` is the fail-closed registry for canonical routes, page
types, indexing, sitemap eligibility, breadcrumbs, and related-content hooks.
Unregistered routes resolve to `draft` and remain non-indexable. Use only the
controlled statuses `published`, `preliminary`, `draft`, `fixture`, `error`,
and `legacy`.

Routes listed under a page's `related` field generate one visible related-content
navigation block and the corresponding machine-readable metadata. Use only
explicit relationships supported by the page hierarchy or authored content;
do not duplicate the generated block in each page source.

Before changing an authored article or report to `published`, remove explicit
unresolved author markers. The publication gate recognizes line-level `TODO:`,
a line containing only `TODO`, and `[PENDING ...]` markers while ignoring fenced
examples, HTML comments, and ordinary prose that merely discusses words such as
“todo” or “pending.” Do not replace preliminary scientific markers with guesses.

## Homepage Navigation

The homepage entry cards are hand-curated. Stable section cards should enter through their section hubs; links to an individual report belong in report-specific context.

## Copying A Component

Each primary page has a `Component Playground` section. Marty can copy a rendered component and then copy the code source directly below it. The main pages that need this treatment are:

- Homepage
- Learn
- Analyze
- Sage vs GNU
- Blog
- About

## Removing Playground Sections

Before public release, search for `Component Playground` and delete or rewrite every section under that boundary. The visible boundary is deliberate so the private material is easy to remove.

## Render And Preview

Render the full site from `site/` with:

```bash
quarto render
```

Preview one page by rendering the page file directly, for example:

```bash
quarto render learn/index.qmd
```

## Shiny

Run the analyzer app from `shiny/position-dashboard/` with the local R environment. The site and Shiny app are separate. The public Analyze page currently provides a board-and-match preview; it does not promise full engine analysis.

## Generated Directories

Do not edit `_site/`, rendered HTML output, or other generated artifacts. Use the source files under `site/` instead.

## References

This guide uses fixture citation examples only, consistent with the private playground approach [@bs-fixture-methodology].
:::::

