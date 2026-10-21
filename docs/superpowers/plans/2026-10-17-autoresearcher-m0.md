# autoresearcher M0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new package `autoresearcher` whose segments ①→⑤ run offline end to end, where the only way any segment can read an earlier segment's output is through the hash-chained `claim_ledger.jsonl`, and where `researcher recompute <run_dir>` re-derives every gate decision from the files on disk.

**Architecture:** Five segments (issue / literature / hypothesize / experiment / gate) implement one `Segment` protocol; `run_chain` writes a `segment_artifact` envelope per segment and stops the chain the moment one returns `REFUSED`. Segment ⑤ is the only gate in M0: it rebuilds each experiment's `RunResult` from the evidence file, verifies the run against the pre-registration that was written to the ledger **before** the subprocess started, then hands the measurement to arx's `EvaluationGate`. Every claim row it writes can be re-decided from disk by the same function the gate used.

**Tech Stack:** Python 3.12, arx (pinned git SHA, installed as `arx-researcher`), numpy (via arx), pytest, ruff, GitHub Actions.

**Spec:** `/home/liuzewen/project-review-20261013/docs/superpowers/specs/2026-10-17-autonomous-research-agent-design.md`

---

## Decisions taken (the spec was ambiguous in three places)

The spec is the authority. Where it did not say, these are the choices, each with the alternative spelled out. Flip any of them before Task 1 and the affected tasks get rewritten.

**D1 — How ⑤ maps verdicts to `gate_decision`, and when the chain stops.**
The spec says both "⑤ 四拒一警 → ACCEPT|MARGINAL|UNDECIDABLE|REJECT" and "⑤/⑦ 开出 UNDECIDABLE/MARGINAL 时链路停住". Those conflict for a single MARGINAL claim: a run of three hypotheses scoring READABLE, READABLE, MARGINAL has something defensible to say and one thing it cannot.
Chosen rule: **map by verdict** — READABLE→ACCEPT, MARGINAL→MARGINAL, UNREADABLE→REJECT, UNDECIDABLE→UNDECIDABLE — and **⑤ returns REFUSED if and only if no claim in this run scored ACCEPT**. A MARGINAL row travels, but it travels labelled, and §7's test ("无 ACCEPT 记录则下游无输入") holds literally.
Alternative not taken: any MARGINAL stops the chain. Rejected because it makes a three-hypothesis run all-or-nothing, discarding the readable claims instead of reporting them.

**D2 — `claim_ledger.jsonl` holds records, not only claims.**
The spec says "每一行一条 claim". But arx's `read_preregistration(records, text)` reads records of `kind == "pre_register"` out of a ledger, and the spec's own §1 leans on the ordering guarantee ("`k_max` decided before the experiment runs").
Chosen: the file **is** an arx `Ledger`. Its `kind="claim"` records are exactly the eight keys in §3.1 (`ClaimRow.from_record` maps a record's `hash` to the spec's `row_hash`); the non-claim records (`run_start`, `pre_register`, `run_end`) share the chain because a second chain would be a second thing to verify, and the ordering guarantee is a property of the chain.
Alternative not taken: a separate `preregistration.jsonl`. Rejected because it needs its own hash chain and its own verifier.

**D3 — M0 excludes arx's sequential and multiplicity layers.**
arx's own agent applies `SequentialState` + `MultiplicityLedger` after the gate. The spec's §2 row for ⑤ lists only `gate.py` + `audit/{floor,power,goodhart,auditor}.py`, so gate-only sits inside the spec. Both layers act on a *family* whose meaning arrives with ⑥⑦ — the family size is the number of hypotheses tested, and `se`/`k_max` describe looks *within* one hypothesis.
Deferred to M1 explicitly, not silently: `GateSegment` runs `EvaluationGate.decision(...)` alone and its module docstring says so.

---

## M0 scope

**In:** scaffolding; the frozen claim-row schema; the `segment_artifact` transport; `ClaimLedger`; the environment fingerprint; `Segment`/`run_chain`/`SegmentContext`; segments ①–⑤; offline dry-run fixtures; `researcher run --dry-run`; `verify-ledger`; `recompute`; `doctor`; the refusal tests; CI.

**Out (M1+):** segments ⑥⑦⑧; `draft.md`; `gate_decisions.jsonl`; the sequential and multiplicity layers; LaTeX; live literature search (the code path exists, it is not exercised); submission packaging.

