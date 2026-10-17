from __future__ import annotations

import json
from pathlib import Path

import pytest
from arx.experiments.ledger import verify_ledger_file

from autoresearcher.claim import CLAIM_FIELDS, GATE_DECISIONS, ClaimLedger, ClaimRow


def test_claim_fields_are_exactly_the_spec_schema() -> None:
    assert CLAIM_FIELDS == (
        "claim_id",
        "segment",
        "text",
        "evidence_ref",
        "gate_decision",
        "metrics",
        "prev_hash",
        "row_hash",
    )


def test_gate_decisions_are_the_four_arx_verdicts_plus_no_decision() -> None:
    assert GATE_DECISIONS == ("ACCEPT", "MARGINAL", "UNDECIDABLE", "REJECT", None)


def test_flat_dict_has_exactly_the_frozen_keys() -> None:
    row = ClaimRow(
        claim_id="gate:000",
        segment="gate",
        text="a claim",
        evidence_ref="evidence/experiment-000.json:1",
        gate_decision="ACCEPT",
        metrics={"margin": 0.0495},
        prev_hash="0" * 64,
        row_hash="1" * 64,
    )
    assert tuple(row.to_flat_dict()) == CLAIM_FIELDS


def test_an_unknown_gate_decision_is_refused() -> None:
    with pytest.raises(ValueError, match="gate_decision"):
        ClaimRow(
            claim_id="gate:000",
            segment="gate",
            text="a claim",
            evidence_ref="evidence/experiment-000.json:1",
            gate_decision="PROBABLY",
            metrics={},
            prev_hash="0" * 64,
            row_hash="1" * 64,
        )


def _ledger(tmp_path: Path) -> ClaimLedger:
    return ClaimLedger(tmp_path / "claim_ledger.jsonl")


def _append_first(ledger: ClaimLedger):
    return ledger.append_claim(
        claim_id=ledger.next_claim_id("gate"),
        segment="gate",
        text="first",
        evidence_ref="evidence/experiment-000.json:1",
        gate_decision="ACCEPT",
        metrics={"margin": 0.0495},
    )


def test_two_claims_chain_to_each_other(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.append_record("run_start", {"topic": "t"})
    first = _append_first(ledger)
    second = ledger.append_claim(
        claim_id=ledger.next_claim_id("gate"),
        segment="gate",
        text="second",
        evidence_ref="evidence/experiment-001.json:1",
        gate_decision="MARGINAL",
        metrics={"margin": 0.0265},
    )
    assert first.claim_id == "gate:000"
    assert second.claim_id == "gate:001"
    assert second.prev_hash == first.row_hash


def test_arx_verify_ledger_accepts_the_file(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.append_record("run_start", {"topic": "t"})
    _append_first(ledger)
    report = verify_ledger_file(ledger.path)
    assert report["chain_valid"] is True
    assert report["n_records"] == 2


def test_rows_reads_back_the_frozen_fields(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.append_record("run_start", {"topic": "t"})
    _append_first(ledger)
    rows = ledger.rows()
    assert len(rows) == 1
    assert tuple(rows[0].to_flat_dict()) == CLAIM_FIELDS
    assert rows[0].row_hash == ledger.as_records()[-1]["hash"]


def test_a_missing_field_is_refused_on_read(tmp_path: Path) -> None:
    path = tmp_path / "claim_ledger.jsonl"
    path.write_text(
        json.dumps({"kind": "claim", "claim_id": "gate:000", "segment": "gate"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing claim fields"):
        ClaimLedger(path).rows()


def test_next_claim_id_counts_only_claims_of_that_segment(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.append_record("pre_register", {"hypothesis": "h"})
    assert ledger.next_claim_id("gate") == "gate:000"
    _append_first(ledger)
    assert ledger.next_claim_id("gate") == "gate:001"
    assert ledger.next_claim_id("literature") == "literature:000"
