#!/usr/bin/env python3
"""Validate AgentLoom authoring artifacts before they are filed or pushed.

    validate.py issue <draft.md> [--emit-body PATH] [--existing issues.json]
    validate.py batch <dir> [--open REF --numbers ref=123,... --emit-body PATH]
    validate.py roadmap [--base REF]
    validate.py blocker <BLK-id> [--base REF] [--ack LABEL ...]

Common options: --repo-root PATH (default: the current directory),
--pin TAG (the platform's engine pin, when known), --context FILE (the saved
result of the AgentLoom MCP tool `get_authoring_context`: the platform's pin
and the repository's resolver roles, live), --json.

Exit codes: 0 pass; 1 errors; 2 usage or environment problem; 3 provisional —
the pin-dependent checks could not be confirmed against the platform's pin
(offline without --pin or --context, or the platform's pin differs from the pin
this kit was built for).
A provisional run is never a pass.

Filing output — `--emit-body`, the batch opening order, `batch --open` — is
produced only when the run has no error of any kind (a provisional one
included) and no pin mismatch; for a batch, the WHOLE batch must be clean.

An issue draft is Markdown with front matter:

    ---
    title: Stop unbounded webhook redelivery
    labels:
      - se
      - se:type:bugfix
      - se:priority:high
      - se:resolve-worker:platform
      - agentloom:user-generated
    ---
    <the exact issue body>

A batch item adds `ref:` and `depends_on:` (sibling refs or real issue
numbers) to the front matter; one item per `.md` file in the batch directory.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import _kit


def split_front_matter(text: str, source: str) -> tuple:
    text = _kit.normalize_newlines(text)
    if not text.startswith("---\n"):
        raise _kit.KitError(f"{source}: a draft starts with a `---` front-matter block")
    end = text.find("\n---\n", 3)
    if end == -1:
        if text.endswith("\n---"):
            end = len(text) - 4
        else:
            raise _kit.KitError(f"{source}: the front-matter block is not closed with `---`")
    meta = _kit.load_yaml_text(text[4:end], source) or {}
    if not isinstance(meta, dict):
        raise _kit.KitError(f"{source}: front matter must be a mapping")
    return meta, text[end + 5 :]


def load_draft(path: Path, batch: bool) -> dict[str, Any]:
    meta, body = split_front_matter(path.read_text(encoding="utf-8"), str(path))
    labels = meta.get("labels") or []
    if not isinstance(labels, list):
        raise _kit.KitError(f"{path}: `labels` must be a list")
    draft: dict[str, Any] = {
        "title": str(meta.get("title") or ""),
        "labels": [str(label) for label in labels],
        "body": body,
    }
    if batch:
        depends = meta.get("depends_on") or []
        if not isinstance(depends, list):
            raise _kit.KitError(f"{path}: `depends_on` must be a list")
        draft["ref"] = str(meta.get("ref") or "")
        draft["depends_on"] = depends
    return draft


# ── Checkout-only checks ────────────────────────────────────────────────────

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "from",
    "by",
    "is",
    "be",
    "when",
    "it",
    "its",
    "that",
    "this",
    "as",
    "at",
}


def _tokens(text: str) -> set:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def _similar(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.5


def duplicate_findings(
    draft: dict[str, Any], repo_root: Path, existing: Path | None, prefix: str = ""
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if existing is not None:
        rows = json.loads(existing.read_text(encoding="utf-8"))
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and _similar(draft["title"], str(row.get("title") or "")):
                findings.append(
                    _kit.finding(
                        "issue.duplicate.open-issue", f"{prefix}title", number=row.get("number"), title=row.get("title")
                    )
                )
    roadmap_path = repo_root / _kit.ROADMAP_PATH
    if roadmap_path.is_file():
        roadmap = _kit.load_yaml_text(roadmap_path.read_text(encoding="utf-8"), _kit.ROADMAP_PATH)
        for item in _kit.iter_roadmap_items(roadmap):
            if item.get("status", "planned") in ("done", "obsolete"):
                continue
            first_line = str(item.get("description") or "").strip().split("\n")[0]
            if _similar(draft["title"], first_line) or _similar(
                draft["title"], str(item.get("id") or "").replace("-", " ")
            ):
                findings.append(_kit.finding("issue.duplicate.roadmap-item", f"{prefix}title", id=item.get("id")))
    return findings


_TRACKED: dict[str, list[str]] = {}


def _tracked_files(repo_root: Path) -> list[str]:
    key = str(repo_root.resolve())
    if key not in _TRACKED:
        code, out, _err = _kit.git(repo_root, "ls-files")
        _TRACKED[key] = out.splitlines() if code == 0 else []
    return _TRACKED[key]


def path_findings(body: str, repo_root: Path, prefix: str = "") -> list[dict[str, Any]]:
    """Cited `path:line` references that name no file in the checkout.

    A bare file name (`issue-ingestion.ts:88`) counts as found when any tracked
    file ends with it; URLs (`host:port`) are not paths.
    """
    findings: list[dict[str, Any]] = []
    seen: set = set()
    for match in _kit.P["codeReference"].finditer(body):
        path = match.group(1)
        if path in seen or body[max(0, match.start() - 3) : match.start()] == "://":
            continue
        seen.add(path)
        if (repo_root / path).exists():
            continue
        if any(f == path or f.endswith("/" + path) for f in _tracked_files(repo_root)):
            continue
        findings.append(_kit.finding("issue.substance.path-not-found", f"{prefix}body", path=path))
    return findings


def gh_command(title: str, labels: Sequence[str], body_path: Path) -> str:
    parts = ["gh", "issue", "create", "--title", title, "--body-file", str(body_path)]
    for label in labels:
        parts += ["--label", label]
    return " ".join(shlex.quote(p) for p in parts)


# ── Commands ────────────────────────────────────────────────────────────────


def cmd_issue(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root)
    draft = load_draft(Path(args.file), batch=False)
    findings = _kit.validate_issue(draft, _kit.authoring_roles(repo_root, args.context, required=True))
    findings += path_findings(draft["body"], repo_root)
    findings += duplicate_findings(draft, repo_root, Path(args.existing) if args.existing else None)
    return finish_issue(args, draft, findings)


def finish_issue(
    args: argparse.Namespace,
    draft: dict[str, Any],
    findings: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> int:
    lines: list[str] = []
    allowed = _kit.filing_allowed(findings, args.pin)
    code = _kit.report(findings, args.pin, args.json, extra, emit=lines.append)
    if args.emit_body and allowed:
        out = Path(args.emit_body)
        out.write_text(draft["body"], encoding="utf-8")
        if not args.json:
            lines.append(f"Body written to {out}. File it with:\n  {gh_command(draft['title'], draft['labels'], out)}")
            if code == _kit.EXIT_PROVISIONAL:
                lines.append(_kit.PROVISIONAL_FILING_NOTE)
    elif args.emit_body and not args.json:
        lines.append("No body written: filing needs a run with no errors and no pin mismatch.")
    print("\n".join(lines))
    return code


def cmd_batch(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root)
    directory = Path(args.dir)
    files = sorted(p for p in directory.glob("*.md") if not p.name.endswith(".body.md"))
    items = [load_draft(p, batch=True) for p in files]
    roles = _kit.authoring_roles(repo_root, args.context, required=True)
    findings, order = _kit.validate_batch(items, roles)
    for i, item in enumerate(items):
        findings += path_findings(item["body"], repo_root, f"items[{i}].")
    # The opening order and every rendered body are filing output: they need the
    # WHOLE batch clean, so a later sibling's defect can never leave the batch
    # half filed.
    allowed = _kit.filing_allowed(findings, args.pin)
    extra = {
        "order": order if allowed else [],
        "files": {item["ref"]: str(p) for item, p in zip(items, files, strict=True)},
    }
    if not args.open or not allowed:
        code = _kit.report(findings, args.pin, args.json, extra)
        if not args.json:
            if allowed:
                print("Open in this order: " + " → ".join(order))
                if code == _kit.EXIT_PROVISIONAL:
                    print(_kit.PROVISIONAL_FILING_NOTE)
            elif args.open:
                print("Nothing rendered: opening needs the whole batch free of errors and no pin mismatch.")
        return code
    item = next((it for it in items if it["ref"] == args.open), None)
    if item is None:
        raise _kit.KitError(f"no batch item has ref {args.open!r}")
    numbers: dict[str, int] = {}
    for pair in (args.numbers or "").split(","):
        if pair.strip():
            ref, _, number = pair.partition("=")
            if not number.strip().isdigit():
                raise _kit.KitError(f"--numbers entry {pair!r} is not ref=<issue number>")
            numbers[ref.strip()] = int(number)
    deps: list[int] = []
    for dep in item["depends_on"]:
        if isinstance(dep, int):
            deps.append(dep)
        elif dep in numbers:
            deps.append(numbers[dep])
        else:
            raise _kit.KitError(
                f"{args.open!r} depends on {dep!r}, which has no issue number yet: open it first and pass --numbers {dep}=<number>"
            )
    body = item["body"]
    if deps:
        body = f"<!-- {_kit.ISSUE['depends_on_marker']}: {', '.join(str(n) for n in deps)} -->\n{body}"
    rendered = {"title": item["title"], "labels": item["labels"], "body": body}
    issue_findings = _kit.validate_issue(rendered, roles) + path_findings(body, repo_root)
    return finish_issue(args, rendered, issue_findings, {"order": order, "ref": args.open})


def load_roadmap_items(text: str | None, source: str) -> list[dict[str, Any]] | None:
    if text is None:
        return None
    return [_kit.to_plain(item) for item in _kit.iter_roadmap_items(_kit.load_yaml_text(text, source))]


def cmd_roadmap(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root)
    path = repo_root / _kit.ROADMAP_PATH
    if not path.is_file():
        raise _kit.KitError(f"{_kit.ROADMAP_PATH} not found under {repo_root}")
    base_ref = args.base or _kit.default_base(repo_root)
    try:
        head_text = path.read_text(encoding="utf-8")
        head = load_roadmap_items(head_text, _kit.ROADMAP_PATH) or []
        placement = _kit.roadmap_placement(_kit.load_yaml_text(head_text, _kit.ROADMAP_PATH))
        base = load_roadmap_items(
            _kit.read_at(repo_root, base_ref, _kit.ROADMAP_PATH), f"{base_ref}:{_kit.ROADMAP_PATH}"
        )
    except ValueError as exc:
        return _kit.report(
            [_kit.finding("roadmap.parse", "roadmap", file=_kit.ROADMAP_PATH, detail=str(exc))], args.pin, args.json
        )
    findings = _kit.validate_roadmap(base, head, _kit.authoring_roles(repo_root, args.context), placement=placement)
    base_ids = {_kit.roadmap_item_id(i) for i in base or []}
    for item in head:
        item_id = _kit.roadmap_item_id(item)
        docs = item.get("docs")
        if item_id in base_ids or not _kit.is_string_list(docs):
            continue
        for doc in docs:
            if not (repo_root / doc.split("#", 1)[0]).exists():
                findings.append(
                    _kit.finding("roadmap.docs.not-found", f"roadmap[{item_id}].docs", id=item_id, path=doc)
                )
    if not args.json:
        print(f"Compared {_kit.ROADMAP_PATH} against {base_ref}.")
    return _kit.report(findings, args.pin, args.json, {"base": base_ref})


def cmd_blocker(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root)
    registry = _kit.BLOCKER["registry_path"]
    base_ref = args.base or _kit.default_base(repo_root)

    def entries(text: str | None, source: str) -> list[Any]:
        data = _kit.to_plain(_kit.load_yaml_text(text, source)) if text else None
        blockers = data.get("blockers") if isinstance(data, dict) else None
        return blockers if isinstance(blockers, list) else []

    path = repo_root / registry
    try:
        head = entries(path.read_text(encoding="utf-8") if path.is_file() else None, registry)
        base = entries(_kit.read_at(repo_root, base_ref, registry), f"{base_ref}:{registry}")
    except ValueError as exc:
        return _kit.report(
            [_kit.finding("blocker.registry.parse", "blockers", file=registry, detail=str(exc))], args.pin, args.json
        )
    findings = _kit.validate_blocker(args.id, base, head, args.ack or [])
    if not args.json:
        print(f"Compared {registry} against {base_ref}.")
    return _kit.report(findings, args.pin, args.json, {"base": base_ref})


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="validate.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo-root", default=".", help="repository checkout (default: .)")
    common.add_argument("--pin", default=None, help="the platform's engine pin, when known")
    common.add_argument(
        "--context", default=None, help="saved get_authoring_context result (live pin and roles, when connected)"
    )
    common.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("issue", parents=[common], help="validate one issue draft")
    p.add_argument("file")
    p.add_argument("--existing", help="JSON from `gh issue list --label se --state open --json number,title`")
    p.add_argument("--emit-body", help="on success, write the exact issue body here")
    p.set_defaults(func=cmd_issue)

    p = sub.add_parser("batch", parents=[common], help="validate a batch directory and print its opening order")
    p.add_argument("dir")
    p.add_argument("--open", help="render the body of this ref for filing")
    p.add_argument("--numbers", help="issue numbers of already-opened siblings, e.g. api-schema=101,api-routes=102")
    p.add_argument("--emit-body", help="with --open, write the rendered body here")
    p.set_defaults(func=cmd_batch)

    p = sub.add_parser(
        "roadmap", parents=[common], help="validate .seed-engine/roadmap.yml against its committed state"
    )
    p.add_argument("--base", help="git ref of the committed state (default: upstream branch, else HEAD)")
    p.set_defaults(func=cmd_roadmap)

    p = sub.add_parser(
        "blocker", parents=[common], help="validate one blocker completion in .seed-engine/blockers-registry.yml"
    )
    p.add_argument("id")
    p.add_argument("--base", help="git ref of the committed state (default: upstream branch, else HEAD)")
    p.add_argument("--ack", action="append", help="a secret-labelled variable confirmed not to hold a secret")
    p.set_defaults(func=cmd_blocker)

    args = parser.parse_args(argv)
    try:
        args.context = _kit.load_context(Path(args.context)) if args.context else None
        args.pin = _kit.context_pin(args.pin, args.context)
        return int(args.func(args))
    except (_kit.KitError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return _kit.EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