**Acceptance (verbatim from the spec's M0 judge):** `researcher run --dry-run` completes offline with zero API keys, and the run directory contains `claim_ledger.jsonl` + `segments/*.json` + `artifacts/*.json` + `evidence/experiment-*.json`.

---

## File structure

New repo at `/home/liuzewen/autoresearcher`.

| Path | Responsibility |
|---|---|
| `pyproject.toml` | metadata; pins arx by SHA; ruff + pytest config |
| `src/autoresearcher/__init__.py` | `__version__` |
| `src/autoresearcher/claim.py` | §3.1 schema: `ClaimRow`, `CLAIM_FIELDS`, `GATE_DECISIONS`, `ClaimLedger` |
| `src/autoresearcher/artifact.py` | §3.2 schema: `SegmentStatus`, `SegmentArtifact`, `write_artifact`/`read_artifact` |
| `src/autoresearcher/fingerprint.py` | environment fingerprint + its digest |
| `src/autoresearcher/config.py` | `offline_config()` for arx's `AgentConfig` |
| `src/autoresearcher/segments/base.py` | `SegmentContext`, `Segment`, `run_chain`, `ChainResult`, payload/evidence I/O |
| `src/autoresearcher/segments/issue.py` | ① |
| `src/autoresearcher/segments/literature.py` | ② |
| `src/autoresearcher/segments/hypothesize.py` | ③ |
| `src/autoresearcher/segments/experiment.py` | ④ + `TemplateExperimentProvider` |
| `src/autoresearcher/segments/gate.py` | ⑤ + `adjudicate()` + `METRIC_KEYS` |
| `src/autoresearcher/dryrun.py` | offline components for `--dry-run` |
| `src/autoresearcher/pipeline.py` | wires the chain for one run |
| `src/autoresearcher/recompute.py` | re-decides every claim from disk |
| `src/autoresearcher/cli.py` | `run` / `verify-ledger` / `recompute` / `doctor` |
| `src/autoresearcher/fixtures/*` | canned papers, seeded hypotheses, experiment template |
| `tests/…` | one file per unit, plus the chain-level and passage tests |
| `.github/workflows/ci.yml` | ruff + pytest + one dry run + verify-ledger |

Files that change together live together: the whole §3.1 schema is in `claim.py`, the whole §3.2 schema in `artifact.py`, and each pipeline segment in one file.

---

## Fixture values are measured, not guessed

These were measured against the pinned arx (`arx-researcher` 0.3.0). The table was
re-measured on 2026-10-17 after the fixture constants were corrected to
`AGREEMENT = 0.92` / `STRONG = 0.94`: that correction is what puts claim 3 into the
marginal band, and the third hypothesis exists precisely to be the marginal one.

```
== 5 generators (the dry-run fixture) ==
claim 1: READABLE  leader=strong  leader_score=0.9475 floor=0.9155  margin=0.032   mde=0.031242
                   mde_method=binomial_approx  n_items=400  n_generators=5  reasons=[]
claim 2: READABLE  leader=strong  leader_score=0.9275 floor=0.885   margin=0.0425  mde=0.036325
claim 3: MARGINAL  leader=strong  leader_score=0.93   floor=0.9015  margin=0.0285  mde=0.035741
                   reasons=['margin +0.0285 is inside the resolution bound 0.0357']
== 2 generators ==
UNDECIDABLE, reasons=['floor_degenerate'], floor=None, margin=None
```

`plan_k_max` for the fixture priors (`confidence` 0.6 / 0.5 / 0.4 at `effect_se_ratio=0.5`) returns **7 / 8 / 9**.

Exact assertions in Task 10, Task 11 and Task 14 come from this table. If a number ever differs, re-measure with the probe in the appendix and fix the *fixture*, never the assertion.

---

## Task 1: Scaffold the repository

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `README.md`
- Create: `src/autoresearcher/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create the tree and initialise git**

```bash
mkdir -p /home/liuzewen/autoresearcher/src/autoresearcher/segments \
         /home/liuzewen/autoresearcher/src/autoresearcher/fixtures \
         /home/liuzewen/autoresearcher/tests
git -C /home/liuzewen/autoresearcher init -b main
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "autoresearcher"
version = "0.1.0"
description = "A research pipeline in which every segment's output must clear a statistical gate before the next segment may read it."
readme = "README.md"
requires-python = ">=3.12"
license = { text = "Apache-2.0" }
dependencies = [
  "numpy>=1.26",
  "arx-researcher @ git+https://github.com/aidless/arx.git@24845f207fe967866d0ebb8bd11aa212e9d7ea99",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.5"]

[project.scripts]
researcher = "autoresearcher.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/autoresearcher"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

The arx pin is a commit SHA, not a branch: the numbers above were measured against that tree, and a floating branch would let them drift. `pip install -e .` fetches it from GitHub — the same thing CI does, which is why dev and CI cannot diverge. If the network is down, `pip install -e /home/liuzewen/project-review-20261013/verify/arx` satisfies the same import surface from the identical tree; the pin stays in `pyproject.toml` because that is what a clean clone resolves.

`numpy` is declared even though arx brings it transitively, because `segments/gate.py` imports it directly.

- [ ] **Step 3: Write `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.ruff_cache/
.venv/
runs/
dist/
build/
```

`runs/` is ignored on purpose: a run directory records the environment it ran in, and that includes the machine's paths. Runs are generated and verified in CI, never committed.

- [ ] **Step 4: Write `src/autoresearcher/__init__.py`**

```python
"""A research pipeline whose segments can only reach each other through a ledger.

The package is deliberately thin at the top: the schemas live in ``claim`` and
``artifact``, the pipeline in ``segments``, and the CLI on top of ``pipeline``.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
```

- [ ] **Step 5: Write `tests/conftest.py`**

```python
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
```

- [ ] **Step 6: Write `README.md`**

```markdown
# autoresearcher

A research pipeline in which every segment's output has to clear a statistical
gate before the next segment may read it. When a segment cannot support its
output, the chain stops and says so — the refusal is the tool working.

Status: **M0** — segments 1-5 run offline end to end. The gated writer (6), the
self-audit gate (7) and submission packaging (8) are not built yet.

## Install and run

```bash
git clone <this repo>
cd autoresearcher
python3 -m pip install -e ".[dev]"
python3 -m autoresearcher.cli run --dry-run \
    "does a noise floor bound what a leaderboard can claim" --out runs/demo
python3 -m autoresearcher.cli verify-ledger runs/demo/claim_ledger.jsonl
python3 -m autoresearcher.cli recompute runs/demo
```

`--dry-run` consults no model and no network. Everything it prints was produced
by the code in this repository.

## Why the gate is the only passage

A later segment reads an earlier one's output in exactly one way: the file the
earlier segment wrote, named by its `segment_artifact`. There is no shared
mutable state and no accessor that returns a neighbour's result, so a segment
whose producer refused has nothing to run on rather than something it must
decline to use.

## Recomputing a decision

```bash
python3 -m autoresearcher.cli recompute runs/demo
```

re-derives every gate decision from the evidence files and the ledger, and
compares the result field by field against what was written down. It calls the
same `adjudicate()` the gate called, so it cannot drift from the gate — only
from the files.
```

- [ ] **Step 7: Install and verify the pin resolves**

Run: `cd /home/liuzewen/autoresearcher && python3 -m pip install -e ".[dev]"`
Expected: `Successfully installed arx-researcher-... autoresearcher-0.1.0`, no traceback.

Run: `python3 -c "import arx; print(arx.__version__)"`
Expected: a version line.

- [ ] **Step 8: Verify pytest and ruff run against an empty suite**

Run: `cd /home/liuzewen/autoresearcher && python3 -m pytest && python3 -m ruff check .`
Expected: `no tests ran`, then `All checks passed!`

- [ ] **Step 9: Commit**

```bash
cd /home/liuzewen/autoresearcher
git add pyproject.toml .gitignore README.md src/autoresearcher/__init__.py tests/conftest.py
git commit -m "chore: scaffold autoresearcher, pinned to arx by SHA"
```

---

## Task 2: The §3.1 claim row and its frozen vocabulary

**Files:**
- Create: `src/autoresearcher/claim.py`
- Test: `tests/test_claim_ledger.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import pytest

from autoresearcher.claim import CLAIM_FIELDS, GATE_DECISIONS, ClaimRow


def test_claim_fields_are_exactly_the_spec_schema() -> None:
    assert CLAIM_FIELDS == (
        "claim_id",
        "segment",
        "text",
        "evidence_ref",
        "gate_decision",
        "metrics",
        "prev_hash",
        "row_hash",
    )


def test_gate_decisions_are_the_four_arx_verdicts_plus_no_decision() -> None:
    assert GATE_DECISIONS == ("ACCEPT", "MARGINAL", "UNDECIDABLE", "REJECT", None)


def test_flat_dict_has_exactly_the_frozen_keys() -> None:
    row = ClaimRow(
        claim_id="gate:000",
        segment="gate",
        text="a claim",
        evidence_ref="evidence/experiment-000.json:1",
        gate_decision="ACCEPT",
        metrics={"margin": 0.0495},
        prev_hash="0" * 64,
        row_hash="1" * 64,
    )
    assert tuple(row.to_flat_dict()) == CLAIM_FIELDS


def test_an_unknown_gate_decision_is_refused() -> None:
    with pytest.raises(ValueError, match="gate_decision"):
        ClaimRow(
            claim_id="gate:000",
            segment="gate",
            text="a claim",
            evidence_ref="evidence/experiment-000.json:1",
            gate_decision="PROBABLY",
            metrics={},
            prev_hash="0" * 64,
            row_hash="1" * 64,
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_claim_ledger.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoresearcher.claim'`

- [ ] **Step 3: Write the implementation**

```python
"""The claim-ledger schema: one row per claim, and the vocabulary it is made of.

This module is the only place the §3.1 keys are written down. Downstream code
reads claims through :meth:`ClaimLedger.rows`, which refuses a record that lost
a field — a claim missing its evidence anchor is not a claim, it is an assertion
with a hash attached.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CLAIM_FIELDS: tuple[str, ...] = (
    "claim_id",
    "segment",
    "text",
    "evidence_ref",
    "gate_decision",
    "metrics",
    "prev_hash",
    "row_hash",
)

#: arx's four verdicts, plus ``None`` for "this segment writes claims but has not
#: judged this one" — which only a measurement-free segment may use.
GATE_DECISIONS: tuple[str | None, ...] = (
    "ACCEPT",
    "MARGINAL",
    "UNDECIDABLE",
    "REJECT",
    None,
)


@dataclass(frozen=True)
class ClaimRow:
    """One row of ``claim_ledger.jsonl``.

    ``prev_hash`` and ``row_hash`` are the chain links arx's ``Ledger`` already
    computes; the row carries them so a reader does not have to re-open the
    ledger to check that a claim they were handed belongs to the chain.
    """

    claim_id: str
    segment: str
    text: str
    evidence_ref: str
    gate_decision: str | None
    metrics: dict = field(default_factory=dict)
    prev_hash: str = ""
    row_hash: str = ""

    def __post_init__(self) -> None:
        if self.gate_decision not in GATE_DECISIONS:
            raise ValueError(
                f"unknown gate_decision {self.gate_decision!r}; "
                f"known decisions are {GATE_DECISIONS}"
            )

    def to_flat_dict(self) -> dict:
        return {name: getattr(self, name) for name in CLAIM_FIELDS}

    @classmethod
    def from_record(cls, record: dict) -> ClaimRow:
        """Project an arx ledger record onto the spec's eight keys.

        The record's ``hash`` becomes the row's ``row_hash``. The rename is the
        spec's, and this is the only place the two names diverge, so it is done
        once, here.
        """
        return cls(
            claim_id=str(record["claim_id"]),
            segment=str(record["segment"]),
            text=str(record["text"]),
            evidence_ref=str(record["evidence_ref"]),
            gate_decision=record.get("gate_decision"),
            metrics=dict(record.get("metrics") or {}),
            prev_hash=str(record.get("prev_hash", "")),
            row_hash=str(record.get("hash", "")),
        )


__all__ = ["CLAIM_FIELDS", "GATE_DECISIONS", "ClaimRow"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_claim_ledger.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoresearcher/claim.py tests/test_claim_ledger.py
git commit -m "feat: freeze the claim-row schema and the gate vocabulary"
```

---

## Task 3: `ClaimLedger`, verified by arx's own verifier

**Files:**
- Modify: `src/autoresearcher/claim.py`
- Test: `tests/test_claim_ledger.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_claim_ledger.py`:

```python
import json
from pathlib import Path

from arx.experiments.ledger import verify_ledger_file

from autoresearcher.claim import ClaimLedger


def _ledger(tmp_path: Path) -> ClaimLedger:
    return ClaimLedger(tmp_path / "claim_ledger.jsonl")


def _append_first(ledger: ClaimLedger):
    return ledger.append_claim(
        claim_id=ledger.next_claim_id("gate"),
        segment="gate",
        text="first",
        evidence_ref="evidence/experiment-000.json:1",
        gate_decision="ACCEPT",
        metrics={"margin": 0.0495},
    )


def test_two_claims_chain_to_each_other(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.append_record("run_start", {"topic": "t"})
    first = _append_first(ledger)
    second = ledger.append_claim(
        claim_id=ledger.next_claim_id("gate"),
        segment="gate",
        text="second",
        evidence_ref="evidence/experiment-001.json:1",
        gate_decision="MARGINAL",
        metrics={"margin": 0.0265},
    )
    assert first.claim_id == "gate:000"
    assert second.claim_id == "gate:001"
    assert second.prev_hash == first.row_hash


def test_arx_verify_ledger_accepts_the_file(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.append_record("run_start", {"topic": "t"})
    _append_first(ledger)
    report = verify_ledger_file(ledger.path)
    assert report.ok is True
    assert report.n_records == 2


def test_rows_reads_back_the_frozen_fields(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.append_record("run_start", {"topic": "t"})
    _append_first(ledger)
    rows = ledger.rows()
    assert len(rows) == 1
    assert tuple(rows[0].to_flat_dict()) == CLAIM_FIELDS
    assert rows[0].row_hash == ledger.as_records()[-1]["hash"]


def test_a_missing_field_is_refused_on_read(tmp_path: Path) -> None:
    path = tmp_path / "claim_ledger.jsonl"
    path.write_text(
        json.dumps({"kind": "claim", "claim_id": "gate:000", "segment": "gate"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing claim fields"):
        ClaimLedger(path).rows()


def test_next_claim_id_counts_only_claims_of_that_segment(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.append_record("pre_register", {"hypothesis": "h"})
    assert ledger.next_claim_id("gate") == "gate:000"
    _append_first(ledger)
    assert ledger.next_claim_id("gate") == "gate:001"
    assert ledger.next_claim_id("literature") == "literature:000"
```

`arx.experiments.ledger.verify_ledger_file` is arx's own verifier. If it accepts our file then the chain is arx's chain and not a lookalike — that is the whole reason for this test.

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_claim_ledger.py -v`
Expected: FAIL with `ImportError: cannot import name 'ClaimLedger'`

- [ ] **Step 3: Add the implementation to `src/autoresearcher/claim.py`**

Add `from pathlib import Path` and these imports to the top:

```python
from pathlib import Path

from arx.experiments.ledger import Ledger, verify_ledger_file
```

Append below `ClaimRow`:

```python
class ClaimLedger:
    """The run's append-only ledger, and the only channel between segments.

    Wraps arx's ``Ledger`` rather than reimplementing it: the chain arithmetic is
    arx's, so ``arx verify-ledger`` and ``arx replay`` read our file with no
    adapter. What this class adds is the §3.1 projection, and the rule that a
    claim row must carry every field.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._ledger = Ledger(self.path)

    def append_record(self, kind: str, payload: dict) -> dict:
        """Append a non-claim record (``run_start``, ``pre_register``, ...).

        These share the claim file because the ordering guarantee the gate relies
        on — ``k_max`` written before the experiment ran — is a property of the
        chain, and a second chain would be a second thing to verify.
        """
        return self._ledger.append(kind, payload)

    def append_claim(
        self,
        *,
        claim_id: str,
        segment: str,
        text: str,
        evidence_ref: str,
        gate_decision: str | None,
        metrics: dict,
    ) -> ClaimRow:
        """Append a claim and return it with its chain links filled in."""
        row = ClaimRow(
            claim_id=claim_id,
            segment=segment,
            text=text,
            evidence_ref=evidence_ref,
            gate_decision=gate_decision,
            metrics=metrics,
        )
        self._ledger.append("claim", row.to_flat_dict())
        written = self.as_records()[-1]
        return ClaimRow.from_record({**written["payload"], **written})

    def as_records(self) -> list[dict]:
        """Every record, for arx's ``read_preregistration``."""
        return self._ledger.as_dicts()

    def rows(self) -> list[ClaimRow]:
        """Every claim row, refusing a record that lost a field."""
        out: list[ClaimRow] = []
        for record in self.as_records():
            if record.get("kind") != "claim":
                continue
            payload = record.get("payload", {})
            missing = [name for name in CLAIM_FIELDS if name not in payload]
            if missing:
                raise ValueError(
                    f"claim at seq {record.get('seq')} is missing claim fields {missing}; "
                    "a claim without its evidence anchor is not a claim"
                )
            out.append(ClaimRow.from_record({**record, **payload}))
        return out

    def by_segment(self, segment: str) -> list[ClaimRow]:
        return [row for row in self.rows() if row.segment == segment]

    def accepted(self) -> list[ClaimRow]:
        return [row for row in self.rows() if row.gate_decision == "ACCEPT"]

    def next_claim_id(self, segment: str) -> str:
        """``segment:NNN``, counted within that segment only.

        Derivable before appending, which is what lets ⑤ name a claim inside the
        other fields of its own row.
        """
        return f"{segment}:{len(self.by_segment(segment)):03d}"

    def verify(self) -> bool:
        return bool(verify_ledger_file(self.path).ok)
```

Update `__all__`:

```python
__all__ = ["CLAIM_FIELDS", "GATE_DECISIONS", "ClaimLedger", "ClaimRow"]
```

Two details worth stating because they are easy to get wrong:

* `Ledger.append(kind, payload)` returns the record envelope; `append_claim` merges the envelope and its payload back into one flat dict so the eight keys land in `payload` where `rows()` looks for them. Reading `self.as_records()[-1]` after the append avoids guessing the envelope's return shape.
* `next_claim_id` counts claims **of that segment**. A run-level counter would make a `literature` row appear to depend on `gate` rows written later.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_claim_ledger.py -v`
Expected: 9 passed

If `Ledger.append` or `as_dicts()` differ from the two assumptions above, fix `append_claim`/`rows`/`as_records` here and re-run — this is the only place the plan depends on arx's record envelope, and the tests fail loudly if it moves.

- [ ] **Step 5: Commit**

```bash
git add src/autoresearcher/claim.py tests/test_claim_ledger.py
git commit -m "feat: ClaimLedger on arx's hash chain, accepted by arx's own verifier"
```

---

## Task 4: The `segment_artifact` transport

**Files:**
- Create: `src/autoresearcher/artifact.py`
- Test: `tests/test_segment_artifact.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from autoresearcher.artifact import SegmentArtifact, SegmentStatus, read_artifact, write_artifact


def test_a_refused_artifact_must_state_a_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        SegmentArtifact(
            segment_id="gate",
            status=SegmentStatus.REFUSED,
            artifact_path="artifacts/gate.json",
            claim_ids=["gate:000"],
            gate_summary={"claims": 1},
            run_fingerprint="abc",
        )


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    artifact = SegmentArtifact(
        segment_id="gate",
        status=SegmentStatus.REFUSED,
        artifact_path="artifacts/gate.json",
        claim_ids=["gate:000"],
        gate_summary={"claims": 1, "reason": "no claim cleared the gate"},
        run_fingerprint="abc",
    )
    stored = write_artifact(artifact, tmp_path / "segments" / "gate.json")
    assert read_artifact(tmp_path / "segments" / "gate.json") == stored
    assert stored.refusal_reason() == "no claim cleared the gate"


def test_an_ok_artifact_needs_no_reason() -> None:
    artifact = SegmentArtifact(
        segment_id="issue",
        status=SegmentStatus.OK,
        artifact_path="artifacts/issue.json",
        claim_ids=[],
        gate_summary={"claims": 0},
        run_fingerprint="abc",
    )
    assert artifact.refusal_reason() == ""
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_segment_artifact.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoresearcher.artifact'`

- [ ] **Step 3: Write the implementation**

```python
"""The segment transport: what one segment hands the next.

Two fields carry the design's weight. ``status`` is what makes the chain stop;
``artifact_path`` is the only address a later segment may read its input from,
which is why it is stored relative to the run directory — see
``segments.base.read_payload``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SegmentStatus(str, Enum):
    OK = "OK"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class SegmentArtifact:
    """One segment's envelope."""

    segment_id: str
    status: SegmentStatus
    artifact_path: str
    claim_ids: list[str] = field(default_factory=list)
    gate_summary: dict = field(default_factory=dict)
    run_fingerprint: str = ""

    def __post_init__(self) -> None:
        if self.status is SegmentStatus.REFUSED and not self.gate_summary.get("reason"):
            raise ValueError(
                "a REFUSED artifact must carry gate_summary['reason']: a refusal "
                "that cannot be explained cannot be reported"
            )

    def refusal_reason(self) -> str:
        if self.status is not SegmentStatus.REFUSED:
            return ""
        return str(self.gate_summary.get("reason", ""))

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "status": self.status.value,
            "artifact_path": self.artifact_path,
            "claim_ids": list(self.claim_ids),
            "gate_summary": dict(self.gate_summary),
            "run_fingerprint": self.run_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SegmentArtifact:
        return cls(
            segment_id=str(data["segment_id"]),
            status=SegmentStatus(data["status"]),
            artifact_path=str(data["artifact_path"]),
            claim_ids=list(data.get("claim_ids") or []),
            gate_summary=dict(data.get("gate_summary") or {}),
            run_fingerprint=str(data.get("run_fingerprint", "")),
        )


def write_artifact(artifact: SegmentArtifact, path: Path) -> SegmentArtifact:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return artifact


def read_artifact(path: Path) -> SegmentArtifact:
    return SegmentArtifact.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


__all__ = ["SegmentArtifact", "SegmentStatus", "read_artifact", "write_artifact"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_segment_artifact.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoresearcher/artifact.py tests/test_segment_artifact.py
git commit -m "feat: the segment_artifact transport, with the refusal-reason invariant"
```

---

## Task 5: Environment fingerprint

**Files:**
- Create: `src/autoresearcher/fingerprint.py`
- Test: `tests/test_fingerprint.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

The second test is the one that matters: a run directory travels — it gets emailed, published, diffed against someone else's — and a fingerprint that recorded `/home/<name>/…` would leak the machine that produced it. The run directory's own path is deliberately **not** in the fingerprint for that reason.

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_fingerprint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoresearcher.fingerprint'`

- [ ] **Step 3: Write the implementation**

```python
"""What a run was produced by, in enough detail to check a rerun against it."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import arx

from autoresearcher import __version__


def environment_fingerprint(*, run_dir: Path | None = None) -> dict:
    """Version-level facts about this interpreter.

    ``run_dir`` is accepted and ignored on purpose: callers have a directory in
    hand when they ask, and the signature records that the path is deliberately
    not part of the fingerprint. Nothing here reads the working directory, the
    user, or the hostname, because a run directory is meant to be publishable.
    """
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.system().lower(),
        "machine": platform.machine(),
        "arx_version": getattr(arx, "__version__", "unknown"),
        "autoresearcher_version": __version__,
    }


def fingerprint_digest(fingerprint: dict) -> str:
    """A stable id for a fingerprint: key order must not change the digest."""
    canonical = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["environment_fingerprint", "fingerprint_digest"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_fingerprint.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoresearcher/fingerprint.py tests/test_fingerprint.py
git commit -m "feat: run fingerprint, without the machine's paths"
```

---

## Task 6: `Segment`, `SegmentContext`, `run_chain`

**Files:**
- Create: `src/autoresearcher/segments/__init__.py`
- Create: `src/autoresearcher/segments/base.py`
- Test: `tests/test_chain.py`
- Create: `tests/tests_helpers.py`

- [ ] **Step 1: Write the failing tests**

`tests/tests_helpers.py`:

```python
"""Context construction shared by the segment tests."""

from __future__ import annotations

from pathlib import Path

from autoresearcher.claim import ClaimLedger
from autoresearcher.segments.base import SegmentContext


def make_context(tmp_path: Path, topic: str = "a topic") -> SegmentContext:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return SegmentContext(
        run_dir=run_dir,
        topic=topic,
        ledger=ClaimLedger(run_dir / "claim_ledger.jsonl"),
        fingerprint="deadbeef",
    )
```

`tests/test_chain.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import (
    ChainResult,
    MissingUpstream,
    PayloadRefused,
    SegmentContext,
    read_evidence_ref,
    run_chain,
    write_payload,
)
from tests_helpers import make_context


class _Stub:
    def __init__(self, segment_id: str, status: SegmentStatus = SegmentStatus.OK) -> None:
        self.segment_id = segment_id
        self.status = status
        self.ran = False

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        self.ran = True
        ref = write_payload(ctx, f"{self.segment_id}.json", {"from": self.segment_id})
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=self.status,
            artifact_path=ref,
            claim_ids=[],
            gate_summary=(
                {"reason": "deliberate refusal"} if self.status is SegmentStatus.REFUSED else {}
            ),
            run_fingerprint=ctx.fingerprint,
        )


def test_the_chain_stops_at_a_refusal(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    first, second, third = _Stub("a"), _Stub("b", SegmentStatus.REFUSED), _Stub("c")
    result = run_chain([first, second, third], ctx, envelopes_dir=ctx.run_dir / "segments")
    assert isinstance(result, ChainResult)
    assert result.completed is False
    assert result.stopped_at == "b"
    assert result.refusal == "deliberate refusal"
    assert third.ran is False


def test_a_completed_chain_runs_every_segment(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    segments = [_Stub("a"), _Stub("b"), _Stub("c")]
    result = run_chain(segments, ctx, envelopes_dir=ctx.run_dir / "segments")
    assert result.completed is True
    assert result.stopped_at is None
    assert [segment.ran for segment in segments] == [True, True, True]


def test_a_downstream_segment_reads_its_upstream_payload(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    run_chain([_Stub("a")], ctx, envelopes_dir=ctx.run_dir / "segments")
    assert ctx.upstream_payload("a") == {"from": "a"}


def test_reading_a_segment_that_never_ran_is_refused(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    with pytest.raises(MissingUpstream, match="no 'gate' artifact"):
        ctx.upstream_payload("gate")


def test_reading_a_refused_segment_is_refused(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    run_chain([_Stub("a", SegmentStatus.REFUSED)], ctx, envelopes_dir=ctx.run_dir / "segments")
    with pytest.raises(PayloadRefused, match="deliberate refusal"):
        ctx.upstream_payload("a")


def test_an_absolute_evidence_ref_is_refused(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    with pytest.raises(ValueError, match="relative"):
        read_evidence_ref(ctx, "/home/someone/run/evidence/experiment-000.json:1")


def test_read_evidence_ref_resolves_and_reports_the_line(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    target = ctx.run_dir / "evidence" / "experiment-000.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"ok": true}\n', encoding="utf-8")
    payload, line = read_evidence_ref(ctx, "evidence/experiment-000.json:1")
    assert payload == {"ok": True}
    assert line == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_chain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoresearcher.segments'`

- [ ] **Step 3: Write `src/autoresearcher/segments/__init__.py`**

```python
"""The pipeline, one module per segment."""

from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 4: Write `src/autoresearcher/segments/base.py`**

```python
"""The segment protocol, the run context, and the chain that stops on refusal.

A segment may read an earlier segment's output in exactly one way: through the
artifact that segment wrote. There is no shared mutable state, no accessor that
returns a neighbour's result, and no path from a later segment back into an
earlier one. That is the design's "闸门即通路" stated as an API, and
``tests/test_gate_is_the_only_passage.py`` holds it to it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from autoresearcher.artifact import SegmentArtifact, SegmentStatus, read_artifact, write_artifact
from autoresearcher.claim import ClaimLedger


class MissingUpstream(RuntimeError):
    """A segment tried to read an input that does not exist."""


class PayloadRefused(RuntimeError):
    """A segment tried to read an input whose producer refused."""


@dataclass
class SegmentContext:
    """What a segment knows: where the run lives, and what ran before it."""

    run_dir: Path
    topic: str
    ledger: ClaimLedger
    fingerprint: str
    upstream: dict[str, SegmentArtifact] = field(default_factory=dict)

    def upstream_payload(self, segment_id: str) -> dict:
        """Read an earlier segment's payload, or refuse.

        A missing artifact raises instead of returning ``{}``: a segment that
        proceeds without its input has bypassed the gate, which is the one thing
        this design exists to prevent. Failing loudly is the feature.
        """
        artifact = self.upstream.get(segment_id)
        if artifact is None:
            raise MissingUpstream(f"no {segment_id!r} artifact in this run")
        if artifact.status is SegmentStatus.REFUSED:
            raise PayloadRefused(
                f"{segment_id!r} refused, so its output is not available: "
                f"{artifact.refusal_reason()}"
            )
        return read_payload(self, artifact.artifact_path)


class Segment(Protocol):
    """One stage of the pipeline."""

    segment_id: str

    def run(self, ctx: SegmentContext) -> SegmentArtifact: ...


@dataclass(frozen=True)
class ChainResult:
    artifacts: list[SegmentArtifact]
    stopped_at: str | None = None
    refusal: str = ""

    @property
    def completed(self) -> bool:
        return self.stopped_at is None

    def status_of(self, segment_id: str) -> SegmentStatus | None:
        for artifact in self.artifacts:
            if artifact.segment_id == segment_id:
                return artifact.status
        return None


def write_payload(ctx: SegmentContext, name: str, data: object) -> str:
    """Write a segment's payload and return the path the artifact points at.

    The returned path is relative to the run directory. An absolute path here
    would put the author's home directory into the ledger, and the ledger is
    meant to be published.
    """
    relative = (Path("artifacts") / name).as_posix()
    target = ctx.run_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return relative


def read_payload(ctx: SegmentContext, relative: str) -> dict:
    return json.loads(_resolve_relative(ctx, relative).read_text(encoding="utf-8"))


def read_evidence_ref(ctx: SegmentContext, ref: str) -> tuple[dict, int]:
    """Read a ``path:line`` anchor and return the payload and the line it names.

    Anchors are relative for the same reason payload paths are, and the check is
    here rather than at each call site so that no segment can opt out of it.
    """
    if ":" not in ref:
        raise ValueError(f"evidence ref {ref!r} is not a path:line anchor")
    path_part, line_part = ref.rsplit(":", 1)
    return read_payload(ctx, path_part), int(line_part)


def _resolve_relative(ctx: SegmentContext, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError(
            f"artifact path {relative!r} must be relative to the run directory; "
            "an absolute path would publish the machine that produced it"
        )
    return ctx.run_dir / candidate


def run_chain(
    segments: Sequence[Segment], ctx: SegmentContext, *, envelopes_dir: Path
) -> ChainResult:
    """Run segments in order and stop at the first refusal.

    Stopping is not error handling. A refused segment has told us what it could
    not support, and everything after it would be built on a number nobody
    stands behind.
    """
    artifacts: list[SegmentArtifact] = []
    for segment in segments:
        artifact = write_artifact(segment.run(ctx), envelopes_dir / f"{segment.segment_id}.json")
        ctx.upstream[segment.segment_id] = artifact
        artifacts.append(artifact)
        if artifact.status is SegmentStatus.REFUSED:
            return ChainResult(
                artifacts=artifacts,
                stopped_at=segment.segment_id,
                refusal=artifact.refusal_reason(),
            )
    return ChainResult(artifacts=artifacts)


__all__ = [
    "ChainResult",
    "MissingUpstream",
    "PayloadRefused",
    "Segment",
    "SegmentContext",
    "read_artifact",
    "read_evidence_ref",
    "read_payload",
    "run_chain",
    "write_payload",
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_chain.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add src/autoresearcher/segments/__init__.py src/autoresearcher/segments/base.py \
        tests/test_chain.py tests/tests_helpers.py
git commit -m "feat: segment protocol and a chain that stops on refusal"
```

---

## Task 7: `config.offline_config`

**Files:**
- Create: `src/autoresearcher/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from pathlib import Path

from autoresearcher.config import offline_config


def test_offline_config_reaches_no_network_and_declares_the_gate_settings(tmp_path: Path) -> None:
    flags = offline_config(tmp_path).ledger_flags()
    assert flags["llm_base_url"] == ""
    assert flags["llm_model"] == ""
    assert flags["gate_alpha"] == 0.05
    assert flags["gate_power"] == 0.8
    assert flags["gate_delta_declared"] == 0.02
    assert flags["sandbox_timeout_s"] > 0
```

The test asserts `ledger_flags()` rather than the config object, because `ledger_flags()` is what actually reaches the ledger — asserting the object would pass even if the flags never got recorded.

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoresearcher.config'`

- [ ] **Step 3: Write the implementation**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoresearcher/config.py tests/test_config.py
git commit -m "feat: the declared arx settings an offline run uses"
```

---

## Task 8: ① issue and ② literature

**Files:**
- Create: `src/autoresearcher/segments/issue.py`
- Create: `src/autoresearcher/segments/literature.py`
- Create: `src/autoresearcher/fixtures/dry_run_papers.json`
- Test: `tests/test_segments_issue_literature.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from pathlib import Path

from arx.literature.search import Paper, SearchOutcome

from autoresearcher.artifact import SegmentStatus
from autoresearcher.segments.base import run_chain
from autoresearcher.segments.issue import IssueSegment
from autoresearcher.segments.literature import LiteratureSegment
from tests_helpers import make_context


def _searcher(topic: str, max_results: int) -> SearchOutcome:
    assert max_results == 20
    return SearchOutcome(
        papers=[Paper(title="On the readability of leaderboards", year=2024, abstract="a")],
        sources_ok=["fixture"],
    )


def test_issue_writes_no_claim(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    artifact = IssueSegment(falsified_by="a claim that survives a floor test", gate_flags={}).run(ctx)
    assert artifact.status is SegmentStatus.OK
    assert artifact.claim_ids == []
    assert ctx.ledger.rows() == []
    assert ctx.upstream_payload("issue")["topic"] == "a topic"


def test_literature_records_what_it_consulted(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    chain = run_chain(
        [IssueSegment(), LiteratureSegment(searcher=_searcher, source="fixture")],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )
    assert chain.completed is True
    payload = ctx.upstream_payload("literature")
    assert payload["source"] == "fixture"
    assert payload["sources_ok"] == ["fixture"]
    assert [paper["title"] for paper in payload["papers"]] == ["On the readability of leaderboards"]
    assert payload["papers"][0]["abstract"] == "a"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_segments_issue_literature.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoresearcher.segments.issue'`

- [ ] **Step 3: Write `src/autoresearcher/segments/issue.py`**

```python
"""① — fix the topic, and state up front what would falsify it.

Nothing here is measured, so nothing here can produce a claim. That is why
``claim_ids`` is empty rather than why a decision is missing: a topic is not a
finding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import SegmentContext, write_payload


@dataclass
class IssueSegment:
    segment_id: str = "issue"
    falsified_by: str = ""
    gate_flags: dict = field(default_factory=dict)

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        payload = write_payload(
            ctx,
            "issue.json",
            {
                "topic": ctx.topic,
                "falsified_by": self.falsified_by,
                "gate_flags": dict(self.gate_flags),
                "run_fingerprint": ctx.fingerprint,
            },
        )
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=payload,
            claim_ids=[],
            gate_summary={
                "claims": 0,
                "note": "a topic is not a measurement, so this segment writes no claim",
            },
            run_fingerprint=ctx.fingerprint,
        )


__all__ = ["IssueSegment"]
```

- [ ] **Step 4: Write `src/autoresearcher/segments/literature.py`**

```python
"""② — sweep the literature and record what came back.

This segment transports, it does not judge: it has no gate, and it returns OK as
long as it can state honestly where its papers came from. An empty sweep is
recorded as an empty sweep rather than padded, which is what lets ③ be judged on
what it was actually given.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from arx.literature.search import Paper, SearchOutcome, search_all

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import SegmentContext, write_payload

Searcher = Callable[[str, int], SearchOutcome]


@dataclass
class LiteratureSegment:
    segment_id: str = "literature"
    searcher: Searcher | None = None
    max_results: int = 20
    source: str = "live"

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        searcher: Searcher = self.searcher or (
            lambda query, limit: search_all(query, max_results=limit)
        )
        outcome = searcher(ctx.topic, self.max_results)
        payload = write_payload(
            ctx,
            "literature.json",
            {
                "query": ctx.topic,
                "source": self.source,
                "papers": [_as_record(paper) for paper in outcome.papers],
                "sources_ok": list(outcome.sources_ok),
                "sources_failed": dict(outcome.sources_failed),
            },
        )
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=payload,
            claim_ids=[],
            gate_summary={
                "claims": 0,
                "n_papers": len(outcome.papers),
                "sources_ok": list(outcome.sources_ok),
                "sources_failed": dict(outcome.sources_failed),
                "note": "a sweep is not a measurement, so this segment writes no claim",
            },
            run_fingerprint=ctx.fingerprint,
        )


def _as_record(paper: Paper) -> dict:
    """``Paper.to_dict()`` plus the abstract.

    arx's own ``to_dict`` drops the abstract because its report writer does not
    need it; ③ does, and dropping the field here would surface later as a model
    being handed bare titles for no visible reason.
    """
    return {
        "title": paper.title,
        "authors": list(paper.authors),
        "year": paper.year,
        "abstract": paper.abstract,
        "url": paper.url,
        "doi": paper.doi,
        "source": paper.source,
    }


__all__ = ["LiteratureSegment"]
```

- [ ] **Step 5: Write `src/autoresearcher/fixtures/dry_run_papers.json`**

```json
[
  {
    "title": "On the readability of leaderboard margins",
    "authors": ["A. Author"],
    "year": 2024,
    "abstract": "A ranking difference is readable only if it clears the noise floor of the labels it was measured against.",
    "url": "",
    "doi": null,
    "source": "fixture"
  },
  {
    "title": "Judge panels as gold producers",
    "authors": ["B. Author"],
    "year": 2023,
    "abstract": "A noise floor is a property of who produced the labels, not of the board.",
    "url": "",
    "doi": null,
    "source": "fixture"
  }
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_segments_issue_literature.py -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add src/autoresearcher/segments/issue.py src/autoresearcher/segments/literature.py \
        src/autoresearcher/fixtures/dry_run_papers.json tests/test_segments_issue_literature.py
git commit -m "feat: segments 1 and 2, neither of which writes a claim"
```

---

## Task 9: ③ hypothesize

**Files:**
- Create: `src/autoresearcher/segments/hypothesize.py`
- Create: `src/autoresearcher/fixtures/dry_run_hypotheses.json`
- Test: `tests/test_segments_hypothesize.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from pathlib import Path

from arx.hypothesis import Hypothesis
from arx.llm import NullLLM

from autoresearcher.artifact import SegmentStatus
from autoresearcher.segments.hypothesize import HypothesizeSegment
from tests_helpers import make_context


def _seeded(*texts: str) -> list[Hypothesis]:
    return [
        Hypothesis(
            text=text,
            rationale="",
            origin="manual",
            confidence=0.5,
            expected_effect_se_ratio=0.5,
        )
        for text in texts
    ]


def test_a_seeded_run_proposes_without_consulting_a_model(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    segment = HypothesizeSegment(llm=NullLLM("dry-run"), seed_hypotheses=_seeded("h one"))
    artifact = segment.run(ctx)
    assert artifact.status is SegmentStatus.OK
    payload = ctx.upstream_payload("hypothesize")
    assert payload["llm"] == "none"
    assert payload["n_kept"] == 1
    assert payload["kept"][0]["expected_effect_se_ratio"] == 0.5


def test_duplicates_are_dropped_and_the_drop_is_recorded(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    segment = HypothesizeSegment(
        llm=NullLLM("dry-run"),
        seed_hypotheses=_seeded("a floor bounds a board", "a floor bounds a board"),
    )
    assert segment.run(ctx).status is SegmentStatus.OK
    payload = ctx.upstream_payload("hypothesize")
    assert payload["n_proposed"] == 2
    assert payload["n_kept"] == 1
    assert payload["dropped"][0]["duplicates"] == ["a floor bounds a board"]


def test_no_hypothesis_refuses_rather_than_cascading_emptiness(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    artifact = HypothesizeSegment(llm=NullLLM("dry-run")).run(ctx)
    assert artifact.status is SegmentStatus.REFUSED
    assert "nothing to test" in artifact.refusal_reason()
    assert artifact.claim_ids == []
    assert ctx.ledger.rows() == []


def test_a_single_hypothesis_is_not_dropped_as_its_own_duplicate(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    segment = HypothesizeSegment(llm=NullLLM("dry-run"), seed_hypotheses=_seeded("only one"))
    assert segment.run(ctx).status is SegmentStatus.OK
```

The last test exists because "a hypothesis is a duplicate of itself" is the classic way a one-item dedup crashes a pipeline that then has nothing to test.

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_segments_hypothesize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoresearcher.segments.hypothesize'`

- [ ] **Step 3: Write the implementation**

```python
"""③ — turn the sweep into a small set of testable statements.

The hypotheses travel with their two declared priors: ``confidence`` and
``expected_effect_se_ratio``. They are not decoration — ④ feeds them to
``plan_k_max`` to decide how many looks the hypothesis is allowed *before* the
experiment exists, which is the ordering guarantee the gate depends on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from arx.hypothesis import Hypothesis, deduplicate, generate
from arx.llm import ChatModel

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import SegmentContext, write_payload


@dataclass
class HypothesizeSegment:
    segment_id: str = "hypothesize"
    n: int = 3
    llm: ChatModel | None = None
    seed_hypotheses: list[Hypothesis] = field(default_factory=list)
    dedup_threshold: float = 0.6

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        literature = ctx.upstream_payload("literature")
        proposals, consulted = self._propose(ctx, literature)
        result = deduplicate(proposals, threshold=self.dedup_threshold)

        payload = write_payload(
            ctx,
            "hypothesize.json",
            {
                "llm": consulted,
                "n_proposed": len(proposals),
                "n_kept": len(result.kept),
                "kept": [hypothesis.to_dict() for hypothesis in result.kept],
                "dropped": [
                    {"text": hypothesis.text, "duplicates": list(hypothesis.duplicates)}
                    for hypothesis in result.dropped
                ],
            },
        )

        if not result.kept:
            return SegmentArtifact(
                segment_id=self.segment_id,
                status=SegmentStatus.REFUSED,
                artifact_path=payload,
                claim_ids=[],
                gate_summary={
                    "claims": 0,
                    "n_proposed": len(proposals),
                    "reason": (
                        "no hypothesis survived de-duplication, so there is nothing to "
                        "test; a run with nothing to test cannot reach a gate"
                    ),
                },
                run_fingerprint=ctx.fingerprint,
            )

        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=payload,
            claim_ids=[],
            gate_summary={"claims": 0, "n_kept": len(result.kept)},
            run_fingerprint=ctx.fingerprint,
        )

    def _propose(self, ctx: SegmentContext, literature: dict) -> tuple[list[Hypothesis], str]:
        """Either consult the model, or use the seeded hypotheses.

        The consulted name is recorded so a reader can tell a run that consulted
        a model from one that did not. A dry run that consulted nothing must not
        be able to look like one that did.
        """
        if self.llm is not None and getattr(self.llm, "available", False):
            context = "\n".join(
                [
                    "Relevant literature:",
                    *(
                        f"  - {paper['title']} ({paper.get('year') or 'n.d.'})"
                        for paper in literature["papers"][:8]
                    ),
                ]
            )
            return generate(self.llm, ctx.topic, n=self.n, context=context), str(self.llm)
        if not self.seed_hypotheses:
            return [], "none"
        # Round-trip through arx's own serialisation so ``deduplicate`` cannot
        # mutate the caller's objects: it writes ``duplicates`` onto them.
        seeded = [Hypothesis.from_dict(hypothesis.to_dict()) for hypothesis in self.seed_hypotheses]
        return seeded[: self.n], "none"


