from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts import bs_post_render
from scripts.publication_config import (
    LEGACY_DISPOSITIONS_PATH,
    PUBLICATION_PATH,
    load_legacy_dispositions,
    load_publication_identity,
    publication_mode,
)


ROOT = Path(__file__).resolve().parents[1]


class PublicationIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.publication = load_publication_identity()
        self.registry = load_legacy_dispositions(self.publication)

    def test_shared_identity_drives_quarto_metadata(self) -> None:
        source = yaml.safe_load(PUBLICATION_PATH.read_text(encoding="utf-8"))
        self.assertEqual(source["website"]["title"], "Backgammon Simplified")
        self.assertEqual(
            source["website"]["site-url"],
            "https://backgammonsimplified.github.io",
        )
        self.assertEqual(self.publication["acronym"], "BS")
        quarto = (ROOT / "site" / "_quarto.yml").read_text(encoding="utf-8")
        self.assertIn("- _publication.yml", quarto)
        self.assertNotRegex(quarto, r"(?m)^\s+(?:title|site-url):")

    def test_indexing_modes_are_explicit_and_default_to_development(self) -> None:
        mode, development = publication_mode(self.publication, {})
        self.assertEqual(mode, "development")
        self.assertEqual(development["robots-meta"], "noindex, follow")
        self.assertEqual(
            bs_post_render.robots_text(development),
            "User-agent: *\nAllow: /\n",
        )
        self.assertNotIn("Disallow:", bs_post_render.robots_text(development))

        mode, production = publication_mode(
            self.publication,
            {"BS_PUBLICATION_MODE": "production"},
        )
        self.assertEqual(mode, "production")
        self.assertEqual(
            production["robots-meta"],
            "index, follow, max-image-preview:large",
        )
        self.assertIn("Allow: /", bs_post_render.robots_text(production))
        self.assertIn(
            "Sitemap: https://backgammonsimplified.github.io/sitemap.xml",
            bs_post_render.robots_text(production),
        )

    def test_rendered_indexing_replaces_existing_policy(self) -> None:
        source = (
            '<!doctype html><html><head><meta name="robots" content="index">'
            '<link rel="canonical" href="https://backgammonsimplified.github.io/">'
            "</head><body></body></html>"
        )
        updated, changed = bs_post_render.indexed_html_text(
            source,
            "noindex, follow",
            "https://backgammonsimplified.github.io/",
        )
        self.assertTrue(changed)
        self.assertEqual(updated.count('name="robots"'), 1)
        self.assertEqual(updated.count('rel="canonical"'), 1)
        self.assertIn('content="noindex, follow"', updated)

    def test_legacy_registry_is_noncanonical_and_generates_route(self) -> None:
        old_origin = "https://backgammon-" + "made-simple.github.io"
        self.assertEqual(self.registry["hosts"][0]["origin"], old_origin)
        self.assertIs(self.registry["hosts"][0]["canonical"], False)
        route = self.registry["routes"][0]
        self.assertEqual(route["source"], "/learn/glossary/")
        self.assertEqual(route["target"], "/glossary/")
        self.assertIs(route["canonical"], False)
        redirect = bs_post_render.legacy_glossary_redirect_text()
        self.assertIn('content="noindex, follow"', redirect)
        self.assertIn(
            'rel="canonical" href="https://backgammonsimplified.github.io/glossary/"',
            redirect,
        )

    def test_source_tree_has_no_old_active_identity_or_namespace(self) -> None:
        paths = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8").split("\0")
        old_slug = "backgammon-" + "made-simple"
        old_compact = "backgammon" + "madesimple"
        old_acronym = "BM" + "S"
        path_pattern = re.compile(
            rf"(?i)(?:{re.escape(old_slug)}|{old_compact}|(?:^|[/_.-]){old_acronym}(?:[/_.-]|$))"
        )
        self.assertEqual([path for path in paths if path_pattern.search(path)], [])

        old_name = "Backgammon " + "Made Simple"
        content_pattern = re.compile(
            rf"(?i)(?:{re.escape(old_name)}|{re.escape(old_slug)}|{old_compact}|\b{old_acronym}\b|{old_acronym}_|_{old_acronym})"
        )
        exceptions = {
            LEGACY_DISPOSITIONS_PATH.relative_to(ROOT),
        }
        findings: dict[str, list[str]] = {}
        for relative in filter(None, paths):
            path = ROOT / relative
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            matches = [match.group(0) for match in content_pattern.finditer(text)]
            if matches and Path(relative) not in exceptions:
                findings[relative] = matches
        self.assertEqual(findings, {})

        registry = LEGACY_DISPOSITIONS_PATH.read_text(encoding="utf-8")
        self.assertEqual(registry.count(old_slug), 1)

    def test_release_builds_select_production_mode(self) -> None:
        server_release = (ROOT / "scripts" / "bs-build-and-publish.sh").read_text(
            encoding="utf-8"
        )
        windows_release = (ROOT / "scripts" / "windows-clean-release.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("export BS_PUBLICATION_MODE=production", server_release)
        self.assertIn("BS_PUBLICATION_MODE=production", windows_release)

    def test_sitemap_and_canonical_validators_reject_legacy_origin(self) -> None:
        old_origin = "https://backgammon-" + "made-simple.github.io"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "index.html"
            page.write_text(
                '<html><head><link rel="canonical" '
                f'href="{old_origin}/"></head></html>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "outside the canonical origin"):
                bs_post_render.validate_rendered_canonicals(root)


if __name__ == "__main__":
    unittest.main()
