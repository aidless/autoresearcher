from __future__ import annotations

import pytest

from autoresearcher.audit import (
    TOL,
    ledger_values,
    numbers_in_text,
    tolerance_for,
    uncovered_numbers,
)
from autoresearcher.claim import ClaimRow


def _row(metrics: dict) -> ClaimRow:
    return ClaimRow(
        claim_id="gate:000",
        segment="gate",
        text="a claim",
        evidence_ref="evidence/experiment-000.json:1",
        gate_decision="ACCEPT",
        metrics=metrics,
    )


def test_tolerance_is_half_a_unit_in_the_last_displayed_digit() -> None:
    # ``pytest.approx``, not ``==``: this is a tolerance, and comparing tolerances
    # with exact float equality is the same trap the measurement tests avoid.
    assert tolerance_for("0.9475") == pytest.approx(5e-5)
    # The rule is ``max(TOL, half a unit)``: 0.02852 displays five decimals, so
    # its half-unit is 5e-6 — *below* the 2e-5 floor, and the floor wins. (The
    # plan's Task 2 text asserts 5e-6 here, which its own helper and the ported
    # reference script cannot return; the tolerance is not widened to match it.)
    assert tolerance_for("0.02852") == pytest.approx(TOL)
    assert tolerance_for("0.9") == pytest.approx(0.05)
    assert tolerance_for("400") == 0.5
    assert TOL == 2e-5


def test_only_decimal_literals_are_numbers() -> None:
    assert numbers_in_text("400 items, 5 generators, +0.0320 over 0.9155") == [
        "+0.0320",
        "0.9155",
    ]
    assert numbers_in_text("no numbers here") == []


def test_ledger_values_walk_nested_metrics() -> None:
    row = _row({"leader_score": 0.9475, "nested": {"x": 1.5}, "listed": [2.5, True], "text": "loo"})
    assert sorted(ledger_values([row])) == [0.9475, 1.5, 2.5]


def test_a_covered_literal_is_not_uncovered() -> None:
    row = _row({"leader_score": 0.9475, "margin": 0.032, "mde": 0.031242})
    assert uncovered_numbers("leader at 0.9475, margin +0.0320, mde 0.0312", [row]) == []


def test_an_uncovered_literal_is_named() -> None:
    rows = [_row({"leader_score": 0.9475})]
    assert uncovered_numbers("leader at 0.9475 but also 0.9999", rows) == ["0.9999"]
