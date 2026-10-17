from __future__ import annotations

import json
from pathlib import Path

from autoresearcher.pipeline import RunConfig, run_pipeline
from autoresearcher.recompute import recompute_run


def test_every_claim_is_reproduced(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    report = recompute_run(run_dir)
    assert report.n_claims == 3
    assert report.n_reproduced == 3
    assert report.ok is True
    assert report.mismatches == []


def test_editing_the_evidence_is_caught(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    evidence = run_dir / "evidence/experiment-000.json"
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    blob = json.loads(payload["result"]["stdout"].strip().splitlines()[-1])
    blob["scores"]["strong"] = 0.99
    payload["result"]["stdout"] = json.dumps(blob) + "\n"
    evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = recompute_run(run_dir)
    assert report.ok is False
    assert {mismatch.claim_id for mismatch in report.mismatches} == {"gate:000"}
    fields = {mismatch.field for mismatch in report.mismatches}
    assert "metrics.leader_score" in fields
    assert "metrics.evidence_sha256" in fields


def test_a_claim_with_no_evidence_file_is_unresolvable(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    (run_dir / "evidence/experiment-001.json").unlink()
    report = recompute_run(run_dir)
    assert report.ok is False
    assert report.unresolvable == ["gate:001"]


def test_a_chain_broken_after_the_run_is_caught(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    ledger = run_dir / "claim_ledger.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    # Drop the ``run_start`` envelope: the chain no longer verifies, but no
    # pre-registration and no evidence file is touched, so every claim still
    # reproduces. That is the distinction between ``chain_ok`` and
    # ``n_reproduced``.
    ledger.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
    report = recompute_run(run_dir)
    assert report.chain_ok is False
    assert report.ok is False
    assert report.n_reproduced == 3
