"""The segment protocol, the run context, and the chain that stops on refusal.

A segment may read an earlier segment's output in exactly one way: through the
artifact that segment wrote. There is no shared mutable state, no accessor that
returns a neighbour's result, and no path from a later segment back into an
earlier one. That is the design's "闸门即通路" stated as an API, and
``tests/test_gate_is_the_only_passage.py`` holds it to it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from autoresearcher.artifact import SegmentArtifact, SegmentStatus, read_artifact, write_artifact
from autoresearcher.claim import ClaimLedger


class MissingUpstream(RuntimeError):
    """A segment tried to read an input that does not exist."""


class PayloadRefused(RuntimeError):
    """A segment tried to read an input whose producer refused."""


@dataclass
class SegmentContext:
    """What a segment knows: where the run lives, and what ran before it."""

    run_dir: Path
    topic: str
    ledger: ClaimLedger
    fingerprint: str
    upstream: dict[str, SegmentArtifact] = field(default_factory=dict)

    def upstream_payload(self, segment_id: str) -> dict:
        """Read an earlier segment's payload, or refuse.

        A missing artifact raises instead of returning ``{}``: a segment that
        proceeds without its input has bypassed the gate, which is the one thing
        this design exists to prevent. Failing loudly is the feature.
        """
        artifact = self.upstream.get(segment_id)
        if artifact is None:
            raise MissingUpstream(f"no {segment_id!r} artifact in this run")
        if artifact.status is SegmentStatus.REFUSED:
            raise PayloadRefused(
                f"{segment_id!r} refused, so its output is not available: "
                f"{artifact.refusal_reason()}"
            )
        return read_payload(self, artifact.artifact_path)


class Segment(Protocol):
    """One stage of the pipeline."""

    segment_id: str

    def run(self, ctx: SegmentContext) -> SegmentArtifact: ...


@dataclass(frozen=True)
class ChainResult:
    artifacts: list[SegmentArtifact]
    stopped_at: str | None = None
    refusal: str = ""

    @property
    def completed(self) -> bool:
        return self.stopped_at is None

    def status_of(self, segment_id: str) -> SegmentStatus | None:
        for artifact in self.artifacts:
            if artifact.segment_id == segment_id:
                return artifact.status
        return None


def write_payload(ctx: SegmentContext, name: str, data: object) -> str:
    """Write a segment's payload and return the path the artifact points at.

    The returned path is relative to the run directory. An absolute path here
    would put the author's home directory into the ledger, and the ledger is
    meant to be published.
    """
    relative = (Path("artifacts") / name).as_posix()
    target = ctx.run_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return relative


def read_payload(ctx: SegmentContext, relative: str) -> dict:
    return json.loads(_resolve_relative(ctx, relative).read_text(encoding="utf-8"))


def read_evidence_ref(ctx: SegmentContext, ref: str) -> tuple[dict, int]:
    """Read a ``path:line`` anchor and return the payload and the line it names.

    Anchors are relative for the same reason payload paths are, and the check is
    here rather than at each call site so that no segment can opt out of it.
    """
    if ":" not in ref:
        raise ValueError(f"evidence ref {ref!r} is not a path:line anchor")
    path_part, line_part = ref.rsplit(":", 1)
    return read_payload(ctx, path_part), int(line_part)


def _resolve_relative(ctx: SegmentContext, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError(
            f"artifact path {relative!r} must be relative to the run directory; "
            "an absolute path would publish the machine that produced it"
        )
    return ctx.run_dir / candidate


def run_chain(
    segments: Sequence[Segment], ctx: SegmentContext, *, envelopes_dir: Path
) -> ChainResult:
    """Run segments in order and stop at the first refusal.

    Stopping is not error handling. A refused segment has told us what it could
    not support, and everything after it would be built on a number nobody
    stands behind.
    """
    artifacts: list[SegmentArtifact] = []
    for segment in segments:
        artifact = write_artifact(segment.run(ctx), envelopes_dir / f"{segment.segment_id}.json")
        ctx.upstream[segment.segment_id] = artifact
        artifacts.append(artifact)
        if artifact.status is SegmentStatus.REFUSED:
            return ChainResult(
                artifacts=artifacts,
                stopped_at=segment.segment_id,
                refusal=artifact.refusal_reason(),
            )
    return ChainResult(artifacts=artifacts)


__all__ = [
    "ChainResult",
    "MissingUpstream",
    "PayloadRefused",
    "Segment",
    "SegmentContext",
    "read_artifact",
    "read_evidence_ref",
    "read_payload",
    "run_chain",
    "write_payload",
]
