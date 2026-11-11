"""The SQL of ``recall`` agrees with the ``temporal.holds_at`` oracle, in both modes.

Generates random histories (fixed seed) with the operations already implemented,
retroactive ones included, and compares, for many instants, the set of versions the
database returns with the set the Python rule accepts. Finds the edges that
hand-written scenarios miss.

PT: O SQL de ``recall`` concorda com o oráculo ``temporal.holds_at``, nos dois modos.

Gera históricos aleatórios (semente fixa) com as operações já implementadas,
inclusive retroativas, e compara, para muitos instantes, o conjunto de versões que
o banco devolve com o conjunto que a regra em Python aceita. Acha as bordas que
os cenários escritos à mão não acham.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime, timedelta

from memory_lifecycle import ConflictError, InvalidArgumentError, Memory, MemoryVersion
from memory_lifecycle.temporal import Moment, holds_at
from tests.conftest import T0, ManualClock

SEED = 20261106
MEMORIES = 60
INSTANTS = 40
HOUR = timedelta(hours=1)


def _instant(rng: random.Random, near: datetime) -> datetime:
    return near + rng.randint(-24 * 60, 24 * 60) * HOUR


def _operations(
    memory: Memory, owner: str
) -> list[Callable[[random.Random, str, datetime], object]]:
    """The operations that change time, drawn over each memory.

    PT: As operações que mudam o tempo, sorteadas sobre cada memória.
    """
    return [
        lambda r, mid, now: memory.expire(owner, mid, valid_to=_instant(r, now)),
        lambda r, mid, now: memory.supersede(
            owner, mid, f"sub-{r.random()}", valid_from=_instant(r, now)
        ),
        lambda r, mid, now: memory.correct(owner, mid, f"cor-{r.random()}"),
    ]


def _generate(memory: Memory, owner: str, clock: ManualClock) -> list[str]:
    rng = random.Random(SEED)
    operations = _operations(memory, owner)
    ids: list[str] = []
    for i in range(MEMORIES):
        clock.advance(hours=rng.randint(1, 48))
        start = _instant(rng, clock())
        end = start + rng.randint(1, 24 * 90) * HOUR if rng.random() < 0.3 else None
        ids.append(
            memory.remember(owner, f"m{i}", kind="nota", valid_from=start, valid_to=end).memory_id
        )
        for _ in range(rng.randint(0, 3)):
            clock.advance(hours=rng.randint(1, 48))
            operation = rng.choice(operations)
            try:
                operation(rng, ids[-1], clock())
            except (ConflictError, InvalidArgumentError):
                # Operation refused by the rule (validity already closed, bound before the start).
                # PT: Operação recusada pela regra (validade já fechada, limite antes do início).
                pass
    return ids


def test_sql_agrees_with_the_oracle(memory: Memory, owner: str, clock: ManualClock):
    ids = _generate(memory, owner, clock)
    every: list[MemoryVersion] = [v for mid in ids for v in memory.history(owner, mid)]
    rng = random.Random(SEED + 1)
    end = clock()
    instants = [T0 + (end - T0) * rng.random() for _ in range(INSTANTS)]
    instants += [v.recorded_at for v in every[:10]] + [v.valid_from for v in every[:10]]

    divergences = []
    for instant in instants:
        for mode in ("as_of", "known_at"):
            expected = {v.version_id for v in every if holds_at(v, Moment(mode, instant))}
            obtained = {
                r.version.version_id for r in memory.recall(owner, limit=10_000, **{mode: instant})
            }
            if expected != obtained:
                divergences.append((mode, instant, expected ^ obtained))
    assert not divergences, divergences[:3]
    # A generator that only swallows errors would leave the test green without testing anything.
    # PT: Um gerador que só engole erros deixaria o teste verde sem testar nada.
    closed = sum(v.superseded_at is not None for v in every)
    copies = sum(v.previous_version_id is not None and v.valid_to is not None for v in every)
    assert closed >= MEMORIES // 2, f"only {closed} closed records in {len(every)} versions"
    assert copies >= MEMORIES // 4, f"only {copies} bounded copies"
