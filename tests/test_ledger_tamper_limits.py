"""Measured limits of the hash chain and of the empty evidence hash.

These are negative cases. They generate a run, or call ``adjudicate`` on a
failing experiment record, and then break the files. Nothing here is a
research result.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arx.experiments.ledger import record_hash, verify_ledger_file

from autoresearcher.claim import ClaimLedger
from autoresearcher.config import offline_config
from autoresearcher.pipeline import RunConfig, run_pipeline
from autoresearcher.recompute import recompute_run
from autoresearcher.segments.gate import adjudicate
from tools.verify_claim_chain import checks

TOPIC = "does a noise floor bound what a leaderboard can claim"


def _run(tmp_path: Path, *, generators: int) -> Path:
    run_dir = tmp_path / "run"
    run_pipeline(
        RunConfig(topic=TOPIC, run_dir=run_dir, dry_run=True, generators=generators)
    )
    return run_dir


def test_flipping_one_ledger_byte_breaks_the_chain(tmp_path: Path) -> None:
    run_dir = _run(tmp_path, generators=5)
    ledger = run_dir / "claim_ledger.jsonl"
    raw = bytearray(ledger.read_bytes())
    raw[40] ^= 0x01
    ledger.write_bytes(raw)
    assert verify_ledger_file(ledger)["chain_valid"] is False


def test_rewriting_a_payload_and_rehashing_still_verifies(tmp_path: Path) -> None:
    """Blind spot: the chain detects a stale hash, not an attacker who rewrites it.

    The first record's topic is replaced and every hash is recomputed with the
    same ``record_hash`` the ledger uses. ``verify_ledger_file`` then reports a
    valid chain. There is no signature to catch the rewrite.
    """
    run_dir = _run(tmp_path, generators=5)
    records = [
        json.loads(line)
        for line in (run_dir / "claim_ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records[0]["payload"]["topic"] = "rewritten by someone who can recompute the chain"
    prev = ""
    rewritten: list[str] = []
    for record in records:
        record["prev_hash"] = prev
        record["hash"] = record_hash(
            record["seq"], record["ts"], record["kind"], record["payload"], prev
        )
        prev = record["hash"]
        rewritten.append(json.dumps(record, sort_keys=True))
    path = tmp_path / "rewritten.jsonl"
    path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
    report = verify_ledger_file(path)
    assert report["chain_valid"] is True
    assert report["n_records"] == len(records)


def test_an_accept_run_notices_a_changed_evidence_file(tmp_path: Path) -> None:
    run_dir = _run(tmp_path, generators=5)
    evidence = run_dir / "evidence" / "experiment-000.json"
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["result"]["duration_s"] = float(payload["result"]["duration_s"]) + 1.0
    evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    by_name = {check.name: check for check in checks(run_dir)}
    evidence_check = next(check for name, check in by_name.items() if name.startswith("every claim's evidence"))
    assert evidence_check.ok is False
    assert recompute_run(run_dir).ok is False


def test_a_failing_experiment_drops_the_evidence_hash(tmp_path: Path) -> None:
    """Blind spot: ``_undecidable`` stores evidence_sha256 as "".

    A nonzero experiment exit never reached a measurement. ``adjudicate`` is
    handed the file's real sha256 and writes an empty string instead. The
    evidence check then has nothing to compare, so editing the file still
    passes that check, and ``recompute`` agrees because it calls the same
    function. This is not the two-generator ``floor_degenerate`` path: that
    path records a real hash and a one-byte evidence edit fails the check.
    """
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    evidence_path = run_dir / "evidence" / "experiment-000.json"
    evidence_path.parent.mkdir()
    evidence = {
        "hypothesis": "a script that exited before it measured anything",
        "result": {
            "entrypoint": "experiment-000.py",
            "returncode": 1,
            "stdout": "",
            "stderr": "boom",
            "timed_out": False,
            "duration_s": 0.01,
            "script_sha256": "abc",
        },
    }
    evidence_path.write_text(json.dumps(evidence, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    decision = adjudicate(
        evidence=evidence,
        records=[],
        config=offline_config(run_dir),
        evidence_sha256=digest,
    )
    assert decision.gate_decision == "UNDECIDABLE"
    assert decision.metrics["evidence_sha256"] == ""
    assert digest

    ledger = ClaimLedger(run_dir / "claim_ledger.jsonl")
    ledger.append_claim(
        claim_id=ledger.next_claim_id("gate"),
        segment="gate",
        text=evidence["hypothesis"],
        evidence_ref="evidence/experiment-000.json:1",
        gate_decision=decision.gate_decision,
        metrics=decision.metrics,
    )
    evidence["result"]["stderr"] = "tampered"
    evidence_path.write_text(json.dumps(evidence, sort_keys=True) + "\n", encoding="utf-8")
    by_name = {check.name: check for check in checks(run_dir)}
    evidence_check = next(
        check for name, check in by_name.items() if name.startswith("every claim's evidence")
    )
    assert evidence_check.ok is True
    report = recompute_run(run_dir)
    assert report.mismatches == []
    assert report.unresolvable == []
