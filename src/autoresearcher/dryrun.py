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
