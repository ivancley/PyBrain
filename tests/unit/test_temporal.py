"""As regras puras de tempo (ADR 0002), sem banco."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from memory_lifecycle import ErroDeArgumentoInvalido, ErroDeConflito, VersaoDeMemoria
from memory_lifecycle.temporal import (
    Momento,
    exigir_fechamento_de_validade,
    exigir_fuso,
    exigir_intervalo,
    exigir_texto,
    resolver_agora,
    resolver_momento,
    vale_em,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
DIA = timedelta(days=1)


def versao(**sobrescritas: object) -> VersaoDeMemoria:
    base = VersaoDeMemoria(
        versao_id="v1",
        memoria_id="m1",
        tenant_id="t",
        dono_id="d",
        categoria="nota",
        conteudo="x",
        entidade_id=None,
        contexto_id=None,
        origem=None,
        modelo_embedding="falso",
        valido_de=T0,
        valido_ate=None,
        registrado_em=T0,
        substituido_em=None,
        versao_anterior_id=None,
    )
    return replace(base, **sobrescritas)  # type: ignore[arg-type]


def test_datetime_sem_fuso_e_recusado():
    with pytest.raises(ErroDeArgumentoInvalido, match="fuso"):
        exigir_fuso("valido_de", datetime(2026, 1, 1))
    exigir_fuso("valido_de", None)
    exigir_fuso("valido_de", T0)


def test_relogio_sem_fuso_e_recusado():
    with pytest.raises(ErroDeArgumentoInvalido):
        resolver_agora(lambda: datetime(2026, 1, 1))
    assert resolver_agora(lambda: T0) == T0
    assert resolver_agora(None).tzinfo is not None


@pytest.mark.parametrize("vazio", ["", "   ", "\n"])
def test_texto_vazio_e_recusado(vazio: str):
    with pytest.raises(ErroDeArgumentoInvalido, match="conteudo"):
        exigir_texto("conteudo", vazio)


def test_como_em_e_sabido_em_juntos_sao_recusados():
    with pytest.raises(ErroDeArgumentoInvalido):
        resolver_momento(T0, T0, T0)


def test_sem_instante_e_como_em_agora():
    assert resolver_momento(T0, None, None) == Momento("como_em", T0)
    assert resolver_momento(T0, T0 - DIA, None) == Momento("como_em", T0 - DIA)
    assert resolver_momento(T0, None, T0 - DIA) == Momento("sabido_em", T0 - DIA)


def test_intervalo_vazio_ou_invertido_e_recusado():
    with pytest.raises(ErroDeArgumentoInvalido):
        exigir_intervalo(T0, T0)
    with pytest.raises(ErroDeArgumentoInvalido):
        exigir_intervalo(T0, T0 - DIA)
    exigir_intervalo(T0, None)
    exigir_intervalo(T0, T0 + DIA)


def test_encerrar_vigente_ja_encerrada_conflita():
    with pytest.raises(ErroDeConflito, match="lembrar"):
        exigir_fechamento_de_validade(versao(valido_ate=T0 + DIA), T0 + 2 * DIA)


def test_fim_no_inicio_ou_antes_e_argumento_invalido():
    with pytest.raises(ErroDeArgumentoInvalido):
        exigir_fechamento_de_validade(versao(), T0)


def test_intervalos_de_validade_sao_semiabertos():
    v = versao(valido_ate=T0 + DIA)
    assert vale_em(v, Momento("como_em", T0))
    assert not vale_em(v, Momento("como_em", T0 + DIA))
    assert not vale_em(v, Momento("como_em", T0 - DIA))


def test_como_em_so_le_o_registro_aberto():
    assert not vale_em(versao(substituido_em=T0 + DIA), Momento("como_em", T0))


def test_sabido_em_le_o_registro_da_epoca_e_a_validade_em_d():
    v = versao(registrado_em=T0 + DIA, substituido_em=T0 + 3 * DIA, valido_ate=T0 + 2 * DIA)
    assert not vale_em(v, Momento("sabido_em", T0))  # ainda não registrada
    assert vale_em(v, Momento("sabido_em", T0 + DIA))  # registrada e válida
    assert not vale_em(v, Momento("sabido_em", T0 + 2 * DIA))  # sabida, mas não válida em D
    assert not vale_em(v, Momento("sabido_em", T0 + 3 * DIA))  # registro já fechado
