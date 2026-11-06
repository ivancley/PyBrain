"""O ciclo de uma conversa com memória: recuperar, montar contexto, responder, gravar.

A biblioteca não chama LLM nenhum: quem responde é o agente da aplicação, e quem
decide o que vira memória é a aplicação. Aqui o "agente" é uma função de mentira
(``responder``), para o exemplo rodar sem rede; troque-a pela chamada ao seu
modelo. Rode com ``DATABASE_URL`` apontando para um PostgreSQL com pgvector::

    DATABASE_URL=postgresql://... python -m exemplos.fluxo_do_agente
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass

from memory_lifecycle import Memoria, ProvedorDeEmbeddingsFalso, ResultadoDeRecuperacao
from memory_lifecycle.connection.dsn import ProvedorDSN


@dataclass(frozen=True)
class Proposta:
    """Uma memória que o agente sugere gravar; a aplicação decide se grava."""

    categoria: str
    conteudo: str


def montar_contexto(resultados: Sequence[ResultadoDeRecuperacao]) -> str:
    """O texto que vai no prompt do agente: uma linha por memória, com a categoria."""
    if not resultados:
        return "(nenhuma memória relevante)"
    return "\n".join(f"- [{r.versao.categoria}] {r.versao.conteudo}" for r in resultados)


def responder(pergunta: str, contexto: str) -> tuple[str, list[Proposta]]:
    """O agente de mentira: responde citando o contexto e propõe memórias.

    Num agente real, o contexto entra no prompt, e as propostas saem de uma
    ferramenta ou de uma extração feita pelo próprio modelo.
    """
    propostas = []
    if pergunta.lower().startswith("prefiro "):
        propostas.append(Proposta("preferencia:estilo", pergunta))
    return f"Respondendo a {pergunta!r} com o que eu sei:\n{contexto}", propostas


def gravar(memoria: Memoria, dono_id: str, proposta: Proposta, contexto_id: str | None) -> None:
    """A política da aplicação: uma preferência por categoria; a nova substitui a antiga."""
    atuais = memoria.recuperar(dono_id, categoria=proposta.categoria, limite=1)
    if atuais:
        memoria.substituir(dono_id, atuais[0].versao.memoria_id, proposta.conteudo)
    else:
        memoria.lembrar(
            dono_id, proposta.conteudo, categoria=proposta.categoria, contexto_id=contexto_id
        )


def conversar(memoria: Memoria, dono_id: str, projeto_id: str, pergunta: str) -> str:
    """Um turno: o escopo é o projeto ativo mais o que vale em todo lugar (``None``)."""
    resultados = memoria.recuperar(
        dono_id, consulta=pergunta, contextos=[projeto_id, None], limite=10
    )
    resposta, propostas = responder(pergunta, montar_contexto(resultados))
    for proposta in propostas:
        gravar(memoria, dono_id, proposta, contexto_id=None)  # preferência vale em todo projeto
    return resposta


def main(dsn: str | None = None, schema: str = "exemplo_agente") -> list[str]:
    """Três turnos de uma conversa; devolve as respostas e as imprime."""
    memoria = Memoria(
        conexao=ProvedorDSN(dsn or os.environ["DATABASE_URL"]),
        embeddings=ProvedorDeEmbeddingsFalso(),  # troque pelo seu provedor de embeddings
        tenant_id="org-1",
        schema=schema,
    )
    memoria.migrar()
    memoria.lembrar(
        "usuario-42", "O projeto usa Python 3.12", categoria="fato", contexto_id="projeto-x"
    )

    respostas = [
        conversar(memoria, "usuario-42", "projeto-x", "prefiro respostas curtas"),
        conversar(memoria, "usuario-42", "projeto-x", "prefiro respostas com exemplos"),
        conversar(memoria, "usuario-42", "projeto-x", "como devo escrever o teste?"),
    ]
    for resposta in respostas:
        print(resposta, end="\n\n")
    return respostas


if __name__ == "__main__":
    main()
