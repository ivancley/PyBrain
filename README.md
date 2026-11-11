# memory-lifecycle

Memória persistente, contextual e **bitemporal** para agentes de IA, embutida na
sua aplicação Python sobre PostgreSQL + pgvector. Sem framework, sem ORM, sem
provedor de LLM no núcleo.

> Status: 0.1.0 implementada e testada contra PostgreSQL 16 + pgvector, com
> psycopg 3, psycopg2, pool do psycopg, Django e SQLAlchemy. Ainda **não
> publicada** no PyPI: instale a partir do repositório. Vocabulário em
> `docs/glossario.md` (os identificadores do código são em inglês; a prosa, em
> português); decisões em `docs/architecture.md` e `docs/adr/`.

## Exemplo

```python
import os

from memory_lifecycle import FakeEmbeddingProvider, Memory
from memory_lifecycle.connection.dsn import DSNProvider

memory = Memory(
    connection=DSNProvider(os.environ["DATABASE_URL"]),
    embeddings=FakeEmbeddingProvider(),  # troque pelo seu provedor de embeddings
    tenant_id="org-1",
)
memory.migrate()  # schema próprio dentro do seu banco; idempotente

v1 = memory.remember("agent-7", "Prefere respostas curtas", kind="preference")
memory.supersede("agent-7", v1.memory_id, "Prefere respostas detalhadas")

now = memory.recall("agent-7", query="estilo de resposta", contexts=[None])
then = memory.recall("agent-7", as_of=v1.recorded_at)
known = memory.recall("agent-7", known_at=v1.recorded_at)
print([r.version.content for r in now])    # ['Prefere respostas detalhadas']
print([r.version.content for r in then])   # ['Prefere respostas curtas']
print([r.version.content for r in known])  # ['Prefere respostas curtas']

memory.forget("agent-7", everything=True)  # apagamento físico de toda versão
```

## Conceitos

Toda memória tem **dois eixos de tempo**: quando o fato era verdade
(`valid_from`, `valid_to`) e quando o sistema acreditava nele (`recorded_at`,
`superseded_at`). Uma linha nunca é reescrita: a única mudança possível é fechar
o seu tempo de registro.

| operação | quando usar | o que fica |
|---|---|---|
| `expire` | o fato era verdade e deixou de ser | a validade termina; o passado continua |
| `supersede` | um fato novo toma o lugar do antigo | o antigo até o instante da troca, o novo dali em diante |
| `correct` | o fato nunca foi verdade | o certo no lugar do errado; o errado só em `known_at` |
| `forget` | um pedido de privacidade | nada: toda versão do alvo é apagada |

`recall` responde em três modos: **agora**, **`as_of=D`** (o que era verdade
em D, pelo que sabemos hoje) e **`known_at=D`** (o que, em D, sabíamos ser
verdade em D — o que o agente sabia quando respondeu).

O **escopo é da aplicação e é estrito**: `contexts` e `entities` listam os ids
ativos na consulta, e `None` na lista inclui as memórias sem contexto ou sem
entidade. Tirar um id do escopo não apaga nada. O escopo também é o que mantém a
busca vetorial barata em donos com muitas memórias (ADR 0009).

## Conexão

A biblioteca nunca abre um segundo pool: ela recebe um provedor de conexão.

| provedor | extra | modo de transação |
|---|---|---|
| `DSNProvider(dsn)` | `psycopg` | própria (`OWN`): commit por operação |
| `PsycopgPoolProvider(pool)` | `psycopg` | própria (`OWN`), com uma conexão do pool do app |
| `DjangoProvider(alias)` | `django` | participar (`PARTICIPATE`): a escrita entra no `atomic()` do request (fora de um, faz commit sozinha) |
| `SQLAlchemyProvider(engine)` | `sqlalchemy` | própria (`OWN`) |
| `SQLAlchemyProvider.from_session(session)` | `sqlalchemy` | participar (`PARTICIPATE`): um savepoint por operação; vale no `session.commit()` |

`load_provider()` lê `MEMORY_LIFECYCLE_CONNECTION_PROVIDER` (`pacote.modulo:funcao`)
quando o app prefere configurar por ambiente. O núcleo não tem dependência
obrigatória; cada adaptador importa a sua sob demanda.

## Documentação

- `docs/conceitos.md` — os dois eixos de tempo, as três operações, os três modos
  de consulta, o escopo, o status e os erros. Os trechos rodam na suíte.
- `docs/integracao.md` — instalação, cada provedor de conexão (com Django do
  começo ao fim), o seu provedor de embeddings, desempenho e testes.
- `examples/agent_flow.py` — recuperar, montar o contexto, responder e gravar
  o que o agente propôs; `examples/django_app/` — o mesmo fluxo numa view Django.
- `docs/architecture.md` e `docs/adr/` — as decisões e as alternativas que perderam.

## Desenvolvimento

Veja `docs/development-workflow.md`. Versão curta:

```bash
make install && make hooks && make db-up && cp .env.example .env
make quality
```
