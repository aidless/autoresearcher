"""③ — turn the sweep into a small set of testable statements.

The hypotheses travel with their two declared priors: ``confidence`` and
``expected_effect_se_ratio``. They are not decoration — ④ feeds them to
``plan_k_max`` to decide how many looks the hypothesis is allowed *before* the
experiment exists, which is the ordering guarantee the gate depends on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from arx.hypothesis import Hypothesis, deduplicate, generate
from arx.llm import ChatModel

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import SegmentContext, write_payload


@dataclass
class HypothesizeSegment:
    segment_id: str = "hypothesize"
    n: int = 3
    llm: ChatModel | None = None
    seed_hypotheses: list[Hypothesis] = field(default_factory=list)
    dedup_threshold: float = 0.6

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        literature = ctx.upstream_payload("literature")
        proposals, consulted = self._propose(ctx, literature)
        result = deduplicate(proposals, threshold=self.dedup_threshold)

        payload = write_payload(
            ctx,
            "hypothesize.json",
            {
                "llm": consulted,
                "n_proposed": len(proposals),
                "n_kept": len(result.kept),
                "kept": [hypothesis.to_dict() for hypothesis in result.kept],
                "dropped": [
                    {"text": hypothesis.text, "duplicates": list(hypothesis.duplicates)}
                    for hypothesis in result.dropped
                ],
            },
        )

        if not result.kept:
            return SegmentArtifact(
                segment_id=self.segment_id,
                status=SegmentStatus.REFUSED,
                artifact_path=payload,
                claim_ids=[],
                gate_summary={
                    "claims": 0,
                    "n_proposed": len(proposals),
                    "reason": (
                        "no hypothesis survived de-duplication, so there is nothing to "
                        "test; a run with nothing to test cannot reach a gate"
                    ),
                },
                run_fingerprint=ctx.fingerprint,
            )

        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=payload,
            claim_ids=[],
            gate_summary={"claims": 0, "n_kept": len(result.kept)},
            run_fingerprint=ctx.fingerprint,
        )

    def _propose(self, ctx: SegmentContext, literature: dict) -> tuple[list[Hypothesis], str]:
        """Either consult the model, or use the seeded hypotheses.

        The consulted name is recorded so a reader can tell a run that consulted
        a model from one that did not. A dry run that consulted nothing must not
        be able to look like one that did.
        """
        if self.llm is not None and getattr(self.llm, "available", False):
            context = "\n".join(
                [
                    "Relevant literature:",
                    *(
                        f"  - {paper['title']} ({paper.get('year') or 'n.d.'})"
                        for paper in literature["papers"][:8]
                    ),
                ]
            )
            return generate(self.llm, ctx.topic, n=self.n, context=context), str(self.llm)
        if not self.seed_hypotheses:
            return [], "none"
        # Round-trip through arx's own serialisation so ``deduplicate`` cannot
        # mutate the caller's objects: it writes ``duplicates`` onto them.
        seeded = [Hypothesis.from_dict(hypothesis.to_dict()) for hypothesis in self.seed_hypotheses]
        return seeded[: self.n], "none"


__all__ = ["HypothesizeSegment"]
