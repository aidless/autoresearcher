"""Wire the five segments into one run.

The pipeline is short on purpose. Everything interesting — when to stop, what a
claim has to carry, how a decision is recomputed — lives in the segment that owns
it, and this module only decides the order and where the files go.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from arx.config import AgentConfig

from autoresearcher.claim import ClaimLedger
from autoresearcher.config import offline_config
from autoresearcher.dryrun import OfflineComponents, offline_components
from autoresearcher.fingerprint import environment_fingerprint, fingerprint_digest
from autoresearcher.segments.base import ChainResult, SegmentContext, run_chain
from autoresearcher.segments.experiment import ExperimentSegment
from autoresearcher.segments.gate import GateSegment
from autoresearcher.segments.hypothesize import HypothesizeSegment
from autoresearcher.segments.issue import IssueSegment
from autoresearcher.segments.literature import LiteratureSegment


@dataclass
class RunConfig:
    topic: str
    run_dir: Path
    dry_run: bool = False
    n_hypotheses: int = 3
    falsified_by: str = ""
    generators: int = 5


@dataclass
class PipelineOutcome:
    run_dir: Path
    claim_ledger: Path
    chain: ChainResult
    fingerprint_digest: str
    records: list[dict]

    @property
    def status(self) -> str:
        return "OK" if self.chain.completed else "REFUSED"

    @property
    def n_claims(self) -> int:
        return sum(len(artifact.claim_ids) for artifact in self.chain.artifacts)

    def chain_records(self) -> list[dict]:
        """The ledger records as they were when the run finished."""
        return list(self.records)


def run_pipeline(cfg: RunConfig, *, components: OfflineComponents | None = None) -> PipelineOutcome:
    """Run one topic through the chain of segments M0 has."""
    run_dir = Path(cfg.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    config: AgentConfig = offline_config(run_dir)
    fingerprint = environment_fingerprint(run_dir=run_dir)
    digest = fingerprint_digest(fingerprint)
    (run_dir / "env_fingerprint.json").write_text(
        json.dumps(fingerprint, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    ledger = ClaimLedger(run_dir / "claim_ledger.jsonl")
    ledger.append_record(
        "run_start",
        {
            "topic": cfg.topic,
            "dry_run": cfg.dry_run,
            "config": config.ledger_flags(),
            "run_fingerprint": digest,
        },
    )

    parts = components or offline_components(generators=cfg.generators)
    ctx = SegmentContext(run_dir=run_dir, topic=cfg.topic, ledger=ledger, fingerprint=digest)
    chain = run_chain(
        [
            IssueSegment(falsified_by=cfg.falsified_by, gate_flags=config.ledger_flags()),
            LiteratureSegment(
                searcher=parts.searcher if cfg.dry_run else None,
                source="fixture" if cfg.dry_run else "live",
            ),
            HypothesizeSegment(
                n=cfg.n_hypotheses,
                llm=parts.llm,
                seed_hypotheses=parts.seed_hypotheses if cfg.dry_run else [],
            ),
            ExperimentSegment(provider=parts.provider, config=config),
            GateSegment(config=config),
        ],
        ctx,
        envelopes_dir=run_dir / "segments",
    )
    ledger.append_record(
        "run_end",
        {
            "stopped_at": chain.stopped_at,
            "refusal": chain.refusal,
            "segments": [
                {"segment_id": artifact.segment_id, "status": artifact.status.value}
                for artifact in chain.artifacts
            ],
        },
    )
    return PipelineOutcome(
        run_dir=run_dir,
        claim_ledger=ledger.path,
        chain=chain,
        fingerprint_digest=digest,
        records=ledger.as_records(),
    )


__all__ = ["PipelineOutcome", "RunConfig", "run_pipeline"]
