"""① — fix the topic, and state up front what would falsify it.

Nothing here is measured, so nothing here can produce a claim. That is why
``claim_ids`` is empty rather than why a decision is missing: a topic is not a
finding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import SegmentContext, write_payload


@dataclass
class IssueSegment:
    segment_id: str = "issue"
    falsified_by: str = ""
    gate_flags: dict = field(default_factory=dict)

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        payload = write_payload(
            ctx,
            "issue.json",
            {
                "topic": ctx.topic,
                "falsified_by": self.falsified_by,
                "gate_flags": dict(self.gate_flags),
                "run_fingerprint": ctx.fingerprint,
            },
        )
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=payload,
            claim_ids=[],
            gate_summary={
                "claims": 0,
                "note": "a topic is not a measurement, so this segment writes no claim",
            },
            run_fingerprint=ctx.fingerprint,
        )


__all__ = ["IssueSegment"]
