"""⑥ renders the ledger, and only the ledger.

The fixtures build their own claim rows with explicit ``metrics`` dicts, because
what is under test is the *rendering*, not the gate. Every assertion is on a
rendered string, a count, or a set — never on float equality.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests_helpers import make_context

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import write_payload
from autoresearcher.segments.writer import WriterSegment

ACCEPT_METRICS = {
    "verdict": "READABLE",
    "leader_system": "strong",
    "leader_score": 0.9475,
    "floor_estimate": 0.9155,
    "floor_method": "loo",
    "margin": 0.032,
    "mde": 0.031242,
    "mde_method": "binomial_approx",
    "threshold": 0.05,
    "n_generators": 5,
    "n_items": 400,
    "reasons": [],
}
MARGINAL_METRICS = {
    **ACCEPT_METRICS,
    "verdict": "MARGINAL",
    "leader_score": 0.93,
    "floor_estimate": 0.9015,
    "margin": 0.0285,
    "mde": 0.035741,
    "reasons": ["margin +0.0285 is inside the resolution bound 0.0357"],
}


def _rows(ctx, specs):
    """Append gate claim rows with explicit metrics and return them."""
    return [
        ctx.ledger.append_claim(
            claim_id=ctx.ledger.next_claim_id("gate"),
            segment="gate",
            text=text,
            evidence_ref="evidence/experiment-000.json:1",
            gate_decision=decision,
            metrics=metrics,
        )
        for text, decision, metrics in specs
    ]


def _register_gate(ctx, rows) -> None:
    """Write the payload ⑤ would have written and register its envelope."""
    ctx.upstream["gate"] = SegmentArtifact(
        segment_id="gate",
        status=SegmentStatus.OK,
        artifact_path=write_payload(
            ctx,
            "gate.json",
            {
                "decisions": [
                    {
                        "claim_id": row.claim_id,
                        "gate_decision": row.gate_decision,
                        "verdict": row.metrics.get("verdict"),
                        "reasons": list(row.metrics.get("reasons") or []),
                    }
                    for row in rows
                ],
                "n_claims": len(rows),
                "n_accept": sum(1 for row in rows if row.gate_decision == "ACCEPT"),
            },
        ),
        claim_ids=[row.claim_id for row in rows],
        gate_summary={"claims": len(rows)},
        run_fingerprint=ctx.fingerprint,
    )


def _sections(draft: str) -> tuple[str, str]:
    verified, _, rest = draft.partition("## Unresolved claims")
    return verified, rest


def test_accept_rows_land_under_verified_findings(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    rows = _rows(
        ctx,
        [
            ("the strong system separates", "ACCEPT", ACCEPT_METRICS),
            ("the median moves the leader", "MARGINAL", MARGINAL_METRICS),
        ],
    )
    _register_gate(ctx, rows)
    artifact = WriterSegment().run(ctx)

    draft = (ctx.run_dir / "draft.md").read_text(encoding="utf-8")
    verified, unresolved = _sections(draft)
    assert artifact.status is SegmentStatus.OK
    assert artifact.artifact_path == "draft.md"
    assert "## Verified findings" in verified
    assert "the strong system separates" in verified
    assert "- Leader: `strong` at `0.9475`" in verified
    assert "- Noise floor: `0.9155` (loo)" in verified
    assert "- Margin over floor: `+0.0320`" in verified
    assert "- Minimum detectable effect: `0.0312` (`binomial_approx`)" in verified
    assert "- Threshold applied: `0.0500`" in verified
    assert "- Generators: `5` over `400` items" in verified
    # The one that did not clear the gate must not appear as a finding.
    assert "the median moves the leader" not in verified


def test_a_non_accepted_row_lands_under_unresolved_with_its_reason(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    rows = _rows(
        ctx,
        [
            ("the strong system separates", "ACCEPT", ACCEPT_METRICS),
            ("the median moves the leader", "MARGINAL", MARGINAL_METRICS),
        ],
    )
    _register_gate(ctx, rows)
    WriterSegment().run(ctx)

    draft = (ctx.run_dir / "draft.md").read_text(encoding="utf-8")
    _verified, unresolved = _sections(draft)
    assert "the median moves the leader" in unresolved
    assert "`MARGINAL`" in unresolved
    assert "margin +0.0285 is inside the resolution bound 0.0357" in unresolved


def test_a_marginal_only_payload_renders_an_empty_verified_section(tmp_path: Path) -> None:
    # ⑤ refuses a MARGINAL-only family, so the live chain cannot reach ⑥ with
    # nothing accepted. ⑥ must still render that shape rather than crash.
    ctx = make_context(tmp_path)
    rows = _rows(ctx, [("only marginal", "MARGINAL", MARGINAL_METRICS)])
    _register_gate(ctx, rows)
    WriterSegment().run(ctx)

    draft = (ctx.run_dir / "draft.md").read_text(encoding="utf-8")
    verified, unresolved = _sections(draft)
    assert "_None. No claim cleared the gate._" in verified
    assert "only marginal" in unresolved


def test_the_writer_payload_lists_the_claim_ids_it_rendered(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    rows = _rows(
        ctx,
        [
            ("the strong system separates", "ACCEPT", ACCEPT_METRICS),
            ("the median moves the leader", "MARGINAL", MARGINAL_METRICS),
        ],
    )
    _register_gate(ctx, rows)
    artifact = WriterSegment().run(ctx)

    payload = json.loads((ctx.run_dir / "artifacts" / "writer.json").read_text(encoding="utf-8"))
    assert payload["claim_ids"] == [row.claim_id for row in rows]
    assert payload["n_verified"] == 1
    assert payload["n_unresolved"] == 1
    assert artifact.claim_ids == [row.claim_id for row in rows]
