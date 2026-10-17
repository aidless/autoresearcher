"""⑥ — write the draft by reading the ledger back, never by re-deriving a number.

The rule this file exists to enforce is arx's: every number in the paper is read
back out of the ledgers. This writer has no arithmetic in it. It renders the
``metrics`` dict the gate already committed to, and it labels each section by the
``gate_decision`` the gate already recorded, so a draft can never say something
the ledger does not.
"""

from __future__ import annotations

from dataclasses import dataclass

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.claim import ClaimRow
from autoresearcher.segments.base import SegmentContext, write_payload

VERIFIED_HEADING = "## Verified findings"
UNRESOLVED_HEADING = "## Unresolved claims (tested, not separable)"
DRAFT_NAME = "draft.md"


@dataclass
class WriterSegment:
    segment_id: str = "writer"

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        gate = ctx.upstream_payload("gate")
        # "Travelled" is what the gate actually handed downstream: a claim whose
        # id appears in its decisions. Reading the ledger for the rows and the
        # gate payload for the set is the design's "only read the ledger" rule
        # with the one piece of information the ledger cannot carry — which rows
        # the gate let through.
        travelled = {
            str(decision["claim_id"])
            for decision in gate["decisions"]
            if decision.get("claim_id")
        }
        rows = [row for row in ctx.ledger.rows() if row.claim_id in travelled]
        verified = [row for row in rows if row.gate_decision == "ACCEPT"]
        unresolved = [row for row in rows if row.gate_decision != "ACCEPT"]

        draft = render_draft(topic=ctx.topic, verified=verified, unresolved=unresolved)
        (ctx.run_dir / DRAFT_NAME).write_text(draft, encoding="utf-8")
        payload = write_payload(
            ctx,
            "writer.json",
            {
                "n_verified": len(verified),
                "n_unresolved": len(unresolved),
                "claim_ids": [row.claim_id for row in rows],
            },
        )
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            # Relative, like every artifact path: the run directory is publishable.
            artifact_path=DRAFT_NAME,
            claim_ids=[row.claim_id for row in rows],
            gate_summary={
                "claims": len(rows),
                "n_verified": len(verified),
                "n_unresolved": len(unresolved),
                "payload": payload,
            },
            run_fingerprint=ctx.fingerprint,
        )


def render_draft(*, topic: str, verified: list[ClaimRow], unresolved: list[ClaimRow]) -> str:
    lines = [f"# Draft: {topic}", ""]
    lines.extend([VERIFIED_HEADING, ""])
    if verified:
        for row in verified:
            lines.extend(_finding_lines(row))
    else:
        lines.extend(["_None. No claim cleared the gate._", ""])
    lines.extend(
        [
            UNRESOLVED_HEADING,
            "",
            "_These were run and did not clear the gate. A claim that cannot be "
            "separated from the noise floor is a result, not a failure, and is "
            "reproduced here rather than omitted._",
            "",
        ]
    )
    if unresolved:
        for row in unresolved:
            lines.extend(_unresolved_lines(row))
    else:
        lines.extend(["_None._", ""])
    return "\n".join(lines) + "\n"


def _finding_lines(row: ClaimRow) -> list[str]:
    """One cleared claim, rendered from its recorded ``metrics``.

    Every ``None`` check below is about the *recording*, not the measurement:
    a metric the ledger does not carry is a line the draft must not print.
    """
    metrics = row.metrics
    out = [f"### {row.text}", "", f"- Verdict: `{metrics.get('verdict')}`"]
    if metrics.get("leader_system") is not None and metrics.get("leader_score") is not None:
        out.append(
            f"- Leader: `{metrics['leader_system']}` at "
            f"`{float(metrics['leader_score']):.4f}`"
        )
    if metrics.get("floor_estimate") is not None:
        out.append(
            f"- Noise floor: `{float(metrics['floor_estimate']):.4f}` "
            f"({metrics.get('floor_method') or 'n/a'})"
        )
    if metrics.get("margin") is not None:
        out.append(f"- Margin over floor: `{float(metrics['margin']):+.4f}`")
    if metrics.get("mde") is not None:
        out.append(
            f"- Minimum detectable effect: `{float(metrics['mde']):.4f}` "
            f"(`{metrics.get('mde_method') or 'n/a'}`)"
        )
    if metrics.get("threshold") is not None:
        out.append(f"- Threshold applied: `{float(metrics['threshold']):.4f}`")
    if metrics.get("n_generators") is not None:
        out.append(
            f"- Generators: `{metrics['n_generators']}` over "
            f"`{metrics.get('n_items')}` items"
        )
    for reason in metrics.get("reasons") or []:
        out.append(f"- Note: {reason}")
    out.append("")
    return out


def _unresolved_lines(row: ClaimRow) -> list[str]:
    out = [f"- **{row.text}** `{row.metrics.get('verdict')}`  "]
    for reason in row.metrics.get("reasons") or []:
        out.append(f"  {reason}")
    return out


__all__ = ["VERIFIED_HEADING", "UNRESOLVED_HEADING", "WriterSegment", "render_draft"]
