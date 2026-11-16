# autoresearcher

**0.1.0** (status M1, Python >=3.12, MIT). Dry-run proves the gate and the ledger: each segment's artifact must clear a statistical gate before the next segment reads it, a refusal stops the chain, and `tools/verify_claim_chain.py` recomputes the hash chain from the run directory alone.
It does not prove research quality, and it does not prove any live-model result. `--dry-run` reads canned fixtures and a `NullLLM`; omitting `--dry-run` still builds `offline_config`, so no model is called.
Unique here, next to [ai-researcher](https://github.com/aidless/ai-researcher) (signed envelope, kill-switch, two-seat review) and [arx](https://github.com/aidless/arx) (the `EvaluationGate` and ledger this package calls): the eight-segment artifact chain, a draft read back from the ledger, and a self-audit that may refuse. arx's sequential and multiplicity layers are out of scope. This package is not on PyPI.

STATUS: WORK-IN-PROGRESS — not A yet

- GitHub About is outside git. On 2026-11-16 it still reads `自主研究循环原型`. Suggested replacement: `v0.1.0 (M1). Dry-run proves the statistical gate and the hash-chained claim ledger only. It does not prove research quality or any live-model result. Variant of ai-researcher; arx sequential and multiplicity layers are out of scope. Not published to PyPI.`
- A clone with no network cannot install. `arx` is pinned in `pyproject.toml` as a git URL. `make check` is offline only after that install.

## Check

```bash
git clone https://github.com/aidless/autoresearcher
cd autoresearcher
python3 -m pip install -e ".[dev]"
make check
```

`make check` runs ruff, pytest with line coverage of `src/autoresearcher` (CI floor 95%), the 20 `eval/cases.jsonl` cases and their self-test, `tools/verify_golden.py`, a fresh `--dry-run`, and `tools/check_fresh_refusal.py`. No API key. The fresh dry-run writes `runs/`, which is gitignored.

CI is `.github/workflows/ci.yml` on Python 3.12. It installs and runs `make check`. On 2026-11-16, CPython 3.12.3, after dependencies were already installed, `make check` finished in 14 seconds and pytest reported **96.14%** line coverage (906 statements, 35 missed) across **111** tests. That number is line coverage of this package, not a research score. `pr-checks.yml` only compile-checks sources. `packaging.yml` builds an sdist and a wheel on Python 3.12 and does not upload them.

`pip install autoresearcher` installs a different project (PyPI `autoresearcher` 0.0.8, Eimen Hamedat). This repository has no GitHub release and no publish workflow.

## What the committed snapshot shows

`golden/dry-run` is one `--dry-run` of the topic string `does a noise floor bound what a leaderboard can claim`. `golden/MANIFEST.sha256` lists sha256 hashes of that directory and of `golden/refused-two-generators`. `python3 tools/verify_golden.py` recomputes the hashes and re-derives every gate decision with the same `adjudicate()` the gate used.

The finished snapshot's gate decisions, read from `gate_decisions.jsonl`, are ACCEPT, ACCEPT, MARGINAL. The MARGINAL reason string is `margin +0.0285 is inside the resolution bound 0.0357`. Those numbers come from `src/autoresearcher/fixtures/dry_run_experiment.py.in` (synthetic votes). They are not a result about leaderboards.

`golden/refused-two-generators` is the same command with `--generators 2`. The CLI exits 2, the chain stops at `gate`, every decision is UNDECIDABLE with reason `floor_degenerate`, and there is no `draft.md`. Details and the other negative cases are in [FAILURE_MODES.md](FAILURE_MODES.md).

## Relation

| Repo | What it is | What this repo does not take from it |
|---|---|---|
| [ai-researcher](https://github.com/aidless/ai-researcher) | Mainline loop: an approved envelope, a kill-switch, Ed25519 bundles, two-seat review | Signing, envelopes, and the two-seat review |
| [arx](https://github.com/aidless/arx) at `24845f207fe967866d0ebb8bd11aa212e9d7ea99` | Statistical gate, pre-registration, hash-chained ledger | Sequential correction and the multiplicity layer |
| this repo, 0.1.0 | Segments ①–⑧, artifact-only handoff, draft from the ledger, self-audit, deterministic `submission.zip` that is never submitted | — |

Author-local paths: `/home/liuzewen/...` in `docs/superpowers/plans/` is the author's machine on 2026-10-17, labeled at the top of each plan. `/home/someone/...` in tests is synthetic.
