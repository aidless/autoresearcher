"""The design's central invariant, as five tests.

If this file passes for the wrong reason the project has failed: the point is
not that a later segment *declines* to run after a refusal, it is that it
*cannot* — there is no object in its hands to run on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from tests_helpers import make_context

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.config import offline_config
from autoresearcher.dryrun import offline_components
from autoresearcher.pipeline import RunConfig, run_pipeline
from autoresearcher.segments.base import (
    MissingUpstream,
    PayloadRefused,
    SegmentContext,
    run_chain,
    write_payload,
)
from autoresearcher.segments.experiment import ExperimentSegment
from autoresearcher.segments.gate import GateSegment
from autoresearcher.segments.hypothesize import HypothesizeSegment
from autoresearcher.segments.issue import IssueSegment
from autoresearcher.segments.literature import LiteratureSegment


@dataclass
class _ProbeSegment:
    """Stands in for ⑥ to observe what actually reached it.

    It records the accepted claims it can read *and* keeps a payload, so a
    downstream refusal can be distinguished from a probe that simply had
    nothing to say.
    """

    segment_id: str = "probe"
    ran: bool = False
    n_accepted: int = -1

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        self.ran = True
        self.n_accepted = len(ctx.ledger.accepted())
        ref = write_payload(ctx, "probe.json", {"n_accepted": self.n_accepted})
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=ref,
            claim_ids=[row.claim_id for row in ctx.ledger.accepted()],
            gate_summary={"n_accepted": self.n_accepted},
            run_fingerprint=ctx.fingerprint,
        )


def _chain(tmp_path: Path, *, generators: int, hypotheses: list | None):
    """Build the five segments M0 has, plus a probe sitting where ⑥ will go."""
    ctx = make_context(tmp_path, topic="does the gate hold")
    config = offline_config(ctx.run_dir)
    parts = offline_components(generators=generators)
    if hypotheses is not None:
        parts.seed_hypotheses = list(hypotheses)
    probe = _ProbeSegment()
    result = run_chain(
        [
            IssueSegment(falsified_by="held-out generator", gate_flags=config.ledger_flags()),
            LiteratureSegment(searcher=parts.searcher, source="fixture"),
            HypothesizeSegment(n=3, llm=parts.llm, seed_hypotheses=parts.seed_hypotheses),
            ExperimentSegment(provider=parts.provider, config=config),
            GateSegment(config=config),
            probe,
        ],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )
    return ctx, result, probe


def test_a_readable_run_reaches_the_segment_after_the_gate(tmp_path: Path) -> None:
    ctx, result, probe = _chain(tmp_path, generators=5, hypotheses=None)
    assert result.completed is True
    assert result.stopped_at is None
    assert probe.ran is True
    # Two of the three fixture hypotheses are READABLE; the third is MARGINAL
    # and travels with its label. This is D1: a MARGINAL claim does not stop
    # the chain, it arrives carrying its verdict.
    assert probe.n_accepted == 2
    assert ctx.upstream_payload("gate")["n_accept"] == 2


def test_a_gate_that_accepts_nothing_stops_before_the_next_segment(tmp_path: Path) -> None:
    ctx, result, probe = _chain(tmp_path, generators=2, hypotheses=None)
    assert result.stopped_at == "gate"
    assert result.completed is False
    assert probe.ran is False
    rows = ctx.ledger.rows()
    assert [row.gate_decision for row in rows] == ["UNDECIDABLE"] * 3
    assert [row.metrics["verdict"] for row in rows] == ["UNDECIDABLE"] * 3


def test_a_segment_that_never_ran_has_an_unreadable_output(tmp_path: Path) -> None:
    ctx, result, probe = _chain(tmp_path, generators=2, hypotheses=None)
    assert result.stopped_at == "gate"
    # The gate wrote its payload, so this is not a missing file: the output
    # exists and is refused. The distinction is the point.
    assert (ctx.run_dir / "artifacts" / "gate.json").exists()
    with pytest.raises(PayloadRefused, match="no claim cleared the gate"):
        ctx.upstream_payload("gate")


def test_a_hypothesisless_run_reaches_no_gate_and_writes_no_claim(tmp_path: Path) -> None:
    ctx, result, probe = _chain(tmp_path, generators=5, hypotheses=[])
    assert result.stopped_at == "hypothesize"
    assert "nothing to test" in result.refusal
    assert probe.ran is False
    assert ctx.ledger.rows() == []
    with pytest.raises(MissingUpstream, match="no 'experiment' artifact"):
        ctx.upstream_payload("experiment")


def test_the_pipeline_reports_a_refusal_as_a_status_not_a_crash(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(
        RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True, generators=2)
    )
    assert outcome.status == "REFUSED"
    assert outcome.chain.completed is False
    assert outcome.chain.stopped_at == "gate"
    # Three claims were written and all three were judged UNDECIDABLE. Counting
    # them is not failure; handing them downstream as if they were readable is.
    assert outcome.n_claims == 3
    assert outcome.claim_ledger.exists()
