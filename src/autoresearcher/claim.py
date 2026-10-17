"""The claim-ledger schema: one row per claim, and the vocabulary it is made of.

This module is the only place the §3.1 keys are written down. Downstream code
reads claims through :meth:`ClaimLedger.rows`, which refuses a record that lost
a field — a claim missing its evidence anchor is not a claim, it is an assertion
with a hash attached.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CLAIM_FIELDS: tuple[str, ...] = (
    "claim_id",
    "segment",
    "text",
    "evidence_ref",
    "gate_decision",
    "metrics",
    "prev_hash",
    "row_hash",
)

#: arx's four verdicts, plus ``None`` for "this segment writes claims but has not
#: judged this one" — which only a measurement-free segment may use.
GATE_DECISIONS: tuple[str | None, ...] = (
    "ACCEPT",
    "MARGINAL",
    "UNDECIDABLE",
    "REJECT",
    None,
)


@dataclass(frozen=True)
class ClaimRow:
    """One row of ``claim_ledger.jsonl``.

    ``prev_hash`` and ``row_hash`` are the chain links arx's ``Ledger`` already
    computes; the row carries them so a reader does not have to re-open the
    ledger to check that a claim they were handed belongs to the chain.
    """

    claim_id: str
    segment: str
    text: str
    evidence_ref: str
    gate_decision: str | None
    metrics: dict = field(default_factory=dict)
    prev_hash: str = ""
    row_hash: str = ""

    def __post_init__(self) -> None:
        if self.gate_decision not in GATE_DECISIONS:
            raise ValueError(
                f"unknown gate_decision {self.gate_decision!r}; "
                f"known decisions are {GATE_DECISIONS}"
            )

    def to_flat_dict(self) -> dict:
        return {name: getattr(self, name) for name in CLAIM_FIELDS}

    @classmethod
    def from_record(cls, record: dict) -> ClaimRow:
        """Project an arx ledger record onto the spec's eight keys.

        The record's ``hash`` becomes the row's ``row_hash``. The rename is the
        spec's, and this is the only place the two names diverge, so it is done
        once, here.
        """
        return cls(
            claim_id=str(record["claim_id"]),
            segment=str(record["segment"]),
            text=str(record["text"]),
            evidence_ref=str(record["evidence_ref"]),
            gate_decision=record.get("gate_decision"),
            metrics=dict(record.get("metrics") or {}),
            prev_hash=str(record.get("prev_hash", "")),
            row_hash=str(record.get("hash", "")),
        )


__all__ = ["CLAIM_FIELDS", "GATE_DECISIONS", "ClaimRow"]
