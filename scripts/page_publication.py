from __future__ import annotations

import html
import json
import os
import re
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import yaml

try:
    from publication_config import (
        load_legacy_dispositions,
        load_publication_identity,
        publication_mode,
    )
except ModuleNotFoundError:  # Imported as scripts.page_publication in tests.
    from scripts.publication_config import (
        load_legacy_dispositions,
        load_publication_identity,
        publication_mode,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_PATH = REPO_ROOT / "site" / "_publication.yml"
OUTPUT_ROOT = REPO_ROOT / "site" / "_site"
SITEMAP_PATH = OUTPUT_ROOT / "sitemap.xml"
UPDATES_FEED_PATH = OUTPUT_ROOT / "updates" / "index.xml"
RESEARCH_SOURCE_PATH = REPO_ROOT / "site" / "research" / "index.qmd"
RESEARCH_CATEGORIES_PATH = OUTPUT_ROOT / "assets" / "bs-research-categories.json"
FULL_BUILD_MARKER = OUTPUT_ROOT / ".bs-full-build.json"
FULL_BUILD_MARKER_SCHEMA = 1

ROBOTS_META_PATTERN = re.compile(
    r'<meta\b[^>]*\bname=["\']robots["\'][^>]*>\s*',
    flags=re.IGNORECASE,
)
CANONICAL_LINK_PATTERN = re.compile(
    r'<link\b[^>]*\brel=["\']canonical["\'][^>]*>\s*',
    flags=re.IGNORECASE,
)
CANONICAL_HREF_PATTERN = re.compile(
    r'<link\b[^>]*\brel=["\']canonical["\'][^>]*\bhref=["\']([^"\']+)["\'][^>]*>',
    flags=re.IGNORECASE,
)
OG_URL_PATTERN = re.compile(
    r'<meta\b[^>]*\bproperty=["\']og:url["\'][^>]*>\s*',
    flags=re.IGNORECASE,
)
OG_URL_CONTENT_PATTERN = re.compile(
    r'<meta\b[^>]*\bproperty=["\']og:url["\'][^>]*\bcontent=["\']([^"\']+)["\'][^>]*>',
    flags=re.IGNORECASE,
)
DESCRIPTION_PATTERN = re.compile(
    r'<meta\b[^>]*\bname=["\']description["\'][^>]*\bcontent=["\']([^"\']*)["\'][^>]*>',
    flags=re.IGNORECASE,
)
TITLE_PATTERN = re.compile(
    r'<h1\b[^>]*\bclass=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>(.*?)</h1>',
    flags=re.IGNORECASE | re.DOTALL,
)
DOCUMENT_TITLE_PATTERN = re.compile(
    r"<title>(.*?)</title>", flags=re.IGNORECASE | re.DOTALL
)
TAG_PATTERN = re.compile(r"<[^>]+>")
JSON_LD_PATTERN = re.compile(
    r'<script\s+id=["\']bs-page-publication-jsonld["\'][^>]*>.*?</script>\s*',
    flags=re.IGNORECASE | re.DOTALL,
)
BREADCRUMB_PATTERN = re.compile(
    r'<nav\s+class=["\']bs-publication-breadcrumbs["\'][^>]*>.*?</nav>\s*',
    flags=re.IGNORECASE | re.DOTALL,
)
BREADCRUMB_STYLE_PATTERN = re.compile(
    r'<style\s+id=["\']bs-publication-breadcrumb-styles["\'][^>]*>.*?</style>\s*',
    flags=re.IGNORECASE | re.DOTALL,
)
RELATED_META_PATTERN = re.compile(
    r'<meta\b[^>]*\bname=["\']bs-related-content["\'][^>]*>\s*',
    flags=re.IGNORECASE,
)
RELATED_NAV_PATTERN = re.compile(
    r'<nav\s+class=["\']bs-publication-related["\'][^>]*>.*?</nav>\s*',
    flags=re.IGNORECASE | re.DOTALL,
)
RESEARCH_CATEGORY_PATTERN = re.compile(
    r'data-bs-filter-category=["\']([^"\']+)["\']'
)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", flags=re.DOTALL)
UNFINISHED_MARKER_PATTERN = re.compile(
    r"(?im)^[ \t]*(?:(?:[-*+] |\d+[.)] ))?"
    r"(?P<marker>TODO(?=\s*(?::|$))|\[PENDING[^\]\r\n]*\])"
)

BREADCRUMB_STYLE = """<style id="bs-publication-breadcrumb-styles">
.bs-publication-breadcrumbs{margin:.25rem 0 1rem;font-size:.82rem;color:var(--bs-text-muted,#68625a)}
.bs-publication-breadcrumbs ol{display:flex;flex-wrap:wrap;gap:.35rem;list-style:none;margin:0;padding:0}
.bs-publication-breadcrumbs li+li::before{content:"/";margin-right:.35rem;color:var(--bs-border-strong,#bcb4a7)}
.bs-publication-breadcrumbs a{color:inherit;text-underline-offset:.14em}
</style>
"""

RSS_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "media": "http://search.yahoo.com/mrss/",
}


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be a mapping")
    return value


