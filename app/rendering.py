from __future__ import annotations

import bleach
from markdown_it import MarkdownIt


_markdown = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
_allowed_tags = {
    "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3", "h4",
    "hr", "li", "ol", "p", "pre", "strong", "table", "tbody", "td", "th",
    "thead", "tr", "ul",
}


def render_markdown(markdown: str) -> str:
    html = _markdown.render(markdown)
    return bleach.clean(
        html,
        tags=_allowed_tags,
        attributes={"a": ["href", "title"]},
        protocols={"http", "https"},
        strip=True,
    )
