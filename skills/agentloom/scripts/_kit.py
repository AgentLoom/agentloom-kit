"""Shared library for the AgentLoom kit scripts.

The validators here mirror `@agentloom/shared`'s authoring module line for
line; their rule ids, messages, constants and patterns come from
`authoring-rules.json`, which is generated from that module. The golden
corpus holds both implementations to identical findings.

No network access, no code fetched at runtime. Reading YAML needs PyYAML; the
roadmap tag writer needs ruamel.yaml, the library the engine itself writes
`roadmap.yml` with.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess  # nosec B404 - reads git objects of the local checkout only
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

if sys.version_info < (3, 10):  # noqa: UP036 - the guard IS the floor check
    sys.stderr.write("ERROR: the AgentLoom kit needs Python 3.10 or newer.\n")
    sys.exit(2)

HERE = Path(__file__).resolve().parent
RULES: dict[str, Any] = json.loads((HERE / "authoring-rules.json").read_text(encoding="utf-8"))

EXIT_OK = 0
EXIT_ERRORS = 1
EXIT_USAGE = 2
EXIT_PROVISIONAL = 3

ROADMAP_PATH = ".seed-engine/roadmap.yml"
ORG_CHART_PATH = ".seed-engine/org-chart.yml"


class KitError(Exception):
    """A usage or environment problem (exit 2), never a validation finding."""


# ── Patterns ────────────────────────────────────────────────────────────────


#: JavaScript's `\s`: ASCII whitespace plus the Unicode space separators, line
#: separators and the BOM (ECMA-262 WhiteSpace + LineTerminator).
_JS_WHITESPACE = "\\t\\n\\x0b\\x0c\\r \\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff"


def _js_whitespace_classes(source: str) -> str:
    """Rewrite `\\s` / `\\S` to JavaScript's whitespace set.

    Python's ASCII mode (needed so `\\b`, `\\w`, `\\d` keep their JavaScript
    meaning) narrows `\\s` to ASCII, so a heading ending in a non-breaking
    space would parse differently on the two sides. Outside a character class
    `\\s` becomes `[…]` and `\\S` `[^…]`; inside one `\\s` contributes the set,
    and `\\S` keeps the ASCII meaning — its only use, `[\\s\\S]`, still spans
    every character.
    """
    out: list[str] = []
    in_class = False
    i = 0
    while i < len(source):
        ch = source[i]
        if ch == "\\" and i + 1 < len(source):
            nxt = source[i + 1]
            if nxt == "s":
                out.append(_JS_WHITESPACE if in_class else f"[{_JS_WHITESPACE}]")
            elif nxt == "S" and not in_class:
                out.append(f"[^{_JS_WHITESPACE}]")
            else:
                out.append(source[i : i + 2])
            i += 2
            continue
        if ch == "[" and not in_class:
            in_class = True
        elif ch == "]" and in_class:
            in_class = False
        out.append(ch)
        i += 1
    return "".join(out)


def compile_pattern(spec: dict[str, str]) -> re.Pattern[str]:
    """Compile a `{source, flags}` pair from the rules document.

    ASCII mode keeps `\\b`, `\\w`, `\\d` on the JavaScript meaning, and `\\s` /
    `\\S` are rewritten to JavaScript's whitespace set. A trailing `$` becomes
    `\\Z` outside multiline mode: in Python `$` also matches before a final
    newline, in JavaScript it does not.
    """
    source, flags = _js_whitespace_classes(spec["source"]), spec["flags"]
    value = re.ASCII
    if "i" in flags:
        value |= re.IGNORECASE
    if "m" in flags:
        value |= re.MULTILINE
    if "s" in flags:
        value |= re.DOTALL
    if "m" not in flags and source.endswith("$") and not source.endswith("\\$"):
        source = source[:-1] + r"\Z"
    return re.compile(source, value)


P = {name: compile_pattern(spec) for name, spec in RULES["patterns"].items()}
TOKEN_PATTERNS = [(p["id"], compile_pattern(p)) for p in RULES["secrets"]["token_patterns"]]
LABELED_ASSIGNMENT = compile_pattern(RULES["secrets"]["labeled_assignment"])
PLACEHOLDERS = [compile_pattern(p) for p in RULES["secrets"]["placeholder_exemptions"]]
POOL: list[str] = list(RULES["tech_skills"]["ids"])
# The identity of the rules this kit enforces: sha256 of the pin-free rule
# document (`authoringRulesFingerprint` in @agentloom/shared). The kit carries
# no engine pin — a pin bump that changes no rule leaves the kit unchanged.
BUILT_FOR_RULES_FINGERPRINT: str = RULES["rules_fingerprint"]


# ── Findings ────────────────────────────────────────────────────────────────

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def format_rule_text(template: str, params: dict[str, Any]) -> str:
    return _PLACEHOLDER.sub(lambda m: str(params[m.group(1)]) if m.group(1) in params else m.group(0), template)


def finding(rule_id: str, at: str, /, **params: Any) -> dict[str, Any]:
    """One finding; `params` fill the rule's `{placeholders}` (positional-only
    arguments leave every name, `path` included, free for them)."""
    rule = RULES["rules"][rule_id]
    return {
        "rule": rule_id,
        "severity": rule["severity"],
        "pin_dependent": rule["pin_dependent"],
        "path": at,
        "message": format_rule_text(rule["message"], params),
        "fix": format_rule_text(rule["fix"], params),
    }


# ── Values ──────────────────────────────────────────────────────────────────


def to_plain(value: Any) -> Any:
    """YAML-loaded data as plain JSON-like values (dates become ISO strings)."""
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    if isinstance(value, str):
        return str(value)
    return value


def deep_equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, list) or isinstance(b, list):
        return (
            isinstance(a, list)
            and isinstance(b, list)
            and len(a) == len(b)
            and all(deep_equal(x, y) for x, y in zip(a, b, strict=True))
        )
    if isinstance(a, dict) or isinstance(b, dict):
        return (
            isinstance(a, dict)
            and isinstance(b, dict)
            and a.keys() == b.keys()
            and all(deep_equal(a[k], b[k]) for k in a)
        )
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


def is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def scalar_text(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def normalize_newlines(text: str) -> str:
    return re.sub(r"\r\n?", "\n", text)


def strip_html_comments(text: str) -> str:
    return P["htmlComment"].sub("", text)


def content_length(text: str) -> int:
    return len(strip_html_comments(text).strip())


def lines_outside_fences(text: str) -> list[str]:
    out: list[str] = []
    in_fence = False
    for line in normalize_newlines(text).split("\n"):
        if P["fence"].search(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return out


def parse_body(body: str) -> tuple[str, list[tuple[str, str]]]:
    """The preamble and the `## ` sections of a body (headings in fences ignored)."""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    in_fence = False
    for line in normalize_newlines(body).split("\n"):
        if P["fence"].search(line):
            in_fence = not in_fence
        match = None if in_fence else P["sectionHeading"].search(line)
        if match:
            sections.append((match.group(1), []))
            continue
        if sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return "\n".join(preamble), [(title, "\n".join(lines)) for title, lines in sections]


_WORD_CHAR = re.compile(r"[a-z0-9]", re.IGNORECASE)


def contains_phrase(text: str, phrase: str) -> bool:
    """`phrase` in `text` as whole words (mirrors `containsPhrase`)."""
    at = text.find(phrase)
    while at != -1:
        before = text[at - 1] if at > 0 else ""
        after = text[at + len(phrase) : at + len(phrase) + 1]
        if not _WORD_CHAR.fullmatch(before or "-") and not _WORD_CHAR.fullmatch(after or "-"):
            return True
        at = text.find(phrase, at + 1)
    return False


def find_cycle_from(start: str, edges: dict[str, list[str]]) -> list[str] | None:
    stack = [start]
    on_stack = {start}
    done: set = set()
    frames = [[start, 0]]
    while frames:
        frame = frames[-1]
        deps = edges.get(frame[0], [])
        if frame[1] < len(deps):
            dep = deps[frame[1]]
            frame[1] += 1
            if dep in on_stack:
                return stack[stack.index(dep) :] + [dep]
            if dep not in done and dep in edges:
                frames.append([dep, 0])
                stack.append(dep)
                on_stack.add(dep)
            continue
        done.add(frame[0])
        on_stack.discard(frame[0])
        stack.pop()
        frames.pop()
    return None


# ── Secret scan (generated patterns from shared/src/lib/secret-content.ts) ──


def _normalize_assigned_value(raw: str) -> str:
    value = raw.strip()
    while True:
        before = value
        value = re.sub(r"[.,;)]+\Z", "", value)
        for open_, close in (("`", "`"), ('"', '"'), ("'", "'")):
            if len(value) >= 2 and value.startswith(open_) and value.endswith(close):
                value = value[len(open_) : len(value) - len(close)]
                break
        if value == before:
            return value


def _is_placeholder(raw: str) -> bool:
    normalized = _normalize_assigned_value(raw)
    return any(p.search(raw.strip()) or p.search(normalized) for p in PLACEHOLDERS)


def detect_secret_content(text: str) -> list[tuple[str, str, int]]:
    """`(kind, label, line)` findings in source order — never the matched value."""
    if not text:
        return []
    positioned: list[tuple[int, str, str, int]] = []
    for pattern_id, pattern in TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            positioned.append((match.start(), "token_shape", pattern_id, text.count("\n", 0, match.start())))
    for match in LABELED_ASSIGNMENT.finditer(text):
        name, value = match.group(1), match.group(2)
        if not name or value is None or _is_placeholder(value):
            continue
        positioned.append((match.start(), "labeled_assignment", name, text.count("\n", 0, match.start())))
    positioned.sort(key=lambda p: p[0])
    seen: set = set()
    out: list[tuple[str, str, int]] = []
    for _offset, kind, label, line in positioned:
        key = (kind, label, line)
        if key in seen:
            continue
        seen.add(key)
        out.append((kind, label, line))
    return out


def labels_requiring_ack(findings: Sequence[tuple[str, str, int]], acknowledged: Sequence[str]) -> list[str]:
    covered = {label.strip() for label in acknowledged}
    out: list[str] = []
    for kind, label, _line in findings:
        label = label.strip()
        if kind != "labeled_assignment" or label in covered or label in out:
            continue
        out.append(label)
    return out


def secret_findings(text: str, path: str, where: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set = set()
    for kind, label, _line in detect_secret_content(text):
        if (kind, label) in seen:
            continue
        seen.add((kind, label))
        if kind == "token_shape":
            out.append(finding("secret.token-shape", path, where=where, pattern=label))
        else:
            out.append(finding("secret.labeled-assignment", path, where=where, label=label))
    return out


# ── Issue validation (mirrors shared/src/authoring/issue.ts) ────────────────

ISSUE = RULES["issue"]
LABELS = RULES["labels"]
REQUIRED: list[str] = ISSUE["required_sections"]
OPTIONAL: list[str] = ISSUE["optional_sections"]
ORDER_TEXT = ", ".join(REQUIRED)
OPTIONAL_TEXT = ", ".join(OPTIONAL)


def _title_findings(title: str, prefix: str) -> list[dict[str, Any]]:
    if not title.strip():
        return [finding("issue.title.missing", f"{prefix}title")]
    if len(title) > ISSUE["title_max"]:
        return [finding("issue.title.too-long", f"{prefix}title", length=len(title), max=ISSUE["title_max"])]
    return []


def _label_findings(
    labels: Sequence[str], roles: Sequence[str] | None, prefix: str
) -> tuple[list[dict[str, Any]], str | None]:
    findings: list[dict[str, Any]] = []
    trimmed = [label.strip() for label in labels]
    types: list[str] = []
    priorities: list[str] = []
    workers: list[str] = []
    type_values = ", ".join(ISSUE["types"])
    priority_values = ", ".join(ISSUE["priorities"])
    for i, label in enumerate(trimmed):
        at = f"{prefix}labels[{i}]"
        if label == LABELS["marker"]:
            continue
        if label.startswith(LABELS["type_prefix"]):
            value = label[len(LABELS["type_prefix"]) :]
            types.append(value)
            if value not in ISSUE["types"]:
                findings.append(finding("issue.labels.type-invalid", at, label=label, values=type_values))
            continue
        if label.startswith(LABELS["priority_prefix"]):
            value = label[len(LABELS["priority_prefix"]) :]
            priorities.append(value)
            if value not in ISSUE["priorities"]:
                findings.append(finding("issue.labels.priority-invalid", at, label=label, values=priority_values))
            continue
        if label.startswith(LABELS["resolve_worker_prefix"]):
            role = label[len(LABELS["resolve_worker_prefix"]) :]
            workers.append(role)
            if roles is not None and role not in roles:
                findings.append(finding("issue.labels.unknown-role", at, role=role))
            continue
        if label in LABELS["lifecycle_exact"] or any(label.startswith(p) for p in LABELS["lifecycle_prefixes"]):
            findings.append(finding("issue.labels.lifecycle", at, label=label))
            continue
        if label in LABELS["operator"]:
            continue
        if label.startswith(f"{LABELS['root']}:"):
            findings.append(finding("issue.labels.unexpected", at, label=label, root=LABELS["root"]))

    path = f"{prefix}labels"
    if LABELS["marker"] not in trimmed:
        findings.append(finding("issue.labels.marker-missing", path, label=LABELS["marker"]))
    if not types:
        findings.append(finding("issue.labels.type-missing", path, prefix=LABELS["type_prefix"], values=type_values))
    elif len(types) > 1:
        findings.append(finding("issue.labels.type-multiple", path, prefix=LABELS["type_prefix"]))
    if not priorities:
        findings.append(
            finding("issue.labels.priority-missing", path, prefix=LABELS["priority_prefix"], values=priority_values)
        )
    elif len(priorities) > 1:
        findings.append(finding("issue.labels.priority-multiple", path, prefix=LABELS["priority_prefix"]))
    if not workers:
        findings.append(finding("issue.labels.resolve-worker-missing", path, prefix=LABELS["resolve_worker_prefix"]))
    elif len(workers) > LABELS["max_resolve_workers"]:
        findings.append(
            finding("issue.labels.resolve-worker-too-many", path, count=len(workers), max=LABELS["max_resolve_workers"])
        )
    if LABELS["provenance"] not in trimmed:
        findings.append(finding("issue.labels.provenance-missing", path, label=LABELS["provenance"]))
    issue_type = types[0] if len(types) == 1 and types[0] in ISSUE["types"] else None
    return findings, issue_type


def _structure_findings(parsed: tuple[str, list[tuple[str, str]]], path: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    preamble, sections = parsed
    if content_length(preamble) == 0:
        findings.append(finding("issue.body.preamble-missing", path))
    seen: set = set()
    last_required = -1
    for title, content in sections:
        if title in seen:
            findings.append(finding("issue.body.section-duplicate", path, section=title))
            continue
        seen.add(title)
        if title in REQUIRED:
            index = REQUIRED.index(title)
            if index < last_required:
                findings.append(finding("issue.body.section-order", path, section=title, order=ORDER_TEXT))
            last_required = max(last_required, index)
        elif title not in OPTIONAL:
            findings.append(
                finding("issue.body.unknown-section", path, section=title, order=ORDER_TEXT, optional=OPTIONAL_TEXT)
            )
            continue
        if title != ISSUE["tech_skills_section"] and content_length(content) == 0:
            findings.append(finding("issue.body.section-empty", path, section=title))
    for title in REQUIRED:
        if title not in seen:
            findings.append(finding("issue.body.section-missing", path, section=title, order=ORDER_TEXT))
    return findings


def _marker_findings(body: str, path: str, in_batch: bool) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    text = normalize_newlines(body)
    reported: set = set()
    for match in P["engineMarker"].finditer(text):
        name = match.group(1)
        if name == ISSUE["depends_on_marker"] or name in reported:
            continue
        reported.add(name)
        findings.append(finding("issue.body.engine-marker", path, marker=name))
    if P["platformMarker"].search(text):
        findings.append(finding("issue.body.platform-marker", path))

    depends = list(P["dependsOnMarker"].finditer(text))
    if depends and in_batch:
        findings.append(finding("issue.depends-on.in-batch-item", path))
    elif len(depends) > 1:
        findings.append(finding("issue.depends-on.duplicate-marker", path, count=len(depends)))
    elif len(depends) == 1:
        entries = [e.strip() for e in depends[0].group(1).split(",")]
        if not entries or any(not P["dependsOnEntry"].search(e) for e in entries):
            findings.append(finding("issue.depends-on.malformed", path))

    origin = ISSUE["origin"]
    params = {"marker": origin["marker"], "marker_with_user": origin["marker_with_user"]}
    origins = list(P["originMarker"].finditer(text))
    requested_prefix = f"{origin['requested_by_key']}:"
    if not origins:
        findings.append(finding("issue.provenance.marker-missing", path, **params))
    elif len(origins) > 1:
        findings.append(finding("issue.provenance.marker-malformed", path, **params))
    else:
        parts = [p.strip() for p in origins[0].group(1).split(";")]
        if parts[0] != origin["source"] or len(parts) > 2:
            findings.append(finding("issue.provenance.marker-malformed", path, **params))
        elif len(parts) == 2:
            if not parts[1].startswith(requested_prefix):
                findings.append(finding("issue.provenance.marker-malformed", path, **params))
            elif not P["uuid"].search(parts[1][len(requested_prefix) :].strip()):
                findings.append(finding("issue.provenance.requested-by-not-uuid", path))
    return findings


def _tech_skill_findings(
    parsed: tuple[str, list[tuple[str, str]]], path: str, roles: Sequence[str] | None, pool: Sequence[str]
) -> list[dict[str, Any]]:
    _preamble, sections = parsed
    content = next((c for t, c in sections if t == ISSUE["tech_skills_section"]), None)
    if content is None:
        return []
    lines = [line.strip() for line in strip_html_comments(content).split("\n")]
    lines = [line for line in lines if line]
    if not lines:
        return [finding("issue.tech-skills.empty-section", path)]
    findings: list[dict[str, Any]] = []
    for line in lines:
        match = P["techSkillItem"].search(line)
        if not match:
            findings.append(finding("issue.tech-skills.malformed", path))
            continue
        skill = match.group(1).strip()
        if skill in pool:
            continue
        if roles is not None and skill in roles:
            findings.append(finding("issue.tech-skills.role-key", path, id=skill))
        else:
            findings.append(finding("issue.tech-skills.unknown-id", path, id=skill))
    return findings


def _substance_findings(
    body: str, parsed: tuple[str, list[tuple[str, str]]], path: str, issue_type: str | None
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    _preamble, sections = parsed
    by_title: dict[str, str] = {}
    for title, content in sections:
        by_title.setdefault(title, content)
    if issue_type is not None and issue_type in ISSUE["evidence_types"]:
        if not P["observedFailure"].search(by_title.get("Background", "")):
            findings.append(finding("issue.substance.observed-failure-missing", path, type=issue_type))
        if not any(P["codeReference"].search(by_title.get(t, "")) for t in ("Background", "Implementation Notes")):
            findings.append(finding("issue.substance.no-code-reference", path, type=issue_type))
    for title in REQUIRED:
        if title not in by_title:
            continue
        length = content_length(by_title[title])
        minimum = ISSUE["section_floors"].get(title, 0)
        if 0 < length < minimum:
            findings.append(finding("issue.substance.section-thin", path, section=title, length=length, min=minimum))
    acceptance = by_title.get("Acceptance Criteria")
    if acceptance is not None and content_length(acceptance) > 0 and not P["checklistItem"].search(acceptance):
        findings.append(finding("issue.substance.acceptance-not-checklist", path))
    if acceptance is not None:
        for needs in unachievable_criteria(acceptance):
            findings.append(finding("issue.substance.unachievable-criterion", path, needs=needs))
    prose = "\n".join(lines_outside_fences(body)).lower()
    for phrase in ISSUE["meta_narration_phrases"]:
        if contains_phrase(prose, phrase):
            findings.append(finding("issue.substance.meta-narration", path, phrase=phrase.strip()))
    return findings


_UNACHIEVABLE = ISSUE["unachievable_criteria"]
_CRITERION_ITEM = compile_pattern(_UNACHIEVABLE["item"])
_CRITERION_ALTERNATIVE = compile_pattern(_UNACHIEVABLE["alternative"])
_CRITERION_SHAPES = [
    (shape["needs"], compile_pattern(shape["first"]), compile_pattern(shape["second"]))
    for shape in _UNACHIEVABLE["shapes"]
]


def unachievable_criteria(section: str) -> list[str]:
    """What each unachievable acceptance criterion requires, one entry per shape.

    Mirrors the engine generator's own check (seed-engine #330): a criterion
    needs both signals of a shape, and one offering an alternative is exempt.
    """
    found: list[str] = []
    for line in section.split("\n"):
        item = _CRITERION_ITEM.match(line)
        criterion = item.group(1) if item else line
        if not criterion.strip() or _CRITERION_ALTERNATIVE.search(criterion):
            continue
        for needs, first, second in _CRITERION_SHAPES:
            if needs not in found and first.search(criterion) and second.search(criterion):
                found.append(needs)
    return found


def _validate_draft(
    draft: dict[str, Any], roles: Sequence[str] | None, pool: Sequence[str], prefix: str, in_batch: bool
) -> list[dict[str, Any]]:
    body_path = f"{prefix}body"
    label_findings, issue_type = _label_findings(draft["labels"], roles, prefix)
    parsed = parse_body(draft["body"])
    return [
        *_title_findings(draft["title"], prefix),
        *label_findings,
        *_structure_findings(parsed, body_path),
        *_marker_findings(draft["body"], body_path, in_batch),
        *_tech_skill_findings(parsed, body_path, roles, pool),
        *_substance_findings(draft["body"], parsed, body_path, issue_type),
        *secret_findings(draft["title"], f"{prefix}title", "the title"),
        *secret_findings(draft["body"], body_path, "the body"),
    ]


def validate_issue(
    draft: dict[str, Any], roles: Sequence[str] | None = None, pool: Sequence[str] = POOL
) -> list[dict[str, Any]]:
    return _validate_draft(draft, roles, pool, "", False)


def topo_order(items: Sequence[dict[str, Any]]) -> list[str]:
    """Opening order: dependencies first, ties in listed order (mirrors topoSortOpenIssueBatch)."""
    ordered: list[str] = []
    emitted: set = set()
    progressed = True
    while progressed and len(ordered) < len(items):
        progressed = False
        for item in items:
            ref = item["ref"]
            if ref in emitted:
                continue
            if any(isinstance(d, str) and d != ref and d not in emitted for d in item["depends_on"]):
                continue
            ordered.append(ref)
            emitted.add(ref)
            progressed = True
    ordered.extend(item["ref"] for item in items if item["ref"] not in emitted)
    return ordered


def validate_batch(
    items: Sequence[dict[str, Any]], roles: Sequence[str] | None = None, pool: Sequence[str] = POOL
) -> tuple[list[dict[str, Any]], list[str]]:
    if not items:
        return [finding("batch.empty", "items")], []
    findings: list[dict[str, Any]] = []
    refs: set = set()
    for i, item in enumerate(items):
        ref = item["ref"]
        at = f"items[{i}].ref"
        if not ref or len(ref) > 64 or not P["batchRef"].search(ref):
            findings.append(finding("batch.ref.invalid", at, ref=ref))
        elif ref in refs:
            findings.append(finding("batch.ref.duplicate", at, ref=ref))
        refs.add(ref)
    graph_clean = not findings
    for i, item in enumerate(items):
        for j, dep in enumerate(item["depends_on"]):
            at = f"items[{i}].depends_on[{j}]"
            if isinstance(dep, bool) or not isinstance(dep, (int, str)):
                findings.append(finding("batch.depends-on.invalid", at))
                graph_clean = False
            elif isinstance(dep, int):
                if dep <= 0:
                    findings.append(finding("batch.depends-on.invalid", at))
                    graph_clean = False
            elif dep == item["ref"]:
                findings.append(finding("batch.depends-on.self", at, ref=item["ref"]))
                graph_clean = False
            elif dep not in refs:
                findings.append(finding("batch.depends-on.unknown-ref", at, ref=item["ref"], dep=dep))
                graph_clean = False
    if graph_clean:
        edges = {item["ref"]: [d for d in item["depends_on"] if isinstance(d, str)] for item in items}
        for item in items:
            cycle = find_cycle_from(item["ref"], edges)
            if cycle:
                findings.append(finding("batch.depends-on.cycle", "items", cycle=" → ".join(cycle)))
                break
    for i, item in enumerate(items):
        findings.extend(_validate_draft(item, roles, pool, f"items[{i}].", True))
    return findings, topo_order(items)


# ── Roadmap validation (mirrors shared/src/authoring/roadmap.ts) ────────────

ROADMAP = RULES["roadmap"]
FIELD_ORDER = [
    "description",
    "priority",
    "dependencies",
    "parent_id",
    "tech_skills",
    "scheduling",
    "pinned",
    "docs",
    "manual_blockers",
]


def roadmap_item_id(item: dict[str, Any]) -> str:
    return scalar_text(item.get("id"))


def _same_field(a: dict[str, Any], b: dict[str, Any], key: str) -> bool:
    if (key in a) != (key in b):
        return False
    return deep_equal(a.get(key), b.get(key))


def _manual_blocker_detail(entry: Any) -> str | None:
    mb = ROADMAP["manual_blocker"]
    if not isinstance(entry, dict):
        return "use the object form, not a string"
    blk_id = entry.get("id")
    if not isinstance(blk_id, str) or len(blk_id) > mb["id_max"] or not P["blockerId"].search(blk_id):
        return "`id` must look like BLK-001"
    title = entry.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > mb["title_max"]:
        return f"`title` must be 1–{mb['title_max']} characters"
    kind = entry.get("kind")
    if not isinstance(kind, str) or kind not in mb["kinds"]:
        return f"`kind` must be one of {', '.join(mb['kinds'])}"
    doc = entry.get("doc")
    if not isinstance(doc, str) or not doc.strip() or len(doc) > mb["doc_max"]:
        return "`doc` must name the guide section or upstream document"
    recipient = entry.get("recipient")
    has_recipient = isinstance(recipient, str) and bool(recipient.strip())
    if kind == "upstream_request" and not has_recipient:
        return "an upstream_request must name its `recipient`"
    if kind != "upstream_request" and "recipient" in entry:
        return "`recipient` is only valid for an upstream_request"
    if has_recipient and len(recipient) > mb["recipient_max"]:
        return f"`recipient` must be at most {mb['recipient_max']} characters"
    return None


def _field_findings(
    item: dict[str, Any],
    item_id: str,
    fields: set,
    added: bool,
    ids: set,
    pool: Sequence[str],
    roles: Sequence[str] | None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def at(field: str) -> str:
        return f"roadmap[{item_id}].{field}"

    deps = item.get("dependencies") if is_string_list(item.get("dependencies")) else []
    parent = item.get("parent_id")
    for field in FIELD_ORDER:
        required = added and field in ("description", "priority")
        if field not in fields and not required:
            continue
        value = item.get(field)
        if field == "description":
            if not isinstance(value, str) or not value.strip():
                findings.append(finding("roadmap.description.missing", at(field), id=item_id))
                continue
            if len(value) > ROADMAP["description_max"]:
                findings.append(
                    finding(
                        "roadmap.description.too-long",
                        at(field),
                        id=item_id,
                        length=len(value),
                        budget=ROADMAP["description_budget"],
                    )
                )
            forbidden = [h.lower() for h in ROADMAP["forbidden_description_headings"]]
            lines = lines_outside_fences(value)
            reported: set = set()
            for line in lines:
                match = P["anyHeading"].search(line)
                heading = match.group(1) if match else ""
                if match and heading.lower() in forbidden and heading not in reported:
                    reported.add(heading)
                    findings.append(
                        finding("roadmap.description.issue-section", at(field), id=item_id, heading=heading)
                    )
            if P["checklistItem"].search("\n".join(lines)):
                findings.append(finding("roadmap.description.checklist", at(field), id=item_id))
            findings.extend(secret_findings(value, at(field), f"the description of `{item_id}`"))
            named: set = set()
            for match in P["backtickedId"].finditer(value):
                token = match.group(1)
                if token in named:
                    continue
                named.add(token)
                if token != item_id and token != parent and token in ids and token not in deps:
                    findings.append(finding("roadmap.dependencies.prose-only", at(field), id=item_id, dep=token))
        elif field == "priority":
            if not isinstance(value, str) or value not in ROADMAP["priorities"]:
                findings.append(
                    finding(
                        "roadmap.priority.invalid",
                        at(field),
                        id=item_id,
                        value=scalar_text(value),
                        values=", ".join(ROADMAP["priorities"]),
                    )
                )
        elif field == "dependencies":
            if not is_string_list(value):
                findings.append(finding("roadmap.dependencies.invalid", at(field), id=item_id))
                continue
            for j, dep in enumerate(value):
                if dep == item_id:
                    findings.append(finding("roadmap.dependencies.self", f"{at(field)}[{j}]", id=item_id))
                elif dep not in ids:
                    findings.append(
                        finding("roadmap.dependencies.unresolved", f"{at(field)}[{j}]", id=item_id, dep=dep)
                    )
        elif field == "parent_id":
            if not isinstance(value, str) or value not in ids:
                findings.append(
                    finding("roadmap.parent-id.unresolved", at(field), id=item_id, parent=scalar_text(value))
                )
        elif field == "tech_skills":
            if not is_string_list(value):
                findings.append(finding("roadmap.tech-skills.invalid", at(field), id=item_id))
                continue
            for j, skill in enumerate(value):
                if skill in pool:
                    continue
                rule = (
                    "roadmap.tech-skills.role-key"
                    if roles is not None and skill in roles
                    else "roadmap.tech-skills.unknown-id"
                )
                findings.append(finding(rule, f"{at(field)}[{j}]", id=item_id, skill=skill))
        elif field == "scheduling":
            if not isinstance(value, str) or value not in ROADMAP["scheduling_values"]:
                findings.append(finding("roadmap.scheduling.invalid", at(field), id=item_id, value=scalar_text(value)))
        elif field == "pinned":
            findings.append(finding("roadmap.pinned.retired", at(field), id=item_id))
        elif field == "docs":
            if not is_string_list(value):
                findings.append(finding("roadmap.docs.invalid", at(field), id=item_id))
        elif field == "manual_blockers":
            if not isinstance(value, list):
                findings.append(
                    finding(
                        "roadmap.manual-blocker.invalid",
                        at(field),
                        id=item_id,
                        index="list",
                        detail="`manual_blockers` must be a list",
                    )
                )
                continue
            for j, entry in enumerate(value):
                detail = _manual_blocker_detail(entry)
                if detail is not None:
                    findings.append(
                        finding(
                            "roadmap.manual-blocker.invalid", f"{at(field)}[{j}]", id=item_id, index=j, detail=detail
                        )
                    )
    return findings


def _provenance_findings(item: dict[str, Any], item_id: str) -> list[dict[str, Any]]:
    path = f"roadmap[{item_id}].tags"
    prov = ROADMAP["provenance"]
    missing = finding("roadmap.tags.provenance-missing", path, id=item_id, tag=prov["user_generated"])
    if "tags" not in item:
        return [missing]
    tags = item["tags"]
    if not is_string_list(tags):
        return [finding("roadmap.tags.invalid", path, id=item_id)]
    findings: list[dict[str, Any]] = []
    if prov["user_generated"] not in tags:
        findings.append(missing)
    for j, tag in enumerate(tags):
        if tag == prov["user_generated"]:
            continue
        if tag.startswith(prov["requested_by_prefix"]):
            if not P["uuid"].search(tag[len(prov["requested_by_prefix"]) :]):
                findings.append(finding("roadmap.tags.requested-by-not-uuid", f"{path}[{j}]", id=item_id, tag=tag))
            continue
        findings.append(
            finding(
                "roadmap.tags.not-provenance",
                f"{path}[{j}]",
                id=item_id,
                tag=tag,
                user_generated=prov["user_generated"],
                requested_by=prov["requested_by_prefix"],
            )
        )
    return findings


def validate_roadmap(
    base: Sequence[dict[str, Any]] | None,
    head: Sequence[dict[str, Any]],
    roles: Sequence[str] | None = None,
    pool: Sequence[str] = POOL,
    placement: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """`placement` mirrors the TypeScript `RoadmapPlacement` (camelCase keys);
    `roadmap_placement()` builds it from the roadmap document."""
    authored, engine_owned = ROADMAP["authored_fields"], ROADMAP["engine_owned_fields"]
    disposition, retired, planned = ROADMAP["disposition_fields"], ROADMAP["retired_fields"], ROADMAP["planned_status"]
    findings: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    head_by_id: dict[str, dict[str, Any]] = {}
    for item in head:
        item_id = roadmap_item_id(item)
        counts[item_id] = counts.get(item_id, 0) + 1
        head_by_id.setdefault(item_id, item)
    for item_id, count in counts.items():
        if count > 1:
            findings.append(finding("roadmap.id.duplicate", f"roadmap[{item_id}]", id=item_id, count=count))
    base_by_id: dict[str, dict[str, Any]] = {}
    for item in base or []:
        base_by_id.setdefault(roadmap_item_id(item), item)
    ids = set(head_by_id)

    touched: list[str] = []
    added: list[str] = []
    for item_id, item in head_by_id.items():
        before = None if base is None else base_by_id.get(item_id)
        at = f"roadmap[{item_id}]"
        if before is None:
            touched.append(item_id)
            added.append(item_id)
            raw_id = item.get("id")
            if not isinstance(raw_id, str) or len(raw_id) > ROADMAP["id_max"] or not P["roadmapId"].search(raw_id):
                findings.append(finding("roadmap.id.invalid", f"{at}.id", id=item_id, max=ROADMAP["id_max"]))
            for key in item:
                if key not in authored and key not in engine_owned and key not in retired:
                    findings.append(
                        finding("roadmap.field.unknown", f"{at}.{key}", field=key, fields=", ".join(authored))
                    )
            if item.get("status") != planned or isinstance(item.get("status"), bool):
                findings.append(finding("roadmap.add.status", f"{at}.status", id=item_id, status=planned))
            for field in engine_owned:
                if field != "status" and field in item:
                    findings.append(finding("roadmap.engine-field.authored", f"{at}.{field}", id=item_id, field=field))
            findings.extend(_field_findings(item, item_id, set(item), True, ids, pool, roles))
            findings.extend(_provenance_findings(item, item_id))
            continue
        if deep_equal(before, item):
            continue
        touched.append(item_id)
        changed = [key for key in dict.fromkeys([*before, *item]) if not _same_field(before, item, key)]
        for field in engine_owned:
            if field in changed:
                findings.append(finding("roadmap.engine-field.changed", f"{at}.{field}", id=item_id, field=field))
        for key in changed:
            if key in item and key not in authored and key not in engine_owned and key not in retired:
                findings.append(finding("roadmap.field.unknown", f"{at}.{key}", field=key, fields=", ".join(authored)))
        substantive = [key for key in changed if key not in disposition and key != "tags" and key not in engine_owned]
        base_status = scalar_text(before["status"]) if "status" in before else planned
        if substantive and base_status != planned:
            findings.append(finding("roadmap.patch.not-planned", at, id=item_id, status=base_status, planned=planned))
        if "tags" in changed:
            findings.append(finding("roadmap.tags.changed", f"{at}.tags", id=item_id))
        findings.extend(
            _field_findings(item, item_id, {key for key in changed if key in item}, False, ids, pool, roles)
        )

    if placement is not None and added:
        current = placement["currentVersion"]
        if current is None or current not in placement["versionIds"]:
            findings.append(finding("roadmap.version.current-missing", "roadmap.current_version"))
        if not placement["maintenanceVersionsValid"]:
            findings.append(finding("roadmap.version.maintenance-invalid", "roadmap.maintenance_versions"))
        for item_id in added:
            version = placement["versionOf"].get(item_id, "")
            if version not in placement["activeVersions"]:
                findings.append(
                    finding(
                        "roadmap.add.inactive-version",
                        f"roadmap[{item_id}]",
                        id=item_id,
                        version=version,
                        current=current or "",
                    )
                )

    edges = {
        item_id: (item.get("dependencies") if is_string_list(item.get("dependencies")) else [])
        for item_id, item in head_by_id.items()
    }
    touched_set = set(touched)
    reported_cycles: set = set()
    for item_id in touched:
        cycle = find_cycle_from(item_id, edges)
        if not cycle or len(cycle) <= 2 or not any(n in touched_set for n in cycle):
            continue
        key = "|".join(sorted(set(cycle)))
        if key in reported_cycles:
            continue
        reported_cycles.add(key)
        findings.append(
            finding("roadmap.dependencies.cycle", f"roadmap[{item_id}].dependencies", cycle=" → ".join(cycle))
        )

    if base is not None:
        for item_id in base_by_id:
            if item_id not in head_by_id:
                findings.append(finding("roadmap.item.removed", f"roadmap[{item_id}]", id=item_id))
    return findings


# ── Blocker validation (mirrors shared/src/authoring/blocker.ts) ────────────

BLOCKER = RULES["blocker"]


def canonical_blocker_status(entry: dict[str, Any]) -> str:
    raw = entry.get("status")
    text = ("pending" if raw is None or raw == "" else scalar_text(raw)).strip()
    return BLOCKER["status_aliases"].get(text, text)


def validate_blocker(
    blk_id: str, base: Sequence[Any], head: Sequence[Any], acknowledged: Sequence[str] = ()
) -> list[dict[str, Any]]:
    at = f"blockers[{blk_id}]"
    head_entries = [e for e in head if isinstance(e, dict)]
    base_entries = [e for e in base if isinstance(e, dict)]
    entry = next((e for e in head_entries if e.get("id") == blk_id), None)
    if entry is None:
        return [finding("blocker.not-found", at, id=blk_id)]
    issue_number = entry.get("issue_number")
    if (
        blk_id.startswith(BLOCKER["resolver_id_prefix"])
        or entry.get("origin") == "resolver"
        or (isinstance(issue_number, int) and not isinstance(issue_number, bool))
    ):
        return [finding("blocker.resolver-origin", at, id=blk_id)]
    before = next((e for e in base_entries if e.get("id") == blk_id), None)
    if before is None:
        return [finding("blocker.new-entry", at, id=blk_id)]
    if deep_equal(before, entry):
        return [finding("blocker.unchanged", at, id=blk_id)]

    findings: list[dict[str, Any]] = []
    kind = entry.get("kind") if isinstance(entry.get("kind"), str) else "other"
    order = (
        BLOCKER["status_order"]["upstream_request"] if kind == "upstream_request" else BLOCKER["status_order"]["simple"]
    )
    values = ", ".join(order)
    status = scalar_text(entry.get("status"))
    frm = canonical_blocker_status(before)
    if status not in order:
        findings.append(finding("blocker.status.invalid", f"{at}.status", status=status, kind=kind, values=values))
    elif frm in order and order.index(status) < order.index(frm):
        findings.append(
            finding("blocker.status.backward", f"{at}.status", id=blk_id, **{"from": frm}, to=status, values=values)
        )
    elif status == frm:
        findings.append(finding("blocker.status.unchanged", f"{at}.status", id=blk_id, status=status))

    summary = entry.get("resolution_summary")
    if status in BLOCKER["resolution_required"] and (not isinstance(summary, str) or not summary.strip()):
        findings.append(finding("blocker.resolution.required", f"{at}.resolution_summary", status=status))
    resolved = entry.get("resolved")
    if not isinstance(resolved, str) or not P["isoDate"].search(resolved):
        findings.append(finding("blocker.resolved.invalid", f"{at}.resolved", id=blk_id))

    if isinstance(summary, str):
        secrets = detect_secret_content(summary)
        seen: set = set()
        for kind_, label, _line in secrets:
            if kind_ != "token_shape" or label in seen:
                continue
            seen.add(label)
            findings.append(
                finding("secret.token-shape", f"{at}.resolution_summary", where="`resolution_summary`", pattern=label)
            )
        for label in labels_requiring_ack(secrets, acknowledged):
            findings.append(finding("blocker.resolution.secret-assignment", f"{at}.resolution_summary", label=label))

    completion = BLOCKER["completion_fields"]
    for field in sorted(set(before) | set(entry)):
        if field in completion:
            continue
        if not _same_field(before, entry, field):
            findings.append(
                finding("blocker.field.changed", f"{at}.{field}", id=blk_id, field=field, fields=", ".join(completion))
            )

    def others(entries: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for e in entries:
            if e.get("id") == blk_id:
                continue
            out[scalar_text(e.get("id"))] = dict(e, status=canonical_blocker_status(e))
        return out

    base_others, head_others = others(base_entries), others(head_entries)
    changed_ids = [i for i, e in head_others.items() if i not in base_others or not deep_equal(base_others[i], e)]
    changed_ids += [i for i in base_others if i not in head_others]
    if changed_ids:
        findings.append(finding("blocker.registry.other-entries", "blockers", id=blk_id, ids=", ".join(changed_ids)))
    return findings


# ── Repository access ───────────────────────────────────────────────────────


def load_yaml_text(text: str, source: str) -> Any:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise KitError("PyYAML is required: `python3 -m pip install pyyaml ruamel.yaml`") from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"{source}: {exc}") from exc


def git(repo_root: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, text=True, check=False)  # nosec B603 B607
    return proc.returncode, proc.stdout, proc.stderr


def default_base(repo_root: Path) -> str:
    """The committed state a change is judged against: the upstream branch when there is one."""
    for ref in ("@{upstream}", "origin/HEAD", "HEAD"):
        code, _out, _err = git(repo_root, "rev-parse", "--verify", "--quiet", ref)
        if code == 0:
            return ref
    raise KitError(f"{repo_root} has no commit to compare against; pass --base <ref>")


def read_at(repo_root: Path, ref: str, rel_path: str) -> str | None:
    """Contents of `rel_path` at `ref`, or None when the file does not exist there."""
    code, out, err = git(repo_root, "show", f"{ref}:{rel_path}")
    if code == 0:
        return out
    if "does not exist" in err or "exists on disk, but not in" in err:
        return None
    raise KitError(f"git show {ref}:{rel_path} failed: {err.strip()}")


def iter_roadmap_items(roadmap: Any) -> Iterable[dict[str, Any]]:
    """Every mapping item across every version (seed-engine `iter_roadmap_items`)."""
    if not isinstance(roadmap, dict):
        return
    for version in roadmap.get("versions") or []:
        if not isinstance(version, dict):
            continue
        for item in version.get("items") or []:
            if isinstance(item, dict):
                yield item


def roadmap_placement(roadmap: Any) -> dict[str, Any]:
    """Version membership of a roadmap document, as the generator reads it."""
    doc = roadmap if isinstance(roadmap, dict) else {}
    current = doc.get("current_version")
    current = current if isinstance(current, str) and current else None
    raw_maintenance = doc.get("maintenance_versions")
    # The generator reads a non-list as no maintenance versions; iterating a
    # scalar would split `v1.1` into characters.
    maintenance_valid = raw_maintenance is None or (
        isinstance(raw_maintenance, list) and all(isinstance(v, str) and v for v in raw_maintenance)
    )
    maintenance = [v for v in raw_maintenance if isinstance(v, str) and v] if isinstance(raw_maintenance, list) else []
    version_ids: list[str] = []
    version_of: dict[str, str] = {}
    for version in doc.get("versions") or []:
        if not isinstance(version, dict):
            continue
        version_id = scalar_text(version.get("id"))
        version_ids.append(version_id)
        for item in version.get("items") or []:
            if isinstance(item, dict):
                version_of.setdefault(roadmap_item_id(to_plain(item)), version_id)
    return {
        "currentVersion": current,
        "activeVersions": ([current] if current else []) + maintenance,
        "maintenanceVersionsValid": maintenance_valid,
        "versionIds": version_ids,
        "versionOf": version_of,
    }


def org_chart_roles(repo_root: Path, required: bool = False) -> list[str] | None:
    """Role keys from `.seed-engine/org-chart.yml` (`roles[].key`).

    A chart that does not parse or lists no role keys is always an error
    (exit 2), never "roles unknown": that reading would silently skip the
    unknown-role check. A MISSING chart is an error too with `required` — every
    command that validates resolve-worker labels — since a wired repository
    always has one; otherwise it returns None and only role-key hints are lost.
    """
    path = repo_root / ORG_CHART_PATH
    if not path.is_file():
        if required:
            raise KitError(f"{ORG_CHART_PATH} not found under {repo_root}: run from the root of a wired repository")
        return None
    try:
        chart = load_yaml_text(path.read_text(encoding="utf-8"), ORG_CHART_PATH)
    except ValueError as exc:
        raise KitError(f"{ORG_CHART_PATH} does not parse: {exc}") from exc
    roles = chart.get("roles") if isinstance(chart, dict) else None
    keys = [str(r["key"]) for r in roles if isinstance(r, dict) and r.get("key")] if isinstance(roles, list) else []
    if not keys:
        raise KitError(f"{ORG_CHART_PATH} lists no `roles[].key`; resolver roles cannot be checked")
    return keys


def load_context(path: Path) -> dict[str, Any]:
    """The live authoring context the AgentLoom MCP tool `get_authoring_context` returned.

    Saved by the agent as JSON: the tool's structured result, or the whole
    `tools/call` result carrying it under `structuredContent`. Its
    `rules_fingerprint` identifies the platform's authoring rules (absent from
    an older server, which leaves the run provisional), its `roles` the resolver roles of the repository's
    org chart on the default branch (null when the platform could not read it),
    and its `user_id` the connected member's uuid for provenance — null when the
    agent connected with an org's headless token, whose work carries no
    requester.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise KitError(f"cannot read --context {path}: {exc}") from exc
    except ValueError as exc:
        raise KitError(f"--context {path} is not JSON: {exc}") from exc
    if isinstance(data, dict) and isinstance(data.get("structuredContent"), dict):
        data = data["structuredContent"]
    if not isinstance(data, dict):
        raise KitError(f"--context {path} is not a get_authoring_context result")
    fingerprint = data.get("rules_fingerprint")
    user_id = data.get("user_id")
    roles = data.get("roles")
    if fingerprint is not None and (not isinstance(fingerprint, str) or not fingerprint.strip()):
        raise KitError(f"--context {path}: rules_fingerprint must be a non-empty string when present")
    if "user_id" not in data or (
        user_id is not None and (not isinstance(user_id, str) or not P["uuid"].search(user_id))
    ):
        raise KitError(f"--context {path} carries no AgentLoom user uuid (nor null, for a headless token)")
    if roles is not None and not (is_string_list(roles) and roles):
        raise KitError(f"--context {path}: roles must be a non-empty list of role keys, or null")
    return data