__all__ = ["HypothesizeSegment"]
```

- [ ] **Step 4: Write `src/autoresearcher/fixtures/dry_run_hypotheses.json`**

```json
[
  {
    "text": "A noise floor computed over five independent label producers bounds what a leaderboard leader can claim",
    "rationale": "The floor is a property of the producers, so a leader inside it is not separated by the apparatus.",
    "origin": "manual",
    "confidence": 0.6,
    "expected_effect_se_ratio": 0.5
  },
  {
    "text": "A five-producer floor separates a strong system but not a weak one",
    "rationale": "If the floor is meaningful, the strong system's margin clears it and the weak system's does not.",
    "origin": "manual",
    "confidence": 0.5,
    "expected_effect_se_ratio": 0.5
  },
  {
    "text": "Swapping the arithmetic mean for the median changes the leader when producers disagree at the margin",
    "rationale": "Aggregation choice should matter only where the margin is inside the resolution bound.",
    "origin": "manual",
    "confidence": 0.4,
    "expected_effect_se_ratio": 0.5
  }
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_segments_hypothesize.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/autoresearcher/segments/hypothesize.py \
        src/autoresearcher/fixtures/dry_run_hypotheses.json tests/test_segments_hypothesize.py
git commit -m "feat: segment 3, with the priors segment 4 pre-registers"
```

---

## Task 10: ④ experiment, pre-registration first

**Files:**
- Create: `src/autoresearcher/segments/experiment.py`
- Create: `src/autoresearcher/fixtures/dry_run_experiment.py.in`
- Test: `tests/test_segments_experiment.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import json
from pathlib import Path

import autoresearcher
from arx.hypothesis import Hypothesis
from arx.llm import NullLLM
from arx.literature.search import Paper, SearchOutcome

from autoresearcher.artifact import SegmentStatus
from autoresearcher.config import offline_config
from autoresearcher.segments.base import run_chain
from autoresearcher.segments.experiment import ExperimentSegment, TemplateExperimentProvider
from autoresearcher.segments.hypothesize import HypothesizeSegment
from autoresearcher.segments.issue import IssueSegment
from autoresearcher.segments.literature import LiteratureSegment
from tests_helpers import make_context

FIXTURES = Path(autoresearcher.__file__).parent / "fixtures"


def _searcher(topic: str, limit: int) -> SearchOutcome:
    return SearchOutcome(papers=[Paper(title="t", year=2024)], sources_ok=["fixture"])


def _hypothesis() -> Hypothesis:
    return Hypothesis(
        text="a floor bounds the leader",
        rationale="",
        origin="manual",
        confidence=0.5,
        expected_effect_se_ratio=0.5,
    )


def _template() -> str:
    return (FIXTURES / "dry_run_experiment.py.in").read_text(encoding="utf-8")


def _run_through_experiment(tmp_path: Path, *, generators: int = 5):
    ctx = make_context(tmp_path)
    provider = TemplateExperimentProvider(template=_template(), fields={"generators": generators})
    chain = run_chain(
        [
            IssueSegment(),
            LiteratureSegment(searcher=_searcher, source="fixture"),
            HypothesizeSegment(llm=NullLLM("dry-run"), seed_hypotheses=[_hypothesis()]),
            ExperimentSegment(provider=provider, config=offline_config(ctx.run_dir)),
        ],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )
    return ctx, chain


def test_the_pre_registration_is_written_and_nothing_else_is(tmp_path: Path) -> None:
    ctx, chain = _run_through_experiment(tmp_path)
    assert chain.completed is True
    records = ctx.ledger.as_records()
    assert [record["kind"] for record in records] == ["pre_register"]
    prereg = records[0]["payload"]
    assert prereg["k_max"] == 8
    assert prereg["hypothesis"] == "a floor bounds the leader"
    assert prereg["alpha"] == 0.05
    assert len(prereg["script_sha256"]) == 64
    assert ctx.ledger.rows() == []


def test_the_evidence_records_the_file_that_ran(tmp_path: Path) -> None:
    ctx, _ = _run_through_experiment(tmp_path)
    runs = ctx.upstream_payload("experiment")["runs"]
    assert len(runs) == 1
    assert runs[0]["hypothesis"] == "a floor bounds the leader"
    assert runs[0]["evidence_ref"] == "evidence/experiment-000.json:1"
    assert runs[0]["k_max"] == 8
    evidence = json.loads((ctx.run_dir / "evidence/experiment-000.json").read_text(encoding="utf-8"))
    result = evidence["result"]
    assert result["returncode"] == 0
    assert result["timed_out"] is False
    assert result["script_sha256"] == runs[0]["script_sha256"]
    blob = json.loads(result["stdout"].strip().splitlines()[-1])
    assert len(blob["votes"]) == 5
    assert set(blob["scores"]) == {"strong", "weak"}


def test_no_entrypoint_is_recorded_as_untested_not_replaced(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)

    class _Empty:
        name = "empty"

        def provide(self, hypothesis: Hypothesis):
            return None

    chain = run_chain(
        [
            IssueSegment(),
            LiteratureSegment(searcher=_searcher, source="fixture"),
            HypothesizeSegment(llm=NullLLM("dry-run"), seed_hypotheses=[_hypothesis()]),
            ExperimentSegment(provider=_Empty(), config=offline_config(ctx.run_dir)),
        ],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )
    assert chain.completed is True
    runs = ctx.upstream_payload("experiment")["runs"]
    assert runs[0]["status"] == "no_entrypoint"
    assert (ctx.run_dir / "evidence/experiment-000.json").exists() is False


def test_a_provider_is_required(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    with pytest.raises(ValueError, match="requires a provider"):
        ExperimentSegment().run(ctx)
```

Add `import pytest` to the imports.

The third test is the one worth keeping: when there is no script, the honest output is "untested", and the tempting alternative — inventing a plausible result so the chain can continue — is exactly what the whole design is built to prevent.

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_segments_experiment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoresearcher.segments.experiment'`

- [ ] **Step 3: Write `src/autoresearcher/fixtures/dry_run_experiment.py.in`**

```python
# Rendered from fixtures/dry_run_experiment.py.in by autoresearcher.dryrun.
# The seed is derived from the hypothesis text, so two different hypotheses get
# two different datasets and a rerun of one hypothesis gets the same one.
import json
import random

SEED = %(seed)d
N_ITEMS = 400
GENERATORS = %(generators)d
AGREEMENT = 0.92
STRONG = 0.94
WEAK = 0.60

rng = random.Random(SEED)
truth = [rng.randint(0, 1) for _ in range(N_ITEMS)]
votes = [
    [int(t) if rng.random() < AGREEMENT else 1 - int(t) for t in truth]
    for _ in range(GENERATORS)
]
strong = [int(t) if rng.random() < STRONG else 1 - int(t) for t in truth]
weak = [int(t) if rng.random() < WEAK else 1 - int(t) for t in truth]

print(json.dumps({
    "votes": votes,
    "scores": {
        "strong": sum(a == b for a, b in zip(strong, truth)) / N_ITEMS,
        "weak": sum(a == b for a, b in zip(weak, truth)) / N_ITEMS,
    },
    "judge_ids": ["g" + str(i) for i in range(GENERATORS)],
    "contestant_ids": ["strong", "weak"],
    "item_ids": list(range(N_ITEMS)),
}))
```

The script deliberately does not print `k_max`, a `script_sha256`, or a `se`: those are the experiment reporting on itself, and arx's runner measures the hash off the file that ran instead. The absence is what makes the measured-hash rule meaningful rather than decorative.

- [ ] **Step 4: Write the implementation**

```python
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
from pathlib import Path

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
```

The unused `Path` import can go if ruff flags it; `path.relative_to` does not need the class.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_segments_experiment.py -v`
Expected: 4 passed

If `ExperimentScript.materialise`, `ExperimentScript.sha256`, or `run_experiment`'s signature differ from the calls above, fix here and re-run: this is the only place the plan touches arx's sandbox, and the tests fail loudly if it moved.

- [ ] **Step 6: Commit**

```bash
git add src/autoresearcher/segments/experiment.py \
        src/autoresearcher/fixtures/dry_run_experiment.py.in tests/test_segments_experiment.py
git commit -m "feat: segment 4, which pre-registers before it runs anything"
```

---

## Task 11: ⑤ the gate — the frozen core

**Files:**
- Create: `src/autoresearcher/segments/gate.py`
- Test: `tests/test_segments_gate.py`
- Create: `tests/tests_segments_experiment_helpers.py`

- [ ] **Step 1: Write the helper and the failing tests**

`tests/tests_segments_experiment_helpers.py`:

```python
"""Templates and hypotheses shared by the experiment and gate tests."""

from __future__ import annotations

import json
from pathlib import Path

import autoresearcher
from arx.hypothesis import Hypothesis

FIXTURES = Path(autoresearcher.__file__).parent / "fixtures"


def template() -> str:
    return (FIXTURES / "dry_run_experiment.py.in").read_text(encoding="utf-8")


def succeeded_hypotheses() -> list[Hypothesis]:
    return [
        Hypothesis.from_dict(item)
        for item in json.loads((FIXTURES / "dry_run_hypotheses.json").read_text(encoding="utf-8"))
    ]
```

`tests/test_segments_gate.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arx.audit.verdict import Verdict
from arx.llm import NullLLM
from arx.literature.search import Paper, SearchOutcome

from autoresearcher.artifact import SegmentStatus
from autoresearcher.config import offline_config
from autoresearcher.segments.base import run_chain
from autoresearcher.segments.experiment import ExperimentSegment, TemplateExperimentProvider
from autoresearcher.segments.gate import METRIC_KEYS, GateSegment, adjudicate
from autoresearcher.segments.hypothesize import HypothesizeSegment
from autoresearcher.segments.issue import IssueSegment
from autoresearcher.segments.literature import LiteratureSegment
from tests_helpers import make_context
from tests_segments_experiment_helpers import succeeded_hypotheses, template


def _searcher(topic: str, limit: int) -> SearchOutcome:
    return SearchOutcome(papers=[Paper(title="t", year=2024)], sources_ok=["fixture"])


def _through_gate(tmp_path: Path, *, generators: int = 5):
    ctx = make_context(tmp_path)
    gate = GateSegment(config=offline_config(ctx.run_dir))
    chain = run_chain(
        [
            IssueSegment(),
            LiteratureSegment(searcher=_searcher, source="fixture"),
            HypothesizeSegment(llm=NullLLM("dry-run"), seed_hypotheses=succeeded_hypotheses()),
            ExperimentSegment(
                provider=TemplateExperimentProvider(
                    template=template(), fields={"generators": generators}
                ),
                config=offline_config(ctx.run_dir),
            ),
            gate,
        ],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )
    return ctx, chain, gate


def test_the_three_hypotheses_get_the_measured_verdicts(tmp_path: Path) -> None:
    ctx, chain, _ = _through_gate(tmp_path)
    assert chain.completed is True
    assert [row.gate_decision for row in ctx.ledger.rows()] == ["ACCEPT", "ACCEPT", "MARGINAL"]


def test_the_pre_registrations_precede_every_claim_they_govern(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    kinds = [record["kind"] for record in ctx.ledger.as_records()]
    first_claim = kinds.index("claim")
    assert kinds[first_claim:] == ["claim"] * (len(kinds) - first_claim)
    assert kinds[:first_claim].count("pre_register") == 3


def test_the_first_claim_carries_the_floor_the_margin_and_the_method(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    metrics = ctx.ledger.rows()[0].metrics
    assert metrics["verdict"] == Verdict.READABLE.value
    assert metrics["leader_system"] == "strong"
    # leader_score and floor_estimate land on exact floats; margin and mde are
    # differences of scores, so they are compared at 6 dp.
    assert metrics["leader_score"] == 0.9475
    assert metrics["floor_estimate"] == 0.9155
    assert round(metrics["margin"], 6) == 0.032
    assert round(metrics["mde"], 6) == 0.031242
    assert metrics["mde_method"] == "binomial_approx"
    assert metrics["n_items"] == 400
    assert metrics["n_generators"] == 5
    assert metrics["k_max"] == 7
    assert metrics["alpha"] == 0.05
    assert metrics["power"] == 0.8
    assert metrics["delta_declared"] == 0.02
    assert metrics["prereg_ok"] is True
    assert metrics["gate_allowed"] is True


def test_the_marginal_claim_says_so_in_words(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    marginal = ctx.ledger.rows()[2]
    assert marginal.gate_decision == "MARGINAL"
    assert marginal.metrics["verdict"] == Verdict.MARGINAL.value
    assert round(marginal.metrics["margin"], 6) == 0.0285
    assert round(marginal.metrics["mde"], 6) == 0.035741
    assert any("resolution bound" in reason for reason in marginal.metrics["reasons"])


def test_every_claim_row_has_the_same_metric_keys(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    for row in ctx.ledger.rows():
        assert tuple(row.metrics) == METRIC_KEYS


def test_every_claim_anchors_its_evidence_and_the_anchor_resolves(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    for row in ctx.ledger.rows():
        path_part, line = row.evidence_ref.rsplit(":", 1)
        assert line == "1"
        assert not Path(path_part).is_absolute()
        assert (ctx.run_dir / path_part).exists()


def test_the_evidence_sha_is_the_sha_of_the_evidence_file(tmp_path: Path) -> None:
    ctx, _, _ = _through_gate(tmp_path)
    row = ctx.ledger.rows()[0]
    path = ctx.run_dir / row.evidence_ref.rsplit(":", 1)[0]
    assert row.metrics["evidence_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_two_generators_are_undecidable_and_the_chain_stops(tmp_path: Path) -> None:
    ctx, chain, _ = _through_gate(tmp_path, generators=2)
    assert chain.completed is False
    assert chain.stopped_at == "gate"
    assert "no claim cleared the gate" in chain.refusal
    rows = ctx.ledger.rows()
    assert [row.gate_decision for row in rows] == ["UNDECIDABLE"] * 3
    assert rows[0].metrics["verdict"] == Verdict.UNDECIDABLE.value
    assert rows[0].metrics["reasons"] == ["floor_degenerate"]
    assert rows[0].metrics["margin"] is None
    assert rows[0].metrics["prereg_ok"] is True


def test_a_claim_can_be_redecided_from_the_evidence_alone(tmp_path: Path) -> None:
    """``adjudicate`` is reachable from an evidence file and the ledger, and nothing else.

    This is what makes ``researcher recompute`` a real recomputation rather than
    a second implementation that happens to agree.
    """
    ctx, _, _ = _through_gate(tmp_path)
    evidence = json.loads((ctx.run_dir / "evidence/experiment-000.json").read_text(encoding="utf-8"))
    decision = adjudicate(
        evidence=evidence,
        records=ctx.ledger.as_records(),
        config=offline_config(ctx.run_dir),
        evidence_sha256="whatever",
    )
    assert decision.gate_decision == "ACCEPT"
    assert decision.k_max == 7
    assert decision.prereg_ok is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_segments_gate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoresearcher.segments.gate'`

- [ ] **Step 3: Write the implementation**

```python
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
#: means "not measured" or "not recorded".
METRIC_KEYS: tuple[str, ...] = (
    "k_max",
    "alpha",
    "power",
    "delta_declared",
    "gate_strict",
    "prereg_ok",
    "verdict",
    "gate_allowed",
    "leader_system",
    "leader_score",
    "floor_estimate",
    "floor_method",
    "margin",
    "mde",
    "mde_method",
    "threshold",
    "n_items",
    "n_generators",
    "n_contestants",
    "reasons",
    "evidence_sha256",
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_segments_gate.py -v`
Expected: 10 passed

The expected numbers are the ones measured in this plan's fixture table. If one differs, re-measure with the appendix probe and fix the *fixture* — never the assertion.

- [ ] **Step 5: Commit**

```bash
git add src/autoresearcher/segments/gate.py tests/test_segments_gate.py \
        tests/tests_segments_experiment_helpers.py
git commit -m "feat: segment 5, whose decisions are recomputable from files alone"
```

---

## Task 12: `dryrun` components and the pipeline

**Files:**
- Create: `src/autoresearcher/dryrun.py`
- Create: `src/autoresearcher/pipeline.py`
- Test: `tests/test_dry_run.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import json
from pathlib import Path

from autoresearcher.dryrun import offline_components
from autoresearcher.fingerprint import fingerprint_digest
from autoresearcher.pipeline import RunConfig, run_pipeline


def test_a_dry_run_completes_every_segment_it_has(tmp_path: Path) -> None:
    outcome = run_pipeline(
        RunConfig(topic="does a floor bound a leader", run_dir=tmp_path / "run", dry_run=True)
    )
    assert outcome.chain.completed is True
    assert [artifact.segment_id for artifact in outcome.chain.artifacts] == [
        "issue",
        "literature",
        "hypothesize",
        "experiment",
        "gate",
    ]
    assert [artifact.status.value for artifact in outcome.chain.artifacts] == ["OK"] * 5


def test_the_run_directory_holds_the_products(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    assert (run_dir / "claim_ledger.jsonl").exists()
    assert (run_dir / "env_fingerprint.json").exists()
    assert len(list((run_dir / "segments").glob("*.json"))) == 5
    assert len(list((run_dir / "artifacts").glob("*.json"))) == 5
    assert len(list((run_dir / "evidence").glob("experiment-*.json"))) == 3
    assert len(list((run_dir / "experiment-*.py"))) == 3


def test_the_fingerprint_in_the_ledger_matches_the_one_on_disk(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    fingerprint = json.loads((run_dir / "env_fingerprint.json").read_text(encoding="utf-8"))
    assert outcome.fingerprint_digest == fingerprint_digest(fingerprint)
    assert outcome.chain.artifacts[0].run_fingerprint == outcome.fingerprint_digest
    start = [record for record in outcome.chain_records() if record["kind"] == "run_start"][0]
    assert start["payload"]["run_fingerprint"] == outcome.fingerprint_digest


def test_the_run_consulted_no_model(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    hypothesize = json.loads((run_dir / "artifacts/hypothesize.json").read_text(encoding="utf-8"))
    assert hypothesize["llm"] == "none"


def test_the_components_can_be_built_without_a_pipeline(tmp_path: Path) -> None:
    components = offline_components(generators=5)
    assert components.llm.available is False
    assert len(components.seed_hypotheses) == 3
    assert components.seed_hypotheses[0].confidence == 0.6
```

The third test uses `outcome.chain_records()`, a small convenience on `PipelineOutcome` so the test does not have to re-open the ledger to check that the fingerprint reached it.

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_dry_run.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoresearcher.dryrun'`

- [ ] **Step 3: Write `src/autoresearcher/dryrun.py`**

```python
"""The offline components a ``--dry-run`` uses.

Everything here is a fixture: canned papers, seeded hypotheses, and a synthetic
leaderboard. The point is not to measure anything — it is to make the chain
runnable with no API key and no network, so the acceptance test exercises the
gate rather than the plumbing around it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from arx.hypothesis import Hypothesis
from arx.literature.search import Paper, SearchOutcome
from arx.llm import ChatModel, NullLLM

from autoresearcher.segments.experiment import TemplateExperimentProvider

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass
class OfflineComponents:
    searcher: Callable[[str, int], SearchOutcome]
    llm: ChatModel
    provider: TemplateExperimentProvider
    seed_hypotheses: list[Hypothesis] = field(default_factory=list)


def fixture_searcher() -> Callable[[str, int], SearchOutcome]:
    """A searcher over the canned papers, with ``search_all``'s signature."""
    papers = [
        Paper(
            title=str(item["title"]),
            authors=list(item.get("authors") or []),
            year=item.get("year"),
            abstract=str(item.get("abstract", "")),
            url=str(item.get("url", "")),
            doi=item.get("doi"),
            source=str(item.get("source", "fixture")),
        )
        for item in json.loads((FIXTURES / "dry_run_papers.json").read_text(encoding="utf-8"))
    ]

    def _search(_query: str, _limit: int) -> SearchOutcome:
        return SearchOutcome(papers=list(papers), sources_ok=["fixture"])

    return _search


def fixture_hypotheses() -> list[Hypothesis]:
    return [
        Hypothesis.from_dict(item)
        for item in json.loads((FIXTURES / "dry_run_hypotheses.json").read_text(encoding="utf-8"))
    ]


def offline_components(*, generators: int = 5) -> OfflineComponents:
    """Canned papers, seeded hypotheses, and a template experiment.

    ``llm`` is arx's ``NullLLM``, so ``available`` is False and nothing that
    consults a model can run by accident.
    """
    return OfflineComponents(
        searcher=fixture_searcher(),
        llm=NullLLM("dry-run: no model is consulted"),
        provider=TemplateExperimentProvider(
            template=(FIXTURES / "dry_run_experiment.py.in").read_text(encoding="utf-8"),
            name="dry-run-template",
            fields={"generators": generators},
        ),
        seed_hypotheses=fixture_hypotheses(),
    )


__all__ = [
    "FIXTURES",
    "OfflineComponents",
    "fixture_hypotheses",
    "fixture_searcher",
    "offline_components",
]
```

- [ ] **Step 4: Write `src/autoresearcher/pipeline.py`**

```python
"""Wire the five segments into one run.

The pipeline is short on purpose. Everything interesting — when to stop, what a
claim has to carry, how a decision is recomputed — lives in the segment that owns
it, and this module only decides the order and where the files go.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from arx.config import AgentConfig

from autoresearcher.claim import ClaimLedger
from autoresearcher.config import offline_config
from autoresearcher.dryrun import OfflineComponents, offline_components
from autoresearcher.fingerprint import environment_fingerprint, fingerprint_digest
from autoresearcher.segments.base import ChainResult, SegmentContext, run_chain
from autoresearcher.segments.experiment import ExperimentSegment
from autoresearcher.segments.gate import GateSegment
from autoresearcher.segments.hypothesize import HypothesizeSegment
from autoresearcher.segments.issue import IssueSegment
from autoresearcher.segments.literature import LiteratureSegment


@dataclass
class RunConfig:
    topic: str
    run_dir: Path
    dry_run: bool = False
    n_hypotheses: int = 3
    falsified_by: str = ""
    generators: int = 5


@dataclass
class PipelineOutcome:
    run_dir: Path
    claim_ledger: Path
    chain: ChainResult
    fingerprint_digest: str
    records: list[dict]

    @property
    def status(self) -> str:
        return "OK" if self.chain.completed else "REFUSED"

    @property
    def n_claims(self) -> int:
        return sum(len(artifact.claim_ids) for artifact in self.chain.artifacts)

    def chain_records(self) -> list[dict]:
        """The ledger records as they were when the run finished."""
        return list(self.records)


def run_pipeline(cfg: RunConfig, *, components: OfflineComponents | None = None) -> PipelineOutcome:
    """Run one topic through the chain of segments M0 has."""
    run_dir = Path(cfg.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    config: AgentConfig = offline_config(run_dir)
    fingerprint = environment_fingerprint(run_dir=run_dir)
    digest = fingerprint_digest(fingerprint)
    (run_dir / "env_fingerprint.json").write_text(
        json.dumps(fingerprint, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    ledger = ClaimLedger(run_dir / "claim_ledger.jsonl")
    ledger.append_record(
        "run_start",
        {
            "topic": cfg.topic,
            "dry_run": cfg.dry_run,
            "config": config.ledger_flags(),
            "run_fingerprint": digest,
        },
    )

    parts = components or offline_components(generators=cfg.generators)
    ctx = SegmentContext(run_dir=run_dir, topic=cfg.topic, ledger=ledger, fingerprint=digest)
    chain = run_chain(
        [
            IssueSegment(falsified_by=cfg.falsified_by, gate_flags=config.ledger_flags()),
            LiteratureSegment(
                searcher=parts.searcher if cfg.dry_run else None,
                source="fixture" if cfg.dry_run else "live",
            ),
            HypothesizeSegment(
                n=cfg.n_hypotheses,
                llm=parts.llm,
                seed_hypotheses=parts.seed_hypotheses if cfg.dry_run else [],
            ),
            ExperimentSegment(provider=parts.provider, config=config),
            GateSegment(config=config),
        ],
        ctx,
        envelopes_dir=run_dir / "segments",
    )
    ledger.append_record(
        "run_end",
        {
            "stopped_at": chain.stopped_at,
            "refusal": chain.refusal,
            "segments": [
                {"segment_id": artifact.segment_id, "status": artifact.status.value}
                for artifact in chain.artifacts
            ],
        },
    )
    return PipelineOutcome(
        run_dir=run_dir,
        claim_ledger=ledger.path,
        chain=chain,
        fingerprint_digest=digest,
        records=ledger.as_records(),
    )


__all__ = ["PipelineOutcome", "RunConfig", "run_pipeline"]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_dry_run.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/autoresearcher/dryrun.py src/autoresearcher/pipeline.py tests/test_dry_run.py
git commit -m "feat: the offline dry run and the pipeline that wires the five segments"
```

---

## Task 13: `recompute` and the CLI

**Files:**
- Create: `src/autoresearcher/recompute.py`
- Create: `src/autoresearcher/cli.py`
- Test: `tests/test_recompute.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_recompute.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from autoresearcher.pipeline import RunConfig, run_pipeline
from autoresearcher.recompute import recompute_run


def test_every_claim_is_reproduced(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    report = recompute_run(run_dir)
    assert report.n_claims == 3
    assert report.n_reproduced == 3
    assert report.ok is True
    assert report.mismatches == []


def test_editing_the_evidence_is_caught(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    evidence = run_dir / "evidence/experiment-000.json"
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    blob = json.loads(payload["result"]["stdout"].strip().splitlines()[-1])
    blob["scores"]["strong"] = 0.99
    payload["result"]["stdout"] = json.dumps(blob) + "\n"
    evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = recompute_run(run_dir)
    assert report.ok is False
    assert {mismatch.claim_id for mismatch in report.mismatches} == {"gate:000"}
    fields = {mismatch.field for mismatch in report.mismatches}
    assert "metrics.leader_score" in fields
    assert "metrics.evidence_sha256" in fields


def test_a_claim_with_no_evidence_file_is_unresolvable(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    (run_dir / "evidence/experiment-001.json").unlink()
    report = recompute_run(run_dir)
    assert report.ok is False
    assert report.unresolvable == ["gate:001"]


def test_a_chain_broken_after_the_run_is_caught(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="t", run_dir=run_dir, dry_run=True))
    ledger = run_dir / "claim_ledger.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    ledger.write_text("\n".join([lines[0], *lines[2:]]) + "\n", encoding="utf-8")
    report = recompute_run(run_dir)
    assert report.chain_ok is False
    assert report.ok is False
    assert report.n_reproduced == 3
```

Deleting a record in the middle leaves every claim's decision still derivable and the chain provably broken: that is the distinction the report makes, and the reason `chain_ok` is a separate field from `n_reproduced`.

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_recompute.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoresearcher.recompute'`

- [ ] **Step 3: Write `src/autoresearcher/recompute.py`**

```python
"""Re-derive every gate decision from the files on disk.

This is the design's "可复算" pillar made into a command. It calls the same
``adjudicate`` the gate called, with the same inputs, and compares the result
field by field against what was written down. It is not a second implementation
of the gate and cannot drift from one: if it ever disagrees, the disagreement is
about the *files*, which is exactly what a third party wants to know.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from arx.experiments.ledger import verify_ledger_file

from autoresearcher.claim import ClaimLedger
from autoresearcher.config import offline_config
from autoresearcher.segments.gate import adjudicate


@dataclass
class Mismatch:
    claim_id: str
    field: str
    recorded: object
    recomputed: object


@dataclass
class RecomputeReport:
    n_claims: int = 0
    n_reproduced: int = 0
    mismatches: list[Mismatch] = field(default_factory=list)
    unresolvable: list[str] = field(default_factory=list)
    chain_ok: bool = False

    @property
    def ok(self) -> bool:
        """A run recomputes only if the chain holds *and* every claim reproduces."""
        return self.chain_ok and not self.mismatches and not self.unresolvable

    def summary(self) -> str:
        return (
            f"chain {'OK' if self.chain_ok else 'BROKEN'} | "
            f"reproduced {self.n_reproduced}/{self.n_claims} | "
            f"mismatches {len(self.mismatches)} | unresolvable {len(self.unresolvable)}"
        )


def recompute_run(run_dir: Path) -> RecomputeReport:
    run_dir = Path(run_dir)
    ledger_path = run_dir / "claim_ledger.jsonl"
    ledger = ClaimLedger(ledger_path)
    config = offline_config(run_dir)
    records = ledger.as_records()
    report = RecomputeReport(chain_ok=bool(verify_ledger_file(ledger_path).ok))

    for row in ledger.rows():
        report.n_claims += 1
        if row.gate_decision is None:
            # A segment that wrote a claim without judging it has nothing to
            # recompute, and saying so beats counting it as reproduced.
            report.unresolvable.append(row.claim_id)
            continue

        try:
            path_part, _line = row.evidence_ref.rsplit(":", 1)
            evidence_path = run_dir / path_part
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        except (OSError, ValueError, KeyError) as exc:
            report.unresolvable.append(f"{row.claim_id} ({exc})")
            continue

        decision = adjudicate(
            evidence=evidence,
            records=records,
            config=config,
            evidence_sha256=evidence_sha,
        )

        before = len(report.mismatches)
        if decision.gate_decision != row.gate_decision:
            report.mismatches.append(
                Mismatch(row.claim_id, "gate_decision", row.gate_decision, decision.gate_decision)
            )
        for key in sorted(set(row.metrics) | set(decision.metrics)):
            recorded = row.metrics.get(key)
            recomputed = decision.metrics.get(key)
            if recorded != recomputed:
                report.mismatches.append(
                    Mismatch(row.claim_id, f"metrics.{key}", recorded, recomputed)
                )
        if len(report.mismatches) == before:
            report.n_reproduced += 1

    return report


__all__ = ["Mismatch", "RecomputeReport", "recompute_run"]
```

- [ ] **Step 4: Write `tests/test_cli.py`**

```python
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
```

- [ ] **Step 5: Write `src/autoresearcher/cli.py`**

```python
"""The command line: run one topic, verify a chain, recompute a run, describe the install.

Exit codes carry meaning, because CI and a reader both need to tell three
outcomes apart: 0 the chain completed and everything recomputed, 2 the chain
refused on purpose (the tool working), 1 something is broken.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from arx.experiments.ledger import verify_ledger_file

from autoresearcher import __version__
from autoresearcher.fingerprint import environment_fingerprint
from autoresearcher.pipeline import RunConfig, run_pipeline
from autoresearcher.recompute import recompute_run

EXIT_OK = 0
EXIT_BROKEN = 1
EXIT_REFUSED = 2


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.handler(args)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="researcher", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one topic through the chain")
    run.add_argument("topic")
    run.add_argument("--dry-run", action="store_true", help="offline fixtures; no model, no network")
    run.add_argument("--out", default="runs/latest", help="run directory")
    run.add_argument("--hypotheses", type=int, default=3)
    run.add_argument("--generators", type=int, default=5)
    run.add_argument("--falsified-by", default="")
    run.set_defaults(handler=_run)

    verify = sub.add_parser("verify-ledger", help="check a claim ledger's hash chain")
    verify.add_argument("ledger")
    verify.set_defaults(handler=_verify)

    recompute = sub.add_parser("recompute", help="re-derive every decision in a run from disk")
    recompute.add_argument("run_dir")
    recompute.set_defaults(handler=_recompute)

    doctor = sub.add_parser("doctor", help="what this install can actually do")
    doctor.set_defaults(handler=_doctor)
    return parser


def _run(args: argparse.Namespace) -> int:
    outcome = run_pipeline(
        RunConfig(
            topic=args.topic,
            run_dir=Path(args.out),
            dry_run=args.dry_run,
            n_hypotheses=args.hypotheses,
            falsified_by=args.falsified_by,
            generators=args.generators,
        )
    )
    print(f"status   {outcome.status}")
    print(f"run      {outcome.run_dir}")
    print(f"ledger   {outcome.claim_ledger}")
    print(f"claims   {outcome.n_claims}")
    print(f"stopped  {outcome.chain.stopped_at or '-'}")
    print(f"recompute it with: python3 -m autoresearcher.cli recompute {outcome.run_dir}")
    if not outcome.chain.completed:
        print(f"refused  {outcome.chain.refusal}", file=sys.stderr)
        return EXIT_REFUSED
    return EXIT_OK


def _verify(args: argparse.Namespace) -> int:
    report = verify_ledger_file(Path(args.ledger))
    print(f"{'OK' if report.ok else 'BROKEN'}  records={report.n_records}")
    for error in getattr(report, "errors", []) or []:
        print(f"  {error}", file=sys.stderr)
    return EXIT_OK if report.ok else EXIT_BROKEN


def _recompute(args: argparse.Namespace) -> int:
    report = recompute_run(Path(args.run_dir))
    print(report.summary())
    for mismatch in report.mismatches:
        print(
            f"  {mismatch.claim_id} {mismatch.field}: recorded {mismatch.recorded!r} "
            f"but recomputes to {mismatch.recomputed!r}",
            file=sys.stderr,
        )
    for claim_id in report.unresolvable:
        print(f"  {claim_id}: evidence could not be resolved", file=sys.stderr)
    return EXIT_OK if report.ok else EXIT_BROKEN


def _doctor(args: argparse.Namespace) -> int:
    import arx

    print(f"autoresearcher {__version__}")
    print(f"arx            {getattr(arx, '__version__', 'unknown')}")
    print(json.dumps(environment_fingerprint(), indent=2, sort_keys=True))
    print("capabilities")
    print("  segments 1-5   available")
    print("  dry-run        available (offline fixtures, no model, no network)")
    print("  live search    implemented, not exercised")
    print("  segments 6-8   not built (M1)")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

The CLI prints the recompute command naming the run directory the user passed. That is the design's "复算命令" delivered at run level, where it can be exact, rather than embedded per claim as a string that cannot know the run's own name.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_recompute.py tests/test_cli.py -v`
Expected: 11 passed

If `verify_ledger_file`'s report uses attribute names other than `ok`/`n_records`/`errors`, adjust `_verify` here and re-run.

- [ ] **Step 7: Commit**

```bash
git add src/autoresearcher/recompute.py src/autoresearcher/cli.py \
        tests/test_recompute.py tests/test_cli.py
git commit -m "feat: recompute from disk, and the CLI that exposes it"
```

---

## Task 14: The gate is the only passage

**Files:**
- Create: `tests/test_gate_is_the_only_passage.py`

This is the task the whole project exists for. Every other test checks that a
segment behaves; this one checks the claim the design makes about the *shape* of
the pipeline — that a segment after the gate cannot run on a run the gate
refused, and not because it politely declines but because the object it would
need does not exist. A `_ProbeSegment` stands where ⑥ will go in M1 and reports
what it was able to see.

- [ ] **Step 1: Write the failing test**

`tests/test_gate_is_the_only_passage.py`:

```python
"""The design's central invariant, as five tests.

If this file passes for the wrong reason the project has failed: the point is
not that a later segment *declines* to run after a refusal, it is that it
*cannot* — there is no object in its hands to run on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.config import offline_config
from autoresearcher.dryrun import offline_components
from autoresearcher.pipeline import RunConfig, run_pipeline
from autoresearcher.segments.base import (
    MissingUpstream,
    PayloadRefused,
    SegmentContext,
    run_chain,
    write_payload,
)
from autoresearcher.segments.experiment import ExperimentSegment
from autoresearcher.segments.gate import GateSegment
from autoresearcher.segments.hypothesize import HypothesizeSegment
from autoresearcher.segments.issue import IssueSegment
from autoresearcher.segments.literature import LiteratureSegment
from tests_helpers import make_context


@dataclass
class _ProbeSegment:
    """Stands in for ⑥ to observe what actually reached it.

    It records the accepted claims it can read *and* keeps a payload, so a
    downstream refusal can be distinguished from a probe that simply had
    nothing to say.
    """

    segment_id: str = "probe"
    ran: bool = False
    n_accepted: int = -1

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        self.ran = True
        self.n_accepted = len(ctx.ledger.accepted())
        ref = write_payload(ctx, "probe.json", {"n_accepted": self.n_accepted})
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=ref,
            claim_ids=[row.claim_id for row in ctx.ledger.accepted()],
            gate_summary={"n_accepted": self.n_accepted},
            run_fingerprint=ctx.fingerprint,
        )


def _chain(tmp_path: Path, *, generators: int, hypotheses: list | None):
    """Build the five segments M0 has, plus a probe sitting where ⑥ will go."""
    ctx = make_context(tmp_path, topic="does the gate hold")
    config = offline_config(ctx.run_dir)
    parts = offline_components(generators=generators)
    if hypotheses is not None:
        parts.seed_hypotheses = list(hypotheses)
    probe = _ProbeSegment()
    result = run_chain(
        [
            IssueSegment(falsified_by="held-out generator", gate_flags=config.ledger_flags()),
            LiteratureSegment(searcher=parts.searcher, source="fixture"),
            HypothesizeSegment(n=3, llm=parts.llm, seed_hypotheses=parts.seed_hypotheses),
            ExperimentSegment(provider=parts.provider, config=config),
            GateSegment(config=config),
            probe,
        ],
        ctx,
        envelopes_dir=ctx.run_dir / "segments",
    )
    return ctx, result, probe


def test_a_readable_run_reaches_the_segment_after_the_gate(tmp_path: Path) -> None:
    ctx, result, probe = _chain(tmp_path, generators=5, hypotheses=None)
    assert result.completed is True
    assert result.stopped_at is None
    assert probe.ran is True
    # Two of the three fixture hypotheses are READABLE; the third is MARGINAL
    # and travels with its label. This is D1: a MARGINAL claim does not stop
    # the chain, it arrives carrying its verdict.
    assert probe.n_accepted == 2
    assert ctx.upstream_payload("gate")["n_accept"] == 2


def test_a_gate_that_accepts_nothing_stops_before_the_next_segment(tmp_path: Path) -> None:
    ctx, result, probe = _chain(tmp_path, generators=2, hypotheses=None)
    assert result.stopped_at == "gate"
    assert result.completed is False
    assert probe.ran is False
    rows = ctx.ledger.rows()
    assert [row.gate_decision for row in rows] == ["UNDECIDABLE"] * 3
    assert [row.metrics["verdict"] for row in rows] == ["UNDECIDABLE"] * 3


def test_a_segment_that_never_ran_has_an_unreadable_output(tmp_path: Path) -> None:
    ctx, result, probe = _chain(tmp_path, generators=2, hypotheses=None)
    assert result.stopped_at == "gate"
    # The gate wrote its payload, so this is not a missing file: the output
    # exists and is refused. The distinction is the point.
    assert (ctx.run_dir / "artifacts" / "gate.json").exists()
    with pytest.raises(PayloadRefused, match="no claim cleared the gate"):
        ctx.upstream_payload("gate")


def test_a_hypothesisless_run_reaches_no_gate_and_writes_no_claim(tmp_path: Path) -> None:
    ctx, result, probe = _chain(tmp_path, generators=5, hypotheses=[])
    assert result.stopped_at == "hypothesize"
    assert "nothing to test" in result.refusal
    assert probe.ran is False
    assert ctx.ledger.rows() == []
    with pytest.raises(MissingUpstream, match="no 'experiment' artifact"):
        ctx.upstream_payload("experiment")


def test_the_pipeline_reports_a_refusal_as_a_status_not_a_crash(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(
        RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True, generators=2)
    )
    assert outcome.status == "REFUSED"
    assert outcome.chain.completed is False
    assert outcome.chain.stopped_at == "gate"
    # Three claims were written and all three were judged UNDECIDABLE. Counting
    # them is not failure; handing them downstream as if they were readable is.
    assert outcome.n_claims == 3
    assert outcome.claim_ledger.exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_gate_is_the_only_passage.py -v`
Expected: collection succeeds but the assertions fail while the pipeline is
incomplete — in particular `test_a_readable_run_reaches_the_segment_after_the_gate`
fails on `probe.n_accepted == 2` until ⑤ and the chain are in place. If every
test passes *before* Tasks 1–13 are implemented, the probe is not observing what
this file claims it observes; stop and find out why.

- [ ] **Step 3: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_gate_is_the_only_passage.py -v`
Expected: 5 passed

If `test_a_readable_run_reaches_the_segment_after_the_gate` reports
`n_accepted == 1` or `3`, the fixture verdicts in Task 11's measured table have
drifted — re-measure with the appendix probe and fix the fixture, never this
assertion.

- [ ] **Step 4: Commit**

```bash
git add tests/test_gate_is_the_only_passage.py
git commit -m "test: a segment past the gate cannot run on a run the gate refused"
```

---

## Task 15: CI, the end-to-end acceptance, and the M0 close-out

**Files:**
- Create: `.github/workflows/ci.yml`

The last task proves the whole thing works from a clean checkout on a machine
that is not this one, which is the only version of "it works" a stranger can
check.

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: ci

on:
  push:
  pull_request:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Lint
        run: ruff check .

      - name: Test
        run: python -m pytest -q

      - name: Dry run end to end
        run: |
          python -m autoresearcher.cli run "does the gate hold" --dry-run --out runs/ci
          python -m autoresearcher.cli verify-ledger runs/ci/claim_ledger.jsonl
          python -m autoresearcher.cli recompute runs/ci
```

The dry-run step is not decoration. It is the acceptance criterion of the whole
milestone executed in CI: a run that produces a ledger, a ledger that verifies,
and a run whose every decision reproduces from disk. If any of those three is
ever wrong, CI goes red before a reader sees it.

- [ ] **Step 2: Run the full suite locally**

Run: `python3 -m pytest -q`
Expected: 68 passed — the per-task suites sum to it (claim 4, claim_ledger 9,
segment_artifact 3, fingerprint 3, chain 7, config 1, issue+literature 2,
hypothesize 4, experiment 4, gate 10, dry_run 5, recompute 4, cli 7, gate-is-the-
only-passage 5). If the total differs, one of the expected counts in an earlier
task drifted; reconcile it there rather than adjusting this line.

- [ ] **Step 3: Run the acceptance by hand**

Run: `python3 -m autoresearcher.cli run "does the gate hold" --dry-run --out runs/local`
Expected on stdout: `status   OK`, `claims   3`, `stopped  -`, and exit code 0.

Run: `python3 -m autoresearcher.cli verify-ledger runs/local/claim_ledger.jsonl`
Expected on stdout: `OK  records=8` (one `run_start`, three `pre_register`,
three `claim`, one `run_end`), and exit code 0.

Run: `python3 -m autoresearcher.cli recompute runs/local`
Expected on stdout: `chain OK | reproduced 3/3 | mismatches 0 | unresolvable 0`,
and exit code 0.

- [ ] **Step 4: Check the run directory carries no machine paths**

Run:

```bash
python3 - <<'PY'
import pathlib

bad = []
for path in sorted(pathlib.Path("runs/local").rglob("*")):
    if path.is_file() and "/home/" in path.read_text(encoding="utf-8", errors="ignore"):
        bad.append(str(path))
print("machine paths:", bad or "none")
PY
```
Expected: `machine paths: none`

A `/home/` in a published run means a segment leaked an absolute path, which
would publish the machine that produced it. This check is the one the artifact
layer's `_resolve_relative` exists to make pass.

- [ ] **Step 5: Confirm the refused path is exercised too**

Run: `python3 -m autoresearcher.cli run "does the gate hold" --dry-run --generators 2 --out runs/refused`
Expected: `status   REFUSED` on stdout, `refused  no claim cleared the gate...` on
stderr, and exit code 2. Exit 2 rather than 0 is deliberate: a refusal is a
result, and the CLI reports it as one instead of pretending the run succeeded.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: lint, the unit suite, and a green end-to-end dry run"

git tag m0
```

The tag is what makes "M0 is done" a fact about the repository rather than a
claim in a message.

---

## Appendix: measuring the fixture values

Every number asserted in Task 10, Task 11 and Task 14 comes from this probe. It is
not shipped code — it renders the *shipped* `dry_run_experiment.py.in` and pushes
the result through the same `EvaluationGate` the pipeline uses — and it is recorded
here so the numbers can be re-derived rather than trusted.

```python
"""Re-derive the fixture table in Task 11. Needs only the pinned arx installed.

Driving the shipped template is the point: an earlier version of this probe
re-implemented the vote rule, and a probe that re-implements the thing it is
supposed to check will disagree with it sooner or later.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from arx.audit.auditor import AuditConfig
from arx.gate import EvaluationGate

TEMPLATE = Path("src/autoresearcher/fixtures/dry_run_experiment.py.in")
HYPOTHESES = [
    "A noise floor computed over five independent label producers bounds what a "
    "leaderboard leader can claim",
    "A five-producer floor separates a strong system but not a weak one",
    "Swapping the arithmetic mean for the median changes the leader when producers "
    "disagree at the margin",
]

work = Path(tempfile.mkdtemp())
source = TEMPLATE.read_text(encoding="utf-8")

for index, text in enumerate(HYPOTHESES):
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
    for generators in (5, 2):
        script = work / "experiment.py"
        script.write_text(source % {"seed": seed, "generators": generators}, encoding="utf-8")
        blob = json.loads(
            subprocess.run(
                [sys.executable, str(script)], capture_output=True, text=True, check=True
            ).stdout.strip().splitlines()[-1]
        )
        allowed, report = EvaluationGate(
            config=AuditConfig(delta_declared=0.02, alpha=0.05, power=0.8, seed=0), strict=True
        ).decision(
            np.array(blob["votes"]).astype(int),
            {name: float(value) for name, value in blob["scores"].items()},
            leaderboard_item_ids=set(blob["item_ids"]),
            floor_item_ids=None,
            judge_ids=set(blob["judge_ids"]),
            contestant_ids=set(blob["contestant_ids"]),
            per_item_scores=None,
        )
        print(
            f"claim {index + 1} gens={generators} {report.verdict.value} "
            f"allowed={allowed} score={report.leader_score} floor={report.floor_estimate} "
            f"margin={report.margin} mde={report.mde} reasons={report.reasons}"
        )
```

Measured output (floats abbreviated to 4-6 dp; the assertions in Task 11 compare
margin and mde at 6 dp for exactly this reason):

```
claim 1 gens=5 READABLE   allowed=True  score=0.9475 floor=0.9155 margin=0.032  mde=0.031242 reasons=[]
claim 2 gens=5 READABLE   allowed=True  score=0.9275 floor=0.885  margin=0.0425 mde=0.036325 reasons=[]
claim 3 gens=5 MARGINAL   allowed=False score=0.93   floor=0.9015 margin=0.0285 mde=0.035741 reasons=['margin +0.0285 is inside the resolution bound 0.0357']
claim 1 gens=2 UNDECIDABLE allowed=False score=None floor=None margin=None mde=None reasons=['floor_degenerate']
claim 2 gens=2 UNDECIDABLE allowed=False score=None floor=None margin=None mde=None reasons=['floor_degenerate']
claim 3 gens=2 UNDECIDABLE allowed=False score=None floor=None margin=None mde=None reasons=['floor_degenerate']
```

A marginal claim is a claim the gate declined to call: `allowed=False`, and the
row is written anyway, carrying its reason, because "I cannot tell" is a result.

`plan_k_max(prior_confidence=0.6, effect_se_ratio=0.5)` → 7;
`0.5` → 8; `0.4` → 9. These three are what Task 10 writes into the ledger
*before* the experiment runs, and what Task 11's gate reads back from the
ledger rather than from the experiment's own report.

---

## Self-review

Run against the spec
(`docs/superpowers/specs/2026-10-17-autonomous-research-agent-design.md`), not
against this plan.

**1. Spec coverage.** Every M0-scoped section maps to a task:

| Spec section | Task |
| --- | --- |
| §3.1 the claim schema, eight keys | Task 2 |
| §3.2 the gate decisions | Task 2, Task 11 |
| §3.3 `claim_ledger.jsonl` as the only channel | Task 3, Task 14 |
| §3.4 `segment_artifact` transport | Task 4 |
| §4 ①②③④⑤ as the M0 chain | Tasks 8–11, Task 12 |
| §5 the gate reads `k_max` from the ledger | Task 10, Task 11 |
| §6 recomputability of every number | Task 13 |
| §7 the offline dry run | Task 12 |
| §8 the three open items | D1, D2, D3 (decided, stated) |

Out of scope by decision, and therefore correctly absent: §9's segments ⑥⑦⑧
(M1), arx's sequential and multiplicity layers (D3), live search exercised
against the network (implemented, not exercised).

**2. Placeholder scan.** No `TBD`, no "implement later", no "similar to Task N",
no test described without its code. The two places where behaviour could not be
known in advance — arx's record-envelope shape and `verify_ledger_file`'s report
fields — are not left vague: each names the exact attribute assumed and says
what to do if it differs (`Task 3` Step 4, `Task 13` Step 6). Every code step
carries the code.

**3. Type consistency.** Checked across task boundaries:

- `SegmentContext` gains fields only in Task 6; `upstream_payload` is called in
  Tasks 8–11 and Task 14 and has one signature.
- `SegmentArtifact` is defined in Task 4 and constructed with the same six
  keyword arguments everywhere (Tasks 8–11, Task 14).
- `ClaimLedger` methods — `append_record`, `append_claim`, `as_records`, `rows`,
  `by_segment`, `accepted`, `next_claim_id`, `verify` — are defined once in
  Task 3 and used with those names in Tasks 10, 11, 13, 14.
- `adjudicate` is defined in Task 11 and called in Task 13 with the identical
  four keyword arguments; that identity is the recomputability claim.
- `METRIC_KEYS` (Task 11) and the gate payload keys `decisions`/`n_claims`/
  `n_accept` (Task 11) match what Task 13 and Task 14 read.
- `run_pipeline`/`RunConfig`/`PipelineOutcome` (Task 12) are used verbatim in
  Tasks 13–15.
- Segment ids are the spec's own words, and identical in artifacts, claims, and
  tests: `issue`, `literature`, `hypothesize`, `experiment`, `gate`.

No inconsistency found. One deliberate asymmetry is recorded rather than
silenced: `ExperimentSegment` and `GateSegment` take a `config`, the first three
segments do not — the first three make no statistical decision, so giving them a
gate config would be a lie about what they do.

---

## Execution Handoff

Plan complete and saved to
`docs/superpowers/plans/2026-10-17-autoresearcher-m0.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task,
review between tasks, fast iteration. Each subagent gets one task, the file
paths, and the verification command; I check the diff and the test output before
the next one starts. Best when you want to keep the main thread clean and catch a
drift early.

**2. Inline Execution** — execute the tasks in this session using
`superpowers:executing-plans`, batched with checkpoints for your review. Best
when you want to watch each step land and interrupt at any point.

Which approach?