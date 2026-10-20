"""Focused reference selectors and the reference inline budget.

Ported rule for rule from Seed-Engine 2026.10.11-stable:

- `seed_engine/utils/markdown_sections.py` — heading scan, slugs, fences, line
  ranges, anchor-then-slug resolution;
- `seed_engine/workflows/resolver.py` `load_references` — the inline budget
  (`REFERENCE_INLINE_ITEM_MAX_CHARS`, `REFERENCE_INLINE_TOTAL_MAX_CHARS`);
- `seed_engine/github/contract.py` `_MD_LINK_RE` — `## References` links.

The TypeScript twin is `shared/src/authoring/markdown-selectors.ts`; both are
held to `shared/src/authoring/corpus/markdown-selectors.json`. Python's own
`\\w`, `\\d`, `\\s`, `strip()` and `int()` are the engine's, so the regexes are
the engine's verbatim. Stdlib only.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

MARKDOWN_SUFFIXES = (".md", ".markdown")
REFERENCE_INLINE_ITEM_MAX_CHARS = 32_000
REFERENCE_INLINE_TOTAL_MAX_CHARS = 64_000

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_INLINE_ANCHOR_RE = re.compile(r'\s*<a\s+id="[^"]*"\s*>\s*</a>\s*')
_ANCHOR_ID_RE = re.compile(r'<a\s+id="([^"]*)"\s*>\s*</a>')
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_LINE_RANGE_RE = re.compile(r"^L(\d+)(?:-L(\d+))?$")
_MD_LINK_RE = re.compile(r"\[(?:[^\]]*)\]\((?P<url>[^)]+)\)")
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
# seed_engine/github/contract.py (2026.10.16-stable): a list line carrying one
# bare URL, and a permalink into a GitHub repository file at a fixed commit.
_BARE_URL_LINE_RE = re.compile(r"^\s*[-*+]\s+(?P<url>https?://\S+)\s*$")
_PERMALINK_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/blob/"
    r"(?P<sha>[0-9a-f]{7,40})/(?P<path>[^#?]+)(?:\?plain=1)?(?:#(?P<fragment>.+))?$"
)


def extract_reference_entries(section_body: str, repo_slug: str | None = None) -> list[tuple[str, str | None]]:
    """`(reference, sha)` for each `## References` entry, in order.

    The engine's `parse_reference_links`: a repo-relative Markdown link passes
    through unpinned (`sha` None); a permalink into `repo_slug` (bare on a list
    line or inside a Markdown link; owner/repo compared case-insensitively)
    projects to its URL-decoded `path#fragment`, pinned at its lowercase sha.
    Any other URL — another host, another repository, or every permalink when
    `repo_slug` is None — is skipped.
    """
    own = (repo_slug or "").strip().lower()
    out: list[tuple[str, str | None]] = []
    for raw in section_body.splitlines():
        line = raw.rstrip()
        if _ANY_HEADING_RE.match(line):
            break
        bare = _BARE_URL_LINE_RE.match(line)
        urls = [bare.group("url")] if bare else [m.group("url") for m in _MD_LINK_RE.finditer(line)]
        for url in urls:
            if not (url.startswith("http://") or url.startswith("https://")):
                out.append((url, None))
                continue
            permalink = _PERMALINK_RE.match(url)
            if permalink is None or not own:
                continue
            if f"{permalink.group('owner')}/{permalink.group('repo')}".lower() != own:
                continue
            path = unquote(permalink.group("path"))
            fragment = permalink.group("fragment")
            out.append((f"{path}#{fragment}" if fragment else path, permalink.group("sha").lower()))
    return out


def extract_reference_links(section_body: str, repo_slug: str | None = None) -> list[str]:
    """Link targets of a `## References` section body, in order.

    Relative targets as written; same-repository permalinks projected to
    `path#fragment` (see `extract_reference_entries`); other URLs skipped.
    """
    return [reference for reference, _sha in extract_reference_entries(section_body, repo_slug)]


def split_reference(reference: str) -> tuple[str, str | None]:
    raw = str(reference or "").strip()
    path_part, _sep, fragment_part = raw.partition("#")
    return path_part.strip(), fragment_part.strip() or None


def is_markdown_path(path: str) -> bool:
    return path.lower().endswith(MARKDOWN_SUFFIXES)


def classify_fragment(path: str, fragment: str | None) -> str:
    if fragment is None:
        return "none"
    if _LINE_RANGE_RE.match(fragment):
        return "line_range"
    return "markdown" if is_markdown_path(path) else "non_markdown"


def slugify(heading_text: str) -> str:
    s = heading_text.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s.strip("-")


def fenced_line_mask(lines: Sequence[str]) -> list[bool]:
    mask = [False] * len(lines)
    fence_char = ""
    fence_len = 0
    for i, line in enumerate(lines):
        if fence_char:
            mask[i] = True
            m = _FENCE_OPEN_RE.match(line)
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len and not m.group(2).strip():
                fence_char = ""
                fence_len = 0
            continue
        m = _FENCE_OPEN_RE.match(line)
        if not m:
            continue
        marker, info = m.group(1), m.group(2)
        if marker[0] == "`" and "`" in info:
            continue
        fence_char = marker[0]
        fence_len = len(marker)
        mask[i] = True
    return mask


@dataclass(frozen=True)
class Heading:
    line_index: int
    level: int
    text: str
    slug: str
    anchor_ids: tuple[str, ...]


def scan_headings(text: str) -> list[Heading]:
    lines = text.split("\n")
    fenced = fenced_line_mask(lines)
    occurrences: dict[str, int] = {}
    headings: list[Heading] = []
    for i, line in enumerate(lines):
        if fenced[i]:
            continue
        m = _HEADING_RE.match(line)
        if not m:
            continue
        raw = m.group(2)
        heading_text = _INLINE_ANCHOR_RE.sub(" ", raw).strip()
        base = slugify(heading_text)
        slug = base
        while slug in occurrences:
            occurrences[base] += 1
            slug = f"{base}-{occurrences[base]}"
        occurrences[slug] = 0
        headings.append(Heading(i, len(m.group(1)), heading_text, slug, tuple(_ANCHOR_ID_RE.findall(raw))))
    return headings


def heading_slugs(text: str) -> list[str]:
    return [h.slug for h in scan_headings(text)]


# ── The guide-section Validate detector (issue #2195) ──────────────────────
#
# Seed-Engine's `guide_section_text` / `section_has_validate_block` /
# `validate_section_for_pointer` (`seed_engine/utils/blocker_registry.py`,
# seed-engine#407); the TypeScript twin is `shared/src/authoring/
# validate-block.ts`, and both are held to `corpus/validate-block.json`.

VALIDATE_MARKER = "**Validate:**"
BOOTSTRAP_GUIDE_PATH = ".seed-engine/docs/bootstrap-guide.md"


def guide_section_text(guide_text: str, anchor: str) -> tuple[str, str] | None:
    """`(heading, section)` for an `<a id>` anchor (else a heading slug), up to the next `## ` line."""
    wanted = anchor.strip()
    if not wanted or not guide_text:
        return None
    headings = scan_headings(guide_text)
    match = next((h for h in headings if wanted in h.anchor_ids), None)
    if match is None:
        match = next((h for h in headings if h.slug == wanted), None)
    if match is None:
        return None
    lines = guide_text.split("\n")
    end = next((i for i in range(match.line_index + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return match.text, "\n".join(lines[match.line_index : end])


def section_has_validate_block(section: str) -> bool:
    """True when any line, after leading whitespace, starts with `**Validate:**`."""
    return any(line.lstrip().startswith(VALIDATE_MARKER) for line in section.split("\n"))


def extract_validate_block(section: str) -> dict[str, str | None] | None:
    """The first Validate line's prose and the fenced command block right after it."""
    lines = section.split("\n")
    at = next((i for i, line in enumerate(lines) if line.lstrip().startswith(VALIDATE_MARKER)), None)
    if at is None:
        return None
    rest = lines[at].lstrip()[len(VALIDATE_MARKER) :].strip()
    fenced = fenced_line_mask(lines)
    commands: str | None = None
    if not fenced[at]:
        i = at + 1
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        block: list[str] = []
        while i < len(lines) and fenced[i]:
            block.append(lines[i])
            i += 1
        if block:
            commands = "\n".join(block)
    return {"prose": rest or None, "commands": commands}


