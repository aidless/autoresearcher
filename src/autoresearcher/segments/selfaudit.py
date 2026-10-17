"""⑦ — the self-audit gate. It runs declared checks, and it may refuse.

Two check kinds are ported from the private ``paper_promotion_gate/gates_config.json``
(``file_exists``, ``script_runs``), and one check is built in: every numeric
literal in ``draft.md`` must be covered by a numeric value in the claim ledger.
The built-in check is the port of the private ``scripts/verify_claim_ledger.py``'s
core rule, and it is the only check that cannot be switched off from a config
file — a draft citing a number the ledger never recorded is exactly the failure
this design exists to catch.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.audit import uncovered_numbers
from autoresearcher.segments.base import SegmentContext, write_payload

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DEFAULT_CONFIG = FIXTURES / "selfaudit_gates.json"
CONFIG_NAME = "selfaudit_gates.json"
COVERAGE_CHECK_NAME = "draft numbers are covered by the ledger"


@dataclass
class SelfAuditSegment:
    segment_id: str = "selfaudit"

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        config, source = self._config(ctx)
        checks = [self._declared_check(ctx, item) for item in config.get("checks") or []]
        checks.append(_coverage_check(ctx))

        failed = [check for check in checks if not check["passed"]]
        payload = write_payload(
            ctx,
            "selfaudit.json",
            {"config": source, "checks": checks, "n_failed": len(failed)},
        )
        if failed:
            named = "; ".join(f"{check['name']} ({check['detail']})" for check in failed)
            return SegmentArtifact(
                segment_id=self.segment_id,
                status=SegmentStatus.REFUSED,
                artifact_path=payload,
                claim_ids=[],
                gate_summary={
                    "checks": len(checks),
                    "failed": [check["name"] for check in failed],
                    "reason": f"self-audit failed: {named}",
                },
                run_fingerprint=ctx.fingerprint,
            )
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=payload,
            claim_ids=[],
            gate_summary={"checks": len(checks), "n_failed": 0},
            run_fingerprint=ctx.fingerprint,
        )

    def _config(self, ctx: SegmentContext) -> tuple[dict, str]:
        """The run's declared configuration, or the shipped default.

        The source is recorded so a reader can tell a run that declared its own
        checks from one that used the fixture.
        """
        declared = ctx.run_dir / CONFIG_NAME
        if declared.is_file():
            return json.loads(declared.read_text(encoding="utf-8")), CONFIG_NAME
        return json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8")), "package-default"

    def _declared_check(self, ctx: SegmentContext, declared: dict) -> dict:
        kind = str(declared.get("type", ""))
        name = str(declared.get("name", kind))
        if kind == "file_exists":
            return _file_exists_check(ctx, name, declared)
        if kind == "script_runs":
            return _script_runs_check(ctx, name, declared)
        # An unknown kind fails closed: a config that asks for a check we do not
        # implement has not been satisfied.
        return {"name": name, "kind": kind, "passed": False, "detail": f"unknown check type {kind!r}"}


def _relative(value: object, *, what: str) -> Path:
    candidate = Path(str(value))
    if candidate.is_absolute():
        raise ValueError(
            f"{what} {value!r} must be relative to the run directory; "
            "an absolute path would publish the machine that produced it"
        )
    return candidate


def _file_exists_check(ctx: SegmentContext, name: str, declared: dict) -> dict:
    relative = _relative(declared.get("path", ""), what=f"file_exists path for {name!r}")
    return {
        "name": name,
        "kind": "file_exists",
        "passed": (ctx.run_dir / relative).is_file(),
        "detail": relative.as_posix(),
    }


def _script_runs_check(ctx: SegmentContext, name: str, declared: dict) -> dict:
    cmd = [str(element) for element in (declared.get("cmd") or [])]
    for element in cmd:
        _relative(element, what=f"script_runs cmd element for {name!r}")
    if not cmd:
        return {"name": name, "kind": "script_runs", "passed": False, "detail": "empty cmd"}
    cwd = _relative(declared.get("cwd", "."), what=f"script_runs cwd for {name!r}")
    timeout = int(declared.get("timeout", 60))
    try:
        completed = subprocess.run(
            cmd,
            cwd=ctx.run_dir / cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": name, "kind": "script_runs", "passed": False, "detail": str(exc)}
    if completed.returncode == 0:
        return {"name": name, "kind": "script_runs", "passed": True, "detail": "exit 0"}
    tail = (completed.stderr or completed.stdout or "").strip().splitlines()
    return {
        "name": name,
        "kind": "script_runs",
        "passed": False,
        "detail": f"exit {completed.returncode}: {tail[-1] if tail else 'no output'}",
    }


def _coverage_check(ctx: SegmentContext) -> dict:
    draft = ctx.run_dir / "draft.md"
    if not draft.is_file():
        return {
            "name": COVERAGE_CHECK_NAME,
            "kind": "coverage",
            "passed": False,
            "detail": "draft.md is missing",
        }
    uncovered = uncovered_numbers(draft.read_text(encoding="utf-8"), ctx.ledger.rows())
    return {
        "name": COVERAGE_CHECK_NAME,
        "kind": "coverage",
        "passed": not uncovered,
        "detail": "all numbers covered" if not uncovered else f"uncovered: {', '.join(uncovered)}",
    }


__all__ = ["COVERAGE_CHECK_NAME", "DEFAULT_CONFIG", "SelfAuditSegment"]
