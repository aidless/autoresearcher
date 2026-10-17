"""The segment transport: what one segment hands the next.

Two fields carry the design's weight. ``status`` is what makes the chain stop;
``artifact_path`` is the only address a later segment may read its input from,
which is why it is stored relative to the run directory — see
``segments.base.read_payload``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class SegmentStatus(StrEnum):
    OK = "OK"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class SegmentArtifact:
    """One segment's envelope."""

    segment_id: str
    status: SegmentStatus
    artifact_path: str
    claim_ids: list[str] = field(default_factory=list)
    gate_summary: dict = field(default_factory=dict)
    run_fingerprint: str = ""

    def __post_init__(self) -> None:
        if self.status is SegmentStatus.REFUSED and not self.gate_summary.get("reason"):
            raise ValueError(
                "a REFUSED artifact must carry gate_summary['reason']: a refusal "
                "that cannot be explained cannot be reported"
            )

    def refusal_reason(self) -> str:
        if self.status is not SegmentStatus.REFUSED:
            return ""
        return str(self.gate_summary.get("reason", ""))

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "status": self.status.value,
            "artifact_path": self.artifact_path,
            "claim_ids": list(self.claim_ids),
            "gate_summary": dict(self.gate_summary),
            "run_fingerprint": self.run_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SegmentArtifact:
        return cls(
            segment_id=str(data["segment_id"]),
            status=SegmentStatus(data["status"]),
            artifact_path=str(data["artifact_path"]),
            claim_ids=list(data.get("claim_ids") or []),
            gate_summary=dict(data.get("gate_summary") or {}),
            run_fingerprint=str(data.get("run_fingerprint", "")),
        )


def write_artifact(artifact: SegmentArtifact, path: Path) -> SegmentArtifact:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return artifact


def read_artifact(path: Path) -> SegmentArtifact:
    return SegmentArtifact.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


__all__ = ["SegmentArtifact", "SegmentStatus", "read_artifact", "write_artifact"]
