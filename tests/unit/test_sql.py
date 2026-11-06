"""``_sql``: identificadores, vetores como texto e tradução de erros dos dois drivers."""

from __future__ import annotations

import pytest

from memory_lifecycle import ErroDeConfiguracao, ErroDeConflito, ErroDeDimensaoDeEmbedding
from memory_lifecycle._sql import (
    citar,
    e_uuid,
    sqlstate,
    traduzir,
    validar_schema,
    vetor_como_texto,
)


class ErroDoPsycopg3(Exception):
    def __init__(self, codigo: str, mensagem: str = "erro") -> None:
        super().__init__(mensagem)
        self.sqlstate = codigo


class ErroDoPsycopg2(Exception):
    def __init__(self, codigo: str, mensagem: str = "erro") -> None:
        super().__init__(mensagem)
        self.pgcode = codigo


@pytest.mark.parametrize("nome", ["x; drop table y", "Maiuscula", "1comeca", "", "a" * 64, 'a"b'])
def test_schema_invalido_e_recusado(nome: str):
    with pytest.raises(ErroDeConfiguracao):
        validar_schema(nome)


def test_citar_qualifica_e_cita():
    assert (
        citar("memory_lifecycle", "versoes_de_memoria") == '"memory_lifecycle"."versoes_de_memoria"'
    )


def test_vetor_vai_como_texto_sem_perder_precisao():
    valores = [0.1, -1 / 3, 1e-300, 123456.789]
    texto = vetor_como_texto(valores)
    assert texto.startswith("[") and texto.endswith("]")
    assert [float(parte) for parte in texto[1:-1].split(",")] == valores


def test_sqlstate_dos_dois_drivers():
    assert sqlstate(ErroDoPsycopg3("23505")) == "23505"
    assert sqlstate(ErroDoPsycopg2("42P01")) == "42P01"
    assert sqlstate(ValueError("sem código")) is None


def test_traducoes_conhecidas():
    # Regressão (reports/review-change-core.md): REPEATABLE READ subia 40001 cru.
    assert isinstance(traduzir(ErroDoPsycopg3("40001")), ErroDeConflito)
    assert isinstance(traduzir(ErroDoPsycopg2("40P01")), ErroDeConflito)
    assert isinstance(traduzir(ErroDoPsycopg2("42P01")), ErroDeConfiguracao)
    assert isinstance(traduzir(ErroDoPsycopg3("3F000")), ErroDeConfiguracao)
    dimensao = ErroDoPsycopg3("22000", "expected 8 dimensions, not 16")
    assert isinstance(traduzir(dimensao), ErroDeDimensaoDeEmbedding)


def test_erro_sem_consequencia_conhecida_nao_e_traduzido():
    assert traduzir(ErroDoPsycopg3("22000", "outro problema")) is None
    assert traduzir(ErroDoPsycopg3("57014")) is None  # consulta cancelada: sobe como veio
    assert traduzir(RuntimeError("não é de banco")) is None


def test_e_uuid():
    assert e_uuid("00000000-0000-0000-0000-000000000000")
    assert not e_uuid("nunca-existiu")
    assert not e_uuid("")


@pytest.mark.parametrize(
    "texto",
    [
        "urn:uuid:00000000-0000-0000-0000-000000000000",
        "{00000000-0000-0000-0000-000000000000}",
        "0000-0000-0000-0000-0000-0000-0000-0000",
        "00000000000000000000000000000000",
    ],
)
def test_e_uuid_recusa_o_que_o_postgres_recusaria_ou_nao_e_canonico(texto: str):
    # Regressão (reports/silent-failure-fatia-10.md, achado 1): o uuid.UUID do Python
    # aceitava formas que o `::uuid` do Postgres rejeita, abortando a transação do app.
    assert not e_uuid(texto)


class Diag:
    def __init__(self, restricao: str | None) -> None:
        self.constraint_name = restricao


def test_unique_violation_so_vira_conflito_no_indice_da_vigente():
    # Regressão (achado 8): todo 23505 virava "outra escrita gravou esta versão primeiro".
    da_vigente = ErroDoPsycopg3("23505")
    da_vigente.diag = Diag("ux_versoes_vigente")  # type: ignore[attr-defined]
    outra = ErroDoPsycopg3("23505")
    outra.diag = Diag("versao_do_schema_pkey")  # type: ignore[attr-defined]
    assert isinstance(traduzir(da_vigente), ErroDeConflito)
    assert traduzir(outra) is None
