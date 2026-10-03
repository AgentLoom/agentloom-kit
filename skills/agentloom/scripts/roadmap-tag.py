#!/usr/bin/env python3
"""Stamp AgentLoom's provenance tags on roadmap tasks you just added.

    roadmap-tag.py <task-id> [<task-id> ...] [--context FILE | --requested-by <uuid>] [--repo-root PATH]

Adds `user-generated` to each task — and `requested-by:<uuid>` when you are
connected, from the saved `get_authoring_context` result (`--context`) or the
user id it returned (`--requested-by`) — exactly as the platform stamps a task
created from the dashboard chat. The edit is the engine's own
`seed-engine roadmap tag <id> --add …`, reproduced byte for byte (the same
round-trip YAML settings), so the diff is what the platform itself would write.

Offline, omit --requested-by: the commit author already attributes the task,
and the tag carries a user uuid or nothing — never an email or a login.
Run it only on tasks you added in this change; existing tasks' tags are
operator-owned.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _kit


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="roadmap-tag.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("task_ids", nargs="+", help="ids of the roadmap tasks you added")
    who = parser.add_mutually_exclusive_group()
    who.add_argument("--requested-by", help="your AgentLoom user uuid (connected only)")
    who.add_argument("--context", help="saved get_authoring_context result; its user_id is the requester")
    parser.add_argument("--repo-root", default=".", help="repository checkout (default: .)")
    args = parser.parse_args(argv)

    if args.context is not None:
        try:
            args.requested_by = _kit.load_context(Path(args.context))["user_id"]
        except _kit.KitError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return _kit.EXIT_USAGE

    prov = _kit.ROADMAP["provenance"]
    tags = [prov["user_generated"]]
    if args.requested_by is not None:
        if not _kit.P["uuid"].search(args.requested_by):
            print(
                "ERROR: --requested-by takes the AgentLoom user uuid, never an email address or login: "
                "a roadmap tag is committed to the repository's history.",
                file=sys.stderr,
            )
            return _kit.EXIT_USAGE
        tags.append(f"{prov['requested_by_prefix']}{args.requested_by}")

    repo_root = Path(args.repo_root)
    if len(set(args.task_ids)) != len(args.task_ids):
        print("ERROR: a task id was given more than once", file=sys.stderr)
        return _kit.EXIT_USAGE
    try:
        for task_id in args.task_ids:
            before, after = _kit.tag_roadmap_task(repo_root, task_id, tags)
            verb = f"{before!r} → {after!r}" if after != before else f"unchanged: {before!r}"
            print(f"Task {task_id!r} tags {verb}.")
    except _kit.KitError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return _kit.EXIT_USAGE
    print("Next: python3 <skill>/scripts/validate.py roadmap, then commit and push.")
    return _kit.EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
