"""O núcleo de ``Memoria``: construção e os passos comuns a toda operação.

Separado de ``api.py`` só pelo tamanho (CLAUDE.md, Tamanho de arquivo): aqui fica
o que nenhum usuário chama — o filtro de tenant e dono, a conferência do schema,
o embedding antes da conexão, a vigente de uma memória e o esqueleto de
``substituir`` e ``corrigir``. A superfície pública é ``api.Memoria``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from memory_lifecycle import migrations, store, temporal
from memory_lifecycle._sql import (
    Filtro,
    citar,
    e_uuid,
    normalizar_uuid,
    validar_schema,
    vetor_como_texto,
)
from memory_lifecycle.connection import Cursor, ProvedorDeConexao
from memory_lifecycle.connection._unidade import unidade_de_trabalho
from memory_lifecycle.embeddings import ProvedorDeEmbeddings, vetorizar
from memory_lifecycle.exceptions import (
    ErroDeArgumentoInvalido,
    ErroDeConflito,
    ErroDeDimensaoDeEmbedding,
    ErroNaoEncontrado,
)
from memory_lifecycle.model import VersaoDeMemoria

#: O schema PostgreSQL em que a biblioteca mantém suas tabelas, dentro do banco do app.
SCHEMA_PADRAO = "memory_lifecycle"

#: ``recuperar`` sempre tem limite; este é o usado quando quem chama não dá nenhum.
LIMITE_PADRAO_RECUPERACAO = 20


@dataclass(frozen=True, slots=True)
class Mudanca:
    """O que ``substituir`` e ``corrigir`` trazem; ``None`` herda da versão vigente."""

    conteudo: str
    categoria: str | None
    entidade_id: str | None
    contexto_id: str | None
    origem: str | None


def _ou(novo: str | None, herdado: str | None) -> str | None:
    return novo if novo is not None else herdado


class Nucleo:
    """A base de ``Memoria``: estado da instância e passos internos das operações."""

    def __init__(
        self,
        *,
        conexao: ProvedorDeConexao,
        embeddings: ProvedorDeEmbeddings,
        tenant_id: str,
        schema: str = SCHEMA_PADRAO,
        relogio: Callable[[], datetime] | None = None,
    ) -> None:
        temporal.exigir_texto("tenant_id", tenant_id)
        self.conexao = conexao
        self.embeddings = embeddings
        self.tenant_id = tenant_id
        self.schema = validar_schema(schema)
        self.relogio = relogio
        self._tabela = citar(self.schema, "versoes_de_memoria")
        self._dimensao_registrada: int | None = None

    def _filtro(self, dono_id: str) -> Filtro:
        """Tenant e dono da operação; ``dono_id`` inválido é recusado antes da conexão."""
        temporal.exigir_texto("dono_id", dono_id)
        return Filtro(tabela=self._tabela, tenant_id=self.tenant_id, dono_id=dono_id)

    def _preparar(self, cur: Cursor, *, com_vetor: bool) -> None:
        """Primeira instrução de toda operação: confere o schema e, com vetor, a dimensão.

        Lê ``configuracao`` uma vez por instância, via ``to_regclass``: um schema
        não migrado vira ``ErroDeConfiguracao`` sem nenhuma instrução falhar, o que
        no modo ``PARTICIPAR`` abortaria a transação do app.
        """
        if self._dimensao_registrada is None:
            self._dimensao_registrada = migrations.ler_dimensao(cur, self.schema)
        if com_vetor and self._dimensao_registrada != self.embeddings.dimensao:
            raise ErroDeDimensaoDeEmbedding(
                f"o schema {self.schema!r} guarda vetores de {self._dimensao_registrada} "
                f"dimensões; o provedor de embeddings gera {self.embeddings.dimensao}"
            )

    def _vetor(self, texto: str) -> str:
        """Embedding do texto, como literal do pgvector; sempre antes da conexão."""
        [vetor] = vetorizar(self.embeddings, [texto])
        return vetor_como_texto(vetor)

    @staticmethod
    def _vigente(
        cur: Cursor, f: Filtro, memoria_id: str, versao_esperada_id: str | None
    ) -> VersaoDeMemoria:
        """A vigente da memória; um id inválido não vai ao banco (ver ``e_uuid``)."""
        if not e_uuid(memoria_id):
            raise ErroNaoEncontrado("memória não encontrada para este tenant e dono")
        if versao_esperada_id is not None and not e_uuid(versao_esperada_id):
            raise ErroDeArgumentoInvalido("versao_esperada_id precisa ser um uuid")
        vigente = store.buscar_vigente(cur, f, memoria_id)
        if versao_esperada_id is not None and vigente.versao_id != normalizar_uuid(
            versao_esperada_id
        ):
            raise ErroDeConflito(
                "a versão vigente não é mais a esperada; releia com historico e decida"
            )
        return vigente

    def _reescrever(
        self,
        dono_id: str,
        memoria_id: str,
        mudanca: Mudanca,
        *,
        versao_esperada_id: str | None,
        corrigir: bool,
        valido_de: datetime | None,
    ) -> VersaoDeMemoria:
        """O esqueleto de ``substituir`` (com cópia limitada) e ``corrigir`` (sem ela).

        Na correção, a versão nova herda os limites da vigente e aponta para ela. Na
        substituição, a vigente ganha a cópia limitada até ``valido_de`` (o agora,
        por padrão) e a nova começa ali, apontando para a cópia (ADR 0002).
        """
        temporal.exigir_texto("conteudo", mudanca.conteudo)
        if mudanca.categoria is not None:
            temporal.exigir_texto("categoria", mudanca.categoria)
        agora = temporal.resolver_agora(self.relogio)
        f = self._filtro(dono_id)
        vetor = self._vetor(mudanca.conteudo)
        with unidade_de_trabalho(self.conexao) as cur:
            self._preparar(cur, com_vetor=True)
            vigente = self._vigente(cur, f, memoria_id, versao_esperada_id)
            if corrigir:
                inicio, fim, anterior_id = vigente.valido_de, vigente.valido_ate, vigente.versao_id
                store.fechar_registro(cur, f, vigente.versao_id, agora)
            else:
                inicio, fim = (valido_de if valido_de is not None else agora), None
                temporal.exigir_fechamento_de_validade(vigente, inicio)
                store.fechar_registro(cur, f, vigente.versao_id, agora)
                copia = store.inserir_copia_limitada(cur, f, vigente.versao_id, inicio, agora)
                anterior_id = copia.versao_id
            return store.inserir(
                cur,
                f,
                memoria_id=vigente.memoria_id,
                conteudo=mudanca.conteudo,
                categoria=mudanca.categoria or vigente.categoria,
                entidade_id=_ou(mudanca.entidade_id, vigente.entidade_id),
                contexto_id=_ou(mudanca.contexto_id, vigente.contexto_id),
                origem=_ou(mudanca.origem, vigente.origem),
                vetor=vetor,
                modelo=self.embeddings.nome_do_modelo,
                valido_de=inicio,
                valido_ate=fim,
                registrado_em=agora,
                versao_anterior_id=anterior_id,
            )
