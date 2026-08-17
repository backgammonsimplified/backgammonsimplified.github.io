from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import page_publication as pp


class PagePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = pp.load_page_policy()
        pp.validate_page_policy(cls.policy)

    @staticmethod
    def page_json_ld(text: str) -> dict[str, object]:
        match = pp.JSON_LD_PATTERN.search(text)
        if match is None:
            raise AssertionError("Rendered page JSON-LD is missing")
        block = match.group(0)
        payload = block[block.index(">") + 1 : block.rindex("</script>")]
        graph = json.loads(payload)["@graph"]
        return graph[0]

    def test_controlled_page_type_and_status_values_reject_unknowns(self) -> None:
        invalid_type = copy.deepcopy(self.policy)
        invalid_type["routes"]["/learn/index.html"]["type"] = "unknown-type"
        with self.assertRaisesRegex(RuntimeError, "Unknown page type"):
            pp.validate_page_policy(
                invalid_type,
                repo_root=None,
                research_source_path=None,
            )

        invalid_status = copy.deepcopy(self.policy)
        invalid_status["routes"]["/learn/index.html"]["status"] = "unknown-status"
        with self.assertRaisesRegex(RuntimeError, "Unknown publication status"):
            pp.validate_page_policy(
                invalid_status,
                repo_root=None,
                research_source_path=None,
            )

    def test_development_and_production_indexing_are_page_aware(self) -> None:
        development = {"robots-meta": "noindex, follow"}
        production = {"robots-meta": "index, follow"}
        published = pp.resolve_route_policy(self.policy, "/learn/index.html")
        preliminary = pp.resolve_route_policy(
            self.policy,
            "/engine-benchmark/sage-vs-gnu-stage1/index.html",
        )

        self.assertEqual(
            pp.page_robots_meta("development", development, published),
            "noindex, follow",
        )
        self.assertEqual(
            pp.page_robots_meta("production", production, published),
            "index, follow",
        )
        self.assertEqual(
            pp.page_robots_meta("production", production, preliminary),
            "noindex, follow",
        )

    def test_fixture_routes_are_not_publishable_outputs(self) -> None:
        fixture = pp.resolve_route_policy(
            self.policy,
            "/posts/2026-07-site-update.html",
        )
        status = fixture["status_config"]
        self.assertEqual(fixture["status"], "fixture")
        self.assertIs(status["indexable"], False)
        self.assertIs(status["sitemap"], False)
        self.assertIs(status["rss"], False)

    def test_unregistered_routes_fail_closed_as_draft(self) -> None:
        unresolved = pp.resolve_route_policy(self.policy, "/unregistered.html")
        self.assertEqual(unresolved["status"], "draft")
        self.assertEqual(
            pp.page_robots_meta(
                "production",
                {"robots-meta": "index, follow"},
                unresolved,
            ),
            "noindex, follow",
        )

    def test_rendered_identity_and_breadcrumbs_share_one_url(self) -> None:
        source = """<!doctype html><html><head>
<meta name="description" content="A clear lesson">
<meta property="og:url" content="https://wrong.example/">
<link rel="canonical" href="https://wrong.example/">
</head><body><main><header id="title-block-header"><h1 class="title">Learn</h1></header></main></body></html>"""
        route = "/learn/index.html"
        config = pp.resolve_route_policy(self.policy, route)
        updated, changed = pp.enriched_html_text(
            source,
            "index, follow",
            config,
            route,
            "https://backgammonsimplified.github.io",
            "Backgammon Simplified",
        )
        canonical = "https://backgammonsimplified.github.io/learn/index.html"

        self.assertTrue(changed)
        self.assertIn(f'rel="canonical" href="{canonical}"', updated)
        self.assertIn(f'property="og:url" content="{canonical}"', updated)
        self.assertIn('"@type":"CollectionPage"', updated)
        self.assertIn('"@type":"BreadcrumbList"', updated)
        self.assertIn('class="bs-publication-breadcrumbs"', updated)
        page = self.page_json_ld(updated)
        for article_only in (
            "headline",
            "author",
            "publisher",
            "datePublished",
            "dateModified",
            "image",
        ):
            self.assertNotIn(article_only, page)
        pp.validate_rendered_identity(updated, canonical)

    def test_authored_json_ld_social_and_date_contracts(self) -> None:
        cases = (
            (
                "/learn/cube/why-is-25-percent-the-take-point.html",
                "Article",
                "why-is-25-percent-the-take-point",
                None,
            ),
            (
                "/research/sage-vs-gnu-additional-details.html",
                "Article",
                "sage-vs-gnu-additional-details",
                "2026-08-09",
            ),
            (
                "/engine-benchmark/sage-vs-gnu-stage1/index.html",
                "Report",
                "sage-vs-gnu-stage1",
                "2026-08-09",
            ),
        )
        for route, schema_type, slug, modified in cases:
            with self.subTest(route=route):
                policy = copy.deepcopy(self.policy)
                policy["routes"][route]["status"] = "published"
                config = pp.resolve_route_policy(policy, route)
                metadata: dict[str, object] = {
                    "author": "Marty Gale",
                    "published": True,
                    "date": "2026-08-08",
                }
                if modified is not None:
                    metadata["date-modified"] = modified
                source = """<!doctype html><html><head>
<meta name="description" content="A real authored description">
<meta property="og:type" content="website">
<meta property="og:image" content="https://backgammonsimplified.github.io/assets/social/generated/social-default.png">
<meta name="twitter:image" content="https://backgammonsimplified.github.io/assets/social/generated/social-default.png">
</head><body><main><header id="title-block-header"><h1 class="title">Authored headline</h1></header></main></body></html>"""
                updated, _ = pp.enriched_html_text(
                    source,
                    "index, follow, max-image-preview:large",
                    config,
                    route,
                    "https://backgammonsimplified.github.io",
                    "Backgammon Simplified",
                    metadata,
                )
                page = self.page_json_ld(updated)
                expected_image = (
                    "https://backgammonsimplified.github.io/"
                    f"assets/social/generated/social-{slug}.png"
                )
                self.assertEqual(page["@type"], schema_type)
                self.assertEqual(page["headline"], "Authored headline")
                self.assertEqual(
                    page["author"],
                    {
                        "@type": "Person",
                        "name": "Marty Gale",
                        "url": "https://backgammonsimplified.github.io/about.html",
                    },
                )
                self.assertEqual(
                    page["publisher"],
                    {
                        "@type": "Organization",
                        "name": "Backgammon Simplified",
                        "url": "https://backgammonsimplified.github.io/",
                    },
                )
                self.assertEqual(page["datePublished"], "2026-08-08")
                self.assertEqual(
                    page["dateModified"], modified or "2026-08-08"
                )
                self.assertEqual(page["image"], expected_image)
                self.assertEqual(updated.count('property="og:type" content="article"'), 1)
                self.assertEqual(updated.count(f'property="og:image" content="{expected_image}"'), 1)
                self.assertEqual(updated.count(f'name="twitter:image" content="{expected_image}"'), 1)
                self.assertIn(
                    'property="article:published_time" content="2026-08-08"',
                    updated,
                )
                if modified is not None:
                    self.assertIn('class="bs-publication-updated"', updated)
                    self.assertIn(f'datetime="{modified}"', updated)
                else:
                    self.assertNotIn('class="bs-publication-updated"', updated)

    def test_draft_and_preliminary_authored_pages_do_not_invent_dates(self) -> None:
        for route in (
            "/learn/cube/why-is-25-percent-the-take-point.html",
            "/research/sage-vs-gnu-additional-details.html",
            "/engine-benchmark/sage-vs-gnu-stage1/index.html",
        ):
            with self.subTest(route=route):
                config = pp.resolve_route_policy(self.policy, route)
                metadata = pp.source_front_matter(pp.REPO_ROOT / config["source"])
                updated, _ = pp.enriched_html_text(
                    '<html><head><meta name="description" content="Draft"></head>'
                    '<body><main><h1 class="title">Draft shape</h1></main></body></html>',
                    "noindex, follow",
                    config,
                    route,
                    "https://backgammonsimplified.github.io",
                    "Backgammon Simplified",
                    metadata,
                )
                page = self.page_json_ld(updated)
                self.assertNotIn("datePublished", page)
                self.assertNotIn("dateModified", page)
                self.assertNotIn("article:published_time", updated)
                self.assertNotIn("article:modified_time", updated)
                self.assertEqual(page["author"]["name"], "Marty Gale")
                self.assertTrue(str(page["image"]).endswith(".png"))

    def test_landing_fallback_social_image_is_preserved(self) -> None:
        fallback = (
            "https://backgammonsimplified.github.io/"
            "assets/social/generated/social-default.png"
        )
        config = pp.resolve_route_policy(self.policy, "/learn/index.html")
        updated, _ = pp.enriched_html_text(
            '<html><head><meta property="og:image" content="'
            + fallback
            + '"><meta name="twitter:image" content="'
            + fallback
            + '"></head><body><main><h1 class="title">Learn</h1></main></body></html>',
            "index, follow, max-image-preview:large",
            config,
            "/learn/index.html",
            "https://backgammonsimplified.github.io",
            "Backgammon Simplified",
        )
        self.assertIn(f'property="og:image" content="{fallback}"', updated)
        self.assertIn(f'name="twitter:image" content="{fallback}"', updated)
        self.assertNotIn("image", self.page_json_ld(updated))

    def test_preliminary_pages_are_excluded_from_sitemap(self) -> None:
        source = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://backgammonsimplified.github.io/index.html</loc></url>
  <url><loc>https://backgammonsimplified.github.io/learn/index.html</loc></url>
  <url><loc>https://backgammonsimplified.github.io/engine-benchmark/sage-vs-gnu-stage1/index.html</loc></url>