def context_fingerprint(fingerprint: str | None, context: dict[str, Any] | None) -> str | None:
    """The rules fingerprint to validate against: the live context's, which
    --rules-fingerprint may only repeat. A context without one (an older server)
    yields None — provisional, never a mismatch."""
    if context is None:
        return fingerprint
    raw = context.get("rules_fingerprint")
    live = raw.strip() if isinstance(raw, str) else None
    if fingerprint is not None and live is not None and fingerprint.strip() != live:
        raise KitError(
            f"--rules-fingerprint {fingerprint.strip()} disagrees with the live context's rules fingerprint {live}"
        )
    return live if live is not None else fingerprint


def authoring_roles(repo_root: Path, context: dict[str, Any] | None, required: bool = False) -> list[str] | None:
    """Resolver roles: the live context's when it has them, else the checkout's org chart."""
    if context is not None and context.get("roles") is not None:
        return [str(r) for r in context["roles"]]
    return org_chart_roles(repo_root, required=required)


def contained_path(repo_root: Path, rel: str) -> Path:
    """`rel` resolved inside the checkout, or KitError.

    Every path the kit writes is named by repository content (the registry's
    `file`, a symlinked `.seed-engine/`), and the kit runs with the user's own
    permissions: an absolute path, a `..` component or a symlink that resolves
    outside the resolved repository root is refused before anything is written.
    """
    root = repo_root.resolve()
    if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise KitError(f"{rel!r} is not a path inside the repository")
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise KitError(f"{rel!r} resolves outside the repository ({target})")
    return target


