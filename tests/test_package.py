from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from autoresearcher.package import (
    METADATA_FILE,
    PACKAGED_FILES,
    REQUIRED_METADATA_KEYS,
    package_run,
)
from autoresearcher.pipeline import RunConfig, run_pipeline


def _good_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(
        RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True)
    )
    assert outcome.chain.completed is True
    return run_dir


def test_packaging_the_same_run_twice_is_byte_identical(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    first = hashlib.sha256(package_run(run_dir).read_bytes()).hexdigest()
    second = hashlib.sha256(package_run(run_dir).read_bytes()).hexdigest()
    assert first == second


def test_the_archive_holds_the_four_run_files_and_the_metadata(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    with zipfile.ZipFile(package_run(run_dir)) as archive:
        assert archive.namelist() == sorted([*PACKAGED_FILES, METADATA_FILE])


def test_every_member_has_a_pinned_timestamp(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    with zipfile.ZipFile(package_run(run_dir)) as archive:
        assert {info.date_time for info in archive.infolist()} == {(1980, 1, 1, 0, 0, 0)}


def test_the_default_metadata_carries_the_required_keys(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    with zipfile.ZipFile(package_run(run_dir)) as archive:
        metadata = json.loads(archive.read(METADATA_FILE))
    assert set(REQUIRED_METADATA_KEYS) <= set(metadata)
    assert metadata["title"] == "does the gate hold"
    assert metadata["artifacts"] == list(PACKAGED_FILES)


def test_an_absolute_path_in_the_metadata_is_rejected(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    with pytest.raises(ValueError, match="absolute"):
        package_run(
            run_dir,
            metadata={
                "title": "t",
                "authors": [],
                "abstract": "",
                "artifacts": ["/home/someone/draft.md"],
            },
        )


def test_a_metadata_missing_a_required_key_is_rejected(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    with pytest.raises(ValueError, match="missing required keys"):
        package_run(run_dir, metadata={"title": "t"})


def test_packaging_a_run_without_a_draft_is_refused(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    (run_dir / "draft.md").unlink()
    with pytest.raises(ValueError, match="draft.md"):
        package_run(run_dir)
