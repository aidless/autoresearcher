"""Context construction shared by the segment tests."""

from __future__ import annotations

from pathlib import Path

from autoresearcher.claim import ClaimLedger
from autoresearcher.segments.base import SegmentContext


def make_context(tmp_path: Path, topic: str = "a topic") -> SegmentContext:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return SegmentContext(
        run_dir=run_dir,
        topic=topic,
        ledger=ClaimLedger(run_dir / "claim_ledger.jsonl"),
        fingerprint="deadbeef",
    )
