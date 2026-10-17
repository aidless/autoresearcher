from __future__ import annotations

from pathlib import Path

from arx.hypothesis import Hypothesis
from arx.literature.search import SearchOutcome
from arx.llm import NullLLM
from tests_helpers import make_context

from autoresearcher.artifact import SegmentStatus
from autoresearcher.segments.base import ChainResult, run_chain
from autoresearcher.segments.hypothesize import HypothesizeSegment
from autoresearcher.segments.literature import LiteratureSegment


def _seeded(*texts: str) -> list[Hypothesis]:
    return [
        Hypothesis(
            text=text,
            rationale="",
            origin="manual",
            confidence=0.5,
            expected_effect_se_ratio=0.5,
        )
        for text in texts
    ]


def _searcher(topic: str, max_results: int) -> SearchOutcome:
    return SearchOutcome(papers=[], sources_ok=["fixture"])


def _chain_to_hypothesize(ctx, hypothesize) -> ChainResult:
    """Run ② then ③, so ③'s upstream read has an artifact to find.

    ③ reads the literature artifact through ``ctx.upstream_payload``, and the
    chain is what writes the artifact into the context. Running ③ on a bare
    context would exercise the missing-artifact path, not the one under test.
    """
    return run_chain(
        [LiteratureSegment(searcher=_searcher, source="fixture"), hypothesize],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )


def test_a_seeded_run_proposes_without_consulting_a_model(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    segment = HypothesizeSegment(llm=NullLLM("dry-run"), seed_hypotheses=_seeded("h one"))
    result = _chain_to_hypothesize(ctx, segment)
    assert result.artifacts[-1].status is SegmentStatus.OK
    payload = ctx.upstream_payload("hypothesize")
    assert payload["llm"] == "none"
    assert payload["n_kept"] == 1
    assert payload["kept"][0]["expected_effect_se_ratio"] == 0.5


def test_duplicates_are_dropped_and_the_drop_is_recorded(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    segment = HypothesizeSegment(
        llm=NullLLM("dry-run"),
        seed_hypotheses=_seeded("a floor bounds a board", "a floor bounds a board"),
    )
    assert _chain_to_hypothesize(ctx, segment).artifacts[-1].status is SegmentStatus.OK
    payload = ctx.upstream_payload("hypothesize")
    assert payload["n_proposed"] == 2
    assert payload["n_kept"] == 1
    assert payload["dropped"][0]["duplicates"] == ["a floor bounds a board"]


def test_no_hypothesis_refuses_rather_than_cascading_emptiness(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    result = _chain_to_hypothesize(ctx, HypothesizeSegment(llm=NullLLM("dry-run")))
    artifact = result.artifacts[-1]
    assert result.stopped_at == "hypothesize"
    assert artifact.status is SegmentStatus.REFUSED
    assert "nothing to test" in artifact.refusal_reason()
    assert artifact.claim_ids == []
    assert ctx.ledger.rows() == []


def test_a_single_hypothesis_is_not_dropped_as_its_own_duplicate(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    segment = HypothesizeSegment(llm=NullLLM("dry-run"), seed_hypotheses=_seeded("only one"))
    assert _chain_to_hypothesize(ctx, segment).artifacts[-1].status is SegmentStatus.OK
