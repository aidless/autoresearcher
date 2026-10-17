"""The M1 acceptance: one command, three artifacts, all offline, all checkable.

Structural assertions only. Nothing here compares a float: the numbers already
went through ⑤'s gate, and repeating its arithmetic in a test would just be a
second implementation to keep in sync.
"""

from __future__ import annotations

import json
from pathlib import Path

from arx.experiments.ledger import verify_ledger_file

from autoresearcher.audit import uncovered_numbers
from autoresearcher.claim import ClaimLedger
from autoresearcher.pipeline import RunConfig, run_pipeline


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_one_command_produces_the_three_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(
        RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True)
    )
    assert outcome.chain.completed is True
    assert outcome.chain.stopped_at is None

    draft = run_dir / "draft.md"
    ledger = run_dir / "claim_ledger.jsonl"
    decisions = run_dir / "gate_decisions.jsonl"
    assert draft.is_file()
    assert ledger.is_file()
    assert decisions.is_file()

    assert verify_ledger_file(ledger)["chain_valid"] is True

    # Both sides are derived, never hardcoded: the claimed count comes from the
    # ledger's claim rows and the checked count from ⑦'s own payload, so a later
    # declared ⑦ check changes the expected total without breaking this test.
    rows = ClaimLedger(ledger).rows()
    checks = json.loads((run_dir / "artifacts/selfaudit.json").read_text(encoding="utf-8"))["checks"]
    lines = _lines(decisions)
    assert len(lines) == len(rows) + len(checks)
    assert sum(1 for line in lines if line["gate"] == "gate") == len(rows)
    assert sum(1 for line in lines if line["gate"] == "selfaudit") == len(checks)


def test_the_draft_is_labelled_by_the_decision_the_gate_recorded(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True))
    rows = ClaimLedger(run_dir / "claim_ledger.jsonl").rows()
    text = (run_dir / "draft.md").read_text(encoding="utf-8")
    verified, _, unresolved = text.partition("## Unresolved claims")
    assert "## Verified findings" in verified
    assert "## Unresolved claims" in text
    accepted = [row for row in rows if row.gate_decision == "ACCEPT"]
    travelled = [row for row in rows if row.gate_decision != "ACCEPT"]
    assert accepted and travelled  # the fixture has both, by construction
    for row in accepted:
        assert row.text in verified
        assert row.text not in unresolved
    for row in travelled:
        assert row.text in unresolved
        assert row.text not in verified


def test_every_number_in_the_draft_is_covered_by_the_ledger(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True))
    rows = ClaimLedger(run_dir / "claim_ledger.jsonl").rows()
    assert uncovered_numbers((run_dir / "draft.md").read_text(encoding="utf-8"), rows) == []


def test_a_run_that_refuses_at_the_gate_leaves_no_draft(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(
        RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True, generators=2)
    )
    assert outcome.chain.stopped_at == "gate"
    assert outcome.draft_path is None
    assert not (run_dir / "draft.md").exists()
    # The decision record is written even for a refusal: a refusal is a decision.
    assert (run_dir / "gate_decisions.jsonl").is_file()
    assert all(line["gate"] == "gate" for line in _lines(run_dir / "gate_decisions.jsonl"))
