"""Lesson loader.

Lessons are markdown files in content/, named NN-slug.md, with a small key:value
header. Keeping them as files means the lessons can be edited without touching
any Python - which matters, because the person who writes them is not
necessarily the person who deploys the site.
"""
from __future__ import annotations

import functools
import re
from pathlib import Path

import markdown

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"

_EXTENSIONS = [
    "extra",              # tables, footnotes, def lists
    "admonition",         # !!! note / !!! warning callouts
    "attr_list",
    "toc",
    "sane_lists",
    "pymdownx.superfences",
    "pymdownx.tilde",
    "pymdownx.caret",
]


def _parse(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = raw
    if raw.startswith("---"):
        _, header, body = raw.split("---", 2)
        for line in header.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    m = re.match(r"(\d+)-(.+)\.md$", path.name)
    number, slug = (m.group(1).lstrip("0") or "0", m.group(2)) if m else ("", path.stem)
    md = markdown.Markdown(extensions=_EXTENSIONS, output_format="html5")
    return {
        "number": meta.get("number", number),
        "slug": meta.get("slug", slug),
        "title": meta.get("title", slug.replace("-", " ").title()),
        "summary": meta.get("summary", ""),
        "time": meta.get("time", ""),
        "status": meta.get("status", "ready"),
        "html": md.convert(body),
        "toc": getattr(md, "toc", ""),
    }


@functools.lru_cache(maxsize=1)
def _all() -> list[dict]:
    if not CONTENT_DIR.exists():
        return []
    mods = [_parse(p) for p in sorted(CONTENT_DIR.glob("*.md"))]
    return sorted(mods, key=lambda m: int(m["number"]) if m["number"].isdigit() else 99)


def list_modules() -> list[dict]:
    return _all()


def get_module(slug: str) -> dict | None:
    for m in _all():
        if m["slug"] == slug or m["number"] == slug:
            return m
    return None


def reload() -> None:
    _all.cache_clear()