def parse_guide_pointer(pointer: str | None) -> dict[str, Any] | None:
    """A registry `file` pointer's anchor and candidate paths, in the engine's order."""
    text = (pointer or "").strip()
    if "#" not in text:
        return None
    doc_rel, anchor = (part.strip() for part in text.split("#", 1))
    if not anchor:
        return None
    guide_name = BOOTSTRAP_GUIDE_PATH.rsplit("/", 1)[-1]
    paths: list[str] = []
    if not doc_rel or doc_rel.rsplit("/", 1)[-1] == guide_name:
        paths.append(BOOTSTRAP_GUIDE_PATH)
    if doc_rel:
        clean = re.sub(r"^\.?/", "", doc_rel)
        if clean not in paths:
            paths.append(clean)
    return {"anchor": anchor, "paths": paths}


def validate_section_for_pointer(guide_text: str | None, pointer: str | None) -> tuple[str, str] | None:
    """The pointer's section when it carries a Validate block, else None (so hosts skip as the engine does)."""
    parsed = parse_guide_pointer(pointer)
    if parsed is None or guide_text is None:
        return None
    section = guide_section_text(guide_text, parsed["anchor"])
    if section is None or not section_has_validate_block(section[1]):
        return None
    return section


def line_count(text: str) -> int:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        return len(lines) - 1
    return len(lines)


