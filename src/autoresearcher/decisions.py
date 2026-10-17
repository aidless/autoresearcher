"""The run's decision record: one line per gate decision, in the order it was made.

This is a projection, not a second chain. The claim ledger's hash chain already
commits to ⑤'s decisions; duplicating them in a chain of their own would leave
two things to verify, and the copy would be stale the first time anyone edited a
record. What the file adds is that "what did this run decide" is answerable
without a ledger reader.
"""

from __future__ import annotations

import json
from pathlib import Path

from autoresearcher.claim import ClaimRow

DECISION_NAME = "gate_decisions.jsonl"

#: The D4 schema. Frozen by test.
DECISION_LINE_KEYS: tuple[str, ...] = (
    "gate",
    "target",
    "claim_id",
    "decision",
    "verdict",
    "reasons",
)


def claim_lines(rows: list[ClaimRow]) -> list[dict]:
    """⑤'s decisions, in ledger order: ACCEPT/MARGINAL/UNDECIDABLE/REJECT."""
    return [
        {
            "gate": "gate",
            "target": row.text,
            "claim_id": row.claim_id,
            "decision": row.gate_decision,
            "verdict": row.metrics.get("verdict"),
            "reasons": list(row.metrics.get("reasons") or []),
        }
        for row in rows
    ]


def check_lines(checks: list[dict]) -> list[dict]:
    """⑦'s decisions, in check order: PASS/FAIL, with the detail as the reason."""
    return [
        {
            "gate": "selfaudit",
            "target": str(check.get("name", "")),
            "claim_id": None,
            "decision": "PASS" if check.get("passed") else "FAIL",
            "verdict": None,
            "reasons": [] if check.get("passed") else [str(check.get("detail", ""))],
        }
        for check in checks
    ]


def decision_lines(rows: list[ClaimRow], checks: list[dict]) -> list[dict]:
    return claim_lines(rows) + check_lines(checks)


def write_decisions(run_dir: Path, lines: list[dict]) -> Path:
    target = Path(run_dir) / DECISION_NAME
    body = "".join(json.dumps(line, sort_keys=True) + "\n" for line in lines)
    target.write_text(body, encoding="utf-8")
    return target


__all__ = [
    "DECISION_LINE_KEYS",
    "DECISION_NAME",
    "check_lines",
    "claim_lines",
    "decision_lines",
    "write_decisions",
]