def _nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{label} must be a non-empty string")
    return value.strip()


def load_page_policy(path: Path = PUBLICATION_PATH) -> dict[str, object]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RuntimeError(f"Could not load page publication policy: {path}") from error
    document = _mapping(document, str(path))
    publication = _mapping(document.get("bs-publication"), "bs-publication")
    pages = _mapping(publication.get("pages"), "bs-publication.pages")
    default = dict(_mapping(pages.get("default"), "bs-publication.pages.default"))
    types = dict(_mapping(pages.get("types"), "bs-publication.pages.types"))
    statuses = dict(_mapping(pages.get("statuses"), "bs-publication.pages.statuses"))
    routes = dict(_mapping(pages.get("routes"), "bs-publication.pages.routes"))
    research = _mapping(publication.get("research"), "bs-publication.research")
    categories = research.get("categories")
    if not isinstance(categories, list) or not categories:
        raise RuntimeError("bs-publication.research.categories must be a non-empty list")
    return {
        "default": default,
        "types": types,
        "statuses": statuses,
        "routes": routes,
        "research_categories": [
            _nonempty_string(value, f"research category {index}")
            for index, value in enumerate(categories)
        ],
    }


def strip_nonvisible_source(text: str) -> str:
    """Remove comments and fenced examples before checking author markers."""
    without_comments = HTML_COMMENT_PATTERN.sub("", text)
    visible_lines: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in without_comments.splitlines(keepends=True):
        fence = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
        if fence_character is None:
            if fence is not None:
                token = fence.group(1)
                fence_character = token[0]
                fence_length = len(token)
                continue
            visible_lines.append(line)
            continue
        if fence is not None:
            token = fence.group(1)
            if token[0] == fence_character and len(token) >= fence_length:
                fence_character = None
                fence_length = 0
        continue
    return "".join(visible_lines)


def unfinished_markers(text: str) -> list[str]:
    visible = strip_nonvisible_source(text)
    return [
        match.group("marker") for match in UNFINISHED_MARKER_PATTERN.finditer(visible)
    ]


def source_front_matter(path: Path) -> dict[str, object]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RuntimeError(f"Could not read publication source: {path}") from error
    if not lines or lines[0].strip() != "---":
        raise RuntimeError(f"Publication source has no YAML front matter: {path}")
    try:
        closing = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
        metadata = yaml.safe_load("\n".join(lines[1:closing]))
    except StopIteration as error:
        raise RuntimeError(
            f"Publication source has unterminated YAML front matter: {path}"
        ) from error
    except yaml.YAMLError as error:
        raise RuntimeError(
            f"Publication source has invalid YAML front matter: {path}"
        ) from error
    return dict(_mapping(metadata, f"front matter for {path}"))


