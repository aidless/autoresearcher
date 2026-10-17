from __future__ import annotations

import json
from pathlib import Path

import pytest
from arx.hypothesis import Hypothesis
from arx.literature.search import Paper, SearchOutcome
from arx.llm import NullLLM
from tests_helpers import make_context

import autoresearcher
from autoresearcher.config import offline_config
from autoresearcher.segments.base import run_chain
from autoresearcher.segments.experiment import ExperimentSegment, TemplateExperimentProvider
from autoresearcher.segments.hypothesize import HypothesizeSegment
from autoresearcher.segments.issue import IssueSegment
from autoresearcher.segments.literature import LiteratureSegment

FIXTURES = Path(autoresearcher.__file__).parent / "fixtures"


def _searcher(topic: str, limit: int) -> SearchOutcome:
    return SearchOutcome(papers=[Paper(title="t", year=2024)], sources_ok=["fixture"])


def _hypothesis() -> Hypothesis:
    return Hypothesis(
        text="a floor bounds the leader",
        rationale="",
        origin="manual",
        confidence=0.5,
        expected_effect_se_ratio=0.5,
    )


def _template() -> str:
    return (FIXTURES / "dry_run_experiment.py.in").read_text(encoding="utf-8")


def _run_through_experiment(tmp_path: Path, *, generators: int = 5):
    ctx = make_context(tmp_path)
    provider = TemplateExperimentProvider(template=_template(), fields={"generators": generators})
    chain = run_chain(
        [
            IssueSegment(),
            LiteratureSegment(searcher=_searcher, source="fixture"),
            HypothesizeSegment(llm=NullLLM("dry-run"), seed_hypotheses=[_hypothesis()]),
            ExperimentSegment(provider=provider, config=offline_config(ctx.run_dir)),
        ],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )
    return ctx, chain


def test_the_pre_registration_is_written_and_nothing_else_is(tmp_path: Path) -> None:
    ctx, chain = _run_through_experiment(tmp_path)
    assert chain.completed is True
    records = ctx.ledger.as_records()
    assert [record["kind"] for record in records] == ["pre_register"]
    prereg = records[0]["payload"]
    assert prereg["k_max"] == 8
    assert prereg["hypothesis"] == "a floor bounds the leader"
    assert prereg["alpha"] == 0.05
    assert len(prereg["script_sha256"]) == 64
    assert ctx.ledger.rows() == []


def test_the_evidence_records_the_file_that_ran(tmp_path: Path) -> None:
    ctx, _ = _run_through_experiment(tmp_path)
    runs = ctx.upstream_payload("experiment")["runs"]
    assert len(runs) == 1
    assert runs[0]["hypothesis"] == "a floor bounds the leader"
    assert runs[0]["evidence_ref"] == "evidence/experiment-000.json:1"
    assert runs[0]["k_max"] == 8
    evidence = json.loads((ctx.run_dir / "evidence/experiment-000.json").read_text(encoding="utf-8"))
    result = evidence["result"]
    assert result["returncode"] == 0
    assert result["timed_out"] is False
    assert result["script_sha256"] == runs[0]["script_sha256"]
    blob = json.loads(result["stdout"].strip().splitlines()[-1])
    assert len(blob["votes"]) == 5
    assert set(blob["scores"]) == {"strong", "weak"}


def test_no_entrypoint_is_recorded_as_untested_not_replaced(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)

    class _Empty:
        name = "empty"

        def provide(self, hypothesis: Hypothesis):
            return None

    chain = run_chain(
        [
            IssueSegment(),
            LiteratureSegment(searcher=_searcher, source="fixture"),
            HypothesizeSegment(llm=NullLLM("dry-run"), seed_hypotheses=[_hypothesis()]),
            ExperimentSegment(provider=_Empty(), config=offline_config(ctx.run_dir)),
        ],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )
    assert chain.completed is True
    runs = ctx.upstream_payload("experiment")["runs"]
    assert runs[0]["status"] == "no_entrypoint"
    assert (ctx.run_dir / "evidence/experiment-000.json").exists() is False


def test_a_provider_is_required(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    with pytest.raises(ValueError, match="requires a provider"):
        ExperimentSegment().run(ctx)
