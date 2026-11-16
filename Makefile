# Offline checks. `pip install -e ".[dev]"` is the one network step: it fetches
# the pinned arx commit. After that, `make check` does not use the network.
.PHONY: eval check

eval:
	python3 -m pytest -q --cov=autoresearcher --cov-report=term-missing --cov-fail-under=95
	python3 eval/run_cases.py

check: eval
	python3 -m ruff check .
	python3 -c 'import tomllib; from autoresearcher import __version__; v=tomllib.load(open("pyproject.toml","rb"))["project"]["version"]; assert v==__version__=="0.1.0", (v, __version__)'
	python3 eval/run_cases.py --selftest
	python3 tools/verify_golden.py
	python3 benchmarks/bench_verify_chain.py
	python3 -m autoresearcher.cli run --dry-run "does a noise floor bound what a leaderboard can claim" --out runs/check
	python3 tools/verify_claim_chain.py runs/check
	python3 -m autoresearcher.cli recompute runs/check
	python3 tools/check_fresh_refusal.py
