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
