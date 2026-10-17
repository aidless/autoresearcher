from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests_helpers import make_context

from autoresearcher.artifact import SegmentStatus
from autoresearcher.segments.selfaudit import COVERAGE_CHECK_NAME, SelfAuditSegment

PASS_SCRIPT = ["python3", "-c", "import sys; sys.exit(0)"]
FAIL_SCRIPT = ["python3", "-c", "import sys; sys.exit(3)"]


def _ledger_row(ctx, score: float = 0.9475) -> None:
    ctx.ledger.append_claim(
        claim_id=ctx.ledger.next_claim_id("gate"),
        segment="gate",
        text="the strong system separates",
        evidence_ref="evidence/experiment-000.json:1",
        gate_decision="ACCEPT",
        metrics={"verdict": "READABLE", "leader_score": score, "mde": 0.031242},
    )


def _config(ctx, checks: list[dict]) -> None:
    (ctx.run_dir / "selfaudit_gates.json").write_text(
        json.dumps({"checks": checks}), encoding="utf-8"
    )


def test_a_run_where_every_check_passes_is_ok(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    _config(
        ctx,
        [
            {"type": "file_exists", "name": "draft present", "path": "draft.md"},
            {"type": "file_exists", "name": "ledger present", "path": "claim_ledger.jsonl"},
            {"type": "script_runs", "name": "interpreter runs", "cmd": PASS_SCRIPT, "cwd": ".", "timeout": 30},
        ],
    )
    artifact = SelfAuditSegment().run(ctx)
    assert artifact.status is SegmentStatus.OK
    assert artifact.gate_summary["n_failed"] == 0


def test_the_shipped_default_configuration_is_used_when_the_run_has_none(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    artifact = SelfAuditSegment().run(ctx)
    assert artifact.status is SegmentStatus.OK
    payload = json.loads((ctx.run_dir / "artifacts" / "selfaudit.json").read_text(encoding="utf-8"))
    assert payload["config"] == "package-default"
    assert len(payload["checks"]) == 4  # three declared + the built-in coverage check


def test_a_missing_declared_file_refuses_and_names_it(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    _config(ctx, [{"type": "file_exists", "name": "results present", "path": "results/e1.json"}])
    artifact = SelfAuditSegment().run(ctx)
    assert artifact.status is SegmentStatus.REFUSED
    assert "results present" in artifact.refusal_reason()


def test_a_script_that_exits_nonzero_refuses(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    _config(ctx, [{"type": "script_runs", "name": "canonical recompute", "cmd": FAIL_SCRIPT, "cwd": ".", "timeout": 30}])
    artifact = SelfAuditSegment().run(ctx)
    assert artifact.status is SegmentStatus.REFUSED
    assert "canonical recompute" in artifact.refusal_reason()


def test_an_uncovered_number_in_the_draft_refuses_and_names_the_number(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9999\n", encoding="utf-8")
    _config(ctx, [])
    artifact = SelfAuditSegment().run(ctx)
    assert artifact.status is SegmentStatus.REFUSED
    reason = artifact.refusal_reason()
    assert COVERAGE_CHECK_NAME in reason
    assert "0.9999" in reason


def test_an_absolute_cwd_is_refused(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    _config(ctx, [{"type": "script_runs", "name": "escapes", "cmd": PASS_SCRIPT, "cwd": "/tmp", "timeout": 30}])
    with pytest.raises(ValueError, match="relative"):
        SelfAuditSegment().run(ctx)


def test_an_absolute_file_exists_path_is_refused(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    _config(ctx, [{"type": "file_exists", "name": "outside", "path": "/etc/hosts"}])
    with pytest.raises(ValueError, match="relative"):
        SelfAuditSegment().run(ctx)
