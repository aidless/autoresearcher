from __future__ import annotations

import json
from pathlib import Path

from autoresearcher.fingerprint import environment_fingerprint, fingerprint_digest


def test_fingerprint_records_the_versions_that_matter() -> None:
    fp = environment_fingerprint(run_dir=Path("/home/someone/private/runs/demo"))
    assert fp["python_version"]
    assert fp["arx_version"]
    assert fp["autoresearcher_version"]
    assert fp["platform"]


def test_fingerprint_carries_no_machine_paths() -> None:
    text = json.dumps(
        environment_fingerprint(run_dir=Path("/home/someone/private/runs/demo")), sort_keys=True
    )
    assert "someone" not in text


def test_digest_is_stable_across_key_order() -> None:
    a = {"python_version": "3.12.0", "arx_version": "0.1.0"}
    b = {"arx_version": "0.1.0", "python_version": "3.12.0"}
    assert fingerprint_digest(a) == fingerprint_digest(b)
    assert fingerprint_digest(a) != fingerprint_digest({**a, "arx_version": "0.2.0"})