@dataclass(frozen=True)
class Resolved:
    reference: str
    path: str
    fragment: str | None
    kind: str
    label: str
    text: str
    degraded: bool
    reason: str | None
    clamped: bool
    is_markdown: bool
    line_count: int
    heading_slugs: list[str] = field(default_factory=list)


def _section_end(headings: Sequence[Heading], start_line: int, max_level: int, total: int) -> int:
    for heading in headings:
        if heading.line_index > start_line and heading.level <= max_level:
            return heading.line_index
    return total


def _whole(text: str, reason: str | None) -> dict[str, Any]:
    return {
        "kind": "whole_file",
        "label": "whole file",
        "text": text,
        "degraded": reason is not None,
        "reason": reason,
        "clamped": False,
    }


def _line_range(text: str, match: re.Match[str]) -> dict[str, Any]:
    lines = text.split("\n")
    count = line_count(text)
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) is not None else start
    if start < 1 or end < start:
        return _whole(text, "malformed-range")
    if start > count:
        return _whole(text, "range-past-end")
    clamped = end > count
    if clamped:
        end = count
    return {
        "kind": "line_range",
        "label": f"line {start}" if start == end else f"lines {start}–{end}",
        "text": "\n".join(lines[start - 1 : end]),
        "degraded": False,
        "reason": None,
        "clamped": clamped,
    }


def _markdown(text: str, fragment: str, headings: Sequence[Heading]) -> dict[str, Any] | None:
    lines = text.split("\n")
    by_line = {h.line_index: h for h in headings}

    def section(heading: Heading) -> dict[str, Any]:
        end = _section_end(headings, heading.line_index, heading.level, len(lines))
        return {
            "kind": "section",
            "label": f'section "{heading.text}"',
            "text": "\n".join(lines[heading.line_index : end]),
            "degraded": False,
            "reason": None,
            "clamped": False,
        }

    fenced = fenced_line_mask(lines)
    for i, line in enumerate(lines):
        if fenced[i] or fragment not in _ANCHOR_ID_RE.findall(line):
            continue
        heading = by_line.get(i)
        if heading is not None:
            return section(heading)
        end = _section_end(headings, i, 6, len(lines))
        return {
            "kind": "anchor",
            "label": f'anchor "{fragment}"',
            "text": "\n".join(lines[i:end]),
            "degraded": False,
            "reason": None,
            "clamped": False,
        }
    for heading in headings:
        if heading.slug == fragment:
            return section(heading)
    return None


