"""The command line: run one topic, verify a chain, recompute a run, describe the install.

Exit codes carry meaning, because CI and a reader both need to tell three
outcomes apart: 0 the chain completed and everything recomputed, 2 the chain
refused on purpose (the tool working), 1 something is broken.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from arx.experiments.ledger import verify_ledger_file

from autoresearcher import __version__
from autoresearcher.fingerprint import environment_fingerprint
from autoresearcher.package import package_run
from autoresearcher.pipeline import RunConfig, run_pipeline
from autoresearcher.recompute import recompute_run

EXIT_OK = 0
EXIT_BROKEN = 1
EXIT_REFUSED = 2


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.handler(args)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="researcher", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one topic through the chain")
    run.add_argument("topic")
    run.add_argument("--dry-run", action="store_true", help="offline fixtures; no model, no network")
    run.add_argument("--out", default="runs/latest", help="run directory")
    run.add_argument("--hypotheses", type=int, default=3)
    run.add_argument("--generators", type=int, default=5)
    run.add_argument("--falsified-by", default="")
    run.set_defaults(handler=_run)

    verify = sub.add_parser("verify-ledger", help="check a claim ledger's hash chain")
    verify.add_argument("ledger")
    verify.set_defaults(handler=_verify)

    recompute = sub.add_parser("recompute", help="re-derive every decision in a run from disk")
    recompute.add_argument("run_dir")
    recompute.set_defaults(handler=_recompute)

    package = sub.add_parser("package", help="package a finished run into a deterministic archive")
    package.add_argument("run_dir")
    package.set_defaults(handler=_package)

    doctor = sub.add_parser("doctor", help="what this install can actually do")
    doctor.set_defaults(handler=_doctor)
    return parser


def _run(args: argparse.Namespace) -> int:
    outcome = run_pipeline(
        RunConfig(
            topic=args.topic,
            run_dir=Path(args.out),
            dry_run=args.dry_run,
            n_hypotheses=args.hypotheses,
            falsified_by=args.falsified_by,
            generators=args.generators,
        )
    )
    print(f"status   {outcome.status}")
    print(f"run      {outcome.run_dir}")
    print(f"draft    {outcome.draft_path or '-'}")
    print(f"ledger   {outcome.claim_ledger}")
    print(f"decisions {outcome.decisions_path}")
    print(f"claims   {outcome.n_claims}")
    print(f"stopped  {outcome.chain.stopped_at or '-'}")
    print(f"recompute it with: python3 -m autoresearcher.cli recompute {outcome.run_dir}")
    if not outcome.chain.completed:
        print(f"refused  {outcome.chain.refusal}", file=sys.stderr)
        return EXIT_REFUSED
    return EXIT_OK


def _verify(args: argparse.Namespace) -> int:
    report = verify_ledger_file(Path(args.ledger))
    ok = bool(report["chain_valid"])
    print(f"{'OK' if ok else 'BROKEN'}  records={report['n_records']}")
    for key in ("error", "reason"):
        if report.get(key):
            print(f"  {report[key]}", file=sys.stderr)
    return EXIT_OK if ok else EXIT_BROKEN


def _recompute(args: argparse.Namespace) -> int:
    report = recompute_run(Path(args.run_dir))
    print(report.summary())
    for mismatch in report.mismatches:
        print(
            f"  {mismatch.claim_id} {mismatch.field}: recorded {mismatch.recorded!r} "
            f"but recomputes to {mismatch.recomputed!r}",
            file=sys.stderr,
        )
    for claim_id in report.unresolvable:
        print(f"  {claim_id}: evidence could not be resolved", file=sys.stderr)
    return EXIT_OK if report.ok else EXIT_BROKEN


def _package(args: argparse.Namespace) -> int:
    try:
        archive = package_run(Path(args.run_dir))
    except ValueError as exc:
        # A run that is missing an artifact is not packageable. Say which, and
        # exit 1: this is broken input, not a refusal the tool made on purpose.
        print(f"cannot package: {exc}", file=sys.stderr)
        return EXIT_BROKEN
    print(f"archive  {archive}")
    print(f"sha256   {hashlib.sha256(archive.read_bytes()).hexdigest()}")
    return EXIT_OK


def _doctor(args: argparse.Namespace) -> int:
    import arx

    print(f"autoresearcher {__version__}")
    print(f"arx            {getattr(arx, '__version__', 'unknown')}")
    print(json.dumps(environment_fingerprint(), indent=2, sort_keys=True))
    print("capabilities")
    print("  segments 1-8   available")
    print("  dry-run        available (offline fixtures, no model, no network)")
    print("  live search    implemented, not exercised")
    print("  packaging      available (researcher package)")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
