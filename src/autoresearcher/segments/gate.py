"""⑤ — the gate. M0's only judge, and the only thing between a measurement and a claim.

``adjudicate`` is deliberately a pure function of four things: the evidence
file's contents, the ledger's records, the declared settings, and the evidence's
hash. It reads no environment and no clock, which is what lets
``researcher recompute`` re-derive the same decision from disk and byte-compare
it against what was written down.

Deliberately **not** here in M0: arx's sequential layer and its multiplicity
ledger. Both act on a *family* of looks whose meaning arrives with ⑥⑦ — the
family size is the number of hypotheses tested, and ``se``/``k_max`` describe
looks *within* one hypothesis. Adding them later is a decision to make on
purpose, so the omission is stated rather than implied.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
from arx.audit.auditor import AuditConfig
from arx.audit.prereg import Preregistration, check_preregistration, read_preregistration
from arx.audit.verdict import Verdict
from arx.config import AgentConfig
from arx.experiments.runner import RunResult
from arx.gate import EvaluationGate

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import SegmentContext, read_evidence_ref, write_payload

#: The exact keys every claim's ``metrics`` carries. Frozen by test: a reader —
#: ⑥ in M1, a third party now — must not have to guess whether a missing key
#: means "not measured" or "not recorded". Listed in the order arx's ``Ledger``
#: preserves them (it writes records with ``sort_keys=True``), so the order a
#: reader gets back from :meth:`ClaimLedger.rows` is this one.
METRIC_KEYS: tuple[str, ...] = (
    "alpha",
    "delta_declared",
    "evidence_sha256",
    "floor_estimate",
    "floor_method",
    "gate_allowed",
    "gate_strict",
    "k_max",
    "leader_score",
    "leader_system",
    "margin",
    "mde",
    "mde_method",
    "n_contestants",
    "n_generators",
    "n_items",
    "power",
    "prereg_ok",
    "reasons",
    "threshold",
    "verdict",
)

#: arx's verdict is the decision's source. Mapping by verdict rather than by the
#: gate's boolean is what keeps MARGINAL a *travelling* value: the boolean calls
#: it a refusal, the verdict says what kind, and only the verdict can be reported
#: downstream without lying about why the chain stopped.
DECISION_BY_VERDICT: dict[Verdict, str] = {
    Verdict.READABLE: "ACCEPT",
    Verdict.MARGINAL: "MARGINAL",
    Verdict.UNREADABLE: "REJECT",
    Verdict.UNDECIDABLE: "UNDECIDABLE",
}


@dataclass(frozen=True)
class Adjudication:
    gate_decision: str
    verdict: str
    prereg_ok: bool | None
    k_max: int | None
    metrics: dict


def adjudicate(
    *,
    evidence: dict,
    records: list[dict],
    config: AgentConfig,
    evidence_sha256: str,
) -> Adjudication:
    """Decide one claim from files alone.

    ``prereg_ok`` is ``None``, not ``False``, on the paths that never got far
    enough to check the pre-registration. A ``False`` there would claim we
    verified something we never looked at.
    """
    hypothesis_text = str(evidence["hypothesis"])
    preregistration = read_preregistration(records, hypothesis_text)
    run = run_result_from_evidence(evidence)

    if not run.ok:
        reason = (
            "the experiment timed out"
            if run.timed_out
            else f"the experiment exited with code {run.returncode}"
        )
        return _undecidable(reason, config=config, preregistration=preregistration, prereg_ok=None)

    ok, why = run.validate()
    if not ok:
        return _undecidable(why, config=config, preregistration=preregistration, prereg_ok=None)

    blob = run.payload() or {}
    measured_hash = run.script_sha256
    claimed_hash = blob.get("script_sha256")
    if claimed_hash is not None and str(claimed_hash) != str(measured_hash):
        return _undecidable(
            f"the experiment reported script_sha256={claimed_hash} but the file that ran "
            f"hashes to {measured_hash}",
            config=config,
            preregistration=preregistration,
            prereg_ok=None,
        )

    prereg_ok, prereg_reason = check_preregistration(
        preregistration,
        blob_k_max=_opt_int(blob.get("k_max")),
        blob_script_sha256=measured_hash,
    )
    if not prereg_ok:
        return _undecidable(
            f"pre-registration violated: {prereg_reason}",
            config=config,
            preregistration=preregistration,
            prereg_ok=False,
        )

    gate = EvaluationGate(
        config=AuditConfig(
            delta_declared=config.gate_delta_declared,
            alpha=config.gate_alpha,
            power=config.gate_power,
            seed=config.seed,
        ),
        strict=config.gate_strict,
    )
    allowed, report = gate.decision(
        _as_votes(blob.get("votes")),
        {str(key): float(value) for key, value in (blob.get("scores") or {}).items()},
        leaderboard_item_ids=_opt_int_set(blob.get("item_ids")),
        floor_item_ids=None,
        judge_ids=_opt_str_set(blob.get("judge_ids")),
        contestant_ids=_opt_str_set(blob.get("contestant_ids")),
        per_item_scores=None,
    )

    metrics = {
        **_base_metrics(config=config, preregistration=preregistration, prereg_ok=True),
        "verdict": report.verdict.value,
        "gate_allowed": allowed,
        "leader_system": report.leader_system,
        "leader_score": report.leader_score,
        "floor_estimate": report.floor_estimate,
        "floor_method": report.floor_method,
        "margin": report.margin,
        "mde": report.mde,
        "mde_method": report.extra.get("mde_method"),
        "threshold": report.threshold,
        "n_items": report.n_items,
        "n_generators": report.n_generators,
        "n_contestants": report.n_contestants,
        "reasons": list(report.reasons),
        "evidence_sha256": evidence_sha256,
    }
    return Adjudication(
        gate_decision=DECISION_BY_VERDICT[report.verdict],
        verdict=report.verdict.value,
        prereg_ok=True,
        # From the *ledger*, never from the evidence blob: the point of
        # pre-registering k_max is that the experiment's own report of it is not
        # evidence.
        k_max=preregistration.k_max if preregistration is not None else None,
        metrics={key: metrics[key] for key in METRIC_KEYS},
    )


def _base_metrics(
    *, config: AgentConfig, preregistration: Preregistration | None, prereg_ok: bool | None
) -> dict:
    return {
        "k_max": preregistration.k_max if preregistration is not None else None,
        "alpha": config.gate_alpha,
        "power": config.gate_power,
        "delta_declared": config.gate_delta_declared,
        "gate_strict": config.gate_strict,
        "prereg_ok": prereg_ok,
        "verdict": Verdict.UNDECIDABLE.value,
        "gate_allowed": None,
        "leader_system": None,
        "leader_score": None,
        "floor_estimate": None,
        "floor_method": "",
        "margin": None,
        "mde": None,
        "mde_method": None,
        "threshold": None,
        "n_items": None,
        "n_generators": None,
        "n_contestants": None,
        "reasons": [],
        "evidence_sha256": "",
    }


def _undecidable(
    reason: str,
    *,
    config: AgentConfig,
    preregistration: Preregistration | None,
    prereg_ok: bool | None,
) -> Adjudication:
    metrics = {
        **_base_metrics(config=config, preregistration=preregistration, prereg_ok=prereg_ok),
        "reasons": [reason],
    }
    return Adjudication(
        gate_decision="UNDECIDABLE",
        verdict=Verdict.UNDECIDABLE.value,
        prereg_ok=prereg_ok,
        k_max=preregistration.k_max if preregistration is not None else None,
        metrics={key: metrics[key] for key in METRIC_KEYS},
    )


def run_result_from_evidence(evidence: dict) -> RunResult:
    """Rebuild the runner's own result object from the evidence file.

    Reused so the gate can call arx's ``validate()`` and ``payload()`` rather than
    reimplementing the contract — and so the gate and ``recompute`` agree on what
    the evidence says by construction, not by care.
    """
    result = evidence.get("result")
    if not isinstance(result, dict):
        raise ValueError("evidence has no 'result' object")
    return RunResult(
        entrypoint=str(result.get("entrypoint", "")),
        returncode=int(result.get("returncode", -1)),
        stdout=str(result.get("stdout", "")),
        stderr=str(result.get("stderr", "")),
        timed_out=bool(result.get("timed_out", False)),
        duration_s=float(result.get("duration_s", 0.0)),
        script_sha256=str(result.get("script_sha256", "")),
    )


def _as_votes(raw: object) -> np.ndarray:
    if raw is None:
        return np.zeros((0, 0), dtype=int)
    return np.array(raw).astype(int)


def _opt_int(value: object) -> int | None:
    return None if value is None else int(value)


def _opt_int_set(value: object) -> set[int] | None:
    return None if value is None else {int(item) for item in value}


def _opt_str_set(value: object) -> set[str] | None:
    return None if value is None else {str(item) for item in value}


@dataclass
class GateSegment:
    segment_id: str = "gate"
    config: AgentConfig = field(default_factory=AgentConfig)

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        experiment = ctx.upstream_payload("experiment")
        records = ctx.ledger.as_records()
        claim_ids: list[str] = []
        decisions: list[dict] = []
        n_accept = 0

        for entry in experiment["runs"]:
            if entry.get("status") == "no_entrypoint":
                decisions.append(
                    {
                        "index": entry["index"],
                        "hypothesis": entry["hypothesis"],
                        "claim_id": None,
                        "gate_decision": None,
                        "verdict": None,
                        "reasons": ["untested: no script was produced for this hypothesis"],
                    }
                )
                continue

            evidence_ref = str(entry["evidence_ref"])
            evidence_path = ctx.run_dir / evidence_ref.rsplit(":", 1)[0]
            evidence, _line = read_evidence_ref(ctx, evidence_ref)
            decision = adjudicate(
                evidence=evidence,
                records=records,
                config=self.config,
                evidence_sha256=hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            )
            row = ctx.ledger.append_claim(
                claim_id=ctx.ledger.next_claim_id(self.segment_id),
                segment=self.segment_id,
                text=str(evidence["hypothesis"]),
                evidence_ref=evidence_ref,
                gate_decision=decision.gate_decision,
                metrics=decision.metrics,
            )
            claim_ids.append(row.claim_id)
            n_accept += 1 if decision.gate_decision == "ACCEPT" else 0
            decisions.append(
                {
                    "index": entry["index"],
                    "hypothesis": entry["hypothesis"],
                    "claim_id": row.claim_id,
                    "gate_decision": decision.gate_decision,
                    "verdict": decision.verdict,
                    "reasons": list(decision.metrics["reasons"]),
                }
            )

        payload = write_payload(
            ctx,
            "gate.json",
            {"decisions": decisions, "n_claims": len(claim_ids), "n_accept": n_accept},
        )

        if n_accept == 0:
            return SegmentArtifact(
                segment_id=self.segment_id,
                status=SegmentStatus.REFUSED,
                artifact_path=payload,
                claim_ids=claim_ids,
                gate_summary={
                    "claims": len(claim_ids),
                    "n_accept": 0,
                    "decisions": decisions,
                    "reason": (
                        "no claim cleared the gate: every hypothesis in this run is "
                        "UNDECIDABLE, MARGINAL or REJECT, and a run with nothing readable "
                        "in it has nothing to hand downstream"
                    ),
                },
                run_fingerprint=ctx.fingerprint,
            )

        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=payload,
            claim_ids=claim_ids,
            gate_summary={"claims": len(claim_ids), "n_accept": n_accept, "decisions": decisions},
            run_fingerprint=ctx.fingerprint,
        )


__all__ = [
    "Adjudication",
    "DECISION_BY_VERDICT",
    "GateSegment",
    "METRIC_KEYS",
    "adjudicate",
    "run_result_from_evidence",
]
