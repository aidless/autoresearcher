"""D4's decision record: the schema, the order, and the pipeline wiring.

The count of ⑤'s lines is *derived from the ledger's own claim rows* rather than
hardcoded, so this file does not have to change when Task 5 adds ⑥⑦ to the chain:
⑦'s `"gate": "selfaudit"` lines arrive then, and nothing here asserts on the total.
"""

from __future__ import annotations

import json
from pathlib import Path

from autoresearcher.claim import ClaimLedger, ClaimRow
from autoresearcher.decisions import DECISION_LINE_KEYS, decision_lines, write_decisions
from autoresearcher.pipeline import RunConfig, run_pipeline


def _row(claim_id: str, text: str, decision: str, metrics: dict) -> ClaimRow:
    return ClaimRow(
        claim_id=claim_id,
        segment="gate",
        text=text,
        evidence_ref="evidence/experiment-000.json:1",
        gate_decision=decision,
        metrics=metrics,
    )


def test_a_claim_line_carries_exactly_the_declared_keys() -> None:
    lines = decision_lines(
        [_row("gate:000", "a claim", "ACCEPT", {"verdict": "READABLE", "reasons": []})], []
    )
    assert len(lines) == 1
    assert tuple(lines[0]) == DECISION_LINE_KEYS
    assert lines[0]["gate"] == "gate"
    assert lines[0]["target"] == "a claim"
    assert lines[0]["claim_id"] == "gate:000"
    assert lines[0]["decision"] == "ACCEPT"
    assert lines[0]["verdict"] == "READABLE"


def test_a_check_line_is_pass_or_fail_and_carries_its_detail() -> None:
    lines = decision_lines(
        [],
        [
            {"name": "draft present", "passed": True, "detail": "draft.md"},
            {"name": "draft numbers are covered by the ledger", "passed": False, "detail": "uncovered: 0.9999"},
        ],
    )
    assert tuple(lines[0]) == DECISION_LINE_KEYS
    assert [line["decision"] for line in lines] == ["PASS", "FAIL"]
    assert all(line["gate"] == "selfaudit" and line["claim_id"] is None for line in lines)
    assert lines[1]["reasons"] == ["uncovered: 0.9999"]


def test_the_lines_are_written_in_chain_order(tmp_path: Path) -> None:
    rows = [
        _row("gate:000", "first", "ACCEPT", {"verdict": "READABLE"}),
        _row("gate:001", "second", "MARGINAL", {"verdict": "MARGINAL"}),
    ]
    checks = [{"name": "a check", "passed": True, "detail": "ok"}]
    target = write_decisions(tmp_path, decision_lines(rows, checks))
    parsed = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert [line["target"] for line in parsed] == ["first", "second", "a check"]


def test_a_run_writes_the_record_even_when_the_chain_refuses(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(
        RunConfig(topic="t", run_dir=run_dir, dry_run=True, generators=2)
    )
    assert outcome.chain.completed is False
    target = run_dir / "gate_decisions.jsonl"
    assert target.is_file()
    assert outcome.decisions_path == target
    lines = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    claim_lines = [line for line in lines if line["gate"] == "gate"]
    rows = ClaimLedger(run_dir / "claim_ledger.jsonl").rows()
    # Derived, not hardcoded: one ⑤ line per claim row the ledger recorded.
    assert len(claim_lines) == len(rows)
    assert {line["claim_id"] for line in claim_lines} == {row.claim_id for row in rows}
    assert {line["decision"] for line in claim_lines} == {"UNDECIDABLE"}
    # ⑦ is not in the chain yet, so ⑦'s "selfaudit" lines are not asserted here.
    # They arrive in Task 5; "whatever the projection finds" is the point.
