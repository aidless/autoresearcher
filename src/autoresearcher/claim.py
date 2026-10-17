"""The claim-ledger schema: one row per claim, and the vocabulary it is made of.

This module is the only place the §3.1 keys are written down. Downstream code
reads claims through :meth:`ClaimLedger.rows`, which refuses a record that lost
a field — a claim missing its evidence anchor is not a claim, it is an assertion
with a hash attached.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from arx.experiments.ledger import Ledger, verify_ledger_file

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


class ClaimLedger:
    """The run's append-only ledger, and the only channel between segments.

    Wraps arx's ``Ledger`` rather than reimplementing it: the chain arithmetic is
    arx's, so ``arx verify-ledger`` and ``arx replay`` read our file with no
    adapter. What this class adds is the §3.1 projection, and the rule that a
    claim row must carry every field.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._ledger = Ledger(self.path)

    def append_record(self, kind: str, payload: dict) -> dict:
        """Append a non-claim record (``run_start``, ``pre_register``, ...).

        These share the claim file because the ordering guarantee the gate relies
        on — ``k_max`` written before the experiment ran — is a property of the
        chain, and a second chain would be a second thing to verify.
        """
        return self._ledger.append(kind, payload)

    def append_claim(
        self,
        *,
        claim_id: str,
        segment: str,
        text: str,
        evidence_ref: str,
        gate_decision: str | None,
        metrics: dict,
    ) -> ClaimRow:
        """Append a claim and return it with its chain links filled in."""
        row = ClaimRow(
            claim_id=claim_id,
            segment=segment,
            text=text,
            evidence_ref=evidence_ref,
            gate_decision=gate_decision,
            metrics=metrics,
        )
        self._ledger.append("claim", row.to_flat_dict())
        written = self.as_records()[-1]
        return ClaimRow.from_record({**written["payload"], **written})

    def as_records(self) -> list[dict]:
        """Every record, for arx's ``read_preregistration``.

        Read straight from the file's lines rather than through arx's
        ``LedgerRecord`` envelope: a claim whose envelope does not even parse is
        exactly the malformed record :meth:`rows` exists to refuse, and arx's
        reader raises ``TypeError`` before the missing-field check can run.
        """
        if not self.path.exists():
            return []
        out: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
        return out

    def rows(self) -> list[ClaimRow]:
        """Every claim row, refusing a record that lost a field."""
        out: list[ClaimRow] = []
        for record in self.as_records():
            if record.get("kind") != "claim":
                continue
            payload = record.get("payload", {})
            missing = [name for name in CLAIM_FIELDS if name not in payload]
            if missing:
                raise ValueError(
                    f"claim at seq {record.get('seq')} is missing claim fields {missing}; "
                    "a claim without its evidence anchor is not a claim"
                )
            out.append(ClaimRow.from_record({**record, **payload}))
        return out

    def by_segment(self, segment: str) -> list[ClaimRow]:
        return [row for row in self.rows() if row.segment == segment]

    def accepted(self) -> list[ClaimRow]:
        return [row for row in self.rows() if row.gate_decision == "ACCEPT"]

    def next_claim_id(self, segment: str) -> str:
        """``segment:NNN``, counted within that segment only.

        Derivable before appending, which is what lets ⑤ name a claim inside the
        other fields of its own row.
        """
        return f"{segment}:{len(self.by_segment(segment)):03d}"

    def verify(self) -> bool:
        return bool(verify_ledger_file(self.path)["chain_valid"])


__all__ = ["CLAIM_FIELDS", "GATE_DECISIONS", "ClaimLedger", "ClaimRow"]
