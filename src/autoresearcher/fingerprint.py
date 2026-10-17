"""What a run was produced by, in enough detail to check a rerun against it."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import arx

from autoresearcher import __version__


def environment_fingerprint(*, run_dir: Path | None = None) -> dict:
    """Version-level facts about this interpreter.

    ``run_dir`` is accepted and ignored on purpose: callers have a directory in
    hand when they ask, and the signature records that the path is deliberately
    not part of the fingerprint. Nothing here reads the working directory, the
    user, or the hostname, because a run directory is meant to be publishable.
    """
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.system().lower(),
        "machine": platform.machine(),
        "arx_version": getattr(arx, "__version__", "unknown"),
        "autoresearcher_version": __version__,
    }


def fingerprint_digest(fingerprint: dict) -> str:
    """A stable id for a fingerprint: key order must not change the digest."""
    canonical = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["environment_fingerprint", "fingerprint_digest"]
