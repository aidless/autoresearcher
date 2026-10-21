# autoresearcher M1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command produces exactly three artifacts for a run directory — `draft.md` (⑥), `claim_ledger.jsonl` (already M0's), and `gate_decisions.jsonl` (the run's decision record) — plus a deterministic `submission.zip` from ⑧ and a standalone third-party verifier that re-checks five things about a run without trusting it. `verify-ledger` stays green on the ledger the writer read from.

**Architecture:** ⑥ and ⑦ join the same `run_chain` the M0 segments travel. ⑥ renders `draft.md` from the ledger's `metrics` dicts and the gate's recorded decisions; it does no arithmetic, so it cannot invent a number. ⑦ runs a declared `selfaudit_gates.json` (two ported check kinds: `file_exists`, `script_runs`) plus one built-in check that no config can switch off — every numeric literal in `draft.md` must be covered by a numeric value in the ledger. ⑦ is a second, independent gate: it may refuse, and when it does the chain stops. `gate_decisions.jsonl` is written by the pipeline after the chain finishes, including when the chain refused, and it is a *projection* of the run rather than a second hash chain. ⑧ packages a finished run into a byte-reproducible archive; it never submits.

**Tech Stack:** Python 3.12, arx (pinned git SHA, installed as `arx-researcher`), numpy (via arx), pytest, ruff, GitHub Actions. No new dependencies.

**Spec:** `/home/liuzewen/project-review-20261013/docs/superpowers/specs/2026-10-17-autonomous-research-agent-design.md`

---

## Decisions taken (the spec was ambiguous in four places)

The spec is the authority. Where it did not say, these are the choices, each with the alternative spelled out. Flip any of them before Task 1 and the affected tasks get rewritten.

**D4 — `gate_decisions.jsonl` is a projection, not a second chain.**
One JSON object per line, one line per gate decision in the run, in chain order: first ⑤'s per-claim decisions, then ⑦'s per-check decisions. Each line has exactly these keys: `gate` (`"gate"` or `"selfaudit"`), `target` (the claim text for ⑤; the check name for ⑦), `claim_id` (or `null` for ⑦), `decision` (`ACCEPT`/`MARGINAL`/`UNDECIDABLE`/`REJECT` for ⑤; `PASS`/`FAIL` for ⑦), `verdict` (or `null`), `reasons` (list). The pipeline writes it after the chain finishes, **including when the chain refused** — a refusal is a decision, and a run that stops at ⑤ must still say so in one file. It is not given its own hash chain: the claim ledger's chain already commits to ⑤'s decisions, and a second chain would be a second thing to verify.
Alternative not taken: give `gate_decisions.jsonl` its own hash chain. Rejected because it would be a second thing to verify.

**D5 — ⑦'s checks are declared, not invented.**
⑦ runs a declarative `selfaudit_gates.json` (a run-dir file; the package fixture `fixtures/selfaudit_gates.json` supplies the dry-run default) supporting exactly two check kinds ported from the private `paper_promotion_gate/gates_config.json`:

```
{"type": "file_exists", "name": ..., "path": <relative to run dir>}
{"type": "script_runs", "name": ..., "cmd": [...], "cwd": <relative to run dir>, "timeout": <int>}
```

plus ONE built-in check that ⑦ always runs, which is the port of `scripts/verify_claim_ledger.py`'s core rule to our JSONL ledger: **every numeric literal appearing in `draft.md` must be covered by a numeric value in the claim ledger's `metrics`** (tolerance: precision-aware, i.e. tolerance for a literal is `max(2e-5, half a unit in its last displayed decimal digit)`; the regexes and the tolerance helper are ported from the reference script, not reinvented). Any failed check → ⑦ returns `REFUSED` with `gate_summary["reason"]` naming the failing checks; the chain then stops (the design's 可拒发). Unknown check types fail closed rather than being skipped. An absolute `cwd`, an absolute `cmd` element, or an absolute `file_exists` path raises `ValueError` at the boundary — the same rule `_resolve_relative` enforces for artifacts, because an absolute path would publish the machine.
Alternative not taken: have ⑦ ask a model to review the draft. Rejected — the design's §6 non-goals forbid AI-Scientist-style self-scoring, and a model is not a check.

**D6 — M1 does NOT add arx's sequential or multiplicity layers.**
The M0 plan's D3 deferred them "to M1". On inspection they are outside the design's §2 row for ⑤ (which lists only `arx/gate.py` + `arx/audit/{floor,power,goodhart,auditor}.py`) and outside §0's success criterion, which names three artifacts and `verify-ledger` and nothing else. The deferral is restated in M1's close-out as still-deferred, explicitly and not silently: they are not in M1's scope, they are not in `GateSegment`, and no M1 task touches them.

**D7 — ⑧ packages, it does not submit.**
`researcher package <run_dir>` writes a deterministic `submission.zip` containing exactly `draft.md`, `claim_ledger.jsonl`, `gate_decisions.jsonl`, `env_fingerprint.json`, plus a validated `submission_metadata.json` (five members). Deterministic means: members sorted by name, every member's `ZipInfo.date_time` pinned to `(1980, 1, 1, 0, 0, 0)`, no filesystem mtimes and no compression timestamps — so building twice **from the same run directory** yields a byte-identical archive (a test asserts the same sha256 twice). Metadata validation rejects any absolute path in any metadata string and any missing required key. No arXiv/TMLR account operations, no network (the design's §6 explicitly excludes automatic submission).
Alternative not taken: submit on the user's behalf. Rejected by the design's §6.
Note on scope of "deterministic": the archive is byte-identical for a *fixed* run directory. Two separate runs are not byte-identical, because arx's `Ledger.append` writes a `ts` field per record and the row hashes commit to it (see "Where this plan meets the code" below). The test therefore packages one run directory twice, which is the only claim the design needs.

---

## Where this plan meets the code