def validate_authored_publication_metadata(
    metadata: Mapping[str, object],
    source: str,
    type_config: Mapping[str, object],
    status: str,
) -> None:
    published = metadata.get("published")
    if published is not None and not isinstance(published, bool):
        raise RuntimeError(f"Publication source {source} published must be boolean")

    updates_feed = type_config.get("updates-feed") is True
    if published is True and not updates_feed:
        raise RuntimeError(
            f"Landing/non-authored page {source} cannot set published: true"
        )
    if published is True and status != "published":
        raise RuntimeError(
            f"Publication source {source} sets published: true but route status is {status}"
        )
    if updates_feed and status == "published" and published is not True:
        raise RuntimeError(
            "Published authored page must explicitly set published: true: " + source
        )
    if published is not True:
        return

    raw_date = metadata.get("date")
    if isinstance(raw_date, str):
        try:
            date.fromisoformat(raw_date.strip())
        except ValueError as error:
            raise RuntimeError(
                f"Published authored page {source} has invalid ISO date: {raw_date!r}"
            ) from error
    elif not isinstance(raw_date, date):
        raise RuntimeError(
            f"Published authored page {source} requires a real ISO publication date"
        )


def validate_page_policy(
    policy: Mapping[str, object],
    repo_root: Path | None = REPO_ROOT,
    research_source_path: Path | None = RESEARCH_SOURCE_PATH,
) -> None:
    types = _mapping(policy.get("types"), "page policy types")
    statuses = _mapping(policy.get("statuses"), "page policy statuses")
    default = _mapping(policy.get("default"), "page policy default")
    routes = _mapping(policy.get("routes"), "page policy routes")
    categories = policy.get("research_categories")

    default_type = _nonempty_string(default.get("type"), "page policy default.type")
    default_status = _nonempty_string(
        default.get("status"), "page policy default.status"
    )
    if default_type not in types:
        raise RuntimeError(f"Unknown default page type: {default_type}")
    if default_status not in statuses:
        raise RuntimeError(f"Unknown default publication status: {default_status}")

    for type_name, raw_config in types.items():
        config = _mapping(raw_config, f"page type {type_name}")
        _nonempty_string(
            config.get("schema-type"), f"page type {type_name}.schema-type"
        )
        if not isinstance(config.get("updates-feed"), bool):
            raise RuntimeError(
                f"page type {type_name}.updates-feed must be boolean"
            )

    for status_name, raw_config in statuses.items():
        config = _mapping(raw_config, f"publication status {status_name}")
        for field in ("indexable", "sitemap", "rss"):
            if not isinstance(config.get(field), bool):
                raise RuntimeError(
                    f"publication status {status_name}.{field} must be boolean"
                )

    if not isinstance(categories, list) or not categories:
        raise RuntimeError("research_categories must be a non-empty list")
    if len(categories) != len(set(categories)):
        raise RuntimeError("research_categories must not contain duplicates")

    for route, raw_config in routes.items():
        if not isinstance(route, str) or not route.startswith("/"):
            raise RuntimeError(f"Publication route must be root-relative: {route!r}")
        config = _mapping(raw_config, f"publication route {route}")
        page_type = _nonempty_string(
            config.get("type"), f"publication route {route}.type"
        )
        status = _nonempty_string(
            config.get("status"), f"publication route {route}.status"
        )
        if page_type not in types:
            raise RuntimeError(f"Unknown page type for {route}: {page_type}")
        if status not in statuses:
            raise RuntimeError(f"Unknown publication status for {route}: {status}")

        parents = config.get("parents", [])
        if not isinstance(parents, list):
            raise RuntimeError(f"publication route {route}.parents must be a list")
        for index, raw_parent in enumerate(parents):
            parent = _mapping(
                raw_parent, f"publication route {route}.parents[{index}]"
            )
            _nonempty_string(
                parent.get("label"),
                f"publication route {route}.parents[{index}].label",
            )
            parent_route = _nonempty_string(
                parent.get("route"),
                f"publication route {route}.parents[{index}].route",
            )
            if not parent_route.startswith("/"):
                raise RuntimeError(
                    f"Breadcrumb route must be root-relative: {parent_route}"
                )

        related = config.get("related", [])
        if not isinstance(related, list):
            raise RuntimeError(f"publication route {route}.related must be a list")
        for index, related_route in enumerate(related):
            related_route = _nonempty_string(
                related_route, f"publication route {route}.related[{index}]"
            )
            if not related_route.startswith("/") or related_route == route:
                raise RuntimeError(
                    f"Invalid related-content route for {route}: {related_route}"
                )
            if related_route not in routes:
                raise RuntimeError(
                    f"Unknown related-content route for {route}: {related_route}"
                )

        source = config.get("source")
        if source is not None:
            source = _nonempty_string(source, f"publication route {route}.source")
            if repo_root is not None:
                source_path = repo_root / source
                if not source_path.exists():
                    raise RuntimeError(
                        f"Publication source is missing for {route}: {source}"
                    )
                metadata = source_front_matter(source_path)
                type_config = _mapping(types.get(page_type), f"page type {page_type}")
                validate_authored_publication_metadata(
                    metadata,
                    source,
                    type_config,
                    status,
                )
                if status == "published":
                    markers = unfinished_markers(
                        source_path.read_text(encoding="utf-8")
                    )
                    if markers:
                        preview = ", ".join(markers[:3])
                        raise RuntimeError(
                            "Published page contains unresolved author marker(s): "
                            f"{source}: {preview}"
                        )

    if research_source_path is not None and research_source_path.exists():
        found = RESEARCH_CATEGORY_PATTERN.findall(
            research_source_path.read_text(encoding="utf-8")
        )
        if found != list(categories):
            raise RuntimeError(
                "Research category controls differ from "
                "bs-publication.research.categories: "
                f"source={found!r}, registry={list(categories)!r}"
            )