def resolve_reference(reference: str, read_file: Callable[[str], str | None]) -> Resolved | None:
    """Resolve like the engine's `resolve_reference`; `read_file(path)` is None when skipped."""
    path, fragment = split_reference(reference)
    if not path:
        return None
    text = read_file(path)
    if text is None:
        return None
    is_markdown = is_markdown_path(path)
    headings = scan_headings(text) if is_markdown else []
    if fragment is None:
        selection = _whole(text, None)
    else:
        range_match = _LINE_RANGE_RE.match(fragment)
        if range_match:
            selection = _line_range(text, range_match)
        elif not is_markdown:
            selection = _whole(text, "not-markdown")
        else:
            selection = _markdown(text, fragment, headings) or _whole(text, "no-match")
    return Resolved(
        reference=reference,
        path=path,
        fragment=fragment,
        is_markdown=is_markdown,
        line_count=line_count(text),
        heading_slugs=[h.slug for h in headings],
        **selection,
    )


def read_repo_file(repo_root: Path, path: str) -> tuple[str | None, str]:
    """Read `path` the way the engine does; `(text, "ok")` or `(None, why)`.

    `why` is `missing`, `outside`, `not-file`, `not-utf8` or `unreadable`.
    """
    try:
        root = Path(repo_root).resolve()
        target = (root / path).resolve()
        target.relative_to(root)
    except ValueError:
        return None, "outside"
    except (OSError, RuntimeError):
        return None, "unreadable"
    try:
        if not target.exists():
            return None, "missing"
        if not target.is_file():
            return None, "not-file"
        return target.read_text(encoding="utf-8"), "ok"
    except UnicodeDecodeError:
        return None, "not-utf8"
    except OSError:
        return None, "unreadable"


def _constant_reader(text: str | None) -> Callable[[str], str | None]:
    """A `read_file` for `resolve_reference` that returns `text` for any path."""

    def read(_path: str) -> str | None:
        return text

    return read


def inline_size(text: str) -> int:
    return len(text.strip())


