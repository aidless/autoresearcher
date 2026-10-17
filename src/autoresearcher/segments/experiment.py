"""④ — run one script per hypothesis, after pinning what the run is allowed to do.

The order in this module is the guarantee. The pre-registration record is
appended to the ledger *before* the script is materialised, and long before the
subprocess exists. arx states why this is structural rather than a policy: a rule
against "run a fixed-sample test, miss, then claim you only ever intended one
look" would have to be enforced by the party that wants to break it. Here the
experiment cannot see its own budget before it is fixed, because the budget is
already written down.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from arx.audit.prereg import Preregistration, plan_k_max
from arx.config import AgentConfig
from arx.experiments.provider import ExperimentProvider, ExperimentScript
from arx.experiments.runner import run_experiment
from arx.hypothesis import Hypothesis

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import SegmentContext, write_payload


@dataclass
class TemplateExperimentProvider:
    """One script per hypothesis, rendered from a template.

    arx ships the same idea in ``examples/_support.FactoryProvider``, which is
    not importable from an installed wheel, so it is rebuilt here. The template's
    job is to make the script a real file: the runner hashes the bytes that ran,
    and a provider that kept the script in memory would leave a third party
    nothing to read.
    """

    template: str
    name: str = "template"
    fields: dict = field(default_factory=dict)

    def provide(self, hypothesis: Hypothesis) -> ExperimentScript | None:
        seed = int(hashlib.sha256(hypothesis.text.encode("utf-8")).hexdigest()[:8], 16)
        values = {"seed": seed, **self.fields}
        try:
            text = self.template % values
        except KeyError as exc:
            raise ValueError(
                f"experiment template needs {exc} but the provider supplied {sorted(values)}"
            ) from exc
        return ExperimentScript(text=text, path=None, source=self.name)


@dataclass
class ExperimentSegment:
    segment_id: str = "experiment"
    provider: ExperimentProvider | None = None
    config: AgentConfig = field(default_factory=AgentConfig)

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        if self.provider is None:
            raise ValueError("ExperimentSegment requires a provider")
        hypothesized = ctx.upstream_payload("hypothesize")
        hypotheses = [Hypothesis.from_dict(item) for item in hypothesized["kept"]]
        runs = [self._one(ctx, index, hypothesis) for index, hypothesis in enumerate(hypotheses)]

        payload = write_payload(ctx, "experiment.json", {"runs": runs})
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=payload,
            claim_ids=[],
            gate_summary={
                "claims": 0,
                "n_runs": len(runs),
                "n_untested": sum(1 for run in runs if run.get("status") == "no_entrypoint"),
                "note": "the experiments ran; nothing is claimed until 5 has judged them",
            },
            run_fingerprint=ctx.fingerprint,
        )

    def _one(self, ctx: SegmentContext, index: int, hypothesis: Hypothesis) -> dict:
        script = self.provider.provide(hypothesis) if self.provider is not None else None
        if script is None:
            return {
                "index": index,
                "hypothesis": hypothesis.text,
                "status": "no_entrypoint",
                "note": (
                    "no script was produced for this hypothesis; recorded as untested "
                    "rather than replaced with a plausible result"
                ),
            }

        k_max = plan_k_max(
            prior_confidence=hypothesis.confidence,
            alpha=self.config.gate_alpha,
            target_power=self.config.gate_power,
            effect_se_ratio=hypothesis.expected_effect_se_ratio,
        )
        preregistration = Preregistration.create(
            hypothesis_text=hypothesis.text,
            k_max=k_max,
            alpha=self.config.gate_alpha,
            script_sha256=script.sha256,
        )
        ctx.ledger.append_record("pre_register", preregistration.to_dict())

        path = script.materialise(ctx.run_dir, f"experiment-{index:03d}.py")
        result = run_experiment(path, timeout_s=self.config.sandbox_timeout_s, cwd=ctx.run_dir)

        evidence_ref = f"evidence/experiment-{index:03d}.json:1"
        target = ctx.run_dir / evidence_ref.rsplit(":", 1)[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "index": index,
                    "hypothesis": hypothesis.text,
                    "k_max": k_max,
                    "provider": script.source,
                    # Listed field by field rather than via ``result.to_dict()``:
                    # the evidence has to be rebuildable into a ``RunResult`` by
                    # ⑤, and ``to_dict`` carries preview fields instead.
                    "result": {
                        "entrypoint": result.entrypoint,
                        "returncode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "timed_out": result.timed_out,
                        "duration_s": result.duration_s,
                        "script_sha256": result.script_sha256,
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        return {
            "index": index,
            "hypothesis": hypothesis.text,
            "k_max": k_max,
            "provider": script.source,
            "script_path": path.relative_to(ctx.run_dir).as_posix(),
            "script_sha256": script.sha256,
            "evidence_ref": evidence_ref,
        }


__all__ = ["ExperimentSegment", "TemplateExperimentProvider"]
