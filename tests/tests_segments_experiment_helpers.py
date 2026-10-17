"""Templates and hypotheses shared by the experiment and gate tests."""

from __future__ import annotations

import json
from pathlib import Path

from arx.hypothesis import Hypothesis

import autoresearcher

FIXTURES = Path(autoresearcher.__file__).parent / "fixtures"


def template() -> str:
    return (FIXTURES / "dry_run_experiment.py.in").read_text(encoding="utf-8")


def succeeded_hypotheses() -> list[Hypothesis]:
    return [
        Hypothesis.from_dict(item)
        for item in json.loads((FIXTURES / "dry_run_hypotheses.json").read_text(encoding="utf-8"))
    ]
