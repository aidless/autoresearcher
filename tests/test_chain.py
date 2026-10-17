from __future__ import annotations

from pathlib import Path

import pytest
from tests_helpers import make_context

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import (
    ChainResult,
    MissingUpstream,
    PayloadRefused,
    SegmentContext,
    read_evidence_ref,
    run_chain,
    write_payload,
)


class _Stub:
    def __init__(self, segment_id: str, status: SegmentStatus = SegmentStatus.OK) -> None:
        self.segment_id = segment_id
        self.status = status
        self.ran = False

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        self.ran = True
        ref = write_payload(ctx, f"{self.segment_id}.json", {"from": self.segment_id})
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=self.status,
            artifact_path=ref,
            claim_ids=[],
            gate_summary=(
                {"reason": "deliberate refusal"} if self.status is SegmentStatus.REFUSED else {}
            ),
            run_fingerprint=ctx.fingerprint,
        )


def test_the_chain_stops_at_a_refusal(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    first, second, third = _Stub("a"), _Stub("b", SegmentStatus.REFUSED), _Stub("c")
    result = run_chain([first, second, third], ctx, envelopes_dir=ctx.run_dir / "segments")
    assert isinstance(result, ChainResult)
    assert result.completed is False
    assert result.stopped_at == "b"
    assert result.refusal == "deliberate refusal"
    assert third.ran is False


def test_a_completed_chain_runs_every_segment(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    segments = [_Stub("a"), _Stub("b"), _Stub("c")]
    result = run_chain(segments, ctx, envelopes_dir=ctx.run_dir / "segments")
    assert result.completed is True
    assert result.stopped_at is None
    assert [segment.ran for segment in segments] == [True, True, True]


def test_a_downstream_segment_reads_its_upstream_payload(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    run_chain([_Stub("a")], ctx, envelopes_dir=ctx.run_dir / "segments")
    assert ctx.upstream_payload("a") == {"from": "a"}


def test_reading_a_segment_that_never_ran_is_refused(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    with pytest.raises(MissingUpstream, match="no 'gate' artifact"):
        ctx.upstream_payload("gate")


def test_reading_a_refused_segment_is_refused(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    run_chain([_Stub("a", SegmentStatus.REFUSED)], ctx, envelopes_dir=ctx.run_dir / "segments")
    with pytest.raises(PayloadRefused, match="deliberate refusal"):
        ctx.upstream_payload("a")


def test_an_absolute_evidence_ref_is_refused(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    with pytest.raises(ValueError, match="relative"):
        read_evidence_ref(ctx, "/home/someone/run/evidence/experiment-000.json:1")


def test_read_evidence_ref_resolves_and_reports_the_line(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    target = ctx.run_dir / "evidence" / "experiment-000.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"ok": true}\n', encoding="utf-8")
    payload, line = read_evidence_ref(ctx, "evidence/experiment-000.json:1")
    assert payload == {"ok": True}
    assert line == 1
