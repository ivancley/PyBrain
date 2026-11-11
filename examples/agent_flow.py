"""One turn of a conversation with memory: recall, build the context, answer, save.

The library calls no LLM: the application's agent answers, and the application
decides what becomes memory. Here the "agent" is a fake function (``respond``), so
the example runs without network; swap it for the call to your model. Run it with
``DATABASE_URL`` pointing at a PostgreSQL with pgvector::

    DATABASE_URL=postgresql://... python -m examples.agent_flow

PT: O ciclo de uma conversa com memória: recuperar, montar contexto, responder, gravar.

A biblioteca não chama LLM nenhum: quem responde é o agente da aplicação, e quem
decide o que vira memória é a aplicação. Aqui o "agente" é uma função de mentira
(``respond``), para o exemplo rodar sem rede; troque-a pela chamada ao seu
modelo. Rode com ``DATABASE_URL`` apontando para um PostgreSQL com pgvector::

    DATABASE_URL=postgresql://... python -m examples.agent_flow
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass

from memory_lifecycle import FakeEmbeddingProvider, Memory, RecallResult
from memory_lifecycle.connection.dsn import DSNProvider


@dataclass(frozen=True)
class Proposal:
    """A memory the agent suggests saving; the application decides whether to save it.

    PT: Uma memória que o agente sugere gravar; a aplicação decide se grava.
    """

    kind: str
    content: str


def build_context(results: Sequence[RecallResult]) -> str:
    """The text that goes into the agent's prompt: one line per memory, with its kind.

    PT: O texto que vai no prompt do agente: uma linha por memória, com a categoria.
    """
    if not results:
        return "(nenhuma memória relevante)"
    return "\n".join(f"- [{r.version.kind}] {r.version.content}" for r in results)


def respond(question: str, context: str) -> tuple[str, list[Proposal]]:
    """The fake agent: answers quoting the context and proposes memories.

    In a real agent, the context goes into the prompt, and the proposals come from
    a tool or from an extraction done by the model itself.

    PT: O agente de mentira: responde citando o contexto e propõe memórias.

    Num agente real, o contexto entra no prompt, e as propostas saem de uma
    ferramenta ou de uma extração feita pelo próprio modelo.
    """
    proposals = []
    if question.lower().startswith("prefiro "):
        proposals.append(Proposal("preferencia:estilo", question))
    return f"Respondendo a {question!r} com o que eu sei:\n{context}", proposals


def save(memory: Memory, owner_id: str, proposal: Proposal, context_id: str | None) -> None:
    """The application's policy: one preference per kind; the new one supersedes the old.

    PT: A política da aplicação: uma preferência por categoria; a nova substitui a antiga.
    """
    current = memory.recall(owner_id, kind=proposal.kind, limit=1)
    if current:
        memory.supersede(owner_id, current[0].version.memory_id, proposal.content)
    else:
        memory.remember(owner_id, proposal.content, kind=proposal.kind, context_id=context_id)


def converse(memory: Memory, owner_id: str, project_id: str, question: str) -> str:
    """One turn: the scope is the active project plus what holds everywhere (``None``).

    PT: Um turno: o escopo é o projeto ativo mais o que vale em todo lugar (``None``).
    """
    results = memory.recall(owner_id, query=question, contexts=[project_id, None], limit=10)
    answer, proposals = respond(question, build_context(results))
    for proposal in proposals:
        # A preference holds in every project.
        # PT: Preferência vale em todo projeto.
        save(memory, owner_id, proposal, context_id=None)
    return answer


def main(dsn: str | None = None, schema: str = "example_agent") -> list[str]:
    """Three turns of a conversation; returns the answers and prints them.

    PT: Três turnos de uma conversa; devolve as respostas e as imprime.
    """
    memory = Memory(
        connection=DSNProvider(dsn or os.environ["DATABASE_URL"]),
        # Swap for your embedding provider.
        # PT: Troque pelo seu provedor de embeddings.
        embeddings=FakeEmbeddingProvider(),
        tenant_id="org-1",
        schema=schema,
    )
    memory.migrate()
    memory.remember("usuario-42", "O projeto usa Python 3.12", kind="fato", context_id="projeto-x")

    answers = [
        converse(memory, "usuario-42", "projeto-x", "prefiro respostas curtas"),
        converse(memory, "usuario-42", "projeto-x", "prefiro respostas com exemplos"),
        converse(memory, "usuario-42", "projeto-x", "como devo escrever o teste?"),
    ]
    for answer in answers:
        print(answer, end="\n\n")
    return answers


if __name__ == "__main__":
    main()
