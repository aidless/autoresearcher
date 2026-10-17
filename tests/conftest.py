"""Shared fixtures.

Most of the suite builds the same offline components, because the dry run is
M0's acceptance test. Nothing here touches the network, a model, or the
developer's home directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """A fresh directory for one run."""
    directory = tmp_path / "run"
    directory.mkdir()
    return directory
