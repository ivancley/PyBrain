"""Scenario: two supersedes of the same version. One wins; the other fails loudly.

Stage 1 expresses the race through ``expected_version_id``: both writers hold the
same current version. Stage 3 adds the two-connection variant, which exercises the
conditional close itself.

PT: Cenário: duas substituições da mesma versão. Uma vence; a outra falha alto.

A Etapa 1 expressa a corrida por ``expected_version_id``: os dois escritores
seguram a mesma versão vigente. A Etapa 3 acrescenta a variante com duas
conexões, que exercita o próprio fechamento condicional.
"""

from __future__ import annotations

import pytest

from memory_lifecycle import ConflictError, Memory
from tests.conftest import ManualClock


def test_second_writer_conflicts(memory: Memory, owner: str, clock: ManualClock):
    current = memory.remember(owner, "v1", kind="note")
    # A validity must last longer than zero.
    # PT: Uma validade precisa durar mais que zero.
    clock.advance(days=1)

    winner = memory.supersede(
        owner, current.memory_id, "v2", expected_version_id=current.version_id
    )
    with pytest.raises(ConflictError):
        memory.supersede(owner, current.memory_id, "v2'", expected_version_id=current.version_id)

    # Only the rows of the winning supersede: the original, the copy and the new one.
    # PT: Só as linhas da substituição vencedora: a original, a cópia e a nova.
    history = memory.history(owner, current.memory_id)
    assert len(history) == 3
    assert (history[0].version_id, history[-1].version_id) == (
        current.version_id,
        winner.version_id,
    )
