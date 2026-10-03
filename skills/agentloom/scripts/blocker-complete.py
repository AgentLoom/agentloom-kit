#!/usr/bin/env python3
"""Record a manual blocker's resolution in `.seed-engine/blockers-registry.yml`.

    blocker-complete.py <BLK-id> --status completed --resolution "<summary>"
                        [--ack LABEL ...] [--date YYYY-MM-DD] [--repo-root PATH]

Writes `status`, `resolved` and `resolution_summary` on one planning blocker —
and patches the `## Resolution` section of an upstream_request document — the
way the engine's `seed-engine blocker resolve` does, after the same gates the
AgentLoom blocker route applies:

  * resolver blockers (`BLK-RES-*`) are refused: they are answered on the run;
  * the status only moves forward for the blocker's kind;
  * `agreed`, `rejected` and `completed` need a resolution summary;
  * the summary is screened with the platform's secret patterns. A credential
    token shape is refused outright; a secret-labelled assignment
    (`API_KEY=…`) is refused until you confirm that label with --ack.

Nothing is committed. Review the diff, then commit and push to the default
branch; the push wakes AgentLoom.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import _kit


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="blocker-complete.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("id", help="registry entry id, e.g. BLK-001")
    parser.add_argument(
        "--status",
        required=True,
        help="new status (completed; upstream_request also raised, in_discussion, agreed, rejected)",
    )
    parser.add_argument(
        "--resolution", default="", help="plain-text summary of what was decided or completed — no secret values"
    )
    parser.add_argument(
        "--ack", action="append", default=[], help="a secret-labelled variable confirmed not to hold a secret"
    )
    parser.add_argument("--date", default=None, help="resolution date (default: today, UTC)")
    parser.add_argument("--repo-root", default=".", help="repository checkout (default: .)")
    args = parser.parse_args(argv)

    resolved = args.date or dt.datetime.now(dt.timezone.utc).date().isoformat()
    if not _kit.P["isoDate"].search(resolved):
        print("ERROR: --date must be YYYY-MM-DD", file=sys.stderr)
        return _kit.EXIT_USAGE

    refusals: list = []
    try:
        written = _kit.complete_blocker(
            Path(args.repo_root), args.id, args.status, args.resolution, resolved, args.ack, on_refusal=refusals.append
        )
    except _kit.KitError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return _kit.EXIT_USAGE
    if written is None:
        for message in refusals:
            print(f"REFUSED: {message}", file=sys.stderr)
        return _kit.EXIT_ERRORS
    print(f"Recorded {args.id} → {args.status} ({resolved}) in: {', '.join(written)}")
    print("Next: run the guide section's Validate: check from a public vantage, then")
    print(f"  git add {' '.join(written)} && git commit -m 'Complete {args.id}' && git push")
    return _kit.EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
