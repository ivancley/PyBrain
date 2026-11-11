"""Spec ``recall``: with ``query``, order by similarity and a score in [0, 1] (ADR 0009).

PT: Spec ``recall``: com ``query``, ordem por similaridade e pontuação em [0, 1] (ADR 0009).
"""

from __future__ import annotations

import math

import pytest

from memory_lifecycle import InvalidArgumentError, Memory
from tests.conftest import ManualClock

TEXTS = ["prefere respostas curtas", "mora em Lisboa", "gosta de exemplos", "usa Python"]


def test_identical_text_comes_first_with_score_one(memory: Memory, owner: str):
    for text in TEXTS:
        memory.remember(owner, text, kind="nota")

    results = memory.recall(owner, query="mora em Lisboa")

    assert results[0].version.content == "mora em Lisboa"
    assert results[0].score is not None
    assert math.isclose(results[0].score, 1.0, abs_tol=1e-6)
    scores = [r.score for r in results]
    assert all(s is not None and 0.0 <= s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)  # type: ignore[type-var]
    assert len(results) == len(TEXTS)


def test_query_respects_scope_mode_and_limit(memory: Memory, owner: str, clock: ManualClock):
    memory.remember(owner, "mora em Lisboa", kind="nota", context_id="c1")
    clock.advance(days=1)
    porto = memory.remember(owner, "mora no Porto", kind="nota")
    clock.advance(days=1)
    memory.expire(owner, porto.memory_id)

    in_scope = memory.recall(owner, query="mora em Lisboa", contexts=[None])
    assert in_scope == []
    yesterday = memory.recall(owner, query="mora", as_of=clock.at(days=1), limit=1)
    assert len(yesterday) == 1


def test_empty_query_is_refused(memory: Memory, owner: str):
    with pytest.raises(InvalidArgumentError):
        memory.recall(owner, query="  ")
