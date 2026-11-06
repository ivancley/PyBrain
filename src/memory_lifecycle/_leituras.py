"""As leituras de ``Memoria``: ``recuperar`` e ``historico``.

Separadas de ``api.py`` só pelo tamanho (CLAUDE.md, Tamanho de arquivo); quem
usa a biblioteca chama ``Memoria.recuperar`` e ``Memoria.historico``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from memory_lifecycle import retrieval, temporal
from memory_lifecycle._nucleo import LIMITE_PADRAO_RECUPERACAO, Nucleo
from memory_lifecycle._sql import (
    e_uuid,
)
from memory_lifecycle.connection._unidade import unidade_de_trabalho
from memory_lifecycle.exceptions import (
    ErroDeArgumentoInvalido,
    ErroNaoEncontrado,
)
from memory_lifecycle.model import ResultadoDeRecuperacao, VersaoDeMemoria


class Leituras(Nucleo):
    """``recuperar`` e ``historico``, sobre o núcleo da ``Memoria``."""

    def recuperar(
        self,
        dono_id: str,
        *,
        consulta: str | None = None,
        contextos: Sequence[str | None] | None = None,
        entidades: Sequence[str | None] | None = None,
        categoria: str | None = None,
        limite: int = LIMITE_PADRAO_RECUPERACAO,
        como_em: datetime | None = None,
        sabido_em: datetime | None = None,
    ) -> list[ResultadoDeRecuperacao]:
        """Devolve as memórias do dono que cabem no escopo e no momento pedidos.

        **Escopo** é da aplicação, e é estrito: ``contextos`` e ``entidades`` são
        os ids ativos nesta consulta. Uma versão é devolvida só se o seu
        ``contexto_id`` está em ``contextos``; ``None`` como membro da lista
        inclui as versões sem contexto (``contextos=["p-2027", None]``).
        ``contextos=None`` significa "não filtrar por este eixo"; ``[]`` não
        devolve nada neste eixo. Mesma regra para entidades. Deixar um id fora do
        escopo não é uma escrita: a memória fica.

        **Momento** escolhe um de três modos: nenhum argumento é "o que é verdade
        agora"; ``como_em`` é "o que era verdade naquele instante, pelo que sabemos
        hoje"; ``sabido_em`` é "o que, naquele instante, o sistema sabia ser verdade
        naquele instante" — o que o agente sabia quando respondeu. Os dois juntos
        levantam ``ErroDeArgumentoInvalido``.

        Com ``consulta`` os resultados vêm ordenados por similaridade e carregam
        ``pontuacao``; sem ela, por ``registrado_em`` decrescente com
        ``pontuacao=None``. ``limite`` deve ser positivo. O embedding da consulta
        é calculado antes de obter uma conexão. A busca vetorial é exata e lê o
        vetor de cada versão que passa nos filtros (ADR 0009): passe o escopo para
        donos com muitas memórias.
        """
        if isinstance(limite, bool) or not isinstance(limite, int) or limite < 1:
            raise ErroDeArgumentoInvalido("limite precisa ser um inteiro positivo")
        momento = temporal.resolver_momento(
            temporal.resolver_agora(self.relogio), como_em, sabido_em
        )
        eixo_contextos = retrieval.montar_eixo(contextos)
        eixo_entidades = retrieval.montar_eixo(entidades)
        if consulta is not None:
            temporal.exigir_texto("consulta", consulta)
        f = self._filtro(dono_id)
        vetor_consulta = self._vetor(consulta) if consulta is not None else None
        with unidade_de_trabalho(self.conexao) as cur:
            self._preparar(cur, com_vetor=vetor_consulta is not None)
            return retrieval.recuperar(
                cur,
                f,
                momento,
                vetor_consulta=vetor_consulta,
                contextos=eixo_contextos,
                entidades=eixo_entidades,
                categoria=categoria,
                limite=limite,
            )

    def historico(self, dono_id: str, memoria_id: str) -> list[VersaoDeMemoria]:
        """Devolve toda versão de uma memória, por ``registrado_em`` e depois ``valido_de``.

        Inclui as versões de registro fechado e as cópias limitadas que ``encerrar``
        e ``substituir`` inserem. A sucessora de uma versão é a que tem
        ``versao_anterior_id`` igual ao seu ``versao_id``; passe-a a
        ``derivar_status`` para rotular. Levanta ``ErroNaoEncontrado`` quando não
        existe versão para este tenant e dono.
        """
        f = self._filtro(dono_id)
        if not e_uuid(memoria_id):
            raise ErroNaoEncontrado("memória não encontrada para este tenant e dono")
        with unidade_de_trabalho(self.conexao) as cur:
            self._preparar(cur, com_vetor=False)
            return retrieval.historico(cur, f, memoria_id)
