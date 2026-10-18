"""A third-party, read-only verifier for one autoresearcher run.

Five checks, no writes, no pipeline, no network. It re-derives what it can and
reports what it cannot; it never repairs a run, and a failure here is a fact
about the files rather than a crash in the reporter.

    python tools/verify_claim_chain.py runs/demo
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from arx.experiments.ledger import verify_ledger_file

from autoresearcher.audit import uncovered_numbers
from autoresearcher.claim import CLAIM_FIELDS, ClaimLedger
from autoresearcher.recompute import recompute_run

CHAIN_CHECK = "the ledger's hash chain verifies"
FIELDS_CHECK = "every claim carries all eight claim fields"
EVIDENCE_CHECK = "every claim's evidence hashes to what the ledger recorded"
RECOMPUTE_CHECK = "every recorded gate decision re-derives from the files"
COVERAGE_CHECK = "every number in draft.md is covered by the ledger"
N_CHECKS = 5


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def checks(run_dir: Path) -> list[Check]:
    """The five checks, in the order a reader cares about them."""
    run_dir = Path(run_dir)
    ledger_path = run_dir / "claim_ledger.jsonl"
    return [
        _chain_check(ledger_path),
        _fields_check(ledger_path),
        _evidence_check(run_dir, ledger_path),
        _recompute_check(run_dir),
        _coverage_check(run_dir, ledger_path),
    ]


def _chain_check(ledger_path: Path) -> Check:
    report = verify_ledger_file(ledger_path)
    return Check(CHAIN_CHECK, bool(report["chain_valid"]), f"records={report['n_records']}")


def _claim_records(ledger_path: Path) -> list[dict]:
    return [record for record in ClaimLedger(ledger_path).as_records() if record.get("kind") == "claim"]


def _fields_check(ledger_path: Path) -> Check:
    # Read the raw records, not ``rows()``: a claim that lost a field is exactly
    # what this check must *report*, and ``rows()`` raises instead.
    bad = [
        f"seq {record.get('seq')}"
        for record in _claim_records(ledger_path)
        if any(field not in (record.get("payload") or {}) for field in CLAIM_FIELDS)
    ]
    return Check(FIELDS_CHECK, not bad, "ok" if not bad else "missing in " + ", ".join(bad))


def _evidence_check(run_dir: Path, ledger_path: Path) -> Check:
    try:
        rows = ClaimLedger(ledger_path).rows()
    except (ValueError, KeyError, TypeError) as exc:
        return Check(EVIDENCE_CHECK, False, f"ledger unreadable: {exc}")
    bad: list[str] = []
    for row in rows:
        path = run_dir / row.evidence_ref.rsplit(":", 1)[0]
        if not path.is_file():
            bad.append(f"{row.claim_id}: missing {row.evidence_ref}")
            continue
        recorded = row.metrics.get("evidence_sha256")
        if not recorded:
            # A claim on a path that never reached the measurement records an
            # empty hash (segments/gate.py's `_undecidable`); the anchor still has
            # to resolve, but there is no recorded digest to compare against, and
            # comparing against `""` would be a false FAIL rather than a finding.
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != str(recorded):
            bad.append(f"{row.claim_id}: sha256 does not match")
    return Check(EVIDENCE_CHECK, not bad, "ok" if not bad else "; ".join(bad))


def _recompute_check(run_dir: Path) -> Check:
    try:
        report = recompute_run(run_dir)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return Check(RECOMPUTE_CHECK, False, f"recompute failed: {exc}")
    ok = not report.mismatches and not report.unresolvable
    return Check(RECOMPUTE_CHECK, ok, report.summary())


def _coverage_check(run_dir: Path, ledger_path: Path) -> Check:
    draft = run_dir / "draft.md"
    if not draft.is_file():
        return Check(COVERAGE_CHECK, False, "draft.md is missing")
    try:
        rows = ClaimLedger(ledger_path).rows()
    except (ValueError, KeyError, TypeError) as exc:
        return Check(COVERAGE_CHECK, False, f"ledger unreadable: {exc}")
    uncovered = uncovered_numbers(draft.read_text(encoding="utf-8"), rows)
    return Check(COVERAGE_CHECK, not uncovered, "ok" if not uncovered else "uncovered: " + ", ".join(uncovered))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python tools/verify_claim_chain.py <run_dir>", file=sys.stderr)
        return 2
    results = checks(Path(args[0]))
    for index, check in enumerate(results, start=1):
        print(f"{'PASS' if check.ok else 'FAIL'}  {index}. {check.name}  ({check.detail})")
    passed = sum(1 for check in results if check.ok)
    print(f"{passed}/{N_CHECKS}")
    return 0 if passed == N_CHECKS else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
