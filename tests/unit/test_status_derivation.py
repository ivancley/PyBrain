"""A tabela de status dos ADR 0001/0002, como exemplos executáveis de ``derivar_status``."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from memory_lifecycle import Status, VersaoDeMemoria, derivar_status

T0 = datetime(2026, 1, 1, tzinfo=UTC)
AGORA = T0 + timedelta(days=200)


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


def test_limites_abertos_sao_ativa():
    assert derivar_status(versao(), agora=AGORA) is Status.ATIVA


def test_valido_ate_fechado_no_passado_e_encerrada():
    fechada = versao(valido_ate=T0 + timedelta(days=10))
    assert derivar_status(fechada, agora=AGORA) is Status.ENCERRADA


def test_valido_ate_fechado_no_futuro_ainda_e_ativa():
    fechada = versao(valido_ate=AGORA + timedelta(days=1))
    assert derivar_status(fechada, agora=AGORA) is Status.ATIVA


def test_registro_aberto_com_um_fato_novo_depois_e_substituida():
    copia = versao(valido_ate=T0 + timedelta(days=150))
    nova = versao(versao_id="v2", valido_de=T0 + timedelta(days=150), versao_anterior_id="v1")
    assert derivar_status(copia, agora=AGORA, sucessora=nova) is Status.SUBSTITUIDA


def test_registro_fechado_e_sucessora_com_os_mesmos_limites_e_corrigida():
    errada = versao(substituido_em=T0 + timedelta(days=150))
    certa = versao(versao_id="v2", conteudo="y", versao_anterior_id="v1")
    assert derivar_status(errada, agora=AGORA, sucessora=certa) is Status.CORRIGIDA


def test_registro_fechado_e_sucessora_que_muda_a_validade_e_substituida():
    original = versao(substituido_em=T0 + timedelta(days=150))
    copia = versao(versao_id="v2", valido_ate=T0 + timedelta(days=150), versao_anterior_id="v1")
    assert derivar_status(original, agora=AGORA, sucessora=copia) is Status.SUBSTITUIDA


def test_registro_fechado_sem_sucessora_conhecida_e_substituida():
    antiga = versao(substituido_em=T0 + timedelta(days=150))
    assert derivar_status(antiga, agora=AGORA) is Status.SUBSTITUIDA