# ── Writers that reproduce the engine's own edits byte for byte ─────────────


def _engine_yaml() -> Any:
    try:
        from ruamel.yaml import YAML
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise KitError("ruamel.yaml is required: `python3 -m pip install pyyaml ruamel.yaml`") from exc
    engine = YAML()
    engine.preserve_quotes = True
    engine.indent(mapping=2, sequence=4, offset=2)
    return engine


def _sanitize_glob_patterns(text: str) -> str:
    return re.sub(
        r"^(\s*-\s+)(\*\S+)(\s*(?:#[^\n]*)?)$",
        lambda m: f'{m.group(1)}"{m.group(2)}"{m.group(3)}',
        text,
        flags=re.MULTILINE,
    )


def _normalize_tag_list(values: Iterable[Any], source: str) -> list[str]:
    out: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise KitError(f"{source} must contain only strings; got {type(value).__name__}")
        tag = value.strip()
        if not tag:
            raise KitError(f"{source} must not contain empty strings")
        if tag not in out:
            out.append(tag)
    return out


def tag_roadmap_task(repo_root: Path, task_id: str, add: Sequence[str]) -> tuple[list[str], list[str]]:
    """`seed-engine roadmap tag <id> --add …`, reproduced: returns (before, after).

    Loads with the engine's round-trip configuration, resolves the id to exactly
    one item across all versions, appends the tags in first-occurrence order and
    writes the whole document back only when something changed.
    """
    from io import StringIO

    path = contained_path(repo_root, ROADMAP_PATH)
    engine = _engine_yaml()
    roadmap = engine.load(_sanitize_glob_patterns(path.read_text(encoding="utf-8")))
    if not roadmap:
        raise KitError(f"could not load {ROADMAP_PATH}")
    matches = [item for item in iter_roadmap_items(roadmap) if str(item.get("id") or "").strip() == task_id]
    if not matches:
        raise KitError(f"task {task_id!r} not found in roadmap")
    if len(matches) > 1:
        raise KitError(f"task {task_id!r} is ambiguous: {len(matches)} roadmap items carry this id")
    node = matches[0]
    add_tags = _normalize_tag_list(add, "--add")
    if "tags" in node and not isinstance(node["tags"], list):
        raise KitError(f"task {task_id!r} has malformed tags; repair the list by hand first")
    before = _normalize_tag_list(node.get("tags") or [], "tags") if "tags" in node else []
    after = _normalize_tag_list([*before, *add_tags], "tags")
    if after != before:
        node["tags"] = after
        stream = StringIO()
        engine.dump(roadmap, stream)
        path.write_text(stream.getvalue(), encoding="utf-8")
    return before, after


