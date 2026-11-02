#!/usr/bin/env python3
"""Offline chain-verification benchmark for autoresearcher.

Runs the real verify_claim_chain tool against the committed demo run and checks
that it reports 5/5. This is the honest claim the pipeline makes: a finished run
can be verified from the outside by reading only its run directory.

Does NOT consult a model or network. Exits 0 only on 5/5.

Usage: python benchmarks/bench_verify_chain.py
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "verify_claim_chain.py"
RUN = ROOT / "runs" / "demo"


def main():
    print("=== autoresearcher chain verification ===")
    if not TOOL.exists():
        print("  [FAIL] verify_claim_chain.py not found")
        return 1
    if not RUN.exists():
        print("  [FAIL] runs/demo not found")
        return 1
    r = subprocess.run([sys.executable, str(TOOL), str(RUN)],
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    print(out)
    ok = r.returncode == 0 and "5/5" in out
    print(f"RESULT: {'PASS' if ok else 'FAIL'}  (exit={r.returncode})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
