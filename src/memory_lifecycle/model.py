"""O registro de versão e seu status derivado.

Uma memória é um ``memoria_id`` com muitas versões imutáveis. Uma versão carrega
o conteúdo, os ids que a localizam e os dois eixos de tempo. Nada aqui toca o
banco; é a forma que todos os outros módulos trocam entre si.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Status(StrEnum):
    """O que uma versão é, lido dos seus limites de tempo e da sucessora; nunca armazenado."""

    ATIVA = "ativa"
    ENCERRADA = "encerrada"
    SUBSTITUIDA = "substituida"
    CORRIGIDA = "corrigida"


@dataclass(frozen=True, slots=True)
class VersaoDeMemoria:
    """Uma linha do histórico: o conteúdo, quando era verdade e quando acreditamos nele.

    ``None`` em ``valido_ate`` ou ``substituido_em`` significa *aberto*, nunca
    desconhecido. Todo ``datetime`` tem fuso. ``entidade_id`` e ``contexto_id``
    são opacos: a aplicação dá o significado. Depois de escrita, a única coisa
    que muda na linha é ``substituido_em`` fechar. ``versao_anterior_id`` aponta
    para a versão cujo registro a operação que criou esta fechou (ADR 0002).
    """

    versao_id: str
    memoria_id: str
    tenant_id: str
    dono_id: str
    categoria: str
    conteudo: str
    entidade_id: str | None
    contexto_id: str | None
    origem: str | None
    modelo_embedding: str | None
    valido_de: datetime
    valido_ate: datetime | None
    registrado_em: datetime
    substituido_em: datetime | None
    versao_anterior_id: str | None


@dataclass(frozen=True, slots=True)
class ResultadoDeRecuperacao:
    """Um resultado de ``recuperar``: a versão e quão parecida ela é com a consulta.

    ``pontuacao`` está em ``[0, 1]``, maior é mais próximo, e é ``None`` quando a
    recuperação não teve ``consulta`` (só filtros estruturados).
    """

    versao: VersaoDeMemoria
    pontuacao: float | None


def derivar_status(
    versao: VersaoDeMemoria,
    *,
    agora: datetime,
    sucessora: VersaoDeMemoria | None = None,
) -> Status:
    """Deriva o status de uma versão em ``agora``; o único lugar que faz isso.

    - ``CORRIGIDA``: registro fechado e a sucessora tem os mesmos ``valido_de`` e
      ``valido_ate`` (o mundo não mudou; o registro estava errado).
    - ``SUBSTITUIDA``: registro fechado e a sucessora muda a validade (``encerrar``
      ou ``substituir``), ou registro aberto com sucessora (um fato novo veio depois).
    - ``ENCERRADA``: registro aberto, sem sucessora, ``valido_ate`` em ou antes de ``agora``.
    - ``ATIVA``: registro aberto, sem sucessora, não encerrada em ``agora``
      (inclui a que ainda vai começar).

    ``sucessora`` é a versão cujo ``versao_anterior_id`` é esta, quando quem chama
    a tem (está em ``historico``). Registro fechado sem sucessora conhecida deriva
    como ``SUBSTITUIDA``.
    """
    if versao.substituido_em is not None:
        mesma_validade = sucessora is not None and (
            (sucessora.valido_de, sucessora.valido_ate) == (versao.valido_de, versao.valido_ate)
        )
        return Status.CORRIGIDA if mesma_validade else Status.SUBSTITUIDA
    if sucessora is not None:
        return Status.SUBSTITUIDA
    if versao.valido_ate is not None and versao.valido_ate <= agora:
        return Status.ENCERRADA
    return Status.ATIVA