def replay_inline_budget(entries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Replay `load_references`' decisions.

    Each entry is `{"reference": str, "resolved": None | {"path", "whole_file", "size"}}`.
    Returns `{"outcomes": [...], "item_oversize": [...], "total_oversize": str | None}`;
    each outcome is `{"reference", "decision", "size", "demoted_by", "remaining"}` with
    `decision` one of inline / pointer / dropped / deduped / skipped.
    """
    outcomes: list[dict[str, Any] | None] = [None] * len(entries)

    def blank(i: int, decision: str) -> None:
        outcomes[i] = {
            "reference": entries[i]["reference"],
            "decision": decision,
            "size": None,
            "demoted_by": None,
            "remaining": None,
        }

    seen: set[str] = set()
    groups: dict[str, list[int]] = {}
    for i, entry in enumerate(entries):
        if entry["reference"] in seen:
            blank(i, "deduped")
            continue
        seen.add(entry["reference"])
        if entry["resolved"] is None:
            blank(i, "skipped")
            continue
        groups.setdefault(entry["resolved"]["path"], []).append(i)

    remaining = REFERENCE_INLINE_TOTAL_MAX_CHARS

    def decide(i: int) -> bool:
        nonlocal remaining
        size = entries[i]["resolved"]["size"]
        before = remaining
        if size <= REFERENCE_INLINE_ITEM_MAX_CHARS and size <= remaining:
            remaining -= size
            outcomes[i] = {
                "reference": entries[i]["reference"],
                "decision": "inline",
                "size": size,
                "demoted_by": None,
                "remaining": before,
            }
            return True
        outcomes[i] = {
            "reference": entries[i]["reference"],
            "decision": "pointer",
            "size": size,
            "demoted_by": "item" if size > REFERENCE_INLINE_ITEM_MAX_CHARS else "total",
            "remaining": before,
        }
        return False

    for indices in groups.values():
        wholes = [i for i in indices if entries[i]["resolved"]["whole_file"]]
        fragments = [i for i in indices if not entries[i]["resolved"]["whole_file"]]
        if wholes:
            primary, *duplicates = wholes
            inlined = decide(primary)
            for i in duplicates:
                if inlined:
                    blank(i, "dropped")
                else:
                    decide(i)
            if inlined:
                for i in fragments:
                    blank(i, "dropped")
                continue
        for i in fragments:
            decide(i)

    done = [o for o in outcomes if o is not None]
    total = next((o["reference"] for o in done if o["demoted_by"] == "total"), None)
    return {
        "outcomes": done,
        "item_oversize": [o["reference"] for o in done if o["demoted_by"] == "item"],
        "total_oversize": total,
    }


# ── Findings (checkout pass of validate.py) ─────────────────────────────────

_SLUG_LIMIT = 5


def _slug_list(slugs: Sequence[str]) -> str:
    return ", ".join(f"`#{s}`" for s in slugs[:_SLUG_LIMIT])


def unresolved_remedy(resolved: Resolved) -> str:
    """Deterministic fix text for a degraded selector."""
    if resolved.reason == "no-match":
        if resolved.heading_slugs:
            return "point at one of the file's heading slugs: " + _slug_list(resolved.heading_slugs)
        return "the file has no headings; use a `#L<a>-L<b>` line range"
    if resolved.reason == "not-markdown":
        return "use a `#L<a>-L<b>` line range"
    return f"use a `#L<a>-L<b>` line range with 1 <= a <= b, starting within the file's {resolved.line_count} lines"


def unresolved_reason(resolved: Resolved) -> str:
    fragment = resolved.fragment
    if resolved.reason == "malformed-range":
        return (
            f"`#{fragment}` is not a valid line range (it must start at line 1 or later and not end before it starts)"
        )
    if resolved.reason == "range-past-end":
        return f"`#{fragment}` starts past the end of the file ({resolved.line_count} lines)"
    if resolved.reason == "not-markdown":
        return f"`#{fragment}` is not a line range and `{resolved.path}` is not Markdown"
    return f"no heading slug or `<a id>` anchor matches `#{fragment}`"


def oversize_remedy(resolved: Resolved) -> str:
    if resolved.is_markdown and resolved.heading_slugs:
        return ": one of the file's heading slugs " + _slug_list(resolved.heading_slugs)
    return " with a `#L<a>-L<b>` line range"


def reference_findings(
    references: Sequence[str],
    repo_root: Path,
    make: Callable[..., dict[str, Any]],
    rules: dict[str, str],
) -> list[dict[str, Any]]:
    """Selector and budget findings for one ordered reference list.

    `rules` maps `missing` / `unresolved` / `oversize` / `total` to rule ids
    (the `missing` id may be absent: then a missing path is not reported here).
    `make(rule_id, **params)` builds a finding.
    """
    findings: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    by_reference: dict[str, Resolved] = {}
    seen: set[str] = set()
    for reference in references:
        resolved: Resolved | None = None
        if reference not in seen:
            seen.add(reference)
            path, _fragment = split_reference(reference)
            status = "missing"
            if path:
                text, status = read_repo_file(repo_root, path)
                resolved = resolve_reference(reference, _constant_reader(text))
            if resolved is None:
                if path and status == "missing" and "missing" in rules:
                    findings.append(make(rules["missing"], path=path, reference=reference))
            else:
                by_reference[reference] = resolved
                if resolved.degraded:
                    findings.append(
                        make(
                            rules["unresolved"],
                            reference=reference,
                            reason=unresolved_reason(resolved),
                            remedy=unresolved_remedy(resolved),
                        )
                    )
        entries.append(
            {
                "reference": reference,
                "resolved": None
                if resolved is None
                else {
                    "path": resolved.path,
                    "whole_file": resolved.kind == "whole_file",
                    "size": inline_size(resolved.text),
                },
            }
        )
    replay = replay_inline_budget(entries)
    for outcome in replay["outcomes"]:
        if outcome["demoted_by"] == "item":
            resolved = by_reference[outcome["reference"]]
            findings.append(
                make(
                    rules["oversize"],
                    reference=outcome["reference"],
                    size=f"{outcome['size']:,}",
                    remedy=oversize_remedy(resolved),
                )
            )
    total = replay["total_oversize"]
    if total is not None:
        outcome = next(o for o in replay["outcomes"] if o["reference"] == total and o["decision"] == "pointer")
        findings.append(
            make(rules["total"], reference=total, size=f"{outcome['size']:,}", remaining=f"{outcome['remaining']:,}")
        )
    return findings
