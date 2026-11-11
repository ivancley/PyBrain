"""Invalid inputs are refused before any statement (reports/review-change-core.md, important 5).

Before, they reached the database as a raw driver error and, in ``PARTICIPATE`` mode,
aborted the app's transaction.

PT: Entradas inválidas são recusadas antes de qualquer instrução (reports/review-change-core.md, importante 5).

Antes, chegavam ao banco como erro cru do driver e, no modo ``PARTICIPATE``,
abortavam a transação do app.
"""

from __future__ import annotations

import pytest

from memory_lifecycle import FakeEmbeddingProvider, InvalidArgumentError, Memory
from memory_lifecycle.connection.dsn import DSNProvider
from tests.conftest import ManualClock


@pytest.mark.parametrize("owner_id", [None, "", "  ", 42])
def test_invalid_owner_is_refused(memory: Memory, owner_id: object):
    with pytest.raises(InvalidArgumentError, match="owner_id"):
        memory.remember(owner_id, "x", kind="nota")  # type: ignore[arg-type]
    with pytest.raises(InvalidArgumentError, match="owner_id"):
        memory.recall(owner_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("tenant_id", [None, "", " "])
def test_invalid_tenant_is_refused_at_construction(dsn: str, tenant_id: object):
    with pytest.raises(InvalidArgumentError, match="tenant_id"):
        Memory(
            connection=DSNProvider(dsn),
            embeddings=FakeEmbeddingProvider(),
            tenant_id=tenant_id,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("kind", ["", "   "])
def test_empty_kind_in_supersede_and_correct(
    memory: Memory, owner: str, clock: ManualClock, kind: str
):
    v = memory.remember(owner, "a", kind="nota")
    clock.advance(days=1)
    with pytest.raises(InvalidArgumentError, match="kind"):
        memory.supersede(owner, v.memory_id, "b", kind=kind)
    with pytest.raises(InvalidArgumentError, match="kind"):
        memory.correct(owner, v.memory_id, "b", kind=kind)
    assert memory.history(owner, v.memory_id) == [v]


def test_forget_with_more_than_one_target_is_refused(memory: Memory, owner: str):
    v = memory.remember(owner, "a", kind="nota", entity_id="e")
    with pytest.raises(InvalidArgumentError, match="exactly one target"):
        memory.forget(owner, memory_id=v.memory_id, everything=True)
    assert memory.history(owner, v.memory_id) == [v]


def test_history_with_a_frozen_clock_ends_at_the_current_version(memory: Memory, owner: str):
    # Regression (reports/temporal-change-core.md, P2): on a recorded_at tie the last
    # version of the history was the wrong one in half of the runs.
    # PT: Regressão (reports/temporal-change-core.md, P2): no empate de registrado_em a
    # PT: última versão do histórico era a errada em metade das execuções.
    for _ in range(10):
        v = memory.remember(owner, "errada", kind="nota")
        right = memory.correct(owner, v.memory_id, "certa")
        assert memory.history(owner, v.memory_id)[-1] == right
