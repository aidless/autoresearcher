"""Re-derive every gate decision from the files on disk.

This is the design's "可复算" pillar made into a command. It calls the same
``adjudicate`` the gate called, with the same inputs, and compares the result
field by field against what was written down. It is not a second implementation
of the gate and cannot drift from one: if it ever disagrees, the disagreement is
about the *files*, which is exactly what a third party wants to know.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from arx.experiments.ledger import verify_ledger_file

from autoresearcher.claim import ClaimLedger
from autoresearcher.config import offline_config
from autoresearcher.segments.gate import adjudicate


@dataclass
class Mismatch:
    claim_id: str
    field: str
    recorded: object
    recomputed: object


@dataclass
class RecomputeReport:
    n_claims: int = 0
    n_reproduced: int = 0
    mismatches: list[Mismatch] = field(default_factory=list)
    unresolvable: list[str] = field(default_factory=list)
    chain_ok: bool = False

    @property
    def ok(self) -> bool:
        """A run recomputes only if the chain holds *and* every claim reproduces."""
        return self.chain_ok and not self.mismatches and not self.unresolvable

    def summary(self) -> str:
        return (
            f"chain {'OK' if self.chain_ok else 'BROKEN'} | "
            f"reproduced {self.n_reproduced}/{self.n_claims} | "
            f"mismatches {len(self.mismatches)} | unresolvable {len(self.unresolvable)}"
        )


def recompute_run(run_dir: Path) -> RecomputeReport:
    run_dir = Path(run_dir)
    ledger_path = run_dir / "claim_ledger.jsonl"
    ledger = ClaimLedger(ledger_path)
    config = offline_config(run_dir)
    records = ledger.as_records()
    report = RecomputeReport(chain_ok=bool(verify_ledger_file(ledger_path)["chain_valid"]))

    for row in ledger.rows():
        report.n_claims += 1
        if row.gate_decision is None:
            # A segment that wrote a claim without judging it has nothing to
            # recompute, and saying so beats counting it as reproduced.
            report.unresolvable.append(row.claim_id)
            continue

        try:
            path_part, _line = row.evidence_ref.rsplit(":", 1)
            evidence_path = run_dir / path_part
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            decision = adjudicate(
                evidence=evidence,
                records=records,
                config=config,
                evidence_sha256=evidence_sha,
            )
        except (OSError, ValueError, KeyError, TypeError):
            # A missing, unreadable or corrupt evidence file is not a decision:
            # it is a claim whose inputs cannot be resolved, which is a result
            # about the *files* and never a crash in the reporter.
            report.unresolvable.append(row.claim_id)
            continue

        before = len(report.mismatches)
        if decision.gate_decision != row.gate_decision:
            report.mismatches.append(
                Mismatch(row.claim_id, "gate_decision", row.gate_decision, decision.gate_decision)
            )
        for key in sorted(set(row.metrics) | set(decision.metrics)):
            recorded = row.metrics.get(key)
            recomputed = decision.metrics.get(key)
            if recorded != recomputed:
                report.mismatches.append(
                    Mismatch(row.claim_id, f"metrics.{key}", recorded, recomputed)
                )
        if len(report.mismatches) == before:
            report.n_reproduced += 1

    return report


__all__ = ["Mismatch", "RecomputeReport", "recompute_run"]
