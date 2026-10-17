"""② — sweep the literature and record what came back.

This segment transports, it does not judge: it has no gate, and it returns OK as
long as it can state honestly where its papers came from. An empty sweep is
recorded as an empty sweep rather than padded, which is what lets ③ be judged on
what it was actually given.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from arx.literature.search import Paper, SearchOutcome, search_all

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import SegmentContext, write_payload

Searcher = Callable[[str, int], SearchOutcome]


@dataclass
class LiteratureSegment:
    segment_id: str = "literature"
    searcher: Searcher | None = None
    max_results: int = 20
    source: str = "live"

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        searcher: Searcher = self.searcher or (
            lambda query, limit: search_all(query, max_results=limit)
        )
        outcome = searcher(ctx.topic, self.max_results)
        payload = write_payload(
            ctx,
            "literature.json",
            {
                "query": ctx.topic,
                "source": self.source,
                "papers": [_as_record(paper) for paper in outcome.papers],
                "sources_ok": list(outcome.sources_ok),
                "sources_failed": dict(outcome.sources_failed),
            },
        )
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=payload,
            claim_ids=[],
            gate_summary={
                "claims": 0,
                "n_papers": len(outcome.papers),
                "sources_ok": list(outcome.sources_ok),
                "sources_failed": dict(outcome.sources_failed),
                "note": "a sweep is not a measurement, so this segment writes no claim",
            },
            run_fingerprint=ctx.fingerprint,
        )


def _as_record(paper: Paper) -> dict:
    """``Paper.to_dict()`` plus the abstract.

    arx's own ``to_dict`` drops the abstract because its report writer does not
    need it; ③ does, and dropping the field here would surface later as a model
    being handed bare titles for no visible reason.
    """
    return {
        "title": paper.title,
        "authors": list(paper.authors),
        "year": paper.year,
        "abstract": paper.abstract,
        "url": paper.url,
        "doi": paper.doi,
        "source": paper.source,
    }


__all__ = ["LiteratureSegment"]