def _load_registry(path: Path) -> dict[str, Any]:
    """seed-engine `load_registry`: PyYAML, alias statuses canonicalised."""
    if not path.exists():
        return {"blockers": []}
    data = load_yaml_text(path.read_text(encoding="utf-8"), BLOCKER["registry_path"])
    if not isinstance(data, dict):
        return {"blockers": []}
    if not isinstance(data.get("blockers"), list):
        data["blockers"] = []
    _canonicalize_statuses(data)
    return data


def _canonicalize_statuses(registry: dict[str, Any]) -> None:
    known = set(BLOCKER["status_order"]["upstream_request"]) | {"duplicate"}
    for entry in registry.get("blockers") or []:
        if not isinstance(entry, dict):
            continue
        raw = str(entry.get("status") or "pending").strip()
        if raw in known:
            continue
        canonical = BLOCKER["status_aliases"].get(raw, raw)
        if canonical in known:
            entry["status"] = canonical


def _save_registry(path: Path, registry: dict[str, Any]) -> None:
    import yaml

    _canonicalize_statuses(registry)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(registry, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)


def complete_blocker(
    repo_root: Path,
    blk_id: str,
    status: str,
    resolution: str,
    resolved_date: str,
    acknowledged: Sequence[str] = (),
    on_refusal: Callable[[str], None] = lambda _msg: None,
) -> list[str] | None:
    """`seed-engine blocker resolve`, reproduced up to the commit.

    Applies the platform route's gates first (resolver-origin refusal, forward
    transition, required resolution, secret screening) and then the engine's
    `apply_resolution` write. Returns the repo-relative paths written, or None
    after reporting a refusal through `on_refusal`.
    """
    registry_path = contained_path(repo_root, BLOCKER["registry_path"])
    if blk_id.startswith(BLOCKER["resolver_id_prefix"]):
        on_refusal(
            format_rule_text(RULES["rules"]["blocker.resolver-origin"]["message"], {"id": blk_id})
            + ". "
            + RULES["rules"]["blocker.resolver-origin"]["fix"]
        )
        return None
    registry = _load_registry(registry_path)
    entry = next((e for e in registry["blockers"] if isinstance(e, dict) and e.get("id") == blk_id), None)
    if entry is None:
        on_refusal(f"`{blk_id}` is not in {BLOCKER['registry_path']}.")
        return None
    issue_number = entry.get("issue_number")
    if entry.get("origin") == "resolver" or (isinstance(issue_number, int) and not isinstance(issue_number, bool)):
        on_refusal(
            format_rule_text(RULES["rules"]["blocker.resolver-origin"]["message"], {"id": blk_id})
            + ". "
            + RULES["rules"]["blocker.resolver-origin"]["fix"]
        )
        return None
    kind = str(entry.get("kind") or "other")
    order = (
        BLOCKER["status_order"]["upstream_request"] if kind == "upstream_request" else BLOCKER["status_order"]["simple"]
    )
    current = str(entry.get("status") or "pending")
    if current == "duplicate":
        on_refusal(f"`{blk_id}` was merged into another entry; complete the surviving blocker instead.")
        return None
    if status not in order:
        on_refusal(f"`{status}` is not a valid status for a `{kind}` blocker; use one of: {', '.join(order)}.")
        return None
    if current in order and order.index(status) <= order.index(current):
        on_refusal(f"`{blk_id}` cannot move from `{current}` to `{status}`; statuses only move forward.")
        return None
    if status in BLOCKER["resolution_required"] and not resolution.strip():
        on_refusal(f"status `{status}` requires --resolution.")
        return None
    secrets = detect_secret_content(resolution)
    tokens = sorted({label for kind_, label, _l in secrets if kind_ == "token_shape"})
    if tokens:
        on_refusal(
            f"the resolution contains a credential token shape ({', '.join(tokens)}); nothing was written. Name where the credential lives instead."
        )
        return None
    unacknowledged = labels_requiring_ack(secrets, acknowledged)
    if unacknowledged:
        on_refusal(
            "the resolution assigns a value to secret-labelled variables: "
            + ", ".join(unacknowledged)
            + ". Replace each value with where it lives, or confirm it is not a secret with "
            + " ".join(f"--ack {label}" for label in unacknowledged)
            + "."
        )
        return None

    # Resolve the document before the first write, so an unsafe `file` leaves
    # the registry untouched too.
    file_path = entry.get("file")
    doc_path: Path | None = None
    if file_path and "#" not in str(file_path):
        try:
            doc_path = contained_path(repo_root, str(file_path))
        except KitError as exc:
            on_refusal(f"the `file` of `{blk_id}` is unsafe: {exc}; nothing was written.")
            return None

    entry["status"] = status
    entry["resolved"] = resolved_date
    entry["resolution_summary"] = resolution
    _save_registry(registry_path, registry)
    written = [BLOCKER["registry_path"]]

    if doc_path is not None:
        if doc_path.exists():
            content = doc_path.read_text(encoding="utf-8")
            block = f"**Status:** {status}\n**Date:** {resolved_date}\n**Summary:** {resolution}"
            patched = re.sub(r"(## Resolution\n+)_Pending_", lambda m: m.group(1) + block, content, count=1)
            if patched == content:
                patched = content.rstrip() + "\n\n## Resolution\n\n" + block + "\n"
            doc_path.write_text(patched, encoding="utf-8")
            written.append(str(file_path))
    return written


