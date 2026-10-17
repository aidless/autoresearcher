from __future__ import annotations

import pytest

from autoresearcher.claim import CLAIM_FIELDS, GATE_DECISIONS, ClaimRow


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
