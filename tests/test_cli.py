from __future__ import annotations

from pathlib import Path

from autoresearcher.cli import main


def test_run_dry_run_writes_the_ledger_and_prints_the_recompute_hint(
    tmp_path: Path, capsys
) -> None:
    run_dir = tmp_path / "run"
    code = main(["run", "--dry-run", "a topic", "--out", str(run_dir)])
    out = capsys.readouterr().out
    assert code == 0
    assert "status   OK" in out
    assert "claims   3" in out
    assert "recompute" in out
    assert (run_dir / "claim_ledger.jsonl").exists()


def test_verify_ledger_exits_zero_for_a_good_chain(tmp_path: Path, capsys) -> None:
    run_dir = tmp_path / "run"
    main(["run", "--dry-run", "a topic", "--out", str(run_dir)])
    assert main(["verify-ledger", str(run_dir / "claim_ledger.jsonl")]) == 0
    assert "OK" in capsys.readouterr().out


def test_verify_ledger_exits_nonzero_for_a_broken_chain(tmp_path: Path, capsys) -> None:
    path = tmp_path / "claim_ledger.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    assert main(["verify-ledger", str(path)]) == 1


def test_recompute_exits_zero_for_a_good_run(tmp_path: Path, capsys) -> None:
    run_dir = tmp_path / "run"
    main(["run", "--dry-run", "a topic", "--out", str(run_dir)])
    assert main(["recompute", str(run_dir)]) == 0
    assert "3/3" in capsys.readouterr().out


def test_recompute_exits_nonzero_for_a_tampered_run(tmp_path: Path, capsys) -> None:
    run_dir = tmp_path / "run"
    main(["run", "--dry-run", "a topic", "--out", str(run_dir)])
    (run_dir / "evidence/experiment-000.json").write_text("{}", encoding="utf-8")
    assert main(["recompute", str(run_dir)]) == 1


def test_a_refused_run_exits_two_and_says_why_on_stderr(tmp_path: Path, capsys) -> None:
    run_dir = tmp_path / "run"
    code = main(["run", "--dry-run", "a topic", "--out", str(run_dir), "--generators", "2"])
    captured = capsys.readouterr()
    assert code == 2
    assert "status   REFUSED" in captured.out
    assert "no claim cleared the gate" in captured.err


def test_doctor_prints_what_the_install_can_do(capsys) -> None:
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "arx" in out
    assert "dry-run" in out
