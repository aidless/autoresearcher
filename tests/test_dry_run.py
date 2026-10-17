from __future__ import annotations

import json
from pathlib import Path

from autoresearcher.dryrun import offline_components
from autoresearcher.fingerprint import fingerprint_digest
from autoresearcher.pipeline import RunConfig, run_pipeline


def test_a_dry_run_completes_every_segment_it_has(tmp_path: Path) -> None:
    outcome = run_pipeline(
        RunConfig(topic="does a floor bound a leader", run_dir=tmp_path / "run", dry_run=True)
    )
    assert outcome.chain.completed is True
    assert [artifact.segment_id for artifact in outcome.chain.artifacts] == [
        "issue",
        "literature",
        "hypothesize",
        "experiment",
        "gate",
    ]
    assert [artifact.status.value for artifact in outcome.chain.artifacts] == ["OK"] * 5


def test_the_run_directory_holds_the_products(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    assert (run_dir / "claim_ledger.jsonl").exists()
    assert (run_dir / "env_fingerprint.json").exists()
    assert len(list((run_dir / "segments").glob("*.json"))) == 5
    assert len(list((run_dir / "artifacts").glob("*.json"))) == 5
    assert len(list((run_dir / "evidence").glob("experiment-*.json"))) == 3
    assert len(list(run_dir.glob("experiment-*.py"))) == 3


def test_the_fingerprint_in_the_ledger_matches_the_one_on_disk(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    fingerprint = json.loads((run_dir / "env_fingerprint.json").read_text(encoding="utf-8"))
    assert outcome.fingerprint_digest == fingerprint_digest(fingerprint)
    assert outcome.chain.artifacts[0].run_fingerprint == outcome.fingerprint_digest
    start = [record for record in outcome.chain_records() if record["kind"] == "run_start"][0]
    assert start["payload"]["run_fingerprint"] == outcome.fingerprint_digest


def test_the_run_consulted_no_model(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    hypothesize = json.loads((run_dir / "artifacts/hypothesize.json").read_text(encoding="utf-8"))
    assert hypothesize["llm"] == "none"


def test_the_components_can_be_built_without_a_pipeline(tmp_path: Path) -> None:
    components = offline_components(generators=5)
    assert components.llm.available is False
    assert len(components.seed_hypotheses) == 3
    assert components.seed_hypotheses[0].confidence == 0.6