These are places where the M1 brief and the repository (or the design, or M0's own plan) disagree. They are recorded here rather than smoothed over; none of them was "fixed" by editing M0's source.

1. **⑧'s member count.** D7 lists four run files *plus* a validated `submission_metadata.json` — five members. The brief's Task 8 test text says "the archive holds exactly the four members". The plan follows D7 (five members, asserted as five in `test_the_archive_holds_the_four_run_files_and_the_metadata`).
2. **arx's ledger carries a clock.** `arx/experiments/ledger.py`'s `Ledger.append` sets `ts = time.time()` and `record_hash(seq, ts, kind, payload, prev_hash)` commits to it, so `claim_ledger.jsonl` and its row hashes differ between two runs of the same topic. Our own code never reads a clock; the timestamp is arx's. Therefore "deterministic packaging" can only mean "one run directory, packaged twice" — which is what Task 8 tests, and why `gate_decisions.jsonl` (which records no hash) is reproducible for a fixed ledger while the ledger itself is not.
3. **A refusal records an empty evidence hash.** `segments/gate.py`'s `_undecidable(...)` builds its metrics from `_base_metrics`, whose `evidence_sha256` defaults to `""` and is never overwritten on that path. So every `UNDECIDABLE` claim records `metrics["evidence_sha256"] == ""`. The M2 tool's check 3 must therefore not fabricate a comparison it cannot make: it requires the anchor to resolve for every claim, and compares the digest only when the recorded field is non-empty (Task 10's `_evidence_check`). M0's source is **not** touched. The empty field still deserves a follow-up — `adjudicate` has the hash in hand on that path and chooses not to record it — but it is recorded here as a deliberate M0 limitation, not repaired under M1.
4. **The tamper matrix cannot isolate check 3.** The brief says each tamper case turns *exactly one* check red. Editing a ledger line (check 1), re-chaining a metrics value (check 4) and adding an uncovered number to the draft (check 5) each do. Altering an evidence file does not: `recompute` re-derives `metrics["evidence_sha256"]` from those same bytes, so check 3 and check 4 both go red, by construction. Task 10 asserts the real red set and says why.
5. **`doctor`'s segment line.** The brief has Task 5 change `segments 1-5` to "1-7 available", but ⑧ lands later in the same milestone, so by the end of M1 the honest line is 1-8. Task 5 writes 1-7 as instructed; Task 9 raises it to 1-8 and adds a `packaging` line.
6. **One assignment the brief leaves open.** Nothing in the task list says *where* ⑥ and ⑦ enter `pipeline.run_pipeline`'s chain. Task 5 does it, because Task 5 is what makes "`researcher run` reports the draft path" true, and because the decision record's ⑦ lines depend on ⑦ having run.
7. **`VALUE_NUM_RE` has no analogue.** The reference verifier uses it to parse a markdown table's numeric column; our ledger is JSON, so there is no such column. Task 2 keeps the constant for parity and uses only `NUM_RE` plus recursive `metrics` walking.
8. **`numbers_in_text` takes text, not a path.** The brief describes it as extracting literals "from a text file". It takes the text instead, so the module stays pure and both callers (⑦, the M2 tool) do their own file reading.
9. **M0's test count.** M0's Task 15 expected `68 passed`; the repository at commit `dc9c380` (tag `m0`) has `63` test functions. This plan uses 63 as the baseline and totals M1 from it.
10. **A shape the live chain cannot produce.** The brief asks the writer to render an "unresolved-only" draft. ⑤ refuses a family with nothing accepted, so the live chain never reaches ⑥ with no ACCEPT rows; the writer's empty-verified branch is defensive and is tested by constructing the upstream artifact directly.
11. **Untested hypotheses have no ⑤ line.** The gate writes a `no_entrypoint` decision with `claim_id: null`, but D4 ties every ⑤ line to a claim row, and an untested hypothesis produced none. Such a decision is therefore absent from `gate_decisions.jsonl`. It is unreachable in the dry run (the template provider always yields a script).
12. **An assertion this plan got wrong, corrected during execution (Task 2).** `tolerance_for("0.02852")` was asserted as `5e-6`, but the reference rule floors at `TOL = 2e-5`, so the answer is `TOL`; the half-unit only wins for three decimals or fewer. The constant was **not** widened and the implementation stayed as ported — the assertion was corrected to match the reference, and the plan's own text is corrected here so the plan and the code agree.
13. **The shipped ⑦ fixture was strengthened while executing (Task 3).** Task 3 first landed with the dry-run `script_runs` check testing only that the ledger file was *readable and non-empty* — a hand-rolled `json.loads` loop, which is a weaker copy of a check arx already provides and therefore runs against the plan's own constraint ("reuse arx by import; do not reimplement what arx provides … `verify_ledger_file`"). The fixture now runs arx's `verify_ledger_file` and exits non-zero when the chain is invalid; it was checked by hand against a good run (`rc=0`) and a tampered one (`rc=1`). The segment's own code is unchanged.
14. **Task 5 needed a file its list did not name, and a definition M0 left ambiguous (both found while executing).** (a) Adding ⑥⑦ to the chain makes `tests/test_dry_run.py`'s "every segment it has" assertions stale — 5 segments become 7, and 5 envelopes/payloads become 7. That file is M0's and Task 5's file list omitted it, so the implementer correctly stopped instead of editing it; the plan's Task 5 file list now names it. (b) `PipelineOutcome.n_claims` summed the per-artifact `claim_ids`, and ⑥ legitimately re-registers ⑤'s ids in its own envelope, so inserting ⑥ doubled the count (3 → 6) and broke M0's `claims   3` expectation. It now counts **distinct** ids: "how many claims does this run make" must not grow when a later segment merely carries them onwards. Neither change touches the ledger — `verify-ledger` still reports `records=8` and `recompute` still reproduces `3/3`, which is the evidence that ⑥⑦ write no claim rows of their own.
15. **The plan's CI and README text ran ahead of the code (found while executing Task 7).** Task 7's text — and Task 10's Step-6 comment — had the end-to-end CI step run `researcher package` and `tools/verify_claim_chain.py`, and the README claim `segments 1-8` with a `package` invocation; none of those exist until Tasks 8–10. Task 7 therefore shipped only the commands that exist today (`run` / `verify-ledger` / `recompute`, plus three `test -f` artifact assertions), and the README says `segments 1-7`, matching `doctor`'s real output. Task 9 raises the README/`doctor` line to 1-8; Task 10 appends the `package` and `tools/verify_claim_chain.py` lines once those files exist. A CI step for a module that does not exist would have been a red pipeline on the first push, which is the one thing this repo's CI must never be.
16. **The plan's own tool code failed its own lint (found while executing Task 10).** Task 10's verbatim `tools/verify_claim_chain.py` opened with `import json`, which nothing in that file uses; `ruff check src tests tools` — that same task's stated gate — flags it as `F401`. The unused import was deleted, with no change to any check, threshold, or assertion. A plan that mandates a clean lint must not ship code that fails it.
17. **The M2 tool passed a run directory that did not exist (found while writing the README, after the tag).** `verify_ledger_file` calls an absent ledger a *valid empty* chain (`chain_valid=True, n_records=0`), so Task 10's `_chain_check` returned `PASS` for a directory holding no run at all — and the tool then scored `4/5`, with checks 2–4 vacuously true over zero claims. Check 1 now requires the ledger file to exist **and** to hold at least one record, and says which of the two failed; a nonexistent directory now scores `3/5` and exits 1, while a real run still scores `5/5`. This is the same class of defect as item 13 (a check that is true and useless), and it is the one kind of bug this repository cannot ship: a false green. Added two tests, and the README's M2 section states the rule so the behaviour is documented rather than implied.

---

## M1 scope

**In:** ⑥ the writer segment; ⑦ the self-audit gate and its declared-config fixture; the numeric-coverage audit module shared by ⑦ and the M2 tool; `gate_decisions.jsonl` and its pipeline wiring; the CLI reporting the three artifacts; ⑧ `package.py` and its CLI subcommand; the M2 read-only verifier `tools/verify_claim_chain.py`; the end-to-end acceptance test; CI; README.

**Out (still deferred, stated rather than implied):** arx's `SequentialState` and `MultiplicityLedger` (D6); LaTeX output; live literature search (the code path exists, it is not exercised); automatic submission to any venue; any model in ⑥ or ⑦.

**Acceptance (the spec's M1 judge, restated exactly):** one command produces the three artifacts; `verify-ledger` is green on the produced ledger; and — the M2 half of the same criterion — `python tools/verify_claim_chain.py runs/ci` prints `5/5` and exits 0, offline, deterministically.

---

## Constraints

- Python 3.12; `ruff check src tests tools` must stay clean. Use `StrEnum` (never `str, Enum`), keep imports isort-sorted, and put `from __future__ import annotations` at the top of every module.
- Deterministic: no `time`, no `datetime`, no `uuid`, no `hash()` in this repository's code. Never write an absolute path, a username, or the machine name into any artifact, the ledger, the draft, or the archive.
- Artifact and ledger paths are always relative to the run directory. `write_payload` returns a relative path — reuse it rather than building paths by hand. An absolute path raises `ValueError` at the boundary (`_resolve_relative` in `segments/base.py`, `_relative` in `segments/selfaudit.py`).
- **Never assert float equality in a test.** No `assert metrics["leader_score"] == 0.9475`. Assert rendered strings, structural facts, counts, sets, or `round(x, 6)`. M0's Task 11 was burned by an exact-float assertion that depended on arx's internal accumulation order; the M1 tests are written so that class of failure cannot recur — ⑥'s tests assert the *strings it renders*, and the end-to-end test asserts structure only.
- Reuse arx by import; do not reimplement what arx provides (`Ledger`, `verify_ledger_file`, `EvaluationGate`, `audit/*`, `prereg`). ⑥ reads `metrics`; it does not call the gate.
- `script_runs` in ⑦ must never receive a machine-absolute path. The shipped fixture uses relative paths with `cwd` inside the run directory.
- No new third-party dependencies (numpy, arx, pytest, ruff only).
- Every task ends with an exact verification command, and the tasks that change end-to-end behaviour also carry a `python3 -m autoresearcher.cli run "..." --dry-run --out runs/...` command a controller can run by hand.

---

## File structure

Existing repo at `/home/liuzewen/autoresearcher`. New files marked **new**; the rest are edits.

| Path | Responsibility |
|---|---|
| `src/autoresearcher/segments/writer.py` **new** | ⑥: render `draft.md` from the ledger; no arithmetic |
| `src/autoresearcher/audit.py` **new** | numeric literals in text, numeric values in a ledger, and `uncovered_numbers` (port of the reference verifier's core rule) |
| `src/autoresearcher/segments/selfaudit.py` **new** | ⑦: declared `file_exists`/`script_runs` checks + the built-in coverage check |
| `src/autoresearcher/fixtures/selfaudit_gates.json` **new** | the dry-run default configuration for ⑦ |
| `src/autoresearcher/decisions.py` **new** | the D4 line schema and its writer |
| `src/autoresearcher/package.py` **new** | ⑧: `package_run` + metadata validation |
| `src/autoresearcher/pipeline.py` | chain gains ⑥⑦; always writes `gate_decisions.jsonl`; reports `draft_path`/`decisions_path` |
| `src/autoresearcher/cli.py` | `run` prints the three artifacts; `package` subcommand; `doctor` capability lines |
| `tools/__init__.py` **new** | makes `tools.verify_claim_chain` importable by pytest (see Task 10) |
| `tools/verify_claim_chain.py` **new** | the M2 third-party verifier: five checks, one line each, `N/5` summary |
| `tests/test_segments_writer.py` **new** | ⑥'s unit tests (assertions on rendered strings) |
| `tests/test_audit.py` **new** | the audit module's unit tests |
| `tests/test_segments_selfaudit.py` **new** | ⑦'s unit tests |
| `tests/test_decisions.py` **new** | the D4 schema and its pipeline wiring |
| `tests/test_m1_end_to_end.py` **new** | the M1 acceptance, structural only |
| `tests/test_package.py` **new** | ⑧ determinism, membership, metadata validation |
| `tests/test_verify_claim_chain.py` **new** | 5/5 on a good run, and the tamper matrix |
| `tests/test_cli.py` | extended for the three artifacts, `doctor`, and `package` |
| `.github/workflows/ci.yml` | the end-to-end step asserts the three artifacts (the tool is added in Task 10) |
| `README.md` | M1 status, the three artifacts, `verify-ledger`, `package` |

Files that change together live together: ⑥ and ⑦ are each one module; the D4 line schema is entirely in `decisions.py`; the archive format is entirely in `package.py`.

---

## The dry run's numbers survive the coverage check

⑦'s built-in check is unforgiving: a decimal literal in `draft.md` that no ledger value covers is a refusal. The dry-run draft is constructed so nothing does. These values were measured in M0 (the table in
`docs/superpowers/plans/2026-10-17-autoresearcher-m0.md` under "Fixture values are measured, not guessed") and are repeated here because ⑥'s rendering and ⑦'s tolerance both depend on them.

The draft emits these literals, and the ledger covers each:

| Literal in `draft.md` | Comes from | Covering metric | Gap vs the literal's tolerance (`max(2e-5, 5e-5)`) |
|---|---|---|---|
| `0.9475` | claim 1 leader | `leader_score` 0.9475 | 0 |
| `0.9155` | claim 1 floor | `floor_estimate` 0.9155 | 0 |
| `+0.0320` | claim 1 margin | `margin` 0.032 | 0 |
| `0.0312` | claim 1 mde | `mde` 0.031242 | 4.2e-5 of 5e-5 |
| `0.0500` | claim 1/2 threshold | `threshold`/`alpha` 0.05 | 0 |
| `0.9275` | claim 2 leader | `leader_score` 0.9275 | 0 |
| `0.8850` | claim 2 floor | `floor_estimate` 0.885 | 0 |
| `+0.0425` | claim 2 margin | `margin` 0.0425 | 0 |
| `0.0363` | claim 2 mde | `mde` 0.036325 | 2.5e-5 of 5e-5 |
| `+0.0285` | claim 3 reason (margin) | `margin` 0.0285 | 0 |
| `0.0357` | claim 3 reason (bound) | `mde` 0.035741 | 4.1e-5 of 5e-5 |

Two entries sit at ~84% of the tolerance. If a fixture value ever moves, re-measure with the M0 appendix probe and fix the *fixture*, never the `< 5e-5` expectation — and never widen the tolerance to make a red test green. `floor_method` (`loo`/`dawid_skene`) and `mde_method` (`binomial_approx`) carry no digits and so cannot leak a literal; `n_generators`/`n_items` render as integers, which `NUM_RE` (it requires a decimal point) does not match. A topic containing a decimal literal would refuse at ⑦ — which is the check working, not a bug.

---

## Task 1: ⑥ the writer — the draft is read back out of the ledger

**Files:**
- Create: `src/autoresearcher/segments/writer.py`
- Test: `tests/test_segments_writer.py`

⑥'s rendering conventions are taken from arx's own report writer,
`/home/liuzewen/.local/lib/python3.12/site-packages/arx/writer.py` (`render_markdown`): the same
`## Verified findings` / `## Unresolved claims (tested, not separable)` headings, the same
`- Leader: \`strong\` at \`0.9475\`` bullet shapes, the same "None." rather than omission. What is
not reused is `AgentResult`/`ReportArtifact` — those carry arx's own run objects, and ⑥'s input is
our ledger. ⑥ must not re-derive any number: every value it prints is read from `ClaimRow.metrics`.

- [ ] **Step 1: Write the failing test**

```python
"""⑥ renders the ledger, and only the ledger.

The fixtures build their own claim rows with explicit ``metrics`` dicts, because
what is under test is the *rendering*, not the gate. Every assertion is on a
rendered string, a count, or a set — never on float equality.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests_helpers import make_context

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.segments.base import write_payload
from autoresearcher.segments.writer import WriterSegment

ACCEPT_METRICS = {
    "verdict": "READABLE",
    "leader_system": "strong",
    "leader_score": 0.9475,
    "floor_estimate": 0.9155,
    "floor_method": "loo",
    "margin": 0.032,
    "mde": 0.031242,
    "mde_method": "binomial_approx",
    "threshold": 0.05,
    "n_generators": 5,
    "n_items": 400,
    "reasons": [],
}
MARGINAL_METRICS = {
    **ACCEPT_METRICS,
    "verdict": "MARGINAL",
    "leader_score": 0.93,
    "floor_estimate": 0.9015,
    "margin": 0.0285,
    "mde": 0.035741,
    "reasons": ["margin +0.0285 is inside the resolution bound 0.0357"],
}


def _rows(ctx, specs):
    """Append gate claim rows with explicit metrics and return them."""
    return [
        ctx.ledger.append_claim(
            claim_id=ctx.ledger.next_claim_id("gate"),
            segment="gate",
            text=text,
            evidence_ref="evidence/experiment-000.json:1",
            gate_decision=decision,
            metrics=metrics,
        )
        for text, decision, metrics in specs
    ]


def _register_gate(ctx, rows) -> None:
    """Write the payload ⑤ would have written and register its envelope."""
    ctx.upstream["gate"] = SegmentArtifact(
        segment_id="gate",
        status=SegmentStatus.OK,
        artifact_path=write_payload(
            ctx,
            "gate.json",
            {
                "decisions": [
                    {
                        "claim_id": row.claim_id,
                        "gate_decision": row.gate_decision,
                        "verdict": row.metrics.get("verdict"),
                        "reasons": list(row.metrics.get("reasons") or []),
                    }
                    for row in rows
                ],
                "n_claims": len(rows),
                "n_accept": sum(1 for row in rows if row.gate_decision == "ACCEPT"),
            },
        ),
        claim_ids=[row.claim_id for row in rows],
        gate_summary={"claims": len(rows)},
        run_fingerprint=ctx.fingerprint,
    )


def _sections(draft: str) -> tuple[str, str]:
    verified, _, rest = draft.partition("## Unresolved claims")
    return verified, rest


def test_accept_rows_land_under_verified_findings(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    rows = _rows(
        ctx,
        [
            ("the strong system separates", "ACCEPT", ACCEPT_METRICS),
            ("the median moves the leader", "MARGINAL", MARGINAL_METRICS),
        ],
    )
    _register_gate(ctx, rows)
    artifact = WriterSegment().run(ctx)

    draft = (ctx.run_dir / "draft.md").read_text(encoding="utf-8")
    verified, unresolved = _sections(draft)
    assert artifact.status is SegmentStatus.OK
    assert artifact.artifact_path == "draft.md"
    assert "## Verified findings" in verified
    assert "the strong system separates" in verified
    assert "- Leader: `strong` at `0.9475`" in verified
    assert "- Noise floor: `0.9155` (loo)" in verified
    assert "- Margin over floor: `+0.0320`" in verified
    assert "- Minimum detectable effect: `0.0312` (`binomial_approx`)" in verified
    assert "- Threshold applied: `0.0500`" in verified
    assert "- Generators: `5` over `400` items" in verified
    # The one that did not clear the gate must not appear as a finding.
    assert "the median moves the leader" not in verified


def test_a_non_accepted_row_lands_under_unresolved_with_its_reason(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    rows = _rows(
        ctx,
        [
            ("the strong system separates", "ACCEPT", ACCEPT_METRICS),
            ("the median moves the leader", "MARGINAL", MARGINAL_METRICS),
        ],
    )
    _register_gate(ctx, rows)
    WriterSegment().run(ctx)

    draft = (ctx.run_dir / "draft.md").read_text(encoding="utf-8")
    _verified, unresolved = _sections(draft)
    assert "the median moves the leader" in unresolved
    assert "`MARGINAL`" in unresolved
    assert "margin +0.0285 is inside the resolution bound 0.0357" in unresolved


def test_a_marginal_only_payload_renders_an_empty_verified_section(tmp_path: Path) -> None:
    # ⑤ refuses a MARGINAL-only family, so the live chain cannot reach ⑥ with
    # nothing accepted. ⑥ must still render that shape rather than crash.
    ctx = make_context(tmp_path)
    rows = _rows(ctx, [("only marginal", "MARGINAL", MARGINAL_METRICS)])
    _register_gate(ctx, rows)
    WriterSegment().run(ctx)

    draft = (ctx.run_dir / "draft.md").read_text(encoding="utf-8")
    verified, unresolved = _sections(draft)
    assert "_None. No claim cleared the gate._" in verified
    assert "only marginal" in unresolved


def test_the_writer_payload_lists_the_claim_ids_it_rendered(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    rows = _rows(
        ctx,
        [
            ("the strong system separates", "ACCEPT", ACCEPT_METRICS),
            ("the median moves the leader", "MARGINAL", MARGINAL_METRICS),
        ],
    )
    _register_gate(ctx, rows)
    artifact = WriterSegment().run(ctx)

    payload = json.loads((ctx.run_dir / "artifacts" / "writer.json").read_text(encoding="utf-8"))
    assert payload["claim_ids"] == [row.claim_id for row in rows]
    assert payload["n_verified"] == 1
    assert payload["n_unresolved"] == 1
    assert artifact.claim_ids == [row.claim_id for row in rows]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_segments_writer.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'autoresearcher.segments.writer'`.

- [ ] **Step 3: Write `src/autoresearcher/segments/writer.py`**

```python
"""⑥ — write the draft by reading the ledger back, never by re-deriving a number.

The rule this file exists to enforce is arx's: every number in the paper is read
back out of the ledgers. This writer has no arithmetic in it. It renders the
``metrics`` dict the gate already committed to, and it labels each section by the
``gate_decision`` the gate already recorded, so a draft can never say something
the ledger does not.
"""

from __future__ import annotations

from dataclasses import dataclass

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.claim import ClaimRow
from autoresearcher.segments.base import SegmentContext, write_payload

VERIFIED_HEADING = "## Verified findings"
UNRESOLVED_HEADING = "## Unresolved claims (tested, not separable)"
DRAFT_NAME = "draft.md"


@dataclass
class WriterSegment:
    segment_id: str = "writer"

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        gate = ctx.upstream_payload("gate")
        # "Travelled" is what the gate actually handed downstream: a claim whose
        # id appears in its decisions. Reading the ledger for the rows and the
        # gate payload for the set is the design's "only read the ledger" rule
        # with the one piece of information the ledger cannot carry — which rows
        # the gate let through.
        travelled = {
            str(decision["claim_id"])
            for decision in gate["decisions"]
            if decision.get("claim_id")
        }
        rows = [row for row in ctx.ledger.rows() if row.claim_id in travelled]
        verified = [row for row in rows if row.gate_decision == "ACCEPT"]
        unresolved = [row for row in rows if row.gate_decision != "ACCEPT"]

        draft = render_draft(topic=ctx.topic, verified=verified, unresolved=unresolved)
        (ctx.run_dir / DRAFT_NAME).write_text(draft, encoding="utf-8")
        payload = write_payload(
            ctx,
            "writer.json",
            {
                "n_verified": len(verified),
                "n_unresolved": len(unresolved),
                "claim_ids": [row.claim_id for row in rows],
            },
        )
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            # Relative, like every artifact path: the run directory is publishable.
            artifact_path=DRAFT_NAME,
            claim_ids=[row.claim_id for row in rows],
            gate_summary={
                "claims": len(rows),
                "n_verified": len(verified),
                "n_unresolved": len(unresolved),
                "payload": payload,
            },
            run_fingerprint=ctx.fingerprint,
        )


def render_draft(*, topic: str, verified: list[ClaimRow], unresolved: list[ClaimRow]) -> str:
    lines = [f"# Draft: {topic}", ""]
    lines.extend([VERIFIED_HEADING, ""])
    if verified:
        for row in verified:
            lines.extend(_finding_lines(row))
    else:
        lines.extend(["_None. No claim cleared the gate._", ""])
    lines.extend(
        [
            UNRESOLVED_HEADING,
            "",
            "_These were run and did not clear the gate. A claim that cannot be "
            "separated from the noise floor is a result, not a failure, and is "
            "reproduced here rather than omitted._",
            "",
        ]
    )
    if unresolved:
        for row in unresolved:
            lines.extend(_unresolved_lines(row))
    else:
        lines.extend(["_None._", ""])
    return "\n".join(lines) + "\n"


def _finding_lines(row: ClaimRow) -> list[str]:
    """One cleared claim, rendered from its recorded ``metrics``.

    Every ``None`` check below is about the *recording*, not the measurement:
    a metric the ledger does not carry is a line the draft must not print.
    """
    metrics = row.metrics
    out = [f"### {row.text}", "", f"- Verdict: `{metrics.get('verdict')}`"]
    if metrics.get("leader_system") is not None and metrics.get("leader_score") is not None:
        out.append(
            f"- Leader: `{metrics['leader_system']}` at "
            f"`{float(metrics['leader_score']):.4f}`"
        )
    if metrics.get("floor_estimate") is not None:
        out.append(
            f"- Noise floor: `{float(metrics['floor_estimate']):.4f}` "
            f"({metrics.get('floor_method') or 'n/a'})"
        )
    if metrics.get("margin") is not None:
        out.append(f"- Margin over floor: `{float(metrics['margin']):+.4f}`")
    if metrics.get("mde") is not None:
        out.append(
            f"- Minimum detectable effect: `{float(metrics['mde']):.4f}` "
            f"(`{metrics.get('mde_method') or 'n/a'}`)"
        )
    if metrics.get("threshold") is not None:
        out.append(f"- Threshold applied: `{float(metrics['threshold']):.4f}`")
    if metrics.get("n_generators") is not None:
        out.append(
            f"- Generators: `{metrics['n_generators']}` over "
            f"`{metrics.get('n_items')}` items"
        )
    for reason in metrics.get("reasons") or []:
        out.append(f"- Note: {reason}")
    out.append("")
    return out


def _unresolved_lines(row: ClaimRow) -> list[str]:
    out = [f"- **{row.text}** `{row.metrics.get('verdict')}`  "]
    for reason in row.metrics.get("reasons") or []:
        out.append(f"  {reason}")
    return out


__all__ = ["VERIFIED_HEADING", "UNRESOLVED_HEADING", "WriterSegment", "render_draft"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_segments_writer.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Lint**

Run: `python3 -m ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/autoresearcher/segments/writer.py tests/test_segments_writer.py
git commit -m "feat(writer): render draft.md from the ledger metrics, with no arithmetic"
```

---

## Task 2: `audit.py` — numeric coverage as one pure function

**Files:**
- Create: `src/autoresearcher/audit.py`
- Test: `tests/test_audit.py`

This module is the port of `/home/liuzewen/.agents/skills/paper-writing-agent/scripts/verify_claim_ledger.py`'s
core rule. The reference verifies a *markdown table* whose fourth column is a human-rounded
number; our ledger is JSON, so the claimed values are the literals in `draft.md` and the
evidence values are the numbers inside `metrics`. `NUM_RE` and the tolerance helper are ported
verbatim. `VALUE_NUM_RE` — the reference's regex for a markdown numeric column — has no analogue
here and is recorded but not exercised; that is the one structural difference between the two
files. Keeping the module pure (text in, list out; no clock, no I/O) is what lets ⑦ and the M2
tool call the same function instead of two near-copies.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import pytest

from autoresearcher.audit import (
    TOL,
    ledger_values,
    numbers_in_text,
    tolerance_for,
    uncovered_numbers,
)
from autoresearcher.claim import ClaimRow


def _row(metrics: dict) -> ClaimRow:
    return ClaimRow(
        claim_id="gate:000",
        segment="gate",
        text="a claim",
        evidence_ref="evidence/experiment-000.json:1",
        gate_decision="ACCEPT",
        metrics=metrics,
    )


def test_tolerance_is_half_a_unit_in_the_last_displayed_digit() -> None:
    # ``pytest.approx``, not ``==``: this is a tolerance, and comparing tolerances
    # with exact float equality is the same trap the measurement tests avoid.
    assert tolerance_for("0.9475") == pytest.approx(5e-5)
    # ``0.02852``'s half-unit is 5e-6, which sits *below* ``TOL``, so the floor
    # wins and the answer is ``TOL``. The constant was not widened to make this
    # pass; the assertion was wrong. (Corrected on execution — see
    # "Where this plan meets the code".)
    assert tolerance_for("0.02852") == pytest.approx(TOL)
    assert tolerance_for("0.9") == pytest.approx(0.05)
    assert tolerance_for("400") == 0.5
    assert TOL == 2e-5


def test_only_decimal_literals_are_numbers() -> None:
    assert numbers_in_text("400 items, 5 generators, +0.0320 over 0.9155") == [
        "+0.0320",
        "0.9155",
    ]
    assert numbers_in_text("no numbers here") == []


def test_ledger_values_walk_nested_metrics() -> None:
    row = _row({"leader_score": 0.9475, "nested": {"x": 1.5}, "listed": [2.5, True], "text": "loo"})
    assert sorted(ledger_values([row])) == [0.9475, 1.5, 2.5]


def test_a_covered_literal_is_not_uncovered() -> None:
    row = _row({"leader_score": 0.9475, "margin": 0.032, "mde": 0.031242})
    assert uncovered_numbers("leader at 0.9475, margin +0.0320, mde 0.0312", [row]) == []


def test_an_uncovered_literal_is_named() -> None:
    rows = [_row({"leader_score": 0.9475})]
    assert uncovered_numbers("leader at 0.9475 but also 0.9999", rows) == ["0.9999"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audit.py -q`
Expected: collection error — `No module named 'autoresearcher.audit'`.

- [ ] **Step 3: Write `src/autoresearcher/audit.py`**

```python
"""Numeric coverage: every decimal in the draft has to come from the ledger.

Ported from ``paper-writing-agent/scripts/verify_claim_ledger.py``. The reference
checks a markdown table's numeric column against resolved evidence values; our
ledger is JSON, so the claimed values are the literals in ``draft.md`` and the
evidence values are the numbers inside ``metrics``. The two regexes and the
tolerance rule are kept as they are there, because a tolerance that differs from
the tool a reader already trusts is a tolerance nobody can compare.

Pure on purpose: text in, list out. ⑦ and the M2 verifier call this, so there is
one implementation of "is this number covered" rather than two that drift.
"""

from __future__ import annotations

import re

#: Ported verbatim from the reference script.
NUM_RE = re.compile(r"[-+]?\d+\.\d+")

#: The reference's regex for a markdown numeric column. Kept for parity; this
#: ledger is JSON, so there is no such column to parse.
VALUE_NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")

#: The reference's floor tolerance.
TOL = 2e-5


def numbers_in_text(text: str) -> list[str]:
    """Every distinct decimal literal, sorted.

    Takes the text rather than a path so that both callers (⑦ reading
    ``draft.md``, the M2 tool reading the same file) share one pure function and
    do their own I/O.
    """
    return sorted({match.group(0) for match in NUM_RE.finditer(text)})


def _numeric_values(value: object) -> list[float]:
    if isinstance(value, bool):  # bool is an int subclass; it is not a number here
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        out: list[float] = []
        for item in value.values():
            out.extend(_numeric_values(item))
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_numeric_values(item))
        return out
    return []


def ledger_values(rows) -> list[float]:
    """Every number the ledger recorded, in row then key order."""
    out: list[float] = []
    for row in rows:
        out.extend(_numeric_values(row.metrics))
    return out


def tolerance_for(literal: str) -> float:
    """Half a unit in the literal's last displayed digit, floored at ``TOL``.

    The ledger's numbers are the machine's; the draft's are what a reader sees.
    A literal displayed to four decimals therefore gets 5e-5, and an integer
    literal gets 0.5 — the reference's rule, unchanged.
    """
    if "." in literal:
        decimals = len(literal.split(".", 1)[1])
        half_unit = 0.5 * 10 ** (-decimals)
    else:
        half_unit = 0.5
    return max(TOL, half_unit)


def is_covered(literal: str, values: list[float]) -> bool:
    target = float(literal)
    tolerance = tolerance_for(literal)
    return any(
        abs(value - target) <= max(tolerance, tolerance * abs(target)) for value in values
    )


def uncovered_numbers(text: str, rows) -> list[str]:
    """The decimal literals in ``text`` that no ledger value covers.

    Empty means every number in the draft can be traced back to something the
    gate measured. It does not mean the numbers are *right* — that is the gate's
    job and ``recompute``'s — only that the draft did not invent one.
    """
    values = ledger_values(rows)
    return [literal for literal in numbers_in_text(text) if not is_covered(literal, values)]


__all__ = [
    "NUM_RE",
    "TOL",
    "VALUE_NUM_RE",
    "is_covered",
    "ledger_values",
    "numbers_in_text",
    "tolerance_for",
    "uncovered_numbers",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_audit.py -q`
Expected: `5 passed`.

- [ ] **Step 5: Lint**

Run: `python3 -m ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/autoresearcher/audit.py tests/test_audit.py
git commit -m "feat(audit): port the numeric-coverage rule to the JSONL ledger"
```

---

## Task 3: ⑦ the self-audit gate

**Files:**
- Create: `src/autoresearcher/segments/selfaudit.py`
- Create: `src/autoresearcher/fixtures/selfaudit_gates.json`
- Test: `tests/test_segments_selfaudit.py`

⑦ is the design's second gate. It reads a declared configuration, runs the declared checks, and
always runs the coverage check from Task 2 — a config cannot turn that one off, because a draft
citing a number the ledger never recorded is precisely the failure this project exists to catch.
Any failure refuses the run and names the failing checks, which is 可拒发 working as intended.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests_helpers import make_context

from autoresearcher.artifact import SegmentStatus
from autoresearcher.segments.selfaudit import COVERAGE_CHECK_NAME, SelfAuditSegment

PASS_SCRIPT = ["python3", "-c", "import sys; sys.exit(0)"]
FAIL_SCRIPT = ["python3", "-c", "import sys; sys.exit(3)"]


def _ledger_row(ctx, score: float = 0.9475) -> None:
    ctx.ledger.append_claim(
        claim_id=ctx.ledger.next_claim_id("gate"),
        segment="gate",
        text="the strong system separates",
        evidence_ref="evidence/experiment-000.json:1",
        gate_decision="ACCEPT",
        metrics={"verdict": "READABLE", "leader_score": score, "mde": 0.031242},
    )


def _config(ctx, checks: list[dict]) -> None:
    (ctx.run_dir / "selfaudit_gates.json").write_text(
        json.dumps({"checks": checks}), encoding="utf-8"
    )


def test_a_run_where_every_check_passes_is_ok(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    _config(
        ctx,
        [
            {"type": "file_exists", "name": "draft present", "path": "draft.md"},
            {"type": "file_exists", "name": "ledger present", "path": "claim_ledger.jsonl"},
            {"type": "script_runs", "name": "interpreter runs", "cmd": PASS_SCRIPT, "cwd": ".", "timeout": 30},
        ],
    )
    artifact = SelfAuditSegment().run(ctx)
    assert artifact.status is SegmentStatus.OK
    assert artifact.gate_summary["n_failed"] == 0


def test_the_shipped_default_configuration_is_used_when_the_run_has_none(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    artifact = SelfAuditSegment().run(ctx)
    assert artifact.status is SegmentStatus.OK
    payload = json.loads((ctx.run_dir / "artifacts" / "selfaudit.json").read_text(encoding="utf-8"))
    assert payload["config"] == "package-default"
    assert len(payload["checks"]) == 4  # three declared + the built-in coverage check


def test_a_missing_declared_file_refuses_and_names_it(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    _config(ctx, [{"type": "file_exists", "name": "results present", "path": "results/e1.json"}])
    artifact = SelfAuditSegment().run(ctx)
    assert artifact.status is SegmentStatus.REFUSED
    assert "results present" in artifact.refusal_reason()


def test_a_script_that_exits_nonzero_refuses(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    _config(ctx, [{"type": "script_runs", "name": "canonical recompute", "cmd": FAIL_SCRIPT, "cwd": ".", "timeout": 30}])
    artifact = SelfAuditSegment().run(ctx)
    assert artifact.status is SegmentStatus.REFUSED
    assert "canonical recompute" in artifact.refusal_reason()


def test_an_uncovered_number_in_the_draft_refuses_and_names_the_number(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9999\n", encoding="utf-8")
    _config(ctx, [])
    artifact = SelfAuditSegment().run(ctx)
    assert artifact.status is SegmentStatus.REFUSED
    reason = artifact.refusal_reason()
    assert COVERAGE_CHECK_NAME in reason
    assert "0.9999" in reason


def test_an_absolute_cwd_is_refused(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    _config(ctx, [{"type": "script_runs", "name": "escapes", "cmd": PASS_SCRIPT, "cwd": "/tmp", "timeout": 30}])
    with pytest.raises(ValueError, match="relative"):
        SelfAuditSegment().run(ctx)


def test_an_absolute_file_exists_path_is_refused(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    _ledger_row(ctx)
    (ctx.run_dir / "draft.md").write_text("Leader at 0.9475\n", encoding="utf-8")
    _config(ctx, [{"type": "file_exists", "name": "outside", "path": "/etc/hosts"}])
    with pytest.raises(ValueError, match="relative"):
        SelfAuditSegment().run(ctx)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_segments_selfaudit.py -q`
Expected: collection error — `No module named 'autoresearcher.segments.selfaudit'`.

- [ ] **Step 3: Write `src/autoresearcher/fixtures/selfaudit_gates.json`**

```json
{
  "checks": [
    {
      "type": "file_exists",
      "name": "draft present",
      "path": "draft.md"
    },
    {
      "type": "file_exists",
      "name": "claim ledger present",
      "path": "claim_ledger.jsonl"
    },
    {
      "type": "script_runs",
      "name": "the ledger is readable and non-empty",
      "cmd": [
        "python3",
        "-c",
        "import json,sys; rows=[json.loads(l) for l in open('claim_ledger.jsonl') if l.strip()]; sys.exit(0 if rows else 1)"
      ],
      "cwd": ".",
      "timeout": 30
    }
  ]
}
```

The third check is deliberately interpreter-agnostic: it runs `python3 -c` over a *relative*
`claim_ledger.jsonl` with `cwd` inside the run directory, so it needs neither this package nor a
machine-absolute interpreter path. A check that shelled out to `sys.executable` would put the
author's interpreter path in the declared config, which is the thing the boundary rule forbids.

- [ ] **Step 4: Write `src/autoresearcher/segments/selfaudit.py`**

```python
"""⑦ — the self-audit gate. It runs declared checks, and it may refuse.

Two check kinds are ported from the private ``paper_promotion_gate/gates_config.json``
(``file_exists``, ``script_runs``), and one check is built in: every numeric
literal in ``draft.md`` must be covered by a numeric value in the claim ledger.
The built-in check is the port of the private ``scripts/verify_claim_ledger.py``'s
core rule, and it is the only check that cannot be switched off from a config
file — a draft citing a number the ledger never recorded is exactly the failure
this design exists to catch.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from autoresearcher.artifact import SegmentArtifact, SegmentStatus
from autoresearcher.audit import uncovered_numbers
from autoresearcher.segments.base import SegmentContext, write_payload

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DEFAULT_CONFIG = FIXTURES / "selfaudit_gates.json"
CONFIG_NAME = "selfaudit_gates.json"
COVERAGE_CHECK_NAME = "draft numbers are covered by the ledger"


@dataclass
class SelfAuditSegment:
    segment_id: str = "selfaudit"

    def run(self, ctx: SegmentContext) -> SegmentArtifact:
        config, source = self._config(ctx)
        checks = [self._declared_check(ctx, item) for item in config.get("checks") or []]
        checks.append(_coverage_check(ctx))

        failed = [check for check in checks if not check["passed"]]
        payload = write_payload(
            ctx,
            "selfaudit.json",
            {"config": source, "checks": checks, "n_failed": len(failed)},
        )
        if failed:
            named = "; ".join(f"{check['name']} ({check['detail']})" for check in failed)
            return SegmentArtifact(
                segment_id=self.segment_id,
                status=SegmentStatus.REFUSED,
                artifact_path=payload,
                claim_ids=[],
                gate_summary={
                    "checks": len(checks),
                    "failed": [check["name"] for check in failed],
                    "reason": f"self-audit failed: {named}",
                },
                run_fingerprint=ctx.fingerprint,
            )
        return SegmentArtifact(
            segment_id=self.segment_id,
            status=SegmentStatus.OK,
            artifact_path=payload,
            claim_ids=[],
            gate_summary={"checks": len(checks), "n_failed": 0},
            run_fingerprint=ctx.fingerprint,
        )

    def _config(self, ctx: SegmentContext) -> tuple[dict, str]:
        """The run's declared configuration, or the shipped default.

        The source is recorded so a reader can tell a run that declared its own
        checks from one that used the fixture.
        """
        declared = ctx.run_dir / CONFIG_NAME
        if declared.is_file():
            return json.loads(declared.read_text(encoding="utf-8")), CONFIG_NAME
        return json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8")), "package-default"

    def _declared_check(self, ctx: SegmentContext, declared: dict) -> dict:
        kind = str(declared.get("type", ""))
        name = str(declared.get("name", kind))
        if kind == "file_exists":
            return _file_exists_check(ctx, name, declared)
        if kind == "script_runs":
            return _script_runs_check(ctx, name, declared)
        # An unknown kind fails closed: a config that asks for a check we do not
        # implement has not been satisfied.
        return {"name": name, "kind": kind, "passed": False, "detail": f"unknown check type {kind!r}"}


def _relative(value: object, *, what: str) -> Path:
    candidate = Path(str(value))
    if candidate.is_absolute():
        raise ValueError(
            f"{what} {value!r} must be relative to the run directory; "
            "an absolute path would publish the machine that produced it"
        )
    return candidate


def _file_exists_check(ctx: SegmentContext, name: str, declared: dict) -> dict:
    relative = _relative(declared.get("path", ""), what=f"file_exists path for {name!r}")
    return {
        "name": name,
        "kind": "file_exists",
        "passed": (ctx.run_dir / relative).is_file(),
        "detail": relative.as_posix(),
    }


def _script_runs_check(ctx: SegmentContext, name: str, declared: dict) -> dict:
    cmd = [str(element) for element in (declared.get("cmd") or [])]
    for element in cmd:
        _relative(element, what=f"script_runs cmd element for {name!r}")
    if not cmd:
        return {"name": name, "kind": "script_runs", "passed": False, "detail": "empty cmd"}
    cwd = _relative(declared.get("cwd", "."), what=f"script_runs cwd for {name!r}")
    timeout = int(declared.get("timeout", 60))
    try:
        completed = subprocess.run(
            cmd,
            cwd=ctx.run_dir / cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": name, "kind": "script_runs", "passed": False, "detail": str(exc)}
    if completed.returncode == 0:
        return {"name": name, "kind": "script_runs", "passed": True, "detail": "exit 0"}
    tail = (completed.stderr or completed.stdout or "").strip().splitlines()
    return {
        "name": name,
        "kind": "script_runs",
        "passed": False,
        "detail": f"exit {completed.returncode}: {tail[-1] if tail else 'no output'}",
    }


def _coverage_check(ctx: SegmentContext) -> dict:
    draft = ctx.run_dir / "draft.md"
    if not draft.is_file():
        return {
            "name": COVERAGE_CHECK_NAME,
            "kind": "coverage",
            "passed": False,
            "detail": "draft.md is missing",
        }
    uncovered = uncovered_numbers(draft.read_text(encoding="utf-8"), ctx.ledger.rows())
    return {
        "name": COVERAGE_CHECK_NAME,
        "kind": "coverage",
        "passed": not uncovered,
        "detail": "all numbers covered" if not uncovered else f"uncovered: {', '.join(uncovered)}",
    }


__all__ = ["COVERAGE_CHECK_NAME", "DEFAULT_CONFIG", "SelfAuditSegment"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_segments_selfaudit.py -q`
Expected: `7 passed`.

- [ ] **Step 6: Lint**

Run: `python3 -m ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add src/autoresearcher/segments/selfaudit.py src/autoresearcher/fixtures/selfaudit_gates.json tests/test_segments_selfaudit.py
git commit -m "feat(selfaudit): declared file_exists/script_runs checks plus built-in numeric coverage"
```

---

## Task 4: `gate_decisions.jsonl`

**Files:**
- Create: `src/autoresearcher/decisions.py`
- Modify: `src/autoresearcher/pipeline.py`
- Test: `tests/test_decisions.py`

The decision record is deliberately thin. It duplicates ⑤'s decisions, which the ledger's chain
already commits to, because a reader wants one file that answers "what did this run decide" without
parsing a ledger and a set of envelopes. It is written by the pipeline *after* the chain, so a
refused run still gets one.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import json
from pathlib import Path

from autoresearcher.claim import ClaimRow
from autoresearcher.decisions import DECISION_LINE_KEYS, decision_lines, write_decisions
from autoresearcher.pipeline import RunConfig, run_pipeline


def _row(claim_id: str, text: str, decision: str, metrics: dict) -> ClaimRow:
    return ClaimRow(
        claim_id=claim_id,
        segment="gate",
        text=text,
        evidence_ref="evidence/experiment-000.json:1",
        gate_decision=decision,
        metrics=metrics,
    )


def test_a_claim_line_carries_exactly_the_declared_keys() -> None:
    lines = decision_lines(
        [_row("gate:000", "a claim", "ACCEPT", {"verdict": "READABLE", "reasons": []})], []
    )
    assert len(lines) == 1
    assert tuple(lines[0]) == DECISION_LINE_KEYS
    assert lines[0]["gate"] == "gate"
    assert lines[0]["target"] == "a claim"
    assert lines[0]["claim_id"] == "gate:000"
    assert lines[0]["decision"] == "ACCEPT"
    assert lines[0]["verdict"] == "READABLE"


def test_a_check_line_is_pass_or_fail_and_carries_its_detail() -> None:
    lines = decision_lines(
        [],
        [
            {"name": "draft present", "passed": True, "detail": "draft.md"},
            {"name": "draft numbers are covered by the ledger", "passed": False, "detail": "uncovered: 0.9999"},
        ],
    )
    assert tuple(lines[0]) == DECISION_LINE_KEYS
    assert [line["decision"] for line in lines] == ["PASS", "FAIL"]
    assert all(line["gate"] == "selfaudit" and line["claim_id"] is None for line in lines)
    assert lines[1]["reasons"] == ["uncovered: 0.9999"]


def test_the_lines_are_written_in_chain_order(tmp_path: Path) -> None:
    rows = [
        _row("gate:000", "first", "ACCEPT", {"verdict": "READABLE"}),
        _row("gate:001", "second", "MARGINAL", {"verdict": "MARGINAL"}),
    ]
    checks = [{"name": "a check", "passed": True, "detail": "ok"}]
    target = write_decisions(tmp_path, decision_lines(rows, checks))
    parsed = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert [line["target"] for line in parsed] == ["first", "second", "a check"]


def test_a_run_writes_the_record_even_when_the_chain_refuses(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(
        RunConfig(topic="t", run_dir=run_dir, dry_run=True, generators=2)
    )
    assert outcome.chain.completed is False
    target = run_dir / "gate_decisions.jsonl"
    assert target.is_file()
    assert outcome.decisions_path == target
    lines = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    claim_lines = [line for line in lines if line["gate"] == "gate"]
    assert len(claim_lines) == 3
    assert {line["decision"] for line in claim_lines} == {"UNDECIDABLE"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_decisions.py -q`
Expected: collection error — `No module named 'autoresearcher.decisions'`.

- [ ] **Step 3: Write `src/autoresearcher/decisions.py`**

```python
"""The run's decision record: one line per gate decision, in the order it was made.

This is a projection, not a second chain. The claim ledger's hash chain already
commits to ⑤'s decisions; duplicating them in a chain of their own would leave
two things to verify, and the copy would be stale the first time anyone edited a
record. What the file adds is that "what did this run decide" is answerable
without a ledger reader.
"""

from __future__ import annotations

import json
from pathlib import Path

from autoresearcher.claim import ClaimRow

DECISION_NAME = "gate_decisions.jsonl"

#: The D4 schema. Frozen by test.
DECISION_LINE_KEYS: tuple[str, ...] = (
    "gate",
    "target",
    "claim_id",
    "decision",
    "verdict",
    "reasons",
)


def claim_lines(rows: list[ClaimRow]) -> list[dict]:
    """⑤'s decisions, in ledger order: ACCEPT/MARGINAL/UNDECIDABLE/REJECT."""
    return [
        {
            "gate": "gate",
            "target": row.text,
            "claim_id": row.claim_id,
            "decision": row.gate_decision,
            "verdict": row.metrics.get("verdict"),
            "reasons": list(row.metrics.get("reasons") or []),
        }
        for row in rows
    ]


def check_lines(checks: list[dict]) -> list[dict]:
    """⑦'s decisions, in check order: PASS/FAIL, with the detail as the reason."""
    return [
        {
            "gate": "selfaudit",
            "target": str(check.get("name", "")),
            "claim_id": None,
            "decision": "PASS" if check.get("passed") else "FAIL",
            "verdict": None,
            "reasons": [] if check.get("passed") else [str(check.get("detail", ""))],
        }
        for check in checks
    ]


def decision_lines(rows: list[ClaimRow], checks: list[dict]) -> list[dict]:
    return claim_lines(rows) + check_lines(checks)


def write_decisions(run_dir: Path, lines: list[dict]) -> Path:
    target = Path(run_dir) / DECISION_NAME
    body = "".join(json.dumps(line, sort_keys=True) + "\n" for line in lines)
    target.write_text(body, encoding="utf-8")
    return target


__all__ = [
    "DECISION_LINE_KEYS",
    "DECISION_NAME",
    "check_lines",
    "claim_lines",
    "decision_lines",
    "write_decisions",
]
```

- [ ] **Step 4: Wire it into `src/autoresearcher/pipeline.py`**

Add these imports to `pipeline.py` (keeping the block isort-sorted):

```python
from autoresearcher.decisions import decision_lines, write_decisions
```

Add the field to `PipelineOutcome`, after `records`:

```python
    decisions_path: Path
```

Add the helper to `pipeline.py` (module level, below `run_pipeline`):

```python
def _selfaudit_checks(run_dir: Path, chain: ChainResult) -> list[dict]:
    """⑦'s per-check results, read from its payload when ⑦ ran.

    Read from the payload rather than from the envelope's ``gate_summary`` so the
    record carries the same detail a reader of the payload sees — including for a
    refusal, which wrote its payload before it refused.
    """
    for artifact in chain.artifacts:
        if artifact.segment_id != "selfaudit":
            continue
        path = run_dir / artifact.artifact_path
        if path.is_file():
            return list(json.loads(path.read_text(encoding="utf-8")).get("checks") or [])
    return []
```

In `run_pipeline`, after the existing `ledger.append_record("run_end", ...)` call and before the
`return`, write the record:

```python
    decisions_path = write_decisions(
        run_dir,
        decision_lines(ledger.rows(), _selfaudit_checks(run_dir, chain)),
    )
```

and pass it to the outcome:

```python
    return PipelineOutcome(
        run_dir=run_dir,
        claim_ledger=ledger.path,
        chain=chain,
        fingerprint_digest=digest,
        records=ledger.as_records(),
        decisions_path=decisions_path,
    )
```

At this point the chain still has no ⑦, so `_selfaudit_checks` returns `[]` and the file holds
claim lines only — which is why the test above asserts on the `"gate"` lines and never on the
total.

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_decisions.py -q`
Expected: `4 passed`.

- [ ] **Step 6: Confirm the rest of the suite still passes**

Run: `python3 -m pytest -q`
Expected: all previously passing tests still pass (`63` M0 tests plus the `20` added in Tasks 1–4).

- [ ] **Step 7: Lint**

Run: `python3 -m ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add src/autoresearcher/decisions.py src/autoresearcher/pipeline.py tests/test_decisions.py
git commit -m "feat(decisions): write gate_decisions.jsonl after every run, refusals included"
```

---

## Task 5: one command, three artifacts

**Files:**
- Modify: `src/autoresearcher/pipeline.py`
- Modify: `src/autoresearcher/cli.py`
- Test: `tests/test_cli.py`

The brief's task list left one insertion unassigned: nothing says *where* ⑥ and ⑦ join the chain.
It has to be here — `researcher run` can only report a draft path once the chain produces a draft,
and the decisions record can only carry ⑦'s lines once ⑦ has run. Everything else in this task is
the CLI surface.

- [ ] **Step 1: Write the failing tests (append to `tests/test_cli.py`)**

```python
def test_run_prints_the_three_artifacts(tmp_path: Path, capsys) -> None:
    run_dir = tmp_path / "run"
    assert main(["run", "--dry-run", "a topic", "--out", str(run_dir)]) == 0
    out = capsys.readouterr().out
    assert "draft" in out
    assert "ledger" in out
    assert "decisions" in out
    assert (run_dir / "draft.md").is_file()
    assert (run_dir / "gate_decisions.jsonl").is_file()


def test_doctor_says_segments_one_to_seven_are_available(capsys) -> None:
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "segments 1-7" in out
    assert "not built" not in out
```

(Note: Task 9 edits the second assertion to `segments 1-8` once ⑧ lands. It is written as
`1-7` here so that this task's expectation is the one the brief states.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py -q`
Expected: 2 failures — no `draft` line yet, and `segments 6-8   not built (M1)` still printed.

- [ ] **Step 3: Add ⑥⑦ to the chain in `pipeline.py`**

Add the imports (isort-sorted) and the two segments:

```python
from autoresearcher.segments.selfaudit import SelfAuditSegment
from autoresearcher.segments.writer import WriterSegment
```

```python
            GateSegment(config=config),
            # The draft is written from the ledger, then self-audited before the
            # run is allowed to call itself finished. ⑦ can refuse, and when it
            # does the chain stops — same rule as ⑤.
            WriterSegment(),
            SelfAuditSegment(),
        ],
        ctx,
        envelopes_dir=run_dir / "segments",
    )
```

Add `draft_path` to `PipelineOutcome` (after `decisions_path`) and compute it before the return:

```python
    draft = run_dir / "draft.md"
    return PipelineOutcome(
        run_dir=run_dir,
        claim_ledger=ledger.path,
        chain=chain,
        fingerprint_digest=digest,
        records=ledger.as_records(),
        decisions_path=decisions_path,
        draft_path=draft if draft.is_file() else None,
    )
```

- [ ] **Step 4: Update `_run` and `_doctor` in `cli.py`**

Replace `_run`'s print block — the five existing lines keep their exact spacing, because the
existing tests match them (`"status   OK"`, `"claims   3"`):

```python
    print(f"status   {outcome.status}")
    print(f"run      {outcome.run_dir}")
    print(f"draft    {outcome.draft_path or '-'}")
    print(f"ledger   {outcome.claim_ledger}")
    print(f"decisions {outcome.decisions_path}")
    print(f"claims   {outcome.n_claims}")
    print(f"stopped  {outcome.chain.stopped_at or '-'}")
    print(f"recompute it with: python3 -m autoresearcher.cli recompute {outcome.run_dir}")
```

Replace the capability lines in `_doctor`:

```python
    print("  segments 1-7   available")
    print("  dry-run        available (offline fixtures, no model, no network)")
    print("  live search    implemented, not exercised")
```

- [ ] **Step 5: Run the tests and the acceptance by hand**

Run: `python3 -m pytest tests/test_cli.py -q`
Expected: `9 passed` (the 7 existing plus the 2 added here).

Run: `python3 -m autoresearcher.cli run "does the gate hold" --dry-run --out runs/m1`
Expected on stdout: `status   OK`, a `draft    .../draft.md` line, a `ledger` line, a
`decisions .../gate_decisions.jsonl` line, `claims   3`, `stopped  -`, and exit code 0.

Run: `python3 -m autoresearcher.cli recompute runs/m1`
Expected: `chain OK | reproduced 3/3 | mismatches 0 | unresolvable 0`, exit 0.

Run: `python3 -m autoresearcher.cli run "does the gate hold" --dry-run --generators 2 --out runs/m1-refused`
Expected: `status   REFUSED`, `draft    -`, exit code 2 — the chain stopped at ⑤, ⑥ never ran,
and the decision record still exists.

- [ ] **Step 6: Check the whole suite and lint**

Run: `python3 -m pytest -q`
Expected: all tests pass.

Run: `python3 -m ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add src/autoresearcher/pipeline.py src/autoresearcher/cli.py tests/test_cli.py
git commit -m "feat(pipeline): run 6 and 7 in the chain and report the three artifacts"
```

---

## Task 6: M1 end-to-end acceptance

**Files:**
- Create: `tests/test_m1_end_to_end.py`

This is the design's success criterion written as a test. It asserts structure and coverage only —
never a float — so it cannot be broken by arx's internal accumulation order.

- [ ] **Step 1: Write `tests/test_m1_end_to_end.py`**

```python
"""The M1 acceptance: one command, three artifacts, all offline, all checkable.

Structural assertions only. Nothing here compares a float: the numbers already
went through ⑤'s gate, and repeating its arithmetic in a test would just be a
second implementation to keep in sync.
"""

from __future__ import annotations

import json
from pathlib import Path

from arx.experiments.ledger import verify_ledger_file

from autoresearcher.audit import uncovered_numbers
from autoresearcher.claim import ClaimLedger
from autoresearcher.pipeline import RunConfig, run_pipeline


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_one_command_produces_the_three_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(
        RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True)
    )
    assert outcome.chain.completed is True
    assert outcome.chain.stopped_at is None

    draft = run_dir / "draft.md"
    ledger = run_dir / "claim_ledger.jsonl"
    decisions = run_dir / "gate_decisions.jsonl"
    assert draft.is_file()
    assert ledger.is_file()
    assert decisions.is_file()

    assert verify_ledger_file(ledger)["chain_valid"] is True

    rows = ClaimLedger(ledger).rows()
    checks = json.loads((run_dir / "artifacts/selfaudit.json").read_text(encoding="utf-8"))["checks"]
    lines = _lines(decisions)
    assert len(lines) == len(rows) + len(checks)
    assert sum(1 for line in lines if line["gate"] == "gate") == len(rows)
    assert sum(1 for line in lines if line["gate"] == "selfaudit") == len(checks)


def test_the_draft_is_labelled_by_the_decision_the_gate_recorded(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True))
    rows = ClaimLedger(run_dir / "claim_ledger.jsonl").rows()
    text = (run_dir / "draft.md").read_text(encoding="utf-8")
    verified, _, unresolved = text.partition("## Unresolved claims")
    assert "## Verified findings" in verified
    assert "## Unresolved claims" in text
    accepted = [row for row in rows if row.gate_decision == "ACCEPT"]
    travelled = [row for row in rows if row.gate_decision != "ACCEPT"]
    assert accepted and travelled  # the fixture has both, by construction
    for row in accepted:
        assert row.text in verified
        assert row.text not in unresolved
    for row in travelled:
        assert row.text in unresolved
        assert row.text not in verified


def test_every_number_in_the_draft_is_covered_by_the_ledger(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_pipeline(RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True))
    rows = ClaimLedger(run_dir / "claim_ledger.jsonl").rows()
    assert uncovered_numbers((run_dir / "draft.md").read_text(encoding="utf-8"), rows) == []


def test_a_run_that_refuses_at_the_gate_leaves_no_draft(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(
        RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True, generators=2)
    )
    assert outcome.chain.stopped_at == "gate"
    assert outcome.draft_path is None
    assert not (run_dir / "draft.md").exists()
    # The decision record is written even for a refusal: a refusal is a decision.
    assert (run_dir / "gate_decisions.jsonl").is_file()
    assert all(line["gate"] == "gate" for line in _lines(run_dir / "gate_decisions.jsonl"))
```

- [ ] **Step 2: Run the acceptance**

Run: `python3 -m pytest tests/test_m1_end_to_end.py -q`
Expected: `4 passed`.

- [ ] **Step 3: Run the acceptance as a command, not a test**

Run: `python3 -m autoresearcher.cli run "does a noise floor bound what a leaderboard can claim" --dry-run --out runs/accept`
Expected: exit 0, and `runs/accept/` contains `draft.md`, `claim_ledger.jsonl`,
`gate_decisions.jsonl`, `env_fingerprint.json`.

- [ ] **Step 4: Confirm no machine path leaked into the new artifacts**

Run:

```bash
python3 - <<'PY'
import pathlib

bad = []
for path in sorted(pathlib.Path("runs/accept").rglob("*")):
    if path.is_file() and path.suffix != ".py" and "/home/" in path.read_text(encoding="utf-8", errors="ignore"):
        bad.append(str(path))
print("machine paths:", bad or "none")
PY
```

Expected: `machine paths: none`.

- [ ] **Step 5: Lint and commit**

Run: `python3 -m ruff check src tests`
Expected: `All checks passed!`

```bash
git add tests/test_m1_end_to_end.py
git commit -m "test(m1): one command produces draft, ledger and decision record"
```

---

## Task 7: CI and README

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`

Task 7's CI step asserts the three artifacts only. The M2 tool does not exist yet at this point in
the order, so its invocation is added by Task 10 — said explicitly here and there rather than
implied, so a reader of either task knows which half is where.

- [ ] **Step 1: Replace the "Dry run end to end" step in `.github/workflows/ci.yml`**

```yaml
      - name: Dry run end to end
        run: |
          python -m autoresearcher.cli run "does the gate hold" --dry-run --out runs/ci
          python -m autoresearcher.cli verify-ledger runs/ci/claim_ledger.jsonl
          python -m autoresearcher.cli recompute runs/ci
          test -f runs/ci/draft.md
          test -f runs/ci/claim_ledger.jsonl
          test -f runs/ci/gate_decisions.jsonl
          python -m autoresearcher.cli package runs/ci
```

The three `test -f` lines are the milestone's acceptance criterion executed in CI: a run that
produces the three artifacts, a ledger that verifies, and a run whose every decision reproduces
from disk. `package` joins the step here because ⑧ lands in Task 8, before Task 10's tool. (Task 10
appends `python tools/verify_claim_chain.py runs/ci` — the last line of this step.)

- [ ] **Step 2: Update `README.md`**

Replace the status paragraph:

```markdown
Status: **M1** — segments 1-8 run offline: ①→⑤ produce a hash-chained claim ledger, ⑥ writes
`draft.md` by reading that ledger back, ⑦ self-audits the draft and may refuse, ⑧ packages the run.
`verify-ledger` verifies any claim's chain, and `verify_claim_chain.py` re-checks a finished run
from the outside. arx's sequential and multiplicity layers are still deliberately out of scope.
```

Add this section after "Why the gate is the only passage":

````markdown
## The three artifacts

One command produces three files, and each answers a different question:

| File | Produced by | Answers |
|---|---|---|
| `claim_ledger.jsonl` | ①→⑤ | what was measured, and what the gate decided about each claim |
| `draft.md` | ⑥ | what the run says, with every number read back out of the ledger |
| `gate_decisions.jsonl` | the pipeline | what this run decided — ⑤'s per-claim decisions first, then ⑦'s per-check decisions |

```bash
python3 -m autoresearcher.cli run --dry-run "does a noise floor bound what a leaderboard can claim" --out runs/demo
python3 -m autoresearcher.cli verify-ledger runs/demo/claim_ledger.jsonl
python3 tools/verify_claim_chain.py runs/demo
python3 -m autoresearcher.cli package runs/demo
```

`gate_decisions.jsonl` is a projection of the run, not a second hash chain: the ledger's chain
already commits to ⑤'s decisions. Package the same run twice and the archive is byte-identical —
that is what "deterministic" buys, and it is the reason packaging is a command and submission is
not.
````

- [ ] **Step 3: Confirm the documented commands work**

Run: `python3 -m autoresearcher.cli run "does the gate hold" --dry-run --out runs/readme`
Expected: exit 0 with the `draft`/`ledger`/`decisions` lines.

Run: `python3 -m autoresearcher.cli verify-ledger runs/readme/claim_ledger.jsonl`
Expected: `OK  records=8`, exit 0.

- [ ] **Step 4: Lint and commit**

Run: `python3 -m ruff check src tests`
Expected: `All checks passed!`

```bash
git add .github/workflows/ci.yml README.md
git commit -m "ci+docs: assert the three artifacts end to end, document them"
```

---

## Task 8: ⑧ `package.py`

**Files:**
- Create: `src/autoresearcher/package.py`
- Test: `tests/test_package.py`

⑧ packages a finished run. It does not submit, and it does not ask a venue anything. The archive
contains the four run files plus the validated metadata — five members, per D7. Determinism is
enforced by construction: members sorted, `date_time` pinned, no filesystem mtime ever read.

- [ ] **Step 1: Write `tests/test_package.py`**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_package.py -q`
Expected: collection error — `No module named 'autoresearcher.package'`.

- [ ] **Step 3: Write `src/autoresearcher/package.py`**

```python
"""⑧ — package a run for submission. It packages; it does not submit.

Determinism is the point: the same run directory packages to the same bytes, so a
stranger can rebuild the archive and compare a sha256 instead of trusting ours.
That is why every member's ``ZipInfo.date_time`` is pinned and the members are
sorted — nothing about the machine or the wall clock may leak into the archive.

No venue, no account, no network: the design's §6 excludes automatic submission.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from autoresearcher.claim import ClaimLedger
from autoresearcher.fingerprint import fingerprint_digest

ARCHIVE_NAME = "submission.zip"

#: The four files a finished run must carry, per D7.
PACKAGED_FILES: tuple[str, ...] = (
    "draft.md",
    "claim_ledger.jsonl",
    "gate_decisions.jsonl",
    "env_fingerprint.json",
)
METADATA_FILE = "submission_metadata.json"

#: The keys a submission's metadata must carry. Frozen by test.
REQUIRED_METADATA_KEYS: tuple[str, ...] = ("title", "authors", "abstract", "artifacts")

#: Pinned so two builds agree byte for byte. 1980-01-01 is zip's own epoch.
PINNED_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def package_run(run_dir: Path, *, metadata: dict | None = None) -> Path:
    """Write ``submission.zip`` and return its path.

    ``metadata`` is an injection point for a caller that already read the run's
    ``submission_metadata.json``; with no argument the run directory's own file
    is used, and a deterministic default derived from the run when there is none.
    """
    run_dir = Path(run_dir)
    meta = metadata if metadata is not None else _run_metadata(run_dir)
    validate_metadata(meta)

    missing = [name for name in PACKAGED_FILES if not (run_dir / name).is_file()]
    if missing:
        raise ValueError(f"cannot package: {', '.join(missing)} missing from {run_dir}")
    metadata_bytes = (json.dumps(meta, indent=2, sort_keys=True) + "\n").encode("utf-8")

    archive = run_dir / ARCHIVE_NAME
    members = {name: (run_dir / name).read_bytes() for name in PACKAGED_FILES}
    members[METADATA_FILE] = metadata_bytes
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=PINNED_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            handle.writestr(info, members[name])
    return archive


def validate_metadata(metadata: dict) -> None:
    """Refuse a metadata file that is missing a key or carries a machine path."""
    missing = [key for key in REQUIRED_METADATA_KEYS if key not in metadata]
    if missing:
        raise ValueError(f"submission metadata is missing required keys {missing}")
    for key, value in metadata.items():
        for text in _strings(value):
            if _is_absolute(text):
                raise ValueError(
                    f"submission metadata field {key!r} carries an absolute path "
                    f"{text!r}; the archive is meant to be publishable"
                )


def _run_metadata(run_dir: Path) -> dict:
    path = run_dir / METADATA_FILE
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return default_metadata(run_dir)


def default_metadata(run_dir: Path) -> dict:
    """Metadata derived from the run, never from the machine.

    The title is the topic the run was started with, and the fingerprint is the
    digest of the run's own ``env_fingerprint.json`` — both are already in the run
    directory, so nothing new is invented and nothing outside it is read.
    """
    return {
        "title": _topic(run_dir),
        "authors": [],
        "abstract": "",
        "artifacts": list(PACKAGED_FILES),
        "run_fingerprint": _fingerprint(run_dir),
    }


def _topic(run_dir: Path) -> str:
    for record in ClaimLedger(run_dir / "claim_ledger.jsonl").as_records():
        if record.get("kind") == "run_start":
            return str((record.get("payload") or {}).get("topic", ""))
    return ""


def _fingerprint(run_dir: Path) -> str:
    path = run_dir / "env_fingerprint.json"
    if not path.is_file():
        return ""
    return fingerprint_digest(json.loads(path.read_text(encoding="utf-8")))


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in _strings(item)]
    return []


def _is_absolute(text: str) -> bool:
    return Path(text).is_absolute() or (len(text) > 1 and text[1] == ":")


__all__ = [
    "ARCHIVE_NAME",
    "METADATA_FILE",
    "PACKAGED_FILES",
    "PINNED_DATE_TIME",
    "REQUIRED_METADATA_KEYS",
    "default_metadata",
    "package_run",
    "validate_metadata",
]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_package.py -q`
Expected: `7 passed`.

- [ ] **Step 5: Lint and commit**

Run: `python3 -m ruff check src tests`
Expected: `All checks passed!`

```bash
git add src/autoresearcher/package.py tests/test_package.py
git commit -m "feat(package): deterministic submission.zip with validated metadata"
```

---

## Task 9: ⑧ CLI wiring

**Files:**
- Modify: `src/autoresearcher/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_cli.py`)**

```python
def test_package_writes_a_reproducible_archive(tmp_path: Path, capsys) -> None:
    run_dir = tmp_path / "run"
    main(["run", "--dry-run", "a topic", "--out", str(run_dir)])
    assert main(["package", str(run_dir)]) == 0
    out = capsys.readouterr().out
    assert "submission.zip" in out
    assert "sha256" in out
    assert (run_dir / "submission.zip").is_file()


def test_package_exits_nonzero_for_an_unfinished_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "claim_ledger.jsonl").write_text("", encoding="utf-8")
    assert main(["package", str(run_dir)]) == 1
```

And change Task 5's assertion so the capabilities line matches ⑧ being available:

```python
def test_doctor_says_segments_one_to_seven_are_available(capsys) -> None:
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "segments 1-8" in out
    assert "packaging" in out
    assert "not built" not in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py -q`
Expected: failures — `invalid choice: 'package'`, and `segments 1-7` where `1-8` is expected.

- [ ] **Step 3: Add the subcommand and the doctor lines to `cli.py`**

Add the import:

```python
from autoresearcher.package import package_run
```

Register the subcommand next to the others:

```python
    package = sub.add_parser("package", help="package a finished run into a deterministic archive")
    package.add_argument("run_dir")
    package.set_defaults(handler=_package)
```

Add the handler:

```python
def _package(args: argparse.Namespace) -> int:
    try:
        archive = package_run(Path(args.run_dir))
    except ValueError as exc:
        # A run that is missing an artifact is not packageable. Say which, and
        # exit 1: this is broken input, not a refusal the tool made on purpose.
        print(f"cannot package: {exc}", file=sys.stderr)
        return EXIT_BROKEN
    print(f"archive  {archive}")
    print(f"sha256   {hashlib.sha256(archive.read_bytes()).hexdigest()}")
    return EXIT_OK
```

and `import hashlib` at the top of `cli.py`. Update `_doctor`:

```python
    print("  segments 1-8   available")
    print("  dry-run        available (offline fixtures, no model, no network)")
    print("  live search    implemented, not exercised")
    print("  packaging      available (researcher package)")
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest tests/test_cli.py -q`
Expected: `11 passed` — the `7` M0 tests, plus `2` from Task 5 and `2` from this task.

- [ ] **Step 5: Run the CLI by hand and lint**

Run: `python3 -m autoresearcher.cli package runs/accept`
Expected: `archive  runs/accept/submission.zip`, a `sha256  ...` line, exit 0.

Run: `python3 -m autoresearcher.cli package runs/accept` (again)
Expected: the same `sha256` — the archive is byte-identical.

Run: `python3 -m ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/autoresearcher/cli.py tests/test_cli.py
git commit -m "feat(cli): researcher package, and a doctor that knows 8 is built"
```

---

## Task 10: the M2 tool — `tools/verify_claim_chain.py`

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/verify_claim_chain.py`
- Test: `tests/test_verify_claim_chain.py`
- Modify: `.github/workflows/ci.yml`

A third party gets the run directory and nothing else. The tool runs exactly five checks, prints
one line per check and a final `N/5`, and exits 0 only on 5/5. It reads `autoresearcher.audit` and
`autoresearcher.claim` (one implementation of each rule, not a copy) and it writes nothing at all —
not even a cache.

`tools/__init__.py` is what makes `from tools import verify_claim_chain` work under pytest. The
suite is run as `python -m pytest` from the repository root, which puts the root on `sys.path`, so
the package imports without a `conftest.py` shim. (A shim would be the fallback if `tools/` ever
moved; it is not needed today and is not added.)

- [ ] **Step 1: Write `tools/__init__.py`**

```python
"""Standalone tools that operate on a finished run without touching the pipeline."""
```

- [ ] **Step 2: Write the failing test**

```python
from __future__ import annotations

import json
from pathlib import Path

from arx.experiments.ledger import Ledger

from autoresearcher.pipeline import RunConfig, run_pipeline
from tools import verify_claim_chain


def _good_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    outcome = run_pipeline(
        RunConfig(topic="does the gate hold", run_dir=run_dir, dry_run=True)
    )
    assert outcome.chain.completed is True
    return run_dir


def _results(run_dir: Path) -> list[bool]:
    return [check.ok for check in verify_claim_chain.checks(run_dir)]


def _ledger_lines(run_dir: Path) -> list[dict]:
    text = (run_dir / "claim_ledger.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _write_ledger(run_dir: Path, records: list[dict]) -> None:
    path = run_dir / "claim_ledger.jsonl"
    path.unlink()
    ledger = Ledger(path)
    for record in records:
        ledger.append(record["kind"], record["payload"])


def test_a_good_run_passes_all_five_checks(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    assert _results(run_dir) == [True] * 5
    assert verify_claim_chain.main([str(run_dir)]) == 0


def test_editing_a_ledger_line_breaks_the_chain_and_only_the_chain(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    records = _ledger_lines(run_dir)
    for record in records:
        if record.get("kind") == "claim":
            record["payload"]["claim_id"] = "gate:999"
            break
    (run_dir / "claim_ledger.jsonl").write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )
    # check 1 only: the payload still has all eight fields, the evidence bytes are
    # untouched, and recompute does not depend on claim_id.
    assert _results(run_dir) == [False, True, True, True, True]


def test_altering_an_evidence_file_fails_the_hash_check(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    evidence = run_dir / "evidence/experiment-000.json"
    evidence.write_bytes(evidence.read_bytes() + b"\n")
    results = _results(run_dir)
    # Check 3 is the one that owns "the evidence hashes to what the ledger says".
    # Check 4 also goes red here, and cannot not: recompute re-derives
    # metrics["evidence_sha256"] from the same bytes, so the file a third party
    # needs to distrust turns two checks red by construction.
    assert results[2] is False
    assert results[3] is False
    assert results[0] is True and results[1] is True and results[4] is True


def test_altering_a_recorded_metric_fails_only_the_recompute_check(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    records = _ledger_lines(run_dir)
    for record in records:
        if record.get("kind") == "claim":
            record["payload"]["metrics"]["power"] = 0.9
            break
    # Re-chain so the ledger is internally consistent: this isolates "the recorded
    # decision does not re-derive" from "the ledger was edited after the fact".
    _write_ledger(run_dir, records)
    # check 4 only: `power` is a metric the draft does not render, so coverage
    # (check 5) is unaffected, and the chain verifies because we rebuilt it.
    assert _results(run_dir) == [True, True, True, False, True]


def test_an_uncovered_number_in_the_draft_fails_only_the_coverage_check(tmp_path: Path) -> None:
    run_dir = _good_run(tmp_path)
    draft = run_dir / "draft.md"
    draft.write_text(draft.read_text(encoding="utf-8") + "\n0.9999\n", encoding="utf-8")
    assert _results(run_dir) == [True, True, True, True, False]


def test_the_summary_line_counts_five(tmp_path: Path, capsys) -> None:
    run_dir = _good_run(tmp_path)
    assert verify_claim_chain.main([str(run_dir)]) == 0
    assert "5/5" in capsys.readouterr().out
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_verify_claim_chain.py -q`
Expected: collection error — `No module named 'tools.verify_claim_chain'`.

- [ ] **Step 4: Write `tools/verify_claim_chain.py`**

```python
"""A third-party, read-only verifier for one autoresearcher run.

Five checks, no writes, no pipeline, no network. It re-derives what it can and
reports what it cannot; it never repairs a run, and a failure here is a fact
about the files rather than a crash in the reporter.

    python tools/verify_claim_chain.py runs/demo
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from arx.experiments.ledger import verify_ledger_file

from autoresearcher.audit import uncovered_numbers
from autoresearcher.claim import CLAIM_FIELDS, ClaimLedger
from autoresearcher.recompute import recompute_run

CHAIN_CHECK = "the ledger's hash chain verifies"
FIELDS_CHECK = "every claim carries all eight claim fields"
EVIDENCE_CHECK = "every claim's evidence hashes to what the ledger recorded"
RECOMPUTE_CHECK = "every recorded gate decision re-derives from the files"
COVERAGE_CHECK = "every number in draft.md is covered by the ledger"
N_CHECKS = 5


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def checks(run_dir: Path) -> list[Check]:
    """The five checks, in the order a reader cares about them."""
    run_dir = Path(run_dir)
    ledger_path = run_dir / "claim_ledger.jsonl"
    return [
        _chain_check(ledger_path),
        _fields_check(ledger_path),
        _evidence_check(run_dir, ledger_path),
        _recompute_check(run_dir),
        _coverage_check(run_dir, ledger_path),
    ]


def _chain_check(ledger_path: Path) -> Check:
    report = verify_ledger_file(ledger_path)
    return Check(CHAIN_CHECK, bool(report["chain_valid"]), f"records={report['n_records']}")


def _claim_records(ledger_path: Path) -> list[dict]:
    return [record for record in ClaimLedger(ledger_path).as_records() if record.get("kind") == "claim"]


def _fields_check(ledger_path: Path) -> Check:
    # Read the raw records, not ``rows()``: a claim that lost a field is exactly
    # what this check must *report*, and ``rows()`` raises instead.
    bad = [
        f"seq {record.get('seq')}"
        for record in _claim_records(ledger_path)
        if any(field not in (record.get("payload") or {}) for field in CLAIM_FIELDS)
    ]
    return Check(FIELDS_CHECK, not bad, "ok" if not bad else "missing in " + ", ".join(bad))


def _evidence_check(run_dir: Path, ledger_path: Path) -> Check:
    try:
        rows = ClaimLedger(ledger_path).rows()
    except (ValueError, KeyError, TypeError) as exc:
        return Check(EVIDENCE_CHECK, False, f"ledger unreadable: {exc}")
    bad: list[str] = []
    for row in rows:
        path = run_dir / row.evidence_ref.rsplit(":", 1)[0]
        if not path.is_file():
            bad.append(f"{row.claim_id}: missing {row.evidence_ref}")
            continue
        recorded = row.metrics.get("evidence_sha256")
        if not recorded:
            # A claim on a path that never reached the measurement records an
            # empty hash (segments/gate.py's `_undecidable`); the anchor still has
            # to resolve, but there is no recorded digest to compare against, and
            # comparing against `""` would be a false FAIL rather than a finding.
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != str(recorded):
            bad.append(f"{row.claim_id}: sha256 does not match")
    return Check(EVIDENCE_CHECK, not bad, "ok" if not bad else "; ".join(bad))


def _recompute_check(run_dir: Path) -> Check:
    try:
        report = recompute_run(run_dir)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return Check(RECOMPUTE_CHECK, False, f"recompute failed: {exc}")
    ok = not report.mismatches and not report.unresolvable
    return Check(RECOMPUTE_CHECK, ok, report.summary())


def _coverage_check(run_dir: Path, ledger_path: Path) -> Check:
    draft = run_dir / "draft.md"
    if not draft.is_file():
        return Check(COVERAGE_CHECK, False, "draft.md is missing")
    try:
        rows = ClaimLedger(ledger_path).rows()
    except (ValueError, KeyError, TypeError) as exc:
        return Check(COVERAGE_CHECK, False, f"ledger unreadable: {exc}")
    uncovered = uncovered_numbers(draft.read_text(encoding="utf-8"), rows)
    return Check(COVERAGE_CHECK, not uncovered, "ok" if not uncovered else "uncovered: " + ", ".join(uncovered))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python tools/verify_claim_chain.py <run_dir>", file=sys.stderr)
        return 2
    results = checks(Path(args[0]))
    for index, check in enumerate(results, start=1):
        print(f"{'PASS' if check.ok else 'FAIL'}  {index}. {check.name}  ({check.detail})")
    passed = sum(1 for check in results if check.ok)
    print(f"{passed}/{N_CHECKS}")
    return 0 if passed == N_CHECKS else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_verify_claim_chain.py -q`
Expected: `6 passed`.

- [ ] **Step 6: Append the tool to CI's end-to-end step**

```yaml
          python -m autoresearcher.cli package runs/ci
          python tools/verify_claim_chain.py runs/ci
```

(Task 7's step asserted the three artifacts and `package`; this line is the M2 acceptance, and it
is added here because the file does not exist any earlier in the plan.)

- [ ] **Step 7: Run the tool by hand, the full suite, and the linter**

Run: `python tools/verify_claim_chain.py runs/accept`
Expected: five `PASS` lines and `5/5`, exit 0.

Run: `python3 -m pytest -q`
Expected: everything passes (`63` M0 tests plus `41` added by this milestone).

Run: `python3 -m ruff check src tests tools`
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add tools/__init__.py tools/verify_claim_chain.py tests/test_verify_claim_chain.py .github/workflows/ci.yml
git commit -m "feat(tools): a read-only five-check verifier for a finished run"
```

---

## M1 close-out

D6 restated, because a deferral that is not restated becomes a silent omission: **arx's
`SequentialState` and `MultiplicityLedger` are still not in this package.** M1 did not add them;
`GateSegment` still runs `EvaluationGate.decision(...)` alone; and no M1 task touches them. They
are not required by the design's §2 row for ⑤ or by §0's success criterion, so their absence is a
decision recorded here rather than a gap discovered later. If they are ever added, it is a
milestone of its own with its own tests.

- [ ] **Step 1: Reconcile the test counts**

Run: `python3 -m pytest -q`
Expected: `104 passed` — `63` M0 tests plus `41` M1 tests (`test_segments_writer` 4, `test_audit` 5,
`test_segments_selfaudit` 7, `test_decisions` 4, `test_m1_end_to_end` 4, `test_package` 7,
`test_verify_claim_chain` 6, and `test_cli` 7 → 11, i.e. `+4`). If the total differs, one of the
per-task counts drifted; reconcile it in that task rather than here.

- [ ] **Step 2: Tag the milestone**

```bash
git tag m1
```

The tag is what makes "M1 is done" a fact about the repository rather than a claim in a message.