def resolve_route_policy(
    policy: Mapping[str, object], route: str
) -> dict[str, object]:
    default = dict(_mapping(policy.get("default"), "page policy default"))
    routes = _mapping(policy.get("routes"), "page policy routes")
    override = routes.get(route)
    if override is not None:
        default.update(_mapping(override, f"publication route {route}"))
    if route == "/404.html":
        default["status"] = "error"
    page_type = _nonempty_string(
        default.get("type"), f"resolved page {route}.type"
    )
    status = _nonempty_string(
        default.get("status"), f"resolved page {route}.status"
    )
    types = _mapping(policy.get("types"), "page policy types")
    statuses = _mapping(policy.get("statuses"), "page policy statuses")
    default["schema_type"] = _nonempty_string(
        _mapping(types.get(page_type), f"page type {page_type}").get("schema-type"),
        f"page type {page_type}.schema-type",
    )
    default["type_config"] = dict(
        _mapping(types.get(page_type), f"page type {page_type}")
    )
    default["status_config"] = dict(
        _mapping(statuses.get(status), f"publication status {status}")
    )
    return default


def route_for_rendered_path(path: Path, output_root: Path = OUTPUT_ROOT) -> str:
    relative = path.relative_to(output_root).as_posix()
    if relative == "index.html":
        return "/"
    if relative == "glossary/index.html":
        return "/glossary/"
    return "/" + relative


def canonical_url(route: str, canonical_origin: str) -> str:
    return canonical_origin.rstrip("/") + route


def route_from_public_url(url: str, canonical_origin: str) -> str | None:
    origin = urlparse(canonical_origin)
    parsed = urlparse(url)
    if parsed.scheme != origin.scheme or parsed.netloc != origin.netloc:
        return None
    route = parsed.path or "/"
    if route == "/index.html":
        route = "/"
    elif route == "/glossary/index.html":
        route = "/glossary/"
    return route


def page_robots_meta(
    mode: str,
    mode_config: Mapping[str, object],
    route_config: Mapping[str, object],
) -> str:
    status_config = _mapping(
        route_config.get("status_config"), "resolved status config"
    )
    if mode != "production" or status_config.get("indexable") is not True:
        return "noindex, follow"
    return _nonempty_string(mode_config.get("robots-meta"), "mode robots-meta")


def _plain_text(value: str) -> str:
    return html.unescape(TAG_PATTERN.sub("", value)).strip()


def rendered_title(text: str) -> str:
    match = TITLE_PATTERN.search(text) or DOCUMENT_TITLE_PATTERN.search(text)
    if match is None:
        return "Backgammon Simplified"
    title = _plain_text(match.group(1))
    if " - " in title:
        title = title.split(" - ", 1)[0].strip()
    return title or "Backgammon Simplified"


def rendered_description(text: str) -> str | None:
    match = DESCRIPTION_PATTERN.search(text)
    if match is None:
        return None
    value = html.unescape(match.group(1)).strip()
    return value or None


def breadcrumb_records(
    route_config: Mapping[str, object],
    title: str,
    route: str,
    canonical_origin: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    parents = route_config.get("parents", [])
    if not isinstance(parents, list) or not parents:
        return records
    for position, raw_parent in enumerate(parents, start=1):
        parent = _mapping(raw_parent, f"breadcrumb parent {position}")
        parent_route = _nonempty_string(parent.get("route"), "breadcrumb route")
        records.append(
            {
                "position": position,
                "name": _nonempty_string(parent.get("label"), "breadcrumb label"),
                "item": canonical_url(parent_route, canonical_origin),
            }
        )
    records.append(
        {
            "position": len(records) + 1,
            "name": title,
            "item": canonical_url(route, canonical_origin),
        }
    )
    return records


def breadcrumb_html(records: list[dict[str, object]]) -> str:
    if not records:
        return ""
    items: list[str] = []
    for index, record in enumerate(records):
        label = html.escape(str(record["name"]))
        url = html.escape(str(record["item"]), quote=True)
        if index == len(records) - 1:
            items.append(f'<li aria-current="page">{label}</li>')
        else:
            items.append(f'<li><a href="{url}">{label}</a></li>')
    return (
        '<nav class="bs-publication-breadcrumbs" aria-label="Breadcrumb">'
        + "<ol>"
        + "".join(items)
        + "</ol></nav>\n"
    )


def related_navigation_html(records: list[dict[str, str]]) -> str:
    if not records:
        return ""
    items = "".join(
        '<li><a href="'
        + html.escape(record["route"], quote=True)
        + '">'
        + html.escape(record["title"])
        + "</a></li>"
        for record in records
    )
    return (
        '<nav class="bs-publication-related" aria-labelledby="bs-related-content-title">'
        '<h2 id="bs-related-content-title">Related content</h2>'
        + "<ul>"
        + items
        + "</ul></nav>\n"
    )


def registered_route_titles(
    policy: Mapping[str, object], repo_root: Path = REPO_ROOT
) -> dict[str, str]:
    titles: dict[str, str] = {}
    routes = _mapping(policy.get("routes"), "page policy routes")
    for route, raw_config in routes.items():
        config = _mapping(raw_config, f"publication route {route}")
        source = config.get("source")
        if not isinstance(source, str) or not source.strip():
            continue
        metadata = source_front_matter(repo_root / source)
        title = metadata.get("title")
        if isinstance(title, str) and title.strip():
            titles[str(route)] = title.strip()
    return titles


def page_json_ld(
    route_config: Mapping[str, object],
    title: str,
    description: str | None,
    route: str,
    canonical_origin: str,
    site_name: str,
    breadcrumbs: list[dict[str, object]],
) -> str:
    page_url = canonical_url(route, canonical_origin)
    page: dict[str, object] = {
        "@type": _nonempty_string(
            route_config.get("schema_type"), "resolved schema type"
        ),
        "@id": page_url + "#page",
        "name": title,
        "url": page_url,
        "isPartOf": {
            "@type": "WebSite",
            "@id": canonical_origin.rstrip("/") + "/#website",
            "name": site_name,
            "url": canonical_origin.rstrip("/") + "/",
        },
    }
    if description:
        page["description"] = description
    graph: list[dict[str, object]] = [page]
    if breadcrumbs:
        breadcrumb_id = page_url + "#breadcrumb"
        page["breadcrumb"] = {"@id": breadcrumb_id}
        graph.append(
            {
                "@type": "BreadcrumbList",
                "@id": breadcrumb_id,
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": record["position"],
                        "name": record["name"],
                        "item": record["item"],
                    }
                    for record in breadcrumbs
                ],
            }
        )
    payload = {"@context": "https://schema.org", "@graph": graph}
    return (
        '<script id="bs-page-publication-jsonld" type="application/ld+json">'
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "</script>\n"
    )


def enriched_html_text(
    text: str,
    robots_meta: str,
    route_config: Mapping[str, object],
    route: str,
    canonical_origin: str,
    site_name: str,
    related_records: list[dict[str, str]] | None = None,
) -> tuple[str, bool]:
    canonical = canonical_url(route, canonical_origin)
    title = rendered_title(text)
    description = rendered_description(text)
    breadcrumbs = breadcrumb_records(
        route_config, title, route, canonical_origin
    )

    updated = ROBOTS_META_PATTERN.sub("", text)
    updated = CANONICAL_LINK_PATTERN.sub("", updated)
    updated = OG_URL_PATTERN.sub("", updated)
    updated = JSON_LD_PATTERN.sub("", updated)
    updated = BREADCRUMB_PATTERN.sub("", updated)
    updated = BREADCRUMB_STYLE_PATTERN.sub("", updated)
    updated = RELATED_META_PATTERN.sub("", updated)
    updated = RELATED_NAV_PATTERN.sub("", updated)

    head = (
        f'<meta name="robots" content="{html.escape(robots_meta, quote=True)}">\n'
        f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">\n'
        f'<meta property="og:url" content="{html.escape(canonical, quote=True)}">\n'
    )
    related = route_config.get("related", [])
    if isinstance(related, list) and related:
        related_json = json.dumps(related, separators=(",", ":"))
        head += (
            '<meta name="bs-related-content" content="'
            + html.escape(related_json, quote=True)
            + '">\n'
        )
    if breadcrumbs:
        head += BREADCRUMB_STYLE
    head += page_json_ld(
        route_config,
        title,
        description,
        route,
        canonical_origin,
        site_name,
        breadcrumbs,
    )

    if "</head>" not in updated.lower():
        raise RuntimeError("Rendered HTML has no closing head element")
    updated, count = re.subn(
        r"</head>",
        head + "</head>",
        updated,
        count=1,
        flags=re.IGNORECASE,
    )
    if count != 1:
        raise RuntimeError("Could not apply page publication metadata")

    navigation = breadcrumb_html(breadcrumbs)
    if navigation:
        if re.search(
            r'<header\b[^>]*\bid=["\']title-block-header["\']',
            updated,
            re.IGNORECASE,
        ):
            updated, count = re.subn(
                r'(<header\b[^>]*\bid=["\']title-block-header["\'][^>]*>)',
                navigation + r"\1",
                updated,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            updated, count = re.subn(
                r"(<main\b[^>]*>)",
                r"\1\n" + navigation,
                updated,
                count=1,
                flags=re.IGNORECASE,
            )
        if count != 1:
            raise RuntimeError("Could not insert visible page breadcrumbs")
    related_navigation = related_navigation_html(related_records or [])
    if related_navigation:
        updated, count = re.subn(
            r"</main>",
            related_navigation + "</main>",
            updated,
            count=1,
            flags=re.IGNORECASE,
        )
        if count != 1:
            raise RuntimeError("Could not insert visible related-content navigation")
    return updated, updated != text


def filtered_sitemap_text(
    text: str,
    policy: Mapping[str, object],
    canonical_origin: str,
) -> tuple[str, bool, int]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as error:
        raise RuntimeError("Rendered sitemap is invalid XML") from error
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ElementTree.register_namespace("", namespace)
    removed = 0
    for url_element in list(root):
        location = next(
            (
                (child.text or "").strip()
                for child in url_element
                if child.tag.rsplit("}", 1)[-1] == "loc"
            ),
            "",
        )
        route = route_from_public_url(location, canonical_origin)
        if route is None:
            continue
        for child in url_element:
            if child.tag.rsplit("}", 1)[-1] == "loc":
                child.text = canonical_url(route, canonical_origin)
                break
        route_config = resolve_route_policy(policy, route)
        status_config = _mapping(
            route_config.get("status_config"), "resolved status"
        )
        if status_config.get("sitemap") is True:
            continue
        root.remove(url_element)
        removed += 1
    ElementTree.indent(root, space="  ")
    updated = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ElementTree.tostring(
            root, encoding="unicode", short_empty_elements=True
        )
        + "\n"
    )
    return updated, updated != text, removed


def stable_rss_guid(route: str) -> str:
    return "urn:backgammonsimplified:route:" + route


def filtered_updates_feed_text(
    text: str,
    policy: Mapping[str, object],
    canonical_origin: str,
) -> tuple[str, bool, int, int]:
    for prefix, namespace in RSS_NAMESPACES.items():
        ElementTree.register_namespace(prefix, namespace)
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as error:
        raise RuntimeError("Updates RSS feed is invalid XML") from error
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("Updates RSS feed has no channel")

    glossary_prefix = canonical_origin.rstrip("/") + "/glossary/#"
    removed = 0
    stabilized = 0
    for item in list(channel.findall("item")):
        link = (item.findtext("link") or "").strip()
        if link.startswith(glossary_prefix):
            continue
        route = route_from_public_url(link, canonical_origin)
        if route is None:
            continue
        route_config = resolve_route_policy(policy, route)
        status_config = _mapping(
            route_config.get("status_config"), "resolved status"
        )
        type_config = _mapping(route_config.get("type_config"), "resolved page type")
        if (
            status_config.get("rss") is not True
            or type_config.get("updates-feed") is not True
        ):
            channel.remove(item)
            removed += 1
            continue
        guid = item.find("guid")
        if guid is None:
            guid = ElementTree.SubElement(item, "guid")
        guid.set("isPermaLink", "false")
        stable = stable_rss_guid(route)
        if guid.text != stable:
            guid.text = stable
            stabilized += 1

    ElementTree.indent(root, space="  ")
    updated = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ElementTree.tostring(
            root, encoding="unicode", short_empty_elements=True
        )
        + "\n"
    )
    return updated, updated != text, removed, stabilized


def write_research_categories(
    categories: list[str],
    path: Path = RESEARCH_CATEGORIES_PATH,
) -> bool:
    payload = {"schema": 1, "categories": categories}
    content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def invalidate_full_build_marker(path: Path = FULL_BUILD_MARKER) -> bool:
    if not path.exists():
        return False
    path.unlink()
    return True


