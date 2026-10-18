"""⑧ — package a run for submission. It packages; it does not submit.

Determinism is the point: the same run directory packages to the same bytes, so a
stranger can rebuild the archive and compare a sha256 instead of trusting ours.
That is why every member's ``ZipInfo.date_time`` is pinned and the members are
sorted — nothing about the machine or the wall clock may leak into the archive.

No venue, no account, no network: the design's §6 excludes automatic submission.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from autoresearcher.claim import ClaimLedger
from autoresearcher.fingerprint import fingerprint_digest

ARCHIVE_NAME = "submission.zip"

#: The four files a finished run must carry, per D7.
PACKAGED_FILES: tuple[str, ...] = (
    "draft.md",
    "claim_ledger.jsonl",
    "gate_decisions.jsonl",
    "env_fingerprint.json",
)
METADATA_FILE = "submission_metadata.json"

#: The keys a submission's metadata must carry. Frozen by test.
REQUIRED_METADATA_KEYS: tuple[str, ...] = ("title", "authors", "abstract", "artifacts")

#: Pinned so two builds agree byte for byte. 1980-01-01 is zip's own epoch.
PINNED_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def package_run(run_dir: Path, *, metadata: dict | None = None) -> Path:
    """Write ``submission.zip`` and return its path.

    ``metadata`` is an injection point for a caller that already read the run's
    ``submission_metadata.json``; with no argument the run directory's own file
    is used, and a deterministic default derived from the run when there is none.
    """
    run_dir = Path(run_dir)
    meta = metadata if metadata is not None else _run_metadata(run_dir)
    validate_metadata(meta)

    missing = [name for name in PACKAGED_FILES if not (run_dir / name).is_file()]
    if missing:
        raise ValueError(f"cannot package: {', '.join(missing)} missing from {run_dir}")
    metadata_bytes = (json.dumps(meta, indent=2, sort_keys=True) + "\n").encode("utf-8")

    archive = run_dir / ARCHIVE_NAME
    members = {name: (run_dir / name).read_bytes() for name in PACKAGED_FILES}
    members[METADATA_FILE] = metadata_bytes
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=PINNED_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            handle.writestr(info, members[name])
    return archive


def validate_metadata(metadata: dict) -> None:
    """Refuse a metadata file that is missing a key or carries a machine path."""
    missing = [key for key in REQUIRED_METADATA_KEYS if key not in metadata]
    if missing:
        raise ValueError(f"submission metadata is missing required keys {missing}")
    for key, value in metadata.items():
        for text in _strings(value):
            if _is_absolute(text):
                raise ValueError(
                    f"submission metadata field {key!r} carries an absolute path "
                    f"{text!r}; the archive is meant to be publishable"
                )


def _run_metadata(run_dir: Path) -> dict:
    path = run_dir / METADATA_FILE
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return default_metadata(run_dir)


def default_metadata(run_dir: Path) -> dict:
    """Metadata derived from the run, never from the machine.

    The title is the topic the run was started with, and the fingerprint is the
    digest of the run's own ``env_fingerprint.json`` — both are already in the run
    directory, so nothing new is invented and nothing outside it is read.
    """
    return {
        "title": _topic(run_dir),
        "authors": [],
        "abstract": "",
        "artifacts": list(PACKAGED_FILES),
        "run_fingerprint": _fingerprint(run_dir),
    }


def _topic(run_dir: Path) -> str:
    for record in ClaimLedger(run_dir / "claim_ledger.jsonl").as_records():
        if record.get("kind") == "run_start":
            return str((record.get("payload") or {}).get("topic", ""))
    return ""


def _fingerprint(run_dir: Path) -> str:
    path = run_dir / "env_fingerprint.json"
    if not path.is_file():
        return ""
    return fingerprint_digest(json.loads(path.read_text(encoding="utf-8")))


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in _strings(item)]
    return []


def _is_absolute(text: str) -> bool:
    return Path(text).is_absolute() or (len(text) > 1 and text[1] == ":")


__all__ = [
    "ARCHIVE_NAME",
    "METADATA_FILE",
    "PACKAGED_FILES",
    "PINNED_DATE_TIME",
    "REQUIRED_METADATA_KEYS",
    "default_metadata",
    "package_run",
    "validate_metadata",
]