</urlset>
"""
        updated, changed, removed = pp.filtered_sitemap_text(
            source,
            self.policy,
            "https://backgammonsimplified.github.io",
        )

        self.assertTrue(changed)
        self.assertEqual(removed, 1)
        self.assertIn("https://backgammonsimplified.github.io/</loc>", updated)
        self.assertIn("/learn/index.html", updated)
        self.assertNotIn("sage-vs-gnu-stage1", updated)

    def test_rss_excludes_preliminary_and_uses_stable_authored_guid(self) -> None:
        policy = copy.deepcopy(self.policy)
        authored_route = "/learn/cube/why-is-25-percent-the-take-point.html"
        policy["routes"][authored_route]["status"] = "published"
        source = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item><title>Learn</title><link>https://backgammonsimplified.github.io/learn/cube/why-is-25-percent-the-take-point.html</link><guid>https://backgammonsimplified.github.io/learn/cube/why-is-25-percent-the-take-point.html</guid></item>
<item><title>Landing</title><link>https://backgammonsimplified.github.io/learn/index.html</link><guid>landing</guid></item>
<item><title>Preliminary</title><link>https://backgammonsimplified.github.io/engine-benchmark/sage-vs-gnu-stage1/index.html</link><guid>old</guid></item>
<item><title>Glossary</title><link>https://backgammonsimplified.github.io/glossary/#take</link><guid isPermaLink="true">https://backgammonsimplified.github.io/glossary/#take</guid></item>
</channel></rss>"""
        updated, changed, removed, stabilized = pp.filtered_updates_feed_text(
            source,
            policy,
            "https://backgammonsimplified.github.io",
        )

        self.assertTrue(changed)
        self.assertEqual(removed, 2)
        self.assertEqual(stabilized, 1)
        self.assertIn(
            "urn:backgammonsimplified:route:"
            "/learn/cube/why-is-25-percent-the-take-point.html",
            updated,
        )
        self.assertIn(
            "https://backgammonsimplified.github.io/glossary/#take",
            updated,
        )
        self.assertNotIn("sage-vs-gnu-stage1", updated)

    def test_unfinished_markers_ignore_comments_and_code(self) -> None:
        source = """Normal prose discussing a TODO list and work that is pending.
<!-- TODO private note -->
````markdown
TODO: example
[PENDING EXAMPLE]
````
TODO is also an ordinary subject when it has no marker colon.
- TODO: visible work
[PENDING FIGURE :: real]
"""
        self.assertEqual(
            pp.unfinished_markers(source),
            ["TODO", "[PENDING FIGURE :: real]"],
        )

    def test_published_source_with_author_marker_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "article.qmd"
            source.write_text(
                "---\ntitle: Test\nauthor: Marty Gale\npublished: true\n"
                "date: 2026-08-08\n---\n"
                "TODO: finish this page\n",
                encoding="utf-8",
            )
            invalid = copy.deepcopy(self.policy)
            invalid["routes"] = {
                "/article.html": {
                    "source": "article.qmd",
                    "type": "research-article",
                    "status": "published",
                }
            }
            with self.assertRaisesRegex(RuntimeError, "unresolved author marker"):
                pp.validate_page_policy(
                    invalid,
                    repo_root=root,
                    research_source_path=None,
                )

    def test_authored_published_switch_and_route_status_must_agree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "article.qmd"
            policy = copy.deepcopy(self.policy)
            policy["routes"] = {
                "/article.html": {
                    "source": "article.qmd",
                    "type": "research-article",
                    "status": "published",
                }
            }

            source.write_text("---\ntitle: Test\n---\nComplete.\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "published: true"):
                pp.validate_page_policy(
                    policy, repo_root=root, research_source_path=None
                )

            source.write_text(
                "---\ntitle: Test\nauthor: Marty Gale\npublished: true\n"
                "---\nComplete.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "publication date"):
                pp.validate_page_policy(
                    policy, repo_root=root, research_source_path=None
                )

            source.write_text(
                "---\ntitle: Test\nauthor: Marty Gale\npublished: true\n"
                "date: 2026-08-08\n---\n"
                "Complete.\n",
                encoding="utf-8",
            )
            pp.validate_page_policy(
                policy, repo_root=root, research_source_path=None
            )

            policy["routes"]["/article.html"]["status"] = "preliminary"
            with self.assertRaisesRegex(RuntimeError, "route status is preliminary"):
                pp.validate_page_policy(
                    policy, repo_root=root, research_source_path=None
                )

    def test_modified_date_cannot_precede_publication_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "article.qmd"
            source.write_text(
                "---\ntitle: Test\nauthor: Marty Gale\npublished: true\n"
                "date: 2026-08-08\ndate-modified: 2026-08-07\n---\n"
                "Complete.\n",
                encoding="utf-8",
            )
            invalid = copy.deepcopy(self.policy)
            invalid["routes"] = {
                "/article.html": {
                    "source": "article.qmd",
                    "type": "research-article",
                    "status": "published",
                }
            }
            with self.assertRaisesRegex(RuntimeError, "cannot be earlier"):
                pp.validate_page_policy(
                    invalid, repo_root=root, research_source_path=None
                )

    def test_final_publication_pass_owns_full_build_marker(self) -> None:
        quarto = pp.yaml.safe_load(
            (pp.REPO_ROOT / "site" / "_quarto.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            quarto["project"]["post-render"][-1],
            "bash ../scripts/project-python.sh ../scripts/page_publication.py apply",
        )

        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / ".bs-full-build.json"
            marker.write_text("stale", encoding="utf-8")
            with (
                mock.patch.object(pp, "FULL_BUILD_MARKER", marker),
                mock.patch.dict(os.environ, {"QUARTO_PROJECT_RENDER_ALL": "1"}),
                mock.patch.object(
                    pp,
                    "apply_page_publication",
                    side_effect=RuntimeError("final pass failed"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "final pass failed"):
                    pp.main(["page_publication.py", "apply"])
            self.assertFalse(marker.exists())

            results = {
                "changed_pages": 0,
                "validated_pages": 1,
                "sitemap_removed": 0,
                "rss_removed": 0,
                "rss_stabilized": 0,
                "categories_written": 0,
            }
            with (
                mock.patch.object(pp, "FULL_BUILD_MARKER", marker),
                mock.patch.dict(os.environ, {"QUARTO_PROJECT_RENDER_ALL": "1"}),
                mock.patch.object(pp, "apply_page_publication", return_value=results),
            ):
                self.assertEqual(pp.main(["page_publication.py", "apply"]), 0)
            self.assertEqual(
                json.loads(marker.read_text(encoding="utf-8")),
                {"complete_full_build": True, "schema": 1},
            )

    def test_404_remains_noindex_in_production(self) -> None:
        config = pp.resolve_route_policy(self.policy, "/404.html")
        self.assertEqual(config["status"], "error")
        self.assertEqual(
            pp.page_robots_meta(
                "production",
                {"robots-meta": "index, follow"},
                config,
            ),
            "noindex, follow",
        )

    def test_research_category_registry_matches_source_and_consumer(self) -> None:
        pp.validate_page_policy(self.policy)
        javascript = (
            pp.REPO_ROOT / "site" / "assets" / "bs-research-index.js"
        ).read_text(encoding="utf-8")
        self.assertIn("/assets/bs-research-categories.json", javascript)
        self.assertIn("verifyCategoryRegistry", javascript)


if __name__ == "__main__":
    unittest.main()
