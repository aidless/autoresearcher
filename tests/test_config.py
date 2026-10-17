from __future__ import annotations

from pathlib import Path

from autoresearcher.config import offline_config


def test_offline_config_reaches_no_network_and_declares_the_gate_settings(tmp_path: Path) -> None:
    config = offline_config(tmp_path)
    flags = config.ledger_flags()
    # arx's ledger_flags() records the settings that change what a result means
    # (the gate numbers, the duplicate threshold, the seed). It does not carry the
    # llm or sandbox fields, so those are asserted on the config itself.
    assert config.llm_base_url == ""
    assert config.llm_model == ""
    assert flags["gate_alpha"] == 0.05
    assert flags["gate_power"] == 0.8
    assert flags["gate_delta_declared"] == 0.02
    assert config.sandbox_timeout_s > 0
