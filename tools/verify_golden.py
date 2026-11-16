#!/usr/bin/env python3
"""Recompute the committed golden snapshots. No network, no model, no writes.

Checks two things a reader can do without re-running the pipeline:

1. Every file under ``golden/dry-run`` and ``golden/refused-two-generators``
   still hashes to ``golden/MANIFEST.sha256``.
2. ``verify_claim_chain`` and ``recompute`` still say what the manifest was
   built against: 5/5 on the finished fixture run, and 4/5 on the refusal
   (no ``draft.md``, by design).

Regenerating a run changes ``duration_s`` and the ledger hashes. This script
does not regenerate. It checks the snapshot.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoresearcher.recompute import recompute_run  # noqa: E402
from tools.verify_claim_chain import checks  # noqa: E402

GOLDEN = ROOT / "golden"
MANIFEST = GOLDEN / "MANIFEST.sha256"
FINISHED = GOLDEN / "dry-run"
REFUSED = GOLDEN / "refused-two-generators"
RECOMPUTE_SUMMARY = "chain OK | reproduced 3/3 | mismatches 0 | unresolvable 0"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_paths() -> list[Path]:
    roots = (FINISHED, REFUSED)
    paths: list[Path] = []
    for root in roots:
        paths.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(paths)


def check_manifest() -> list[str]:
    problems: list[str] = []
    if not MANIFEST.is_file():
        return ["golden/MANIFEST.sha256 is missing"]
    recorded: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split(maxsplit=1)
        recorded[rel] = digest
    actual = {path.relative_to(ROOT).as_posix(): _sha256(path) for path in _manifest_paths()}
    for rel, digest in sorted(recorded.items()):
        if rel not in actual:
            problems.append(f"manifest lists {rel} but the file is gone")
        elif actual[rel] != digest:
            problems.append(f"hash mismatch {rel}")
    for rel in sorted(set(actual) - set(recorded)):
        problems.append(f"unlisted file {rel}")
    return problems


def _require(condition: bool, detail: str, problems: list[str]) -> None:
    if not condition:
        problems.append(detail)


def check_finished() -> list[str]:
    problems: list[str] = []
    report = checks(FINISHED)
    _require(all(item.ok for item in report), "dry-run snapshot is not 5/5: " + "; ".join(
        f"{item.name} ({item.detail})" for item in report if not item.ok
    ) or "dry-run snapshot is not 5/5", problems)
    summary = recompute_run(FINISHED).summary()
    _require(summary == RECOMPUTE_SUMMARY, f"dry-run recompute: {summary}", problems)
    draft = (FINISHED / "draft.md").read_text(encoding="utf-8")
    _require("Verified findings" not in draft, "draft still says Verified findings", problems)
    _require(
        "Nothing in this file is a research finding" in draft,
        "draft notice is missing",
        problems,
    )
    return problems


def check_refused() -> list[str]:
    problems: list[str] = []
    report = checks(REFUSED)
    failed = [item for item in report if not item.ok]
    _require(len(failed) == 1, f"refused snapshot should fail exactly one check, failed {len(failed)}", problems)
    if failed:
        _require(
            "draft.md is missing" in failed[0].detail,
            f"refused snapshot failed for a different reason: {failed[0].detail}",
            problems,
        )
    summary = recompute_run(REFUSED).summary()
    _require(summary == RECOMPUTE_SUMMARY, f"refused recompute: {summary}", problems)
    _require(not (REFUSED / "draft.md").exists(), "refused snapshot has a draft", problems)
    return problems


def main() -> int:
    problems = check_manifest() + check_finished() + check_refused()
    if problems:
        print("GOLDEN FAIL")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("GOLDEN OK")
    print(f"  files {len(_manifest_paths())}")
    print(f"  dry-run 5/5 | {RECOMPUTE_SUMMARY}")
    print("  refused-two-generators 4/5 (draft.md is missing) | " + RECOMPUTE_SUMMARY)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
