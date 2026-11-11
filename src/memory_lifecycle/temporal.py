"""The time rules, in pure Python: no SQL and no connection.

Everything that decides "what instant is now", "is this instant acceptable" and
"does this version hold at this moment" lives here, to be tested without a database
(ADR 0002). ``holds_at`` is the oracle: the same rule as the SQL predicates, used by
the coherence tests to check the database against it.

PT: As regras de tempo, em Python puro: sem SQL e sem conexão.

Tudo o que decide "que instante é agora", "este instante é aceitável" e "esta
versão vale neste momento" vive aqui, para ser testado sem banco (ADR 0002).
``holds_at`` é o oráculo: a mesma regra dos predicados SQL, usada pelos testes de
coerência para conferir o banco contra ela.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from memory_lifecycle.exceptions import ConflictError, InvalidArgumentError
from memory_lifecycle.model import MemoryVersion

Mode = Literal["as_of", "known_at"]


@dataclass(frozen=True, slots=True)
class Moment:
    """The instant and mode of a read; the "now" mode is ``as_of(now)``.

    PT: O instante e o modo de uma leitura; o modo "agora" é ``as_of(now)``.
    """

    mode: Mode
    instant: datetime


def require_timezone(name: str, instant: datetime | None) -> None:
    """Reject a naive ``datetime``: an ambiguous instant would corrupt both axes.

    PT: Recusa um ``datetime`` sem fuso: um instante ambíguo corromperia os dois eixos.
    """
    if instant is not None and instant.utcoffset() is None:
        raise InvalidArgumentError(f"{name} must be timezone-aware (a datetime with tzinfo)")


def require_text(name: str, value: str) -> None:
    """Reject what is not text, or is empty or whitespace only, before it reaches the database.

    PT: Recusa o que não é texto, ou é vazio ou só de espaços, antes de chegar ao banco.
    """
    if not isinstance(value, str) or not value.strip():
        raise InvalidArgumentError(f"{name} must be a non-empty string")


def resolve_now(clock: Callable[[], datetime] | None) -> datetime:
    """This operation's instant, read once: from the injected clock or the current UTC.

    PT: O instante desta operação, lido uma vez: do relógio injetado ou o UTC atual.
    """
    instant = clock() if clock is not None else datetime.now(UTC)
    require_timezone("the clock", instant)
    return instant


def resolve_moment(now: datetime, as_of: datetime | None, known_at: datetime | None) -> Moment:
    """Choose the read mode; ``as_of`` and ``known_at`` together are rejected.

    PT: Escolhe o modo da leitura; ``as_of`` e ``known_at`` juntos são recusados.
    """
    if as_of is not None and known_at is not None:
        raise InvalidArgumentError("pass as_of or known_at, not both")
    require_timezone("as_of", as_of)
    require_timezone("known_at", known_at)
    if known_at is not None:
        return Moment("known_at", known_at)
    return Moment("as_of", as_of if as_of is not None else now)


def require_interval(valid_from: datetime, valid_to: datetime | None) -> None:
    """Reject an empty or inverted validity time: ``valid_to`` comes after.

    PT: Recusa um tempo de validade vazio ou invertido: ``valid_to`` vem depois.
    """
    if valid_to is not None and valid_to <= valid_from:
        raise InvalidArgumentError("valid_to must be later than valid_from")


def require_validity_close(current: MemoryVersion, new_end: datetime) -> None:
    """Check that ``expire``/``supersede`` close an open validity, after its start.

    Only what is open gets closed: a current version already expired is a
    ``ConflictError`` (for a new fact, ``remember``); an end at or before the start is
    an ``InvalidArgumentError``.

    PT: Confere que ``expire``/``supersede`` fecham uma validade aberta, depois do início.

    Só se fecha o que está aberto: uma vigente já encerrada é ``ConflictError``
    (para um fato novo, ``remember``); um fim no início ou antes dele é
    ``InvalidArgumentError``.
    """
    if current.valid_to is not None:
        raise ConflictError("the memory was already expired; use remember to record a new fact")
    if new_end <= current.valid_from:
        raise InvalidArgumentError(
            "the new bound must be later than the current version's valid_from"
        )


def holds_at(version: MemoryVersion, moment: Moment) -> bool:
    """Each mode's rule in Python; the SQL of ``recall`` must agree with it.

    Half-open intervals: ``[valid_from, valid_to)`` and ``[recorded_at, superseded_at)``.

    PT: A regra de cada modo em Python; o SQL de ``recall`` tem de concordar com ela.

    Intervalos semiabertos: ``[valid_from, valid_to)`` e ``[recorded_at, superseded_at)``.
    """
    d = moment.instant
    valid = version.valid_from <= d and (version.valid_to is None or version.valid_to > d)
    if moment.mode == "as_of":
        return version.superseded_at is None and valid
    known = version.recorded_at <= d and (
        version.superseded_at is None or version.superseded_at > d
    )
    return known and valid
