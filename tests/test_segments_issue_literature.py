from __future__ import annotations

from pathlib import Path

from arx.literature.search import Paper, SearchOutcome
from tests_helpers import make_context

from autoresearcher.artifact import SegmentStatus
from autoresearcher.segments.base import run_chain
from autoresearcher.segments.issue import IssueSegment
from autoresearcher.segments.literature import LiteratureSegment


def _searcher(topic: str, max_results: int) -> SearchOutcome:
    assert max_results == 20
    return SearchOutcome(
        papers=[Paper(title="On the readability of leaderboards", year=2024, abstract="a")],
        sources_ok=["fixture"],
    )


def test_issue_writes_no_claim(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    result = run_chain(
        [IssueSegment(falsified_by="a claim that survives a floor test", gate_flags={})],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )
    artifact = result.artifacts[-1]
    assert artifact.status is SegmentStatus.OK
    assert artifact.claim_ids == []
    assert ctx.ledger.rows() == []
    assert ctx.upstream_payload("issue")["topic"] == "a topic"


def test_literature_records_what_it_consulted(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    chain = run_chain(
        [IssueSegment(), LiteratureSegment(searcher=_searcher, source="fixture")],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )
    assert chain.completed is True
    payload = ctx.upstream_payload("literature")
    assert payload["source"] == "fixture"
    assert payload["sources_ok"] == ["fixture"]
    assert [paper["title"] for paper in payload["papers"]] == ["On the readability of leaderboards"]
    assert payload["papers"][0]["abstract"] == "a"
