from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from scripts import page_publication


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "learn_glossary.py"
SPEC = importlib.util.spec_from_file_location("learn_glossary", MODULE_PATH)
assert SPEC and SPEC.loader
learn_glossary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(learn_glossary)

PRE_RENDER_PATH = ROOT / "scripts" / "bs_pre_render.py"
PRE_RENDER_SPEC = importlib.util.spec_from_file_location(
    "bs_pre_render",
    PRE_RENDER_PATH,
)
assert PRE_RENDER_SPEC and PRE_RENDER_SPEC.loader
bs_pre_render = importlib.util.module_from_spec(PRE_RENDER_SPEC)
PRE_RENDER_SPEC.loader.exec_module(bs_pre_render)

POST_RENDER_PATH = ROOT / "scripts" / "bs_post_render.py"
POST_RENDER_SPEC = importlib.util.spec_from_file_location(
    "bs_post_render",
    POST_RENDER_PATH,
)
assert POST_RENDER_SPEC and POST_RENDER_SPEC.loader
bs_post_render = importlib.util.module_from_spec(POST_RENDER_SPEC)
POST_RENDER_SPEC.loader.exec_module(bs_post_render)


@contextmanager
def writable_test_directory():
    runtime_root = ROOT / "task-work" / "W3W-REGRESSION-01" / "runtime"
    path = runtime_root / f"validator-fixture-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)


class LearnGlossaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(
            learn_glossary.PUBLIC_DATA_PATH.read_text(encoding="utf-8")
        )
        cls.entries = learn_glossary.validate_public_data(cls.data)
        cls.tracks = learn_glossary.discover_tracks()
        cls.lessons = learn_glossary.discover_lessons()
        cls.real_lessons = learn_glossary.discover_lessons()
        cls.lesson_sections = learn_glossary.build_curriculum(
            cls.tracks,
            cls.lessons,
        )
        cls.learn_sequence = learn_glossary.build_learn_sequence(
            cls.lesson_sections
        )
        cls.related_lessons = learn_glossary.validate_lessons(
            cls.lessons,
            cls.entries,
        )
        cls.research_articles = learn_glossary.discover_research_articles()
        cls.related_research = learn_glossary.validate_research_articles(
            cls.research_articles,
            cls.entries,
        )
        cls.cube_lessons = learn_glossary.discover_cube_lessons()
        cls.update_publications = learn_glossary.discover_update_publications()
        cls.entries_html = learn_glossary.GENERATED_ENTRIES_PATH.read_text(
            encoding="utf-8"
        )

    def test_public_safe_counts_and_forbidden_guards(self) -> None:
        self.assertEqual(len(self.data["entries"]), 12)
        self.assertEqual(len(self.entries), 12)
        self.assertEqual(
            sum(len(entry["aliases"]) for entry in self.entries),
            3,
        )
        self.assertEqual(12 + 3, 15)
        self.assertTrue(
            all(
                entry["date_added"] == "2026-07-30"
                for entry in self.entries
                if "date_added" in entry
            )
        )
        self.assertEqual(
            sum("date_added" in entry for entry in self.entries),
            12,
        )
        learn_glossary.assert_no_forbidden_keys(self.data)
        learn_glossary.assert_no_forbidden_text(
            learn_glossary.PUBLIC_DATA_PATH.read_text(encoding="utf-8"),
            "tracked public glossary data",
        )
        learn_glossary.assert_no_forbidden_text(
            self.entries_html,
            "single-page glossary entries",
        )

    def test_generator_manages_glossary_and_sidebar_driven_learn_outputs(self) -> None:
        outputs = learn_glossary.generated_outputs(
            self.entries,
            self.lesson_sections,
            self.related_lessons,
            self.related_research,
            self.research_articles,
        )
        track_outputs = {
            track["path"].parent / "_lesson-index.html"
            for track in self.lesson_sections
        }
        self.assertEqual(
            set(outputs),
            {
                learn_glossary.GENERATED_LESSON_CATALOGUE_PATH,
                learn_glossary.GENERATED_NAVIGATION_PATH,
                learn_glossary.GENERATED_ENTRIES_PATH,
                learn_glossary.GENERATED_LOOKUP_DATA_PATH,
                learn_glossary.GENERATED_LEARN_SEQUENCE_PATH,
                learn_glossary.GENERATED_RESEARCH_SEQUENCE_PATH,
                learn_glossary.AUTHORING_TERMS_PATH,
                *track_outputs,
            }
        )
        self.assertEqual(len(outputs), 10)
        self.assertEqual(
            outputs,
            learn_glossary.generated_outputs(
                self.entries,
                self.lesson_sections,
                self.related_lessons,
                self.related_research,
                self.research_articles,
            ),
        )
        for path, expected in outputs.items():
            self.assertEqual(path.read_text(encoding="utf-8"), expected)

    def test_lesson_search_indexes_metadata_first_and_body_prose_second(self) -> None:
        with writable_test_directory() as directory:
            lesson_path = directory / "lesson.qmd"
            lesson_path.write_text(
                """---
title: Metadata title
tags: [Tagged phrase]
---

# Body heading

The body-only phrase is searchable.

[Visible link words](https://example.com)

```text
private code phrase
```

<span>Visible HTML words</span>
""",
                encoding="utf-8",
            )
            body = learn_glossary.lesson_body_search_text(lesson_path)
        self.assertIn("Body heading", body)
        self.assertIn("body-only phrase", body)
        self.assertIn("Visible link words", body)
        self.assertIn("Visible HTML words", body)
        self.assertNotIn("Metadata title", body)
        self.assertNotIn("private code phrase", body)
        self.assertNotIn(":::", body)

        lesson = next(
            lesson
            for lesson in self.lessons
            if lesson["relative_path"] == "cube/what-the-cube-is-asking.qmd"
        )
        markup = "\n".join(
            learn_glossary.lesson_catalogue_item_html(
                lesson,
                {str(entry["slug"]): str(entry["term"]) for entry in self.entries},
            )
        )
        self.assertIn("data-bs-search-primary=", markup)
        self.assertIn("data-bs-search-body=", markup)
        self.assertIn(str(lesson["title"]), markup)
        self.assertIn(str(lesson["description"]), markup)
        self.assertIn("Doubling Cube", markup)
        self.assertIn("worked position", markup.casefold())
        self.assertNotIn(":::", markup)
        self.assertNotIn("{ }", markup)
        self.assertNotIn("data-bs-search=", markup)

    def test_research_sequence_is_sorted_and_linked(self) -> None:
        sequence = learn_glossary.build_research_sequence(
            self.research_articles
        )
        articles = sequence["articles"]
        self.assertEqual(sequence["schema_version"], 1)
        self.assertEqual(
            [article["title"] for article in articles],
            sorted(
                [str(article["title"]) for article in self.research_articles],
                key=str.casefold,
            ),
        )
        for index, article in enumerate(articles):
            self.assertEqual(article["sequence_index"], index)
            self.assertEqual(
                article["previous_route"],
                articles[index - 1]["route"] if index else None,
            )
            self.assertEqual(
                article["next_route"],
                articles[index + 1]["route"]
                if index + 1 < len(articles)
                else None,
            )

    def test_exactly_one_glossary_source_page_and_zero_term_pages(self) -> None:
        self.assertEqual(
            learn_glossary.GLOSSARY_ROOT,
            learn_glossary.SITE_ROOT / "glossary",
        )
        self.assertFalse((learn_glossary.LEARN_ROOT / "glossary").exists())
        self.assertTrue((learn_glossary.GLOSSARY_ROOT / "index.qmd").exists())
        self.assertEqual(
            list(learn_glossary.GLOSSARY_ROOT.glob("*/index.qmd")),
            [],
        )
        self.assertFalse(learn_glossary.LEGACY_GENERATED_ROUTES_PATH.exists())
        self.assertEqual(
            [
                path
                for path in learn_glossary.GLOSSARY_ROOT.rglob("*.qmd")
                if path.name == "index.qmd"
            ],
            [learn_glossary.GLOSSARY_ROOT / "index.qmd"],
        )

    def test_single_page_has_unique_canonical_anchors_and_collapsed_terms(self) -> None:
        canonical = {str(entry["slug"]) for entry in self.entries}
        anchors = re.findall(
            r'<details class="bs-glossary-entry" id="([^"]+)"',
            self.entries_html,
        )
        self.assertEqual(len(anchors), 12)
        self.assertEqual(len(set(anchors)), 12)
        self.assertEqual(set(anchors), canonical)
        self.assertEqual(
            self.entries_html.count('class="bs-glossary-entry-summary"'),
            12,
        )
        entry_tags = re.findall(
            r'<details class="bs-glossary-entry"[^>]*>',
            self.entries_html,
        )
        self.assertEqual(len(entry_tags), 12)
        self.assertTrue(
            all(
                re.search(
                    r"\sopen(?:\s|>)",
                    re.sub(r'"[^"]*"', '""', tag),
                )
                is None
                for tag in entry_tags
            )
        )

    def test_aliases_map_to_canonical_entries_without_visible_duplicates(self) -> None:
        canonical = {entry["slug"]: entry for entry in self.entries}
        alias_to_canonical = {
            alias["slug"]: entry["slug"]
            for entry in self.entries
            for alias in entry["aliases"]
        }
        self.assertEqual(len(alias_to_canonical), 3)
        self.assertEqual(
            alias_to_canonical["ahead-in-the-race"],
            "ahead-in-the-count",
        )
        self.assertEqual(
            alias_to_canonical["american-backgammon-tour"],
            "abt",
        )
        self.assertNotIn("ahead-in-the-race", canonical)
        self.assertEqual(self.entries_html.count('data-bs-alias="'), 3)
        self.assertIn(
            'data-bs-aliases="[&quot;ahead-in-the-race&quot;]"',
            self.entries_html,
        )
        self.assertNotIn('id="ahead-in-the-race"', self.entries_html)
        self.assertNotIn("candidate only", self.entries_html.casefold())

    def test_full_definitions_usage_and_related_links_are_initial_html(self) -> None:
        self.assertEqual(
            self.entries_html.count('class="bs-glossary-definition"'),
            12,
        )
        self.assertEqual(
            self.entries_html.count('class="bs-glossary-short-definition"'),
            12,
        )
        zone = next(
            entry for entry in self.entries
            if entry["slug"] == "10-in-the-zone"
        )
        self.assertIn(
            "Bringing two active builders down from the mid-point",
            zone["definition"],
        )
        self.assertIn(
            'data-bs-glossary-slug="active-builder" '
            'data-bs-definition-link="active-builder">active builders</a>',
            self.entries_html,
        )
        self.assertNotIn('target="_blank"', self.entries_html)
        self.assertNotIn("bs-learn-card-taxonomy", self.entries_html)
        self.assertNotIn("bs-research-post-taxonomy", self.entries_html)
        self.assertNotIn("Link to this term", self.entries_html)
        self.assertNotIn("bs-glossary-anchor", self.entries_html)
        self.assertEqual(
            sum(len(value) for value in self.related_lessons.values()),
            sum(
                1
                for lesson in self.lessons
                for slug in lesson["terms"]
                if slug in {entry["slug"] for entry in self.entries}
            ),
        )
        self.assertEqual(
            sum(len(value) for value in self.related_research.values()),
            sum(
                1
                for article in self.research_articles
                for slug in article["terms"]
                if slug in {entry["slug"] for entry in self.entries}
            ),
        )

    def test_no_old_term_routes_metadata_or_navigation_remain(self) -> None:
        canonical = {str(entry["slug"]) for entry in self.entries}
        self.assertFalse(
            any(f"/glossary/{slug}/" in self.entries_html for slug in canonical)
        )
        for forbidden in (
            "canonical-url:",
            "bs-glossary-term-navigation",
            'rel="prev"',
            'rel="next"',
            "bs-glossary-term-card",
        ):
            self.assertNotIn(forbidden, self.entries_html)

        script = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("def build_term_qmd", script)
        self.assertNotIn("sampled_term_paths", script)
        self.assertNotIn("Expected 625 glossary HTML files", script)
        self.assertIn("sitemap_glossary_routes", script)
        self.assertIn('"standalone_term_pages": 0', script)

    def test_glossary_has_one_canonical_and_one_shared_social_image(self) -> None:
        source = (learn_glossary.GLOSSARY_ROOT / "index.qmd").read_text(
            encoding="utf-8"
        )
        self.assertEqual(source.count("canonical-url:"), 1)
        self.assertIn("sidebar: false", source)
        self.assertNotIn("sidebar: learn", source)
        self.assertIn(
            'canonical-url: "https://backgammonsimplified.github.io/glossary/"',
            source,
        )
        self.assertEqual(source.count("social-card-slug: glossary"), 1)
        self.assertIn(
            "image: /assets/social/generated/social-glossary.png",
            source,
        )

        manifest = (
            learn_glossary.SITE_ROOT / "assets" / "social" / "social-cards.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(manifest.count("- slug: glossary"), 1)
        self.assertEqual(
            manifest.count(
                "output: site/assets/social/generated/social-glossary.png"
            ),
            1,
        )
        canonical_slugs = {entry["slug"] for entry in self.entries}
        per_term_images = [
            path
            for path in (
                learn_glossary.SITE_ROOT / "assets" / "social" / "generated"
            ).glob("social-*.png")
            if path.stem.removeprefix("social-") in canonical_slugs
        ]
        self.assertEqual(per_term_images, [])

    def test_letter_sections_open_and_term_disclosures_do_not(self) -> None:
        letter_tags = re.findall(
            r'<details class="bs-glossary-letter-group"[^>]*>',
            self.entries_html,
        )
        self.assertGreater(len(letter_tags), 0)
        self.assertTrue(all(" open" in tag for tag in letter_tags))
        self.assertEqual(
            self.entries_html.count("data-bs-glossary-collapse-all"),
            1,
        )
        self.assertEqual(
            self.entries_html.count("data-bs-glossary-expand-all"),
            1,
        )
        self.assertRegex(
            self.entries_html,
            r"data-bs-glossary-expand-all[^>]*disabled",
        )
        self.assertIn('href="#letter-a"', self.entries_html)
        self.assertIn('id="letter-a"', self.entries_html)
        self.assertNotIn('id="letter-A"', self.entries_html)

    def test_fragment_search_and_letter_behavior_are_wired(self) -> None:
        javascript = (
            learn_glossary.SITE_ROOT / "assets" / "bs-glossary.js"
        ).read_text(encoding="utf-8")
        for required in (
            "function canonicalSlugForFragment",
            "function setExactlyOneExpandedTerm",
            "function closeTermEntries",
            "function openCurrentHash",
            "normalizedTermFragmentUrl(",
            "const rankedItems = rankGlossaryItems(visibleItems, query)",
            "expandBestGlossaryMatch(",
            "autoOpenedSearchItem",
            'searchInput.value = ""',
            "activeLetterBrowse =",
            "closeTermEntries(items)",
            "applyFilters({ updateUrl: false })",
            "letterNavigationUrl(",
        ):
            self.assertIn(required, javascript)
        self.assertNotIn("item.element.open = visible", javascript)
        self.assertNotIn("setAllGroupsExpanded(items", javascript)
        self.assertIn("group.open = expanded", javascript)

    def test_lookup_get_contract_and_same_tab_link_policy_are_preserved(self) -> None:
        term_lookup = (
            learn_glossary.SITE_ROOT
            / "_extensions"
            / "bs-term-lookup"
            / "bs-term-lookup.lua"
        ).read_text(encoding="utf-8")
        self.assertRegex(
            term_lookup,
            r'<form action="/glossary/" method="get" '
            r"data-bs-term-lookup-form",
        )
        self.assertRegex(term_lookup, r'<input[^>]*name="q"')
        self.assertIn(
            'aria-controls="bs-term-lookup-panel" aria-expanded="true"',
            term_lookup,
        )
        self.assertNotIn(
            ">Collapse <span aria-hidden",
            term_lookup,
        )
        self.assertNotIn("target=", term_lookup)
        self.assertNotRegex(term_lookup, r"(?i)opens? in (?:a )?new tab")

        link_policy = (
            learn_glossary.SITE_ROOT
            / "_extensions"
            / "bs-link-policy"
            / "bs-link-policy.lua"
        ).read_text(encoding="utf-8")
        self.assertIn("function Link(link)", link_policy)
        self.assertIn("link.attributes.target = nil", link_policy)
        self.assertNotIn("link.attributes.download =", link_policy)
        self.assertNotIn("_blank", link_policy)
        self.assertNotRegex(link_policy, r"(?i)opens? in (?:a )?new tab")

    def test_temporary_site_wide_same_tab_source_contract(self) -> None:
        source_paths = [
            path
            for path in learn_glossary.SITE_ROOT.rglob("*")
            if path.is_file()
            and path.suffix in {".qmd", ".html", ".yml", ".yaml", ".lua", ".js"}
            and "_site" not in path.parts
            and "_freeze" not in path.parts
        ]
        for path in source_paths:
            content = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("_blank", content, str(path.relative_to(ROOT)))
            self.assertNotRegex(
                content,
                r"(?i)opens? in (?:a )?new tab",
                str(path.relative_to(ROOT)),
            )

        config = (learn_glossary.SITE_ROOT / "_quarto.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("link-external-newwindow: false", config)
        self.assertNotRegex(config, r"(?m)^\s+target:")
        self.assertIn("href: /updates/index.xml", config)

        about = (learn_glossary.SITE_ROOT / "about.qmd").read_text(
            encoding="utf-8"
        )
        self.assertIn("[Read what I am building ->](/research/)", about)

        learn_home = (learn_glossary.LEARN_ROOT / "index.qmd").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            learn_home.split("---", 2)[-1].strip(),
            "{{< include _lesson-catalogue.html >}}",
        )
        self.assertIn('href="#letter-a"', self.entries_html)
        self.assertIn('href="/learn/', self.entries_html)

        analyze = (learn_glossary.SITE_ROOT / "analyze" / "index.qmd").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "](https://backgammon-simplified.shinyapps.io/",
            analyze,
        )
        self.assertIn("bs-analyze-page", analyze)
        self.assertIn("term-lookup: false", analyze)

        match_predictor = (
            learn_glossary.SITE_ROOT / "match-predictor" / "index.qmd"
        ).read_text(encoding="utf-8")
        self.assertIn("term-lookup: false", match_predictor)
        self.assertIn("bs-match-predictor-page", match_predictor)

        engine_benchmark = (
            learn_glossary.SITE_ROOT / "engine-benchmark" / "index.qmd"
        ).read_text(encoding="utf-8")
        self.assertIn("bs-engine-benchmark-page", engine_benchmark)
        engine_stage = (
            learn_glossary.SITE_ROOT
            / "engine-benchmark"
            / "sage-vs-gnu-stage1"
            / "index.qmd"
        ).read_text(encoding="utf-8")
        self.assertIn("bs-engine-benchmark-page", engine_stage)

        research_index = (
            learn_glossary.SITE_ROOT / "research" / "index.qmd"
        ).read_text(encoding="utf-8")
        self.assertIn("bs-research-index", research_index)
        self.assertNotIn("bs-research-article", research_index)
        self.assertNotIn("term-lookup: false", research_index)
        for research_article in (
            "what-we-are-building.qmd",
            "sage-vs-gnu-additional-details.qmd",
        ):
            article_source = (
                learn_glossary.SITE_ROOT / "research" / research_article
            ).read_text(encoding="utf-8")
            self.assertIn("bs-research-article", article_source)

        link_policy = (
            learn_glossary.SITE_ROOT
            / "_extensions"
            / "bs-link-policy"
            / "bs-link-policy.lua"
        ).read_text(encoding="utf-8")
        self.assertIn("link.attributes.target = nil", link_policy)
        self.assertNotIn("link.attributes.download =", link_policy)
        self.assertNotIn("link.target =", link_policy)

    def test_only_approved_metadata_terms_create_public_relationships(self) -> None:
        canonical = {entry["slug"] for entry in self.entries}
        aliases = {
            alias["slug"]
            for entry in self.entries
            for alias in entry["aliases"]
        }
        self.assertEqual(len(self.tracks), 3)
        self.assertEqual(self.lessons, self.real_lessons)
        for lesson in self.lessons:
            self.assertTrue(
                set(lesson["categories"]).issubset(learn_glossary.DIFFICULTIES)
            )
            self.assertTrue(set(lesson["tags"]).issubset(learn_glossary.TRACKS))
            self.assertFalse(set(lesson["terms"]).intersection(aliases))
            for slug in set(lesson["terms"]).intersection(canonical):
                self.assertIn(lesson, self.related_lessons[slug])
        for article in self.research_articles:
            self.assertFalse(set(article["terms"]).intersection(aliases))
            for slug in set(article["terms"]).intersection(canonical):
                self.assertIn(article, self.related_research[slug])

    def test_source_glossary_links_use_root_or_canonical_fragments(self) -> None:
        href_pattern = re.compile(r'href=["\'](/glossary/[^"\']*)')
        source_paths = [
            *learn_glossary.LEARN_ROOT.rglob("*.qmd"),
            *learn_glossary.RESEARCH_ROOT.rglob("*.qmd"),
        ]
        for path in source_paths:
            for href in href_pattern.findall(path.read_text(encoding="utf-8")):
                suffix = href.removeprefix("/glossary/")
                self.assertTrue(
                    suffix == "" or suffix.startswith(("#", "?")),
                    f"{path.relative_to(ROOT)} uses obsolete glossary route {href}",
                )

    def test_cube_sequence_is_preserved_in_generated_track_index(self) -> None:
        self.assertEqual(
            [lesson["relative_path"] for lesson in self.cube_lessons[:2]],
            [
                "why-is-25-percent-the-basic-take-point.qmd",
                "what-the-cube-is-asking.qmd",
            ],
        )
        self.assertEqual(
            [lesson["cube-order"] for lesson in self.cube_lessons],
            list(range(1, len(self.cube_lessons) + 1)),
        )
        cube_index = (learn_glossary.CUBE_ROOT / "index.qmd").read_text(
            encoding="utf-8"
        )
        self.assertIn("learn-track-index: doubling-cube", cube_index)
        self.assertIn("{{< include _lesson-index.html >}}", cube_index)
        generated = (learn_glossary.CUBE_ROOT / "_lesson-index.html").read_text(
            encoding="utf-8"
        )
        self.assertTrue(
            generated.index(str(self.cube_lessons[0]["title"]))
            < generated.index(str(self.cube_lessons[1]["title"]))
        )
        self.assertNotIn("data-bs-filter-track", generated)
        self.assertEqual(
            set(
                re.findall(
                    r'data-bs-filter-term="([^"]+)"',
                    generated,
                )
            ),
            {
                str(slug)
                for lesson in self.cube_lessons
                for slug in lesson["terms"]
                if str(slug) in {str(entry["slug"]) for entry in self.entries}
            },
        )
        self.assertNotIn("No options yet", generated)

    def test_continuous_learn_manifest_matches_discovered_curriculum(self) -> None:
        manifest = json.loads(
            learn_glossary.GENERATED_LEARN_SEQUENCE_PATH.read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest, self.learn_sequence)
        self.assertEqual(manifest["schema_version"], 1)
        expected = [
            lesson["route"]
            for track in self.lesson_sections
            for lesson in track["lessons"]
        ]
        actual = [lesson["route"] for lesson in manifest["lessons"]]
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), len(set(actual)))
        self.assertTrue(
            learn_glossary.GENERATED_LEARN_SEQUENCE_PATH.read_text(
                encoding="utf-8"
            ).endswith("\n")
        )

    def test_continuous_learn_manifest_skips_empty_tracks_and_non_lessons(
        self,
    ) -> None:
        sequence_track_ids = {
            lesson["track_id"] for lesson in self.learn_sequence["lessons"]
        }
        expected_non_empty_track_ids = {
            track["id"] for track in self.lesson_sections if track["lessons"]
        }
        self.assertEqual(sequence_track_ids, expected_non_empty_track_ids)
        synthetic = [
            {
                **track,
                "lessons": (
                    []
                    if index == len(self.lesson_sections) - 1
                    else track["lessons"]
                ),
            }
            for index, track in enumerate(self.lesson_sections)
        ]
        synthetic_sequence = learn_glossary.build_learn_sequence(synthetic)
        self.assertNotIn(
            self.lesson_sections[-1]["id"],
            {
                lesson["track_id"]
                for lesson in synthetic_sequence["lessons"]
            },
        )
        routes = {lesson["route"] for lesson in self.learn_sequence["lessons"]}
        excluded = {
            "/learn/",
            "/glossary/",
            *[str(track["route"]) for track in self.lesson_sections],
        }
        self.assertTrue(routes.isdisjoint(excluded))
        self.assertFalse(
            any("/glossary/" in route for route in routes)
        )

    def test_continuous_learn_manifest_chain_and_route_styles(self) -> None:
        lessons = self.learn_sequence["lessons"]
        self.assertIsNone(lessons[0]["previous_route"])
        self.assertIsNone(lessons[-1]["next_route"])
        for index, lesson in enumerate(lessons):
            self.assertEqual(lesson["sequence_index"], index)
            self.assertEqual(
                lesson["previous_route"],
                lessons[index - 1]["route"] if index else None,
            )
            self.assertEqual(
                lesson["next_route"],
                lessons[index + 1]["route"]
                if index + 1 < len(lessons)
                else None,
            )
            self.assertEqual(
                lesson["next_starts_new_track"],
                bool(
                    index + 1 < len(lessons)
                    and lesson["track_id"] != lessons[index + 1]["track_id"]
                ),
            )
        self.assertTrue(any(lesson["route"].endswith("/") for lesson in lessons))
        self.assertTrue(
            any(lesson["route"].endswith(".html") for lesson in lessons)
        )
        self.assertTrue(any(
            lesson["next_starts_new_track"] for lesson in lessons
        ))

    def test_continuous_learn_manifest_rejects_duplicate_and_broken_routes(
        self,
    ) -> None:
        duplicate = {
            "schema_version": 1,
            "lessons": [
                {
                    "sequence_index": 0,
                    "route": "/learn/duplicate.html",
                    "previous_route": None,
                    "next_route": "/learn/duplicate.html",
                    "track_id": "one",
                    "next_starts_new_track": False,
                },
                {
                    "sequence_index": 1,
                    "route": "/learn/duplicate.html",
                    "previous_route": "/learn/duplicate.html",
                    "next_route": None,
                    "track_id": "one",
                    "next_starts_new_track": False,
                },
            ],
        }
        with self.assertRaisesRegex(
            learn_glossary.ValidationError,
            "duplicate lesson routes",
        ):
            learn_glossary.validate_learn_sequence(duplicate)

        broken = json.loads(json.dumps(self.learn_sequence))
        broken["lessons"][0]["next_route"] = "/learn/not-the-next-lesson.html"
        with self.assertRaisesRegex(
            learn_glossary.ValidationError,
            "broken next route",
        ):
            learn_glossary.validate_learn_sequence(broken)

    def test_removed_scrolling_fixtures_are_not_in_the_sequence(self) -> None:
        self.assertFalse((learn_glossary.LEARN_ROOT / "scrolling-test").exists())
        sequence_lessons = self.learn_sequence["lessons"]
        sequence_routes = [lesson["route"] for lesson in sequence_lessons]
        self.assertEqual(len(sequence_routes), len(set(sequence_routes)))
        self.assertFalse(
            any("/scrolling-test/" in str(route) for route in sequence_routes)
        )

        non_empty_tracks = [
            track for track in self.lesson_sections if track["lessons"]
        ]
        for index, track in enumerate(non_empty_tracks[:-1]):
            last = [
                lesson
                for lesson in sequence_lessons
                if lesson["track_id"] == track["id"]
            ][-1]
            next_track = non_empty_tracks[index + 1]
            first_next = next(
                lesson
                for lesson in sequence_lessons
                if lesson["track_id"] == next_track["id"]
            )
            self.assertEqual(last["next_route"], first_next["route"])
            self.assertTrue(last["next_starts_new_track"])
        self.assertIsNone(sequence_lessons[-1]["next_route"])

    def test_custom_404_source_contract(self) -> None:
        not_found_path = learn_glossary.SITE_ROOT / "404.qmd"
        self.assertTrue(not_found_path.exists())
        content = not_found_path.read_text(encoding="utf-8")
        self.assertIn('title: "Page closed out"', content)
        self.assertIn(
            "The page you're looking for doesn't exist, has moved, "
            "or suspiciously bounced off the board.",
            content,
        )
        for label, route in (
            ("Home", "/"),
            ("Learn", "/learn/"),
            ("Backgammon Glossary", "/glossary/"),
            ("Research", "/research/"),
        ):
            self.assertIn(f"[{label}]({route})", content)
        self.assertIn("toc: false", content)
        self.assertIn("sidebar: false", content)
        self.assertIn("search: false", content)
        self.assertNotRegex(
            content,
            r"(?i)(http-equiv\s*=\s*[\"']?refresh|window\.location|"
            r"location\.replace|github pages)",
        )

    def test_native_toc_expansion_and_exclusions(self) -> None:
        learn_metadata = (
            learn_glossary.LEARN_ROOT / "_metadata.yml"
        ).read_text(encoding="utf-8")
        research_metadata = (
            learn_glossary.RESEARCH_ROOT / "_metadata.yml"
        ).read_text(encoding="utf-8")
        self.assertRegex(
            learn_metadata,
            r"format:\s+html:\s+toc-expand: true",
        )
        self.assertRegex(
            research_metadata,
            r"format:\s+html:\s+toc-expand: true",
        )
        excluded = [
            learn_glossary.LEARN_ROOT / "index.qmd",
            learn_glossary.CUBE_ROOT / "index.qmd",
            learn_glossary.GLOSSARY_ROOT / "index.qmd",
            learn_glossary.RESEARCH_ROOT / "index.qmd",
            learn_glossary.SITE_ROOT / "404.qmd",
        ]
        for path in excluded:
            self.assertRegex(
                path.read_text(encoding="utf-8"),
                r"toc:\s*false",
                str(path.relative_to(ROOT)),
            )

        extension = (
            learn_glossary.SITE_ROOT
            / "_extensions"
            / "bs-research-taxonomy"
            / "bs-research-taxonomy.lua"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "initializeResearchToc",
            "setResearchTocExpanded",
            "bs-research-toc-toggle",
            'classList.toggle("collapse"',
        ):
            self.assertNotIn(forbidden, extension)
        for required in (
            "initializeResearchTaxonomyToggle",
            "bs-post-taxonomy-toggle",
            "bs-post-taxonomy--collapsed",
            "Hide article categories and tags",
            "Show article categories and tags",
            'toggle.textContent = collapsed ? "\\u25be" : "\\u25b4"',
            "window.scrollY > 32",
        ):
            self.assertIn(required, extension)

    def test_authoring_docs_describe_single_page_anchors_and_404(self) -> None:
        guide = (ROOT / "docs" / "authoring-guide.md").read_text(
            encoding="utf-8"
        )
        terms = learn_glossary.AUTHORING_TERMS_PATH.read_text(
            encoding="utf-8"
        )
        for required in (
            "## Single-Page Glossary",
            "/glossary/#prime",
            "Do not create a directory or page for an individual term",
            "site/404.qmd",
            "canonical `terms` metadata",
            "single curriculum sequence",
            "learn-track-index",
            "learn-order",
            "## Updates RSS",
            "published: true",
        ):
            self.assertIn(required, guide)
        self.assertIn("there are no standalone term routes", terms)
        self.assertEqual(terms.count("/glossary/#"), 12)

    def test_moved_analyzer_include_and_all_cube_includes_resolve(self) -> None:
        include_copies = list(
            learn_glossary.SITE_ROOT.rglob("analyzer-form.html")
        )
        self.assertEqual(
            include_copies,
            [learn_glossary.SITE_ROOT / "includes" / "analyzer-form.html"],
        )
        lesson_path = learn_glossary.CUBE_ROOT / "what-the-cube-is-asking.qmd"
        source = lesson_path.read_text(encoding="utf-8")
        includes = re.findall(r"\{\{< include ([^ >]+) >\}\}", source)
        self.assertEqual(
            includes,
            [
                "../../includes/analyzer-form.html",
                "../../includes/subscribe.html",
                "../../includes/report-problem.html",
            ],
        )
        for include in includes:
            resolved = (lesson_path.parent / include).resolve()
            self.assertTrue(
                resolved.is_relative_to(learn_glossary.SITE_ROOT.resolve())
            )
            self.assertTrue(resolved.is_file(), resolved)
        self.assertNotRegex(source, r"[A-Za-z]:\\")
        self.assertIn("data-bs-cube-decision", source)
        self.assertIn(
            'data-bs-fixture-src="/data/lesson-analysis-svg-mvp.json"',
            source,
        )
        self.assertIn("[Back to the cube overview](index.qmd)", source)
        self.assertNotIn("[Back to the cube overview](../index.qmd)", source)

    def test_cube_order_is_metadata_driven_and_consistent(self) -> None:
        required_prefix = [
            "why-is-25-percent-the-basic-take-point.qmd",
            "what-the-cube-is-asking.qmd",
        ]
        required_titles = [
            "Why Is 25% the Basic Take Point When a Double Is Offered?",
            "What the Cube Is Really Asking",
        ]
        self.assertEqual(
            [lesson["relative_path"] for lesson in self.cube_lessons[:2]],
            required_prefix,
        )
        self.assertEqual(
            [lesson["title"] for lesson in self.cube_lessons[:2]],
            required_titles,
        )
        self.assertEqual(
            [lesson["cube-order"] for lesson in self.cube_lessons],
            list(range(1, len(self.cube_lessons) + 1)),
        )

        navigation = learn_glossary.GENERATED_NAVIGATION_PATH.read_text(
            encoding="utf-8"
        )
        sidebar_paths = [
            f"learn/cube/{lesson['relative_path']}"
            for lesson in self.cube_lessons
        ]
        self.assertTrue(
            navigation.index(sidebar_paths[0]) < navigation.index(sidebar_paths[1])
        )
        for path in sidebar_paths:
            self.assertEqual(navigation.count(path), 1)

        cube_index = (learn_glossary.CUBE_ROOT / "index.qmd").read_text(
            encoding="utf-8"
        )
        self.assertIn("learn-track-order: 2", cube_index)
        for lesson in self.cube_lessons:
            lesson_source = lesson["path"].read_text(encoding="utf-8")
            self.assertEqual(lesson_source.count("cube-order:"), 0)
            self.assertEqual(lesson_source.count("learn-order:"), 1)

    def test_learn_catalogue_uses_sidebar_hierarchy_and_lesson_metadata(self) -> None:
        self.assertEqual(
            [section["title"] for section in self.lesson_sections],
            ["Start Here", "The Doubling Cube", "Opening Play Lab"],
        )
        catalogue = (
            learn_glossary.GENERATED_LESSON_CATALOGUE_PATH.read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(catalogue.count("data-bs-learn-item"), len(self.lessons))
        self.assertEqual(
            catalogue.count('class="bs-learn-catalogue-description"'),
            len(self.lessons),
        )
        self.assertNotRegex(
            catalogue,
            r'<details class="bs-learn-catalogue-description"[^>]*\sopen',
        )
        self.assertEqual(
            catalogue.count(
                '<details class="bs-learn-catalogue-section" '
                "data-bs-learn-group"
            ),
            3,
        )
        self.assertNotIn("bs-learn-track-number", catalogue)
        self.assertEqual(
            re.findall(
                r'<a class="bs-learn-catalogue-link"[^>]*>(\d+)\. ',
                catalogue,
            ),
            [
                str(index)
                for section in self.lesson_sections
                for index in range(1, len(section["lessons"]) + 1)
            ],
        )
        self.assertNotIn("bs-learn-catalogue-tag", catalogue)
        self.assertNotIn(">Description<", catalogue)
        self.assertIn("Difficulty Filter", catalogue)
        self.assertIn("Learning Track Filter", catalogue)
        self.assertIn("Term Filter", catalogue)
        self.assertIn(
            '<summary class="bs-learn-filters-summary">'
            "Click to search and filter lessons</summary>",
            catalogue,
        )
        self.assertNotRegex(
            catalogue,
            r'<details class="bs-learn-filter-panel"[^>]*\sopen',
        )
        self.assertIn("data-bs-filter-term", catalogue)
        self.assertEqual(catalogue.count("data-bs-learn-collapse-all"), 1)
        self.assertEqual(catalogue.count("data-bs-learn-expand-all"), 1)
        for lesson in self.lessons:
            self.assertIn(
                f'href="{lesson["route"]}">'
                f'{int(lesson["order"])}. {lesson["title"]}</a>',
                catalogue,
            )
            self.assertIn(str(lesson["description"]), catalogue)

        learn_index = (learn_glossary.LEARN_ROOT / "index.qmd").read_text(
            encoding="utf-8"
        )
        self.assertIn("{{< include _lesson-catalogue.html >}}", learn_index)
        for lesson in self.lessons:
            self.assertNotIn(str(lesson["relative_path"]), learn_index)

        navigation = learn_glossary.GENERATED_NAVIGATION_PATH.read_text(
            encoding="utf-8"
        )
        self.assertIn("Generated by scripts/learn_glossary.py", navigation)
        for lesson in self.lessons:
            self.assertIn(
                f'text: "{int(lesson["order"])}. {lesson["title"]}"',
                navigation,
            )
        for track in self.lesson_sections:
            self.assertIn(
                f'section: "{track["title"]}"',
                navigation,
            )
            self.assertNotIn(
                f'section: "{learn_glossary.roman_number(int(track["order"]))} ',
                navigation,
            )
            track_page = track["path"].read_text(encoding="utf-8")
            self.assertIn("{{< include _lesson-index.html >}}", track_page)
            generated_track = (
                track["path"].parent / "_lesson-index.html"
            ).read_text(encoding="utf-8")
            self.assertIn('data-bs-learn-mode="track"', generated_track)
            self.assertIn("Click to search and filter lessons", generated_track)
            self.assertIn("Term Filter", generated_track)
            self.assertNotIn("Learning Track Filter", generated_track)

    def test_lesson_finder_is_removed_and_track_links_target_learn(self) -> None:
        self.assertFalse(
            (learn_glossary.LEARN_ROOT / "lesson-finder" / "index.qmd").exists()
        )
        public_sources = [
            learn_glossary.SITE_ROOT / "_quarto.yml",
            learn_glossary.SITE_ROOT / "404.qmd",
            learn_glossary.LEARN_ROOT / "index.qmd",
            ROOT / "scripts" / "bs_post_render.py",
        ]
        for path in public_sources:
            self.assertNotIn(
                "lesson-finder",
                path.read_text(encoding="utf-8"),
                str(path.relative_to(ROOT)),
            )
        taxonomy_filter = (
            learn_glossary.SITE_ROOT
            / "_extensions"
            / "bs-learn-taxonomy"
            / "bs-learn-taxonomy.lua"
        ).read_text(encoding="utf-8")
        self.assertIn('href="/learn/?track=', taxonomy_filter)

    def test_track_landings_use_generated_difficulty_and_approved_term_filters(self) -> None:
        cube_index = (learn_glossary.CUBE_ROOT / "index.qmd").read_text(
            encoding="utf-8"
        )
        self.assertIn("term-lookup: false", cube_index)
        self.assertIn("lesson-taxonomy: false", cube_index)
        self.assertIn("{{< include _lesson-index.html >}}", cube_index)

        generated = (learn_glossary.CUBE_ROOT / "_lesson-index.html").read_text(
            encoding="utf-8"
        )
        difficulty_buttons = set(
            re.findall(r'data-bs-filter-difficulty="([^"]+)"', generated)
        )
        term_buttons = set(
            re.findall(r'data-bs-filter-term="([^"]+)"', generated)
        )
        cube_curriculum_lessons = [
            lesson
            for lesson in self.lessons
            if lesson["track_id"] == "doubling-cube"
        ]
        expected_difficulties = {
            str(value)
            for lesson in cube_curriculum_lessons
            for value in lesson["categories"]
        }
        expected_terms = {
            str(value)
            for lesson in cube_curriculum_lessons
            for value in lesson["terms"]
            if str(value) in {entry["slug"] for entry in self.entries}
        }
        self.assertEqual(difficulty_buttons, expected_difficulties)
        self.assertEqual(term_buttons, expected_terms)
        self.assertNotIn("data-bs-filter-track", generated)
        self.assertEqual(
            generated.count('aria-pressed="false"'),
            len(difficulty_buttons) + len(term_buttons),
        )

        taxonomy_filter = (
            learn_glossary.SITE_ROOT
            / "_extensions"
            / "bs-learn-taxonomy"
            / "bs-learn-taxonomy.lua"
        ).read_text(encoding="utf-8")
        self.assertIn('doc.meta["lesson-taxonomy"]', taxonomy_filter)
        self.assertIn('doc.meta["learn-track"]', taxonomy_filter)
        self.assertIn("== false", taxonomy_filter)

        lesson_source = (
            learn_glossary.CUBE_ROOT
            / "why-is-25-percent-the-basic-take-point.qmd"
        ).read_text(encoding="utf-8")
        research_source = (
            learn_glossary.RESEARCH_ROOT / "what-we-are-building.qmd"
        ).read_text(encoding="utf-8")
        self.assertNotIn("term-lookup: false", lesson_source)
        self.assertNotIn("term-lookup: false", research_source)

    def test_track_roman_is_omitted_and_lesson_arabic_numbering_is_generated(
        self,
    ) -> None:
        css = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.css"
        ).read_text(encoding="utf-8")
        self.assertFalse(
            (learn_glossary.LEARN_ROOT / "_lesson-listing.ejs.md").exists()
        )
        self.assertEqual(learn_glossary.roman_number(1), "I")
        self.assertEqual(learn_glossary.roman_number(3), "III")
        self.assertNotIn(".bs-learn-track-number", css)
        self.assertNotIn(".bs-learn-lesson-number", css)
        self.assertNotIn(
            ".bs-learn-catalogue-item + .bs-learn-catalogue-item",
            css,
        )
        for lesson in self.cube_lessons:
            self.assertNotRegex(str(lesson["title"]), r"^\d+\.\s")

    def test_rendered_validator_expects_unnumbered_track_headings(self) -> None:
        validator_source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn('track_title = str(track["title"])', validator_source)
        self.assertNotIn(
            'f"{roman_number(int(track[\'order\']))} {str(track[\'title\'])}"',
            validator_source,
        )

    def test_compact_site_lookup_data_is_public_safe_and_complete(self) -> None:
        lookup = json.loads(
            learn_glossary.GENERATED_LOOKUP_DATA_PATH.read_text(
                encoding="utf-8"
            )
        )
        entries = lookup["entries"]
        self.assertEqual(len(entries), 12)
        self.assertEqual(
            sum(len(entry["aliases"]) for entry in entries),
            3,
        )
        self.assertEqual(
            sum(len(entry["related_lessons"]) for entry in entries),
            sum(len(value) for value in self.related_lessons.values()),
        )
        self.assertTrue(all(entry["definition"] for entry in entries))
        learn_glossary.assert_no_forbidden_keys(lookup)
        learn_glossary.assert_no_forbidden_text(
            learn_glossary.GENERATED_LOOKUP_DATA_PATH.read_text(
                encoding="utf-8"
            ),
            "compact site lookup data",
        )

    def test_site_navigation_and_lookup_controls_contract(self) -> None:
        config = (learn_glossary.SITE_ROOT / "_quarto.yml").read_text(
            encoding="utf-8"
        )
        research = config.index("text: Research")
        glossary = config.index("text: Glossary")
        about = config.index("text: About")
        self.assertLess(research, glossary)
        self.assertLess(glossary, about)
        self.assertIn("href: glossary/index.qmd", config)
        learn_navigation = (
            learn_glossary.GENERATED_NAVIGATION_PATH.read_text(encoding="utf-8")
        )
        self.assertNotIn("Backgammon Glossary", learn_navigation)
        self.assertNotIn("glossary/index.qmd", learn_navigation)
        self.assertIn("assets/bs-glossary-lookup.json", config)
        self.assertIn("assets/bs-research-sequence.json", config)
        scripts_include = (
            learn_glossary.SITE_ROOT / "includes" / "bs-scripts.html"
        ).read_text(encoding="utf-8")
        self.assertIn("assets/bs-research-scroll.js", scripts_include)

        javascript = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.js"
        ).read_text(encoding="utf-8")
        for required in (
            "initializeMobileLessonBar",
            "initializeLearnLeftSidebarToggle",
            "bs-learn-left-sidebar-toggle",
            "Hide Learn table of contents",
            "Show Learn table of contents",
            "isMobileDrawerSwipe",
            "bs-mobile-tools-drawer",
            "bs-mobile-tools-edge",
            "Open table of contents and term search",
            'links.removeAttribute("id")',
            r"\u2190 Expand Lesson Index",
            r"Look Up a Term \u2192",
            "data-bs-site-back-to-top",
            "data-bs-toc-toggle",
            "data-bs-margin-sidebar-toggle",
            "bs-site-tools--sidebar",
            "bs-site-tools--editorial-dock",
            "bs-site-tools--floating",
            'aria-controls="bs-term-lookup-panel"',
            'aria-controls="quarto-margin-sidebar"',
            "Collapse term lookup",
            "Collapse TOC",
            "Expand TOC",
            "Collapse all right sidebar content",
            "Expand all right sidebar content",
            "bs-toc-collapsed",
            "bs-margin-sidebar-collapsed",
            "marginSidebar.appendChild(tools)",
            "const mountTocHeadingToggle = function",
            "const bindTocHeadingToggle = function",
            "toggle.dataset.bsTocToggleBound",
            "const boundTocHeadingToggles = new WeakSet()",
            "tocCloneObserver = new MutationObserver",
            "const tocCandidates = Array.from(document.querySelectorAll(\"#TOC\"));",
            "tocCandidates.find(tocHasHashLinks)",
            "marginSidebar.contains(candidate) && tocHasHashLinks(candidate)",
            '"#quarto-margin-sidebar:not(.quarto-sidebar-toggle-contents)"',
            '!candidate.closest(".quarto-sidebar-toggle-contents")',
            "isSamePageTocHref",
            "tocObserver = new MutationObserver",
            "inEditorialDock",
            "bs-research-index",
            "desktopCollapsed",
            "tocCollapsed",
            "marginSidebarCollapsed",
            "const preservePagePosition = function",
            "window.setTimeout(restore, 180)",
            "/assets/bs-glossary-lookup.json",
            "renderLookupResult",
            "related_lessons",
            "Go to glossary entry",
            "isMainSiteIndex",
            "lookupDisabled",
            'document.body.classList.contains("bs-learn-index")',
            'document.body.classList.contains("bs-learn-track-index")',
            'document.body.classList.contains("bs-analyze-page")',
            'document.body.classList.contains("bs-match-predictor-page")',
            'document.body.classList.contains(\n      "bs-glossary-index"',
            "(!glossarySearch || glossaryIndexPage)",
            "if (glossarySearch && !lookup)",
            "const updateGlossaryLookupForScroll = function",
            "let lastGlossaryScrollY = window.scrollY",
            "Math.abs(currentScrollY - lastGlossaryScrollY) > 4",
            "lastGlossaryScrollY = currentScrollY",
            "let desktopCollapsed = !refinedRightRailPage;",
            "window.scrollY <= window.innerHeight",
            'window.addEventListener("resize", updateBackToTop)',
        ):
            self.assertIn(required, javascript)
        close_lookup = javascript[
            javascript.index("    const closeLookup = function") :
            javascript.index("    const updateMarginSidebar = function")
        ]
        self.assertNotIn("if (inRefinedRightRail())", close_lookup)
        self.assertNotIn("Collapse <span aria-hidden", javascript)
        self.assertIn('aria-label="Open term lookup"', javascript)

        css = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.css"
        ).read_text(encoding="utf-8")
        catalogue_section_css = re.search(
            r"\.bs-learn-catalogue-section \{([^}]*)\}",
            css,
        )
        self.assertIsNotNone(catalogue_section_css)
        self.assertNotIn("border-top:", catalogue_section_css.group(1))
        self.assertNotIn("border-bottom:", catalogue_section_css.group(1))
        self.assertIn(
            ".bs-learn-filter[aria-pressed=\"true\"]:hover",
            css,
        )
        self.assertIn("color: var(--bs-ivory)", css)
        self.assertIn(
            ".bs-site-tools--floating .bs-term-lookup-close",
            css,
        )
        self.assertIn("position: absolute", css)
        self.assertIn("top: 0.75rem", css)
        self.assertIn("right: 0", css)
        self.assertIn(
            "body:is(.bs-learn-index, .bs-learn-track-index)"
            " .bs-learn-clear",
            css,
        )
        self.assertRegex(
            css,
            r"body:is\(\.bs-learn-index, \.bs-learn-track-index\)"
            r"\s+\.bs-learn-filter-disclosure \{\s+border-top: 0;",
        )
        self.assertRegex(
            css,
            r"\.bs-learn-filters-summary \{[^}]*"
            r"padding: 0\.35rem 0\.55rem;",
        )
        self.assertRegex(
            css,
            r"\.bs-learn-catalogue-link \{[^}]*"
            r"color: var\(--bs-text\);[^}]*"
            r"font-size: 1rem;[^}]*"
            r"font-weight: 400;[^}]*"
            r"line-height: 1\.15;",
        )
        self.assertRegex(
            css,
            r"\.bs-learn-track-heading \[data-bs-learn-group-count\] "
            r"\{[^}]*margin-left: 0\.35rem;",
        )
        self.assertRegex(
            css,
            r"body\.bs-glossary-index \.bs-site-tools--floating "
            r"\{[^}]*top: 5rem;[^}]*bottom: auto;",
        )
        self.assertRegex(
            css,
            r"\.bs-learn-catalogue-title-row \{[^}]*"
            r"grid-template-columns: minmax\(0, 1fr\);",
        )
        self.assertNotIn(
            "grid-template-columns: 1.4rem minmax(0, 1fr);",
            css,
        )
        self.assertRegex(
            css,
            r"body:is\(\.bs-learn-index, \.bs-learn-article\)"
            r"\s+#quarto-sidebar\s+\.sidebar-link \{[^}]*"
            r"line-height: 1\.15;",
        )
        self.assertRegex(
            css,
            r"body\.bs-learn-article #quarto-margin-sidebar \{[^}]*"
            r"width: clamp\(10rem, 16vw, 18rem\);[^}]*"
            r"min-width: clamp\(10rem, 16vw, 18rem\);",
        )
        self.assertRegex(
            css,
            r"body\.bs-engine-benchmark-page #quarto-margin-sidebar \{[^}]*"
            r"width: clamp\(10rem, 16vw, 18rem\);[^}]*"
            r"min-width: clamp\(10rem, 16vw, 18rem\);",
        )
        self.assertRegex(
            css,
            r"\.bs-site-tools--editorial-dock \{[^}]*"
            r"padding-top: 0;[^}]*border-top: 0;",
        )
        self.assertRegex(
            css,
            r"\.bs-site-tools--sidebar \.bs-term-lookup-reveal \{[^}]*"
            r"width: auto;[^}]*"
            r"background: var\(--bs-page-background\);[^}]*"
            r"color: var\(--bs-text-muted\);[^}]*"
            r"white-space: nowrap;",
        )
        self.assertRegex(
            css,
            r"body\.bs-glossary-index\s+"
            r"\.bs-site-tools--floating\s+"
            r"\.bs-term-lookup-reveal \{[^}]*"
            r"width: auto;[^}]*"
            r"padding-inline: 0\.45rem;[^}]*"
            r"background: var\(--bs-page-background\);[^}]*"
            r"color: var\(--bs-text-muted\);[^}]*"
            r"font-size: 0\.72rem;[^}]*"
            r"font-weight: 500;[^}]*"
            r"white-space: nowrap;",
        )
        self.assertRegex(
            css,
            r"\.bs-site-tools > \.bs-term-lookup-reveal \{[^}]*"
            r"width: 1\.45rem;[^}]*min-height: 1\.45rem;[^}]*"
            r"padding: 0;",
        )
        self.assertRegex(
            css,
            r"\.bs-site-tools > \.bs-site-back-to-top \{[^}]*"
            r"min-width: 8\.5rem;",
        )
        self.assertRegex(
            css,
            r"\.bs-site-tools--sidebar \.bs-site-back-to-top \{[^}]*"
            r"align-self: flex-end;[^}]*width: auto;[^}]*"
            r"min-width: 0;[^}]*min-height: 1\.45rem;[^}]*"
            r"color: var\(--bs-text-muted\);[^}]*"
            r"font-size: 0\.72rem;[^}]*font-weight: 500;",
        )
        self.assertRegex(
            css,
            r"body\.bs-analyze-page \.bs-site-tools--floating,[^}]*"
            r"left: calc\(50% \+ 26\.625rem\);",
        )
        self.assertRegex(
            css,
            r"\.bs-term-lookup-controls button \{[^}]*"
            r"background: var\(--bs-surface\);[^}]*"
            r"color: var\(--bs-link\);",
        )
        for required in (
            "#quarto-margin-sidebar > *",
            "opacity: 1 !important",
            "#quarto-margin-sidebar #TOC[data-toc-expanded] ul.collapse",
            "#quarto-toc-toggle",
            "display: none !important",
            "#quarto-margin-sidebar .bs-site-tools",
            ".bs-site-tools--sidebar .bs-term-lookup-reveal",
            ".bs-site-tools--sidebar .bs-toc-toggle",
            ".bs-site-tools--sidebar .bs-margin-sidebar-toggle",
            ".bs-site-tools--sidebar .bs-site-back-to-top",
            "#quarto-margin-sidebar.bs-margin-sidebar-collapsed",
            "#quarto-margin-sidebar.bs-toc-collapsed:not(.bs-refined-right-rail) #TOC",
            "> :not(.bs-margin-sidebar-toggle)",
            ".bs-site-tools--floating",
            ".bs-site-tools--editorial-dock",
            ".bs-term-lookup--floating",
            "z-index: 1060",
        ):
            self.assertIn(required, css)

    def test_mobile_brand_wraps_and_has_a_narrow_screen_fallback(self) -> None:
        css = (
            learn_glossary.SITE_ROOT / "assets" / "bs-shared.css"
        ).read_text(encoding="utf-8")
        for required in (
            ".navbar-brand-container > .navbar-brand-logo",
            "white-space: normal",
            ".quarto-secondary-nav .quarto-page-breadcrumbs",
            "@media (max-width: 350px)",
            'content: "BS"',
        ):
            self.assertIn(required, css)

    def test_desktop_site_scale_is_125_percent_without_changing_mobile(self) -> None:
        css = (
            learn_glossary.SITE_ROOT / "assets" / "bs-shared.css"
        ).read_text(encoding="utf-8")
        self.assertRegex(
            css,
            r"@media \(min-width: 992px\) \{\s*html \{\s*"
            r"font-size: 125%;\s*\}\s*body \{\s*"
            r"font-size: 21\.25px;",
        )

    def test_lesson_and_research_article_desktop_right_rail_contract(
        self,
    ) -> None:
        javascript = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.js"
        ).read_text(encoding="utf-8")
        for required in (
            "refinedRightRailPage",
            "engineBenchmarkPage",
            '? "Expand TOC"',
            ': "Collapse TOC"',
            "bs-research-article",
            "bs-lesson-track-content",
            'querySelectorAll("[data-bs-lesson-track-nav]")',
            "trackContent.hidden = tocCollapsed",
            "preservePagePosition(function ()",
            "bs-toc-heading-toggle",
            'tocHeadingToggle.setAttribute("aria-controls", tocLinks.id)',
            "const visiblyCollapsed =",
            'clickedToggle.getAttribute("aria-expanded") === "false"',
            '"Table of Contents \\u25be"',
            "bs-toc-toggle-divider",
            "placeTocHeadingToggleBeforeLinks",
            "toc.insertBefore(divider, tocLinks)",
            "updateLookupForScroll",
            "window.scrollY <= 32",
            "updateRightRailForScroll",
            "rightRailScrollCollapsed = currentScrollY > lastRightRailScrollY",
            "suppressRightRailAutoCollapse",
            '"bs-refined-right-rail-scroll-collapsed"',
            "lastRightRailScrollY = window.scrollY",
            "positionRefinedRightTools",
            "placeRefinedBackToTop",
            '"--bs-refined-tools-left"',
            '"--bs-refined-tools-width"',
            '"--bs-refined-tools-top"',
            "sidebarBounds.width * 3",
            '"--bs-refined-tools-right"',
            'backToTop.classList.toggle("bs-refined-back-to-top", refined)',
            "document.body.appendChild(backToTop)",
            "marginSidebar.getBoundingClientRect()",
            "document.documentElement.clientWidth",
            "Browse the full glossary",
            "marginSidebarToggle || backToTop",
            "inRefinedRightRail",
        ):
            self.assertIn(required, javascript)
        for removed in (
            "lookupPinnedOpen",
            "pinOpen",
            "preservePinned",
        ):
            self.assertNotIn(removed, javascript)
        self.assertNotIn("data.bsLessonTrackToggle", javascript)
        for required in (
            '<span aria-hidden="true">&larr;</span> Term Search',
            'toggle.textContent = active ? "\\u2192 Show Lessons" : "\\u2190 Hide"',
            '"bs-learn-left-sidebar-toggle--nav-hidden"',
            'pageHeader.classList.contains("headroom--unpinned")',
            "pageScrollingDown = currentScrollY > lastScrollY",
            'attributeFilter: ["class"]',
            'if ("ResizeObserver" in window)',
            ").observe(sidebar)",
            'sidebar.querySelector(".sidebar-menu-container") || sidebar',
            "const positionExpandedToggle = function",
            "if (!toggle.hidden && !collapsed)",
            "const updateVisibility = function",
            "const keepExpandedWhileScrolling =",
            "!keepExpandedWhileScrolling &&",
            "sidebarScroller.addEventListener",
            "let autoCollapsePending = window.scrollY <= 32",
            "if (!keepExpandedWhileScrolling && collapsed)",
            "collapsed = false",
            "lastScrollY = currentScrollY",
            "autoCollapsePending &&",
            "collapsed = true",
        ):
            self.assertIn(required, javascript)
        self.assertNotIn("initializeDistractionFreeMode", javascript)
        self.assertNotIn("bs-distraction-free", javascript)
        left_sidebar_toggle = javascript[
            javascript.index("  function initializeLearnLeftSidebarToggle") :
            javascript.index("  function findIdWithinRoot")
        ]
        self.assertEqual(
            left_sidebar_toggle.count("!keepExpandedWhileScrolling &&"),
            3,
        )
        glossary_scroll = javascript[
            javascript.index("    const updateGlossaryLookupForScroll") :
            javascript.index("    if (form && input && result)")
        ]
        self.assertIn("closeLookup();", glossary_scroll)
        self.assertNotIn("open({ focusInput: false });", glossary_scroll)

        css = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.css"
        ).read_text(encoding="utf-8")
        for required in (
            "body.bs-learn-article:not(.bs-learn-track-index)",
            "width: clamp(10rem, 16vw, 18rem)",
            "font-size: 0.78rem",
            ".bs-lesson-track-collapsed",
            ".bs-refined-right-rail.bs-toc-collapsed",
            ".bs-refined-right-rail-scroll-collapsed",
            "#TOC\n    > :not(.bs-toc-toggle-divider)",
            "> .bs-lesson-track-nav",
            ".bs-research-article",
            ".bs-toc-toggle-divider",
            ".bs-toc-heading-toggle",
            '.bs-toc-heading-toggle[aria-expanded="false"]',
            ":is(.bs-toc-toggle, .bs-margin-sidebar-toggle)",
            ".bs-term-lookup-close",
            ".bs-term-lookup-browse",
            "background: var(--bs-page-background)",
            "outline: 2px solid var(--bs-link-hover)",
            "@media (min-width: 992px)",
        ):
            self.assertIn(required, css)
        refined_lookup_heading = re.search(
            r"\.bs-term-lookup-heading \{([^}]*)\}",
            css[css.index("body:is(\n      .bs-research-article") :],
        )
        self.assertIsNotNone(refined_lookup_heading)
        self.assertIn(
            "justify-content: space-between",
            refined_lookup_heading.group(1),
        )
        self.assertIn("top: 0.9rem", css)
        self.assertGreaterEqual(css.count(".bs-engine-benchmark-page"), 18)
        self.assertRegex(
            css,
            r"body\.bs-engine-benchmark-page\s+"
            r"\.bs-toc-heading-toggle\[aria-expanded\] "
            r"\{[^}]*width: auto;[^}]*"
            r"white-space: nowrap;",
        )
        self.assertRegex(
            css,
            r"\.bs-site-tools--sidebar \{[^}]*"
            r"padding-top: 0\.15rem;[^}]*border-top: 0;",
        )
        self.assertIn(
            ".bs-refined-right-rail-scroll-collapsed\n"
            "    > :not(#TOC):not(.bs-site-tools)",
            css,
        )
        self.assertNotIn(
            ".bs-refined-right-rail-scroll-collapsed\n"
            "    .bs-term-lookup",
            css,
        )
        self.assertNotIn(".bs-lesson-track-toggle", css)
        self.assertNotIn(".bs-distraction-free-toggle", css)
        self.assertRegex(
            css,
            r"\.bs-toc-toggle-divider \{[^}]*"
            r"margin: 0\.3rem 0 0\.15rem;[^}]*\}",
        )
        self.assertIn(
            "sidebarRight - toggle.offsetWidth - 24",
            javascript,
        )
        self.assertRegex(
            css,
            r"\.bs-term-lookup-close \{[^}]*"
            r"display: inline-flex;[^}]*"
            r"width: 1\.35rem;[^}]*"
            r"padding: 0;",
        )
        self.assertRegex(
            css,
            r"\.bs-site-tools--sidebar \{[^}]*"
            r"position: fixed;[^}]*"
            r"top: var\(--bs-refined-tools-top, 8rem\);[^}]*"
            r"left: var\(--bs-refined-tools-left, auto\);[^}]*"
            r"width: var\(--bs-refined-tools-width,[^}]*"
            r"align-items: flex-end;",
        )
        self.assertRegex(
            css,
            r"\.bs-site-tools--sidebar\s+"
            r"\.bs-term-lookup \{[^}]*"
            r"position: static;[^}]*"
            r"width: calc\(100% / 3\);[^}]*"
            r"align-self: flex-end;",
        )
        self.assertRegex(
            css,
            r"\.bs-learn-left-sidebar-toggle--nav-hidden,[^}]*"
            r"#quarto-header\.headroom--unpinned[^}]*"
            r"top: 0\.5rem;",
        )
        self.assertRegex(
            css,
            r"\.bs-term-lookup-reveal \{[^}]*"
            r"align-self: flex-end;",
        )
        self.assertRegex(
            css,
            r"button\.bs-refined-back-to-top \{[^}]*"
            r"position: fixed;[^}]*"
            r"right: var\(--bs-refined-tools-right, 0\.75rem\);[^}]*"
            r"bottom: 1rem;",
        )

        learn_home = (learn_glossary.LEARN_ROOT / "index.qmd").read_text(
            encoding="utf-8"
        )
        cube_landing = (learn_glossary.CUBE_ROOT / "index.qmd").read_text(
            encoding="utf-8"
        )
        analyze = (
            learn_glossary.SITE_ROOT / "analyze" / "index.qmd"
        ).read_text(encoding="utf-8")
        self.assertNotIn("bs-learn-article", learn_home)
        self.assertIn("bs-learn-track-index", cube_landing)
        self.assertNotIn("bs-research-article", analyze)

    def test_mobile_articles_use_a_swipeable_left_page_tools_drawer(
        self,
    ) -> None:
        javascript = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.js"
        ).read_text(encoding="utf-8")
        self.assertIn("input.focus({ preventScroll: true });", javascript)
        self.assertIn(
            "if (input && focusInput && desktopQuery.matches)",
            javascript,
        )

        css = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.css"
        ).read_text(encoding="utf-8")
        for required in (
            "@media (max-width: 991.98px)",
            ".bs-mobile-tools-edge",
            "left: 0;",
            "width: 0.42rem;",
            ".bs-mobile-tools-drawer",
            "transform: translateX(-102%);",
            ".bs-mobile-tools-drawer--open",
            ".bs-mobile-tools-toc",
            ".bs-mobile-tools-drawer .bs-term-lookup",
            "[data-bs-site-term-toggle]",
            "display: none !important;",
            ".bs-mobile-term-toggle {\n    display: none;",
            "color: var(--bs-text-muted);",
        ):
            self.assertIn(required, css)
        self.assertNotIn("@keyframes bs-term-lookup-slide-in", css)

    def test_lookup_result_uses_full_definition(self) -> None:
        javascript = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.js"
        ).read_text(encoding="utf-8")
        lookup_renderer = javascript[
            javascript.index("  function renderLookupResult(") :
            javascript.index("  function initializeTermLookup()")
        ]
        self.assertIn(
            "definition.textContent = entry.definition;",
            lookup_renderer,
        )
        self.assertNotIn(
            "definition.textContent = entry.short_definition;",
            lookup_renderer,
        )

    def test_lookup_related_terms_replace_the_sidebar_result(self) -> None:
        javascript = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.js"
        ).read_text(encoding="utf-8")
        lookup_renderer = javascript[
            javascript.index("  function renderLookupResult(") :
            javascript.index("  function initializeTermLookup()")
        ]
        self.assertIn(
            'button.dataset.bsTermLookupRelated = related.slug;',
            lookup_renderer,
        )
        self.assertIn('button.type = "button";', lookup_renderer)
        self.assertIn(
            'fullEntry.textContent = "Go to glossary entry";',
            lookup_renderer,
        )
        self.assertNotIn("new Set(items.map", lookup_renderer)
        self.assertIn(
            'event.target.closest("[data-bs-term-lookup-related]")',
            javascript,
        )
        self.assertIn("detail: { slug: slug, focusResult: true }", javascript)
        self.assertIn('heading.focus({ preventScroll: true });', javascript)
        self.assertIn(
            "if (suppressRightRailAutoCollapse) {\n        return;\n      }",
            javascript,
        )
        open_by_slug = javascript[
            javascript.index(
                'document.addEventListener("bs:open-glossary-term"'
            ) :
            javascript.index(
                'const legacyBackToTop = document.querySelector('
            )
        ]
        self.assertIn("suppressRightRailAutoCollapse = true;", open_by_slug)
        self.assertIn("rightRailScrollCollapsed = false;", open_by_slug)
        self.assertIn("suppressRightRailAutoCollapse = false;", open_by_slug)

    def test_glossary_related_terms_use_the_page_term_lookup(self) -> None:
        javascript = (
            learn_glossary.SITE_ROOT / "assets" / "bs-glossary.js"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "detail: { slug: canonicalSlug, focusResult: true }",
            javascript,
        )
        self.assertIn(
            '"[data-bs-term-lookup-form]"',
            javascript,
        )
        self.assertIn("if (slug && !pageTermLookup)", javascript)

    def test_learn_client_initialization_is_idempotent(self) -> None:
        javascript = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.js"
        ).read_text(encoding="utf-8")
        initializer = javascript[
            javascript.index(
                'document.addEventListener("DOMContentLoaded", function () {'
            ) :
            javascript.index("      initializeLearnFilters();")
        ]
        self.assertIn(
            'document.documentElement.dataset.bsLearnInitialized === "true"',
            initializer,
        )
        self.assertIn(
            'document.documentElement.dataset.bsLearnInitialized = "true";',
            initializer,
        )
        self.assertEqual(
            javascript.count(
                'document.documentElement.dataset.bsLearnInitialized = "true";'
            ),
            1,
        )

    def test_update_toc_null_guard_contract(self) -> None:
        javascript = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.js"
        ).read_text(encoding="utf-8")
        update_toc = javascript[
            javascript.index("    const updateToc = function () {") :
            javascript.index("    const placeTools = function () {")
        ]

        guarded_legacy_toggle = (
            "        if (tocToggle) {\n"
            "          tocToggle.hidden = true;\n"
            "        }\n"
        )
        self.assertIn(guarded_legacy_toggle, update_toc)
        self.assertIn("      tocToggle.hidden = !available;", update_toc)

        guard_end = update_toc.index(guarded_legacy_toggle) + len(
            guarded_legacy_toggle
        )
        heading_update = update_toc.index(
            "        tocHeadingToggle.hidden = false;"
        )
        self.assertEqual(guard_end, heading_update)

        self.assertNotIn("document.createElement", update_toc)
        self.assertEqual(
            javascript.count(
                'tocHeadingToggle = document.createElement("button");'
            ),
            1,
        )

    def test_lesson_right_rail_card_joins_sidebar_stack_contract(self) -> None:
        javascript = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.js"
        ).read_text(encoding="utf-8")
        placement = javascript[
            javascript.index("  function placeLessonRightRailCards() {") :
            javascript.index("  function isMainSiteIndex() {")
        ]
        for required in (
            'document.body.classList.contains("bs-learn-article")',
            '!document.body.classList.contains("bs-learn-track-index")',
            '".column-margin .bs-right-rail-card"',
            'document.getElementById("quarto-margin-sidebar")',
            'window.matchMedia("(min-width: 992px)")',
            'margin: card.closest(".column-margin")',
            "sidebar.appendChild(placement.card);",
            "placement.margin.hidden = true;",
            "placement.margin.hidden = false;",
            'placement.card.classList.add("bs-right-rail-card--stacked")',
            'placement.card.classList.remove("bs-right-rail-card--stacked")',
        ):
            self.assertIn(required, placement)
        self.assertNotIn("bs-research-article", placement)
        self.assertNotIn("position", placement)
        self.assertLess(
            javascript.index("      placeLessonTrackLinks();"),
            javascript.index("      placeLessonRightRailCards();"),
        )

        css = (
            learn_glossary.SITE_ROOT / "assets" / "bs-learn.css"
        ).read_text(encoding="utf-8")
        self.assertRegex(
            css,
            r"body\.bs-learn-article:not\(\.bs-learn-track-index\)"
            r"\s+#quarto-margin-sidebar"
            r"\s+> \.bs-right-rail-card--stacked \{[^}]*"
            r"width: 100%;[^}]*"
            r"margin: 1rem 0 0;[^}]*"
            r"box-sizing: border-box;",
        )

    def test_lesson_embedded_html_is_explicitly_raw(self) -> None:
        lesson = (
            learn_glossary.CUBE_ROOT / "what-the-cube-is-asking.qmd"
        ).read_text(encoding="utf-8")
        for fragment_name in ("analyzer-form.html", "subscribe.html"):
            include_path = f"../../includes/{fragment_name}"
            self.assertIn(f"{{{{< include {include_path} >}}}}", lesson)

            fragment = (
                learn_glossary.SITE_ROOT / "includes" / fragment_name
            ).read_text(encoding="utf-8")
            self.assertTrue(fragment.startswith("```{=html}\n"))
            self.assertTrue(fragment.rstrip().endswith("\n```"))

    def test_learn_home_contains_only_generated_catalogue(self) -> None:
        source = (learn_glossary.LEARN_ROOT / "index.qmd").read_text(
            encoding="utf-8"
        )
        body = source.split("---", 2)[-1].strip()
        self.assertEqual(body, "{{< include _lesson-catalogue.html >}}")
        for removed in (
            "Come with a question",
            "Start with the Cube Lessons",
            "Look Up a Term",
            "How Each Lesson Works",
            "A Real Question",
            "A Board Position",
            "A Reusable Idea",
        ):
            self.assertNotIn(removed, source)

    def test_clean_glossary_canonical_and_sitemap_contract(self) -> None:
        source = (learn_glossary.GLOSSARY_ROOT / "index.qmd").read_text(
            encoding="utf-8"
        )
        clean_url = "https://backgammonsimplified.github.io/glossary/"
        self.assertIn(f'canonical-url: "{clean_url}"', source)
        self.assertNotIn("/glossary/index.html", source)
        generator = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn(f'"{clean_url}"', generator)
        self.assertNotIn(
            '"https://backgammonsimplified.github.io/glossary/index.html"',
            generator,
        )

    def test_combined_updates_feed_contract_and_footer(self) -> None:
        updates_path = learn_glossary.SITE_ROOT / "updates" / "index.qmd"
        self.assertTrue(updates_path.is_file())
        source = updates_path.read_text(encoding="utf-8")
        for required in (
            '"../learn/**/*.qmd"',
            '"../research/**/*.qmd"',
            '"../engine-benchmark/**/*.qmd"',
            "published: true",
            'sort: "date desc"',
            "feed:",
            'title: "Backgammon Simplified Updates"',
        ):
            self.assertIn(required, source)
        self.assertNotIn("../posts/", source)
        self.assertNotIn("../templates/", source)
        self.assertEqual(len(self.update_publications), 12)
        self.assertTrue(
            all(
                publication["publication_type"] == "Glossary"
                for publication in self.update_publications
            )
        )
        self.assertEqual(
            {publication["date"] for publication in self.update_publications},
            {"2026-07-30"},
        )
        self.assertIn(
            "/glossary/#10-in-the-zone",
            {
                publication["route"]
                for publication in self.update_publications
            },
        )
        self.assertIn("glossary definitions", source)
        generator = MODULE_PATH.read_text(encoding="utf-8")
        for guard in (
            "excluded_landings",
            'metadata.get("draft"',
            'metadata.get("hidden"',
            '{"draft", "planned"}',
            "date.fromisoformat",
        ):
            self.assertIn(guard, generator)

        config = (learn_glossary.SITE_ROOT / "_quarto.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("href: /updates/index.xml", config)
        self.assertNotIn("href: research/index.xml", config)

        private_dated = list((learn_glossary.SITE_ROOT / "posts").rglob("*.qmd"))
        self.assertGreater(len(private_dated), 0)
        for path in private_dated:
            private_source = path.read_text(encoding="utf-8")
            self.assertRegex(private_source, r"(?i)(private|fixture)")

    def test_pre_render_wrapper_preserves_full_and_incremental_policy(self) -> None:
        config = (learn_glossary.SITE_ROOT / "_quarto.yml").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            config,
            r"pre-render:\s*\n\s*-\s+python ../scripts/bs_pre_render\.py",
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            with (
                mock.patch.object(
                    bs_pre_render,
                    "invalidate_full_build_marker",
                    return_value=False,
                ),
                mock.patch.object(bs_pre_render, "run") as run,
            ):
                self.assertEqual(bs_pre_render.main(), 0)
                run.assert_called_once()
                command = run.call_args.args[0]
                self.assertIn("learn_glossary.py", " ".join(command))
                self.assertIn("validate", command)

        with mock.patch.dict(os.environ, {}, clear=True):
            with (
                mock.patch.object(
                    bs_pre_render,
                    "invalidate_full_build_marker",
                    return_value=False,
                ),
                mock.patch.object(
                    bs_pre_render,
                    "run",
                    side_effect=RuntimeError("Generated files are stale"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "Generated files are stale"):
                    bs_pre_render.main()

        with mock.patch.dict(
            os.environ,
            {"QUARTO_PROJECT_RENDER_ALL": "1"},
            clear=True,
        ):
            with (
                mock.patch.object(
                    bs_pre_render,
                    "invalidate_full_build_marker",
                    return_value=False,
                ),
                mock.patch.object(bs_pre_render, "run") as run,
            ):
                self.assertEqual(bs_pre_render.main(), 0)
                self.assertEqual(run.call_count, 2)
                commands = [call.args[0] for call in run.call_args_list]
                self.assertIn("learn_glossary.py", " ".join(commands[0]))
                self.assertIn("generate", commands[0])
                self.assertIn("run_social_pipeline.py", " ".join(commands[1]))

        with mock.patch.dict(
            os.environ,
            {
                "QUARTO_PROJECT_RENDER_ALL": "1",
                "BS_SKIP_SOCIAL_CARDS": "1",
            },
            clear=True,
        ):
            with (
                mock.patch.object(
                    bs_pre_render,
                    "invalidate_full_build_marker",
                    return_value=False,
                ),
                mock.patch.object(bs_pre_render, "run") as run,
            ):
                self.assertEqual(bs_pre_render.main(), 0)
                self.assertEqual(run.call_count, 1)
                self.assertIn(
                    "learn_glossary.py",
                    " ".join(run.call_args_list[0].args[0]),
                )

        preview_script = (
            learn_glossary.REPOSITORY_ROOT / "scripts" / "preview-site.sh"
        ).read_text(encoding="utf-8")
        for required in (
            "BS_SKIP_SOCIAL_CARDS=1",
            'PORT="${1:-8765}"',
            'kill -0 "${STATIC_SERVER_PID}"',
            '-m http.server "${PORT}"',
            "--directory site/_site",
            'trap cleanup EXIT',
            'quarto preview site',
            "--no-serve",
            "--no-browser",
            "--no-navigate",
        ):
            self.assertIn(required, preview_script)

        with writable_test_directory() as runtime:
            marker = runtime / ".bs-full-build.json"
            marker.write_text("stale", encoding="utf-8")
            self.assertTrue(bs_pre_render.invalidate_full_build_marker(marker))
            self.assertFalse(marker.exists())

    def test_same_tab_policy_preserves_download_mailto_and_tel_destinations(
        self,
    ) -> None:
        link_policy = (
            learn_glossary.SITE_ROOT
            / "_extensions"
            / "bs-link-policy"
            / "bs-link-policy.lua"
        ).read_text(encoding="utf-8")
        self.assertNotIn("link.target =", link_policy)
        self.assertNotIn("link.attributes.download =", link_policy)
        self.assertNotIn("link.attributes.href =", link_policy)
        self.assertNotIn("link.attributes.action =", link_policy)
        for representative in (
            '<a href="/files/guide.pdf" download>Download</a>',
            '<a href="mailto:hello@example.com">Email</a>',
            '<a href="tel:+14165550123">Call</a>',
        ):
            self.assertNotIn("target=", representative)

    def test_sitemap_clean_url_post_render_contract_is_narrow(self) -> None:
        config = (learn_glossary.SITE_ROOT / "_quarto.yml").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            config,
            r"post-render:\s*\n\s*-\s+python ../scripts/bs_post_render\.py",
        )
        unrelated = "https://backgammonsimplified.github.io/research/index.html"
        dirty = bs_post_render.GLOSSARY_INDEX_URL
        clean = bs_post_render.GLOSSARY_CANONICAL_URL
        source = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<urlset>\n"
            f"  <url><loc>{unrelated}</loc></url>\n"
            f"  <url><loc>{dirty}</loc></url>\n"
            "</urlset>\n"
        )
        normalized, changed = bs_post_render.normalized_glossary_sitemap_text(
            source
        )
        self.assertTrue(changed)
        self.assertIn(f"<loc>{clean}</loc>", normalized)
        self.assertNotIn(f"<loc>{dirty}</loc>", normalized)
        self.assertIn(f"<loc>{unrelated}</loc>", normalized)
        current, changed_again = (
            bs_post_render.normalized_glossary_sitemap_text(normalized)
        )
        self.assertFalse(changed_again)
        self.assertEqual(current, normalized)

        incremental = normalized.replace(
            "</urlset>",
            f"  <url><loc>{dirty}</loc><lastmod>new</lastmod></url>\n</urlset>",
        )
        repaired, repaired_changed = (
            bs_post_render.normalized_glossary_sitemap_text(incremental)
        )
        self.assertTrue(repaired_changed)
        self.assertEqual(repaired.count(f"<loc>{clean}</loc>"), 1)
        self.assertNotIn(f"<loc>{dirty}</loc>", repaired)
        self.assertIn("<lastmod>new</lastmod>", repaired)

    def test_post_render_404_and_footer_routes_are_clean_and_narrow(self) -> None:
        dirty_404 = (
            '<a href="/.">Home</a>'
            '<a href="/.\\learn/">Learn</a>'
            '<a href="/./glossary/">Glossary</a>'
            '<a href="/.\\research/">Research</a>'
            '<a href="/unrelated/">Unrelated</a>'
        )
        normalized_404, changed = bs_post_render.normalized_404_text(dirty_404)
        self.assertTrue(changed)
        for route in learn_glossary.NOT_FOUND_ROUTES:
            self.assertIn(f'href="{route}"', normalized_404)
        self.assertIn('href="/unrelated/"', normalized_404)

        dirty_footer = (
            '<main><a href="../../updates/index.xml">Body link</a></main>'
            '<footer><a href="..\\..\\updates/index.xml">RSS</a></footer>'
        )
        normalized_footer, footer_changed = (
            bs_post_render.normalized_footer_rss_text(dirty_footer)
        )
        self.assertTrue(footer_changed)
        self.assertIn(
            '<main><a href="../../updates/index.xml">Body link</a></main>',
            normalized_footer,
        )
        self.assertIn(
            '<footer><a href="/updates/index.xml">RSS</a></footer>',
            normalized_footer,
        )

    def test_post_render_preserves_legacy_glossary_queries_and_fragments(self) -> None:
        redirect = bs_post_render.legacy_glossary_redirect_text()
        self.assertIn('<meta name="robots" content="noindex, follow">', redirect)
        self.assertIn(
            '<link rel="canonical" '
            'href="https://backgammonsimplified.github.io/glossary/">',
            redirect,
        )
        self.assertIn('content="0; url=/glossary/"', redirect)
        self.assertIn(
            '"/glossary/" + window.location.search + window.location.hash',
            redirect,
        )

    def test_post_render_adds_full_glossary_definitions_to_rss_once(self) -> None:
        base_feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Backgammon Simplified Updates</title>
    <item>
      <title>Newer lesson</title>
      <link>https://backgammonsimplified.github.io/learn/newer.html</link>
      <pubDate>Fri, 31 Jul 2026 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
        records = bs_post_render.glossary_feed_records(self.data)
        self.assertEqual(len(records), 12)
        updated, changed = bs_post_render.augmented_updates_feed_text(
            base_feed,
            records,
        )
        self.assertTrue(changed)
        updated_again, changed_again = (
            bs_post_render.augmented_updates_feed_text(updated, records)
        )
        self.assertFalse(changed_again)
        self.assertEqual(updated_again, updated)

        root = bs_post_render.ElementTree.fromstring(updated)
        items = root.findall("./channel/item")
        self.assertEqual(len(items), 13)
        self.assertEqual(items[0].findtext("title"), "Newer lesson")
        glossary_items = [
            item
            for item in items
            if item.findtext("category") == "Glossary"
        ]
        self.assertEqual(len(glossary_items), 12)
        zone = next(
            item
            for item in glossary_items
            if item.findtext("title") == "Glossary: 10 in the Zone"
        )
        self.assertEqual(
            zone.findtext("link"),
            "https://backgammonsimplified.github.io/glossary/"
            "#10-in-the-zone",
        )
        self.assertIn(
            "Bringing two active builders down from the mid-point",
            zone.findtext("description", ""),
        )
        self.assertEqual(
            zone.findtext("pubDate"),
            "Thu, 30 Jul 2026 00:00:00 GMT",
        )
        encoded = zone.findtext(
            f"{{{bs_post_render.RSS_NAMESPACES['content']}}}encoded",
            "",
        )
        self.assertIn("<p>The zone is your side of the board", encoded)

    def test_rendered_validator_distinguishes_partial_and_missing_artifacts(
        self,
    ) -> None:
        with writable_test_directory() as output_root:
            with self.assertRaisesRegex(
                learn_glossary.ValidationError,
                "partial or has not completed a full site build",
            ):
                learn_glossary.validate_full_build_output(output_root)

            marker = output_root / learn_glossary.FULL_BUILD_MARKER_NAME
            page_publication.write_full_build_marker(marker)
            with self.assertRaisesRegex(
                learn_glossary.ValidationError,
                "site output is incomplete",
            ):
                learn_glossary.validate_full_build_output(output_root)

            for relative in learn_glossary.RENDERED_CORE_PATHS:
                path = output_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            learn_glossary.validate_full_build_output(output_root)

            with self.assertRaisesRegex(
                learn_glossary.ValidationError,
                "root 404.html is missing",
            ):
                learn_glossary.check_rendered(output_root)

            not_found = output_root / "404.html"
            not_found.write_text(
                "Page closed out suspiciously bounced off the board "
                + " ".join(
                    f'<a href="{route}">{route}</a>'
                    for route in learn_glossary.NOT_FOUND_ROUTES
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                learn_glossary.ValidationError,
                "Updates RSS feed is missing",
            ):
                learn_glossary.check_rendered(output_root)

            feed = output_root / "updates" / "index.xml"
            feed.write_text("<rss><channel /></rss>", encoding="utf-8")
            with self.assertRaisesRegex(
                learn_glossary.ValidationError,
                "sitemap.xml is missing",
            ):
                learn_glossary.check_rendered(output_root)

    def test_rendered_404_and_footer_diagnostics_are_specific(self) -> None:
        with self.assertRaisesRegex(
            learn_glossary.ValidationError,
            "404 links are malformed",
        ):
            learn_glossary.validate_rendered_404(
                "Page closed out suspiciously bounced off the board"
            )

        with writable_test_directory() as output_root:
            for relative in learn_glossary.RSS_FOOTER_REPRESENTATIVE_PATHS:
                path = output_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    '<footer><a href="../updates/index.xml">RSS</a></footer>',
                    encoding="utf-8",
                )
            with self.assertRaisesRegex(
                learn_glossary.ValidationError,
                "footer RSS mismatch",
            ):
                learn_glossary.validate_representative_rss_footers(output_root)

    def test_social_render_state_includes_os_identity_without_layout_changes(
        self,
    ) -> None:
        renderer = (
            ROOT
            / "social_generator"
            / "scripts"
            / "social"
            / "render_cards.py"
        ).read_text(encoding="utf-8")
        self.assertIn("import platform", renderer)
        self.assertIn('"render_platform": {', renderer)
        self.assertIn('"system": platform.system()', renderer)
        self.assertIn('"machine": platform.machine()', renderer)

    def test_validation_reports_single_page_counts(self) -> None:
        result = learn_glossary.validate_generated()
        self.assertEqual(result["source_entries"], 805)
        self.assertEqual(result["canonical_entries"], 12)
        self.assertEqual(result["alias_entries"], 3)
        self.assertEqual(result["canonical_anchors"], 12)
        self.assertEqual(result["standalone_term_pages"], 0)
        self.assertEqual(result["generated_files"], 10)
        self.assertEqual(result["continuous_lessons"], len(self.lessons))
        self.assertEqual(result["lesson_catalogue_sections"], 3)
        self.assertEqual(result["learn_tracks"], 3)
        self.assertEqual(result["lessons"], len(self.lessons))
        self.assertEqual(result["cube_lessons"], len(self.cube_lessons))
        self.assertEqual(result["updates_publications"], 12)
        self.assertEqual(
            result["related_lesson_links"],
            sum(len(value) for value in self.related_lessons.values()),
        )
        self.assertEqual(
            result["related_research_links"],
            sum(len(value) for value in self.related_research.values()),
        )


if __name__ == "__main__":
    unittest.main()
