from __future__ import annotations

import json
from pathlib import Path

from arx.experiments.ledger import Ledger

from autoresearcher.pipeline import RunConfig, run_pipeline
from tools import verify_claim_chain


def _good_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(
        RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True)
    )
    assert outcome.chain.completed is True
    return run_dir


def _results(run_dir: Path) -> list[bool]:
    return [check.ok for check in verify_claim_chain.checks(run_dir)]


def _ledger_lines(run_dir: Path) -> list[dict]:
    text = (run_dir / "claim_ledger.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _write_ledger(run_dir: Path, records: list[dict]) -> None:
    path = run_dir / "claim_ledger.jsonl"
    path.unlink()
    ledger = Ledger(path)
    for record in records:
        ledger.append(record["kind"], record["payload"])


def test_a_good_run_passes_all_five_checks(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    assert _results(run_dir) == [True] * 5
    assert verify_claim_chain.main([str(run_dir)]) == 0


def test_editing_a_ledger_line_breaks_the_chain_and_only_the_chain(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    records = _ledger_lines(run_dir)
    for record in records:
        if record.get("kind") == "claim":
            record["payload"]["claim_id"] = "gate:999"
            break
    (run_dir / "claim_ledger.jsonl").write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )
    # check 1 only: the payload still has all eight fields, the evidence bytes are
    # untouched, and recompute does not depend on claim_id.
    assert _results(run_dir) == [False, True, True, True, True]


def test_altering_an_evidence_file_fails_the_hash_check(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    evidence = run_dir / "evidence/experiment-000.json"
    evidence.write_bytes(evidence.read_bytes() + b"\n")
    results = _results(run_dir)
    # Check 3 is the one that owns "the evidence hashes to what the ledger says".
    # Check 4 also goes red here, and cannot not: recompute re-derives
    # metrics["evidence_sha256"] from the same bytes, so the file a third party
    # needs to distrust turns two checks red by construction.
    assert results[2] is False
    assert results[3] is False
    assert results[0] is True and results[1] is True and results[4] is True


def test_altering_a_recorded_metric_fails_only_the_recompute_check(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    records = _ledger_lines(run_dir)
    for record in records:
        if record.get("kind") == "claim":
            record["payload"]["metrics"]["power"] = 0.9
            break
    # Re-chain so the ledger is internally consistent: this isolates "the recorded
    # decision does not re-derive" from "the ledger was edited after the fact".
    _write_ledger(run_dir, records)
    # check 4 only: `power` is a metric the draft does not render, so coverage
    # (check 5) is unaffected, and the chain verifies because we rebuilt it.
    assert _results(run_dir) == [True, True, True, False, True]


def test_an_uncovered_number_in_the_draft_fails_only_the_coverage_check(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    draft = run_dir / "draft.md"
    draft.write_text(draft.read_text(encoding="utf-8") + "\n0.9999\n", encoding="utf-8")
    assert _results(run_dir) == [True, True, True, True, False]


def test_the_summary_line_counts_five(tmp_path: Path, capsys) -> None:
    run_dir = _good_run(tmp_path)
    assert verify_claim_chain.main([str(run_dir)]) == 0
    assert "5/5" in capsys.readouterr().out
