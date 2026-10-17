"""The arx settings this pipeline runs under, and nothing else.

Every number here is a *declared* design parameter that gets written into the
ledger, which is arx's rule: a margin without the settings it was measured
against is not interpretable. The defaults mirror arx's own offline example
configuration so the two agree on what a run means.
"""

from __future__ import annotations

from pathlib import Path

from arx.config import AgentConfig


def offline_config(run_dir: Path, **overrides: object) -> AgentConfig:
    """An ``AgentConfig`` that reaches no network and no model.

    ``workspace`` points at the run directory so an experiment sandbox is
    confined to it. The empty ``llm_*`` values are what make arx's ``build_llm``
    return a ``NullLLM`` rather than an HTTP client, and the gate flags are arx's
    own names, not a parallel vocabulary.
    """
    defaults: dict[str, object] = {
        "workspace": Path(run_dir),
        "llm_base_url": "",
        "llm_model": "",
        "semantic_duplicate_threshold": 0.6,
        "sandbox_timeout_s": 60.0,
        "gate_alpha": 0.05,
        "gate_power": 0.8,
        "gate_delta_declared": 0.02,
        "gate_strict": True,
        "seed": 0,
    }
    return AgentConfig(**{**defaults, **overrides})


__all__ = ["offline_config"]
