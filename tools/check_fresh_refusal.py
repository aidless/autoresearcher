#!/usr/bin/env python3
"""Re-measure the two-generator refusal. Offline fixtures only.

This does not read the committed golden snapshot. It runs the pipeline again
with ``--generators 2`` and checks the refusal the gate actually returns.
Exit 0 only when the chain stops at the gate with three UNDECIDABLE claims
whose reason is ``floor_degenerate``, and no draft is written.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from autoresearcher.cli import main as cli_main

TOPIC = "does a noise floor bound what a leaderboard can claim"


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "refused"
        code = cli_main(
            ["run", "--dry-run", TOPIC, "--generators", "2", "--out", str(run_dir)]
        )
        decisions = [
            json.loads(line)
            for line in (run_dir / "gate_decisions.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        reasons = sorted({reason for row in decisions for reason in row["reasons"]})
        draft = (run_dir / "draft.md").exists()
        ok = (
            code == 2
            and len(decisions) == 3
            and {row["decision"] for row in decisions} == {"UNDECIDABLE"}
            and reasons == ["floor_degenerate"]
            and not draft
        )
        print(
            "MEASURED refusal "
            f"exit={code} decisions={[row['decision'] for row in decisions]} "
            f"reasons={reasons} draft={draft}"
        )
        if not ok:
            print("FRESH REFUSAL FAIL", file=sys.stderr)
            return 1
        print("FRESH REFUSAL OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
