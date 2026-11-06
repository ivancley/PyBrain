"""As regras de tempo, em Python puro: sem SQL e sem conexão.

Tudo o que decide "que instante é agora", "este instante é aceitável" e "esta
versão vale neste momento" vive aqui, para ser testado sem banco (ADR 0002).
``vale_em`` é o oráculo: a mesma regra dos predicados SQL, usada pelos testes de
coerência para conferir o banco contra ela.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from memory_lifecycle.exceptions import ErroDeArgumentoInvalido, ErroDeConflito
from memory_lifecycle.model import VersaoDeMemoria

Modo = Literal["como_em", "sabido_em"]


@dataclass(frozen=True, slots=True)
class Momento:
    """O instante e o modo de uma leitura; o modo "agora" é ``como_em(agora)``."""

    modo: Modo
    instante: datetime


def exigir_fuso(nome: str, instante: datetime | None) -> None:
    """Recusa um ``datetime`` sem fuso: um instante ambíguo corromperia os dois eixos."""
    if instante is not None and instante.utcoffset() is None:
        raise ErroDeArgumentoInvalido(f"{nome} precisa de fuso horário (datetime com tzinfo)")


def exigir_texto(nome: str, valor: str) -> None:
    """Recusa o que não é texto, ou é vazio ou só de espaços, antes de chegar ao banco."""
    if not isinstance(valor, str) or not valor.strip():
        raise ErroDeArgumentoInvalido(f"{nome} precisa ser um texto não vazio")


def resolver_agora(relogio: Callable[[], datetime] | None) -> datetime:
    """O instante desta operação, lido uma vez: do relógio injetado ou o UTC atual."""
    instante = relogio() if relogio is not None else datetime.now(UTC)
    exigir_fuso("o relógio", instante)
    return instante


def resolver_momento(
    agora: datetime, como_em: datetime | None, sabido_em: datetime | None
) -> Momento:
    """Escolhe o modo da leitura; ``como_em`` e ``sabido_em`` juntos são recusados."""
    if como_em is not None and sabido_em is not None:
        raise ErroDeArgumentoInvalido("passe como_em ou sabido_em, não os dois")
    exigir_fuso("como_em", como_em)
    exigir_fuso("sabido_em", sabido_em)
    if sabido_em is not None:
        return Momento("sabido_em", sabido_em)
    return Momento("como_em", como_em if como_em is not None else agora)


def exigir_intervalo(valido_de: datetime, valido_ate: datetime | None) -> None:
    """Recusa um tempo de validade vazio ou invertido: ``valido_ate`` vem depois."""
    if valido_ate is not None and valido_ate <= valido_de:
        raise ErroDeArgumentoInvalido("valido_ate precisa ser posterior a valido_de")


def exigir_fechamento_de_validade(vigente: VersaoDeMemoria, novo_fim: datetime) -> None:
    """Confere que ``encerrar``/``substituir`` fecham uma validade aberta, depois do início.

    Só se fecha o que está aberto: uma vigente já encerrada é ``ErroDeConflito``
    (para um fato novo, ``lembrar``); um fim no início ou antes dele é
    ``ErroDeArgumentoInvalido``.
    """
    if vigente.valido_ate is not None:
        raise ErroDeConflito(
            "a memória já estava encerrada; use lembrar para registrar um fato novo"
        )
    if novo_fim <= vigente.valido_de:
        raise ErroDeArgumentoInvalido(
            "o novo limite precisa ser posterior ao valido_de da versão vigente"
        )


def vale_em(versao: VersaoDeMemoria, momento: Momento) -> bool:
    """A regra de cada modo em Python; o SQL de ``recuperar`` tem de concordar com ela.

    Intervalos semiabertos: ``[valido_de, valido_ate)`` e
    ``[registrado_em, substituido_em)``.
    """
    d = momento.instante
    valida = versao.valido_de <= d and (versao.valido_ate is None or versao.valido_ate > d)
    if momento.modo == "como_em":
        return versao.substituido_em is None and valida
    sabida = versao.registrado_em <= d and (
        versao.substituido_em is None or versao.substituido_em > d
    )
    return sabida and valida