# ── Reporting ───────────────────────────────────────────────────────────────


def rules_state(fingerprint: str | None) -> str:
    """`confirmed`, `unknown` (offline, no --rules-fingerprint, or an older
    server's context without one) or `mismatch`."""
    if fingerprint is None:
        return "unknown"
    return "confirmed" if fingerprint.strip() == BUILT_FOR_RULES_FINGERPRINT else "mismatch"


PROVISIONAL_FILING_NOTE = (
    "Filing on a PROVISIONAL result: tell the user the pin-dependent checks ran against the kit's own rules "
    f"(fingerprint `{BUILT_FOR_RULES_FINGERPRINT[:12]}`), not rules confirmed against the platform."
)


def filing_allowed(findings: Sequence[dict[str, Any]], fingerprint: str | None) -> bool:
    """Whether a run may produce filing output (a body file, an opening order).

    Never with an error of any kind — a provisional, pin-dependent one included,
    since it is an error against the only pool the kit knows — and never on a
    known rules mismatch (the platform's rules fingerprint differs from the
    kit's). A provisional run with no error may file: offline there is no live
    source for the platform's rules, and the note above makes the caveat
    explicit to the user.
    """
    return rules_state(fingerprint) != "mismatch" and not any(f["severity"] == "error" for f in findings)


