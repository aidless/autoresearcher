from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arx.audit.verdict import Verdict
from arx.literature.search import Paper, SearchOutcome
from arx.llm import NullLLM
from tests_helpers import make_context
from tests_segments_experiment_helpers import succeeded_hypotheses, template

from autoresearcher.config import offline_config
from autoresearcher.segments.base import run_chain
from autoresearcher.segments.experiment import ExperimentSegment, TemplateExperimentProvider
from autoresearcher.segments.gate import METRIC_KEYS, GateSegment, adjudicate
from autoresearcher.segments.hypothesize import HypothesizeSegment
from autoresearcher.segments.issue import IssueSegment
from autoresearcher.segments.literature import LiteratureSegment


def _searcher(topic: str, limit: int) -> SearchOutcome:
    return SearchOutcome(papers=[Paper(title="t", year=2024)], sources_ok=["fixture"])


def _through_gate(tmp_path: Path, *, generators: int = 5):
    ctx = make_context(tmp_path)
    gate = GateSegment(config=offline_config(ctx.run_dir))
    chain = run_chain(
        [
            IssueSegment(),
            LiteratureSegment(searcher=_searcher, source="fixture"),
            HypothesizeSegment(llm=NullLLM("dry-run"), seed_hypotheses=succeeded_hypotheses()),
            ExperimentSegment(
                provider=TemplateExperimentProvider(
                    template=template(), fields={"generators": generators}
                ),
                config=offline_config(ctx.run_dir),
            ),
            gate,
        ],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )
    return ctx, chain, gate


def test_the_three_hypotheses_get_the_measured_verdicts(tmp_path: Path) -> None:
    ctx, chain, _ = _through_gate(tmp_path)
    assert chain.completed is True
    assert [row.gate_decision for row in ctx.ledger.rows()] == ["ACCEPT", "ACCEPT", "MARGINAL"]


def test_the_pre_registrations_precede_every_claim_they_govern(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    kinds = [record["kind"] for record in ctx.ledger.as_records()]
    first_claim = kinds.index("claim")
    assert kinds[first_claim:] == ["claim"] * (len(kinds) - first_claim)
    assert kinds[:first_claim].count("pre_register") == 3


def test_the_first_claim_carries_the_floor_the_margin_and_the_method(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    metrics = ctx.ledger.rows()[0].metrics
    assert metrics["verdict"] == Verdict.READABLE.value
    assert metrics["leader_system"] == "strong"
    # leader_score and floor_estimate land on exact floats; margin and mde are
    # differences of scores, so they are compared at 6 dp.
    assert metrics["leader_score"] == 0.9475
    assert metrics["floor_estimate"] == 0.9155
    assert round(metrics["margin"], 6) == 0.032
    assert round(metrics["mde"], 6) == 0.031242
    assert metrics["mde_method"] == "binomial_approx"
    assert metrics["n_items"] == 400
    assert metrics["n_generators"] == 5
    assert metrics["k_max"] == 7
    assert metrics["alpha"] == 0.05
    assert metrics["power"] == 0.8
    assert metrics["delta_declared"] == 0.02
    assert metrics["prereg_ok"] is True
    assert metrics["gate_allowed"] is True


def test_the_marginal_claim_says_so_in_words(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    marginal = ctx.ledger.rows()[2]
    assert marginal.gate_decision == "MARGINAL"
    assert marginal.metrics["verdict"] == Verdict.MARGINAL.value
    assert round(marginal.metrics["margin"], 6) == 0.0285
    assert round(marginal.metrics["mde"], 6) == 0.035741
    assert any("resolution bound" in reason for reason in marginal.metrics["reasons"])


def test_every_claim_row_has_the_same_metric_keys(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    for row in ctx.ledger.rows():
        assert tuple(row.metrics) == METRIC_KEYS


def test_every_claim_anchors_its_evidence_and_the_anchor_resolves(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    for row in ctx.ledger.rows():
        path_part, line = row.evidence_ref.rsplit(":", 1)
        assert line == "1"
        assert not Path(path_part).is_absolute()
        assert (ctx.run_dir / path_part).exists()


def test_the_evidence_sha_is_the_sha_of_the_evidence_file(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    row = ctx.ledger.rows()[0]
    path = ctx.run_dir / row.evidence_ref.rsplit(":", 1)[0]
    assert row.metrics["evidence_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_two_generators_are_undecidable_and_the_chain_stops(tmp_path: Path) -> None:
    ctx, chain, _ = _through_gate(tmp_path, generators=2)
    assert chain.completed is False
    assert chain.stopped_at == "gate"
    assert "no claim cleared the gate" in chain.refusal
    rows = ctx.ledger.rows()
    assert [row.gate_decision for row in rows] == ["UNDECIDABLE"] * 3
    assert rows[0].metrics["verdict"] == Verdict.UNDECIDABLE.value
    assert rows[0].metrics["reasons"] == ["floor_degenerate"]
    assert rows[0].metrics["margin"] is None
    assert rows[0].metrics["prereg_ok"] is True


def test_a_claim_can_be_redecided_from_the_evidence_alone(tmp_path: Path) -> None:
    """``adjudicate`` is reachable from an evidence file and the ledger, and nothing else.

    This is what makes ``researcher recompute`` a real recomputation rather than
    a second implementation that happens to agree.
    """
    ctx, _, _ = _through_gate(tmp_path)
    evidence = json.loads((ctx.run_dir / "evidence/experiment-000.json").read_text(encoding="utf-8"))
    decision = adjudicate(
        evidence=evidence,
        records=ctx.ledger.as_records(),
        config=offline_config(ctx.run_dir),
        evidence_sha256="whatever",
    )
    assert decision.gate_decision == "ACCEPT"
    assert decision.k_max == 7
    assert decision.prereg_ok is True