def write_full_build_marker(path: Path = FULL_BUILD_MARKER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": FULL_BUILD_MARKER_SCHEMA,
        "complete_full_build": True,
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def validate_rendered_identity(text: str, canonical: str) -> None:
    canonical_match = CANONICAL_HREF_PATTERN.search(text)
    og_match = OG_URL_CONTENT_PATTERN.search(text)
    if canonical_match is None or canonical_match.group(1) != canonical:
        raise RuntimeError(
            f"Rendered canonical does not match resolved URL: {canonical}"
        )
    if og_match is None or og_match.group(1) != canonical:
        raise RuntimeError(
            f"Rendered Open Graph URL does not match resolved URL: {canonical}"
        )
    json_match = JSON_LD_PATTERN.search(text)
    if json_match is None or canonical not in json_match.group(0):
        raise RuntimeError(
            f"Rendered JSON-LD does not include resolved URL: {canonical}"
        )


def apply_page_publication(
    policy: Mapping[str, object],
    output_root: Path = OUTPUT_ROOT,
    sitemap_path: Path = SITEMAP_PATH,
    feed_path: Path = UPDATES_FEED_PATH,
    categories_path: Path = RESEARCH_CATEGORIES_PATH,
) -> dict[str, int]:
    publication = load_publication_identity()
    legacy = load_legacy_dispositions(publication)
    mode, mode_config = publication_mode(publication)
    canonical_origin = str(publication["canonical-origin"])
    site_name = str(publication["name"])

    if not output_root.exists():
        raise RuntimeError(f"Rendered output is missing: {output_root}")
    legacy_paths = {
        (
            output_root
            / str(route["source"]).strip("/")
            / "index.html"
        ).resolve()
        for route in legacy["routes"]
    }
    rendered_pages: list[tuple[Path, str, str]] = []
    route_titles = registered_route_titles(policy)
    for path in sorted(output_root.rglob("*.html")):
        if path.resolve() in legacy_paths:
            continue
        route = route_for_rendered_path(path, output_root)
        current = path.read_text(encoding="utf-8")
        rendered_pages.append((path, route, current))
        route_titles.setdefault(route, rendered_title(current))

    changed_pages = 0
    validated_pages = 0
    for path, route, current in rendered_pages:
        route_config = resolve_route_policy(policy, route)
        robots_meta = page_robots_meta(mode, mode_config, route_config)
        related_records: list[dict[str, str]] = []
        related_routes = route_config.get("related", [])
        if isinstance(related_routes, list):
            for related_route in related_routes:
                if not isinstance(related_route, str):
                    continue
                related_title = route_titles.get(related_route)
                if related_title is None:
                    raise RuntimeError(
                        f"Rendered related-content target is missing: {related_route}"
                    )
                related_records.append(
                    {"route": related_route, "title": related_title}
                )
        updated, changed = enriched_html_text(
            current,
            robots_meta,
            route_config,
            route,
            canonical_origin,
            site_name,
            related_records,
        )
        if changed:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed_pages += 1
        validate_rendered_identity(
            updated, canonical_url(route, canonical_origin)
        )
        validated_pages += 1

    sitemap_removed = 0
    if sitemap_path.exists():
        current = sitemap_path.read_text(encoding="utf-8")
        updated, changed, sitemap_removed = filtered_sitemap_text(
            current, policy, canonical_origin
        )
        if changed:
            sitemap_path.write_text(updated, encoding="utf-8", newline="\n")

    rss_removed = 0
    rss_stabilized = 0
    if feed_path.exists():
        current = feed_path.read_text(encoding="utf-8")
        updated, changed, rss_removed, rss_stabilized = (
            filtered_updates_feed_text(current, policy, canonical_origin)
        )
        if changed:
            feed_path.write_text(updated, encoding="utf-8", newline="\n")

    categories = policy.get("research_categories")
    if not isinstance(categories, list):
        raise RuntimeError("research_categories must be a list")
    categories_changed = write_research_categories(categories, categories_path)
    return {
        "changed_pages": changed_pages,
        "validated_pages": validated_pages,
        "sitemap_removed": sitemap_removed,
        "rss_removed": rss_removed,
        "rss_stabilized": rss_stabilized,
        "categories_written": int(categories_changed),
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    command = argv[1] if len(argv) > 1 else "apply"
    full_build = os.getenv("QUARTO_PROJECT_RENDER_ALL") == "1"
    if full_build and invalidate_full_build_marker(FULL_BUILD_MARKER):
        print("Invalidated the previous full-build completion marker.")
    policy = load_page_policy()
    validate_page_policy(policy)

    if command == "validate-source":
        routes = _mapping(policy["routes"], "routes")
        categories = policy["research_categories"]
        if not isinstance(categories, list):
            raise RuntimeError("research_categories must be a list")
        print(
            "Page publication source validation passed: "
            f"{len(routes)} controlled routes, "
            f"{len(categories)} research categories."
        )
        return 0
    if command != "apply":
        raise RuntimeError(f"Unsupported page publication command: {command}")

    results = apply_page_publication(policy)
    print(
        "Page-aware publication applied: "
        f"{results['changed_pages']} HTML page(s) changed, "
        f"{results['validated_pages']} identity checks, "
        f"{results['sitemap_removed']} sitemap URL(s) removed, "
        f"{results['rss_removed']} RSS item(s) removed, "
        f"{results['rss_stabilized']} RSS GUID(s) stabilized."
    )
    if full_build:
        write_full_build_marker(FULL_BUILD_MARKER)
        print(f"Recorded complete full build: {FULL_BUILD_MARKER}")
    else:
        print("Partial render: no full-build completion marker recorded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