def exit_code(findings: Sequence[dict[str, Any]], state: str) -> int:
    errors = [f for f in findings if f["severity"] == "error"]
    if any(not f["pin_dependent"] for f in errors):
        return EXIT_ERRORS
    if state != "confirmed":
        return EXIT_PROVISIONAL
    return EXIT_ERRORS if errors else EXIT_OK


def report(
    findings: list[dict[str, Any]],
    fingerprint: str | None,
    as_json: bool,
    extra: dict[str, Any] | None = None,
    emit: Callable[[str], None] = print,
) -> int:
    state = rules_state(fingerprint)
    if state == "mismatch":
        findings = [f for f in findings if not f["pin_dependent"]]
    else:
        for f in findings:
            f["provisional"] = bool(f["pin_dependent"] and state != "confirmed")
    code = exit_code(findings, state)
    status = {EXIT_OK: "pass", EXIT_ERRORS: "fail", EXIT_PROVISIONAL: "provisional"}[code]
    if as_json:
        emit(
            json.dumps(
                {
                    "status": status,
                    "exit_code": code,
                    "built_for_rules_fingerprint": BUILT_FOR_RULES_FINGERPRINT,
                    "rules_fingerprint": fingerprint,
                    "rules_state": state,
                    "findings": findings,
                    **(extra or {}),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return code
    for f in findings:
        tag = f["severity"].upper() + (" (provisional)" if f.get("provisional") else "")
        emit(f"{tag} {f['rule']} at {f['path']}: {f['message']}\n    fix: {f['fix']}")
    if state == "mismatch":
        emit(
            f"PROVISIONAL: kit built for rules `{BUILT_FOR_RULES_FINGERPRINT}`, platform serves rules `{fingerprint.strip() if fingerprint else ''}`: update the kit. Pin-dependent checks (tech-skill pool, scheduling/tags grammar, label root) were not run."
        )
    elif state == "unknown":
        emit(
            "PROVISIONAL: pin-dependent checks ran against the kit's own rules, unconfirmed against the platform. "
            "Pass --context (or --rules-fingerprint) when connected; this is not a pass."
        )
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    emit(f"{status.upper()}: {errors} error(s), {warnings} warning(s)")
    return code
