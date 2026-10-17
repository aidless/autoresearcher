from __future__ import annotations

from pathlib import Path

import pytest

from autoresearcher.artifact import SegmentArtifact, SegmentStatus, read_artifact, write_artifact


def test_a_refused_artifact_must_state_a_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        SegmentArtifact(
            segment_id="gate",
            status=SegmentStatus.REFUSED,
            artifact_path="artifacts/gate.json",
            claim_ids=["gate:000"],
            gate_summary={"claims": 1},
            run_fingerprint="abc",
        )


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    artifact = SegmentArtifact(
        segment_id="gate",
        status=SegmentStatus.REFUSED,
        artifact_path="artifacts/gate.json",
        claim_ids=["gate:000"],
        gate_summary={"claims": 1, "reason": "no claim cleared the gate"},
        run_fingerprint="abc",
    )
    stored = write_artifact(artifact, tmp_path / "segments" / "gate.json")
    assert read_artifact(tmp_path / "segments" / "gate.json") == stored
    assert stored.refusal_reason() == "no claim cleared the gate"


def test_an_ok_artifact_needs_no_reason() -> None:
    artifact = SegmentArtifact(
        segment_id="issue",
        status=SegmentStatus.OK,
        artifact_path="artifacts/issue.json",
        claim_ids=[],
        gate_summary={"claims": 0},
        run_fingerprint="abc",
    )
    assert artifact.refusal_reason() == ""
