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
        pp.validate_rendered_identity(updated, canonical)

    def test_related_content_hook_renders_reusable_visible_navigation(self) -> None:
        source = """<!doctype html><html><head>
<meta name="description" content="Benchmark methods">
</head><body><main><h1 class="title">Engine Benchmark</h1></main></body></html>"""
        route = "/engine-benchmark/index.html"
        config = pp.resolve_route_policy(self.policy, route)
        records = [
            {
                "route": "/engine-benchmark/sage-vs-gnu-stage1/index.html",
                "title": "Sage vs GNU: Stage 1",
            }
        ]
        updated, changed = pp.enriched_html_text(
            source,
            "index, follow",
            config,
            route,
            "https://backgammonsimplified.github.io",
            "Backgammon Simplified",
            records,
        )

        self.assertTrue(changed)
        self.assertIn('name="bs-related-content"', updated)
        self.assertIn('class="bs-publication-related"', updated)
        self.assertIn(
            'href="/engine-benchmark/sage-vs-gnu-stage1/index.html"',
            updated,
        )
        self.assertIn("Sage vs GNU: Stage 1", updated)

        reapplied, _ = pp.enriched_html_text(
            updated,
            "index, follow",
            config,
            route,
            "https://backgammonsimplified.github.io",
            "Backgammon Simplified",
            records,
        )
        self.assertEqual(reapplied.count('class="bs-publication-related"'), 1)

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
                "---\ntitle: Test\npublished: true\ndate: 2026-08-08\n---\n"
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
                "---\ntitle: Test\npublished: true\n---\nComplete.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "publication date"):
                pp.validate_page_policy(
                    policy, repo_root=root, research_source_path=None
                )

            source.write_text(
                "---\ntitle: Test\npublished: true\ndate: 2026-08-08\n---\n"
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

    def test_final_publication_pass_owns_full_build_marker(self) -> None:
        quarto = pp.yaml.safe_load(
            (pp.REPO_ROOT / "site" / "_quarto.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            quarto["project"]["post-render"][-1],
            "python ../scripts/page_publication.py apply",
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
