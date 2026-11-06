# memory-lifecycle

Memória persistente, contextual e **bitemporal** para agentes de IA, embutida na
sua aplicação Python sobre PostgreSQL + pgvector. Sem framework, sem ORM, sem
provedor de LLM no núcleo.

> Status: 0.1.0 implementada e testada contra PostgreSQL 16 + pgvector, com
> psycopg 3, psycopg2, pool do psycopg, Django e SQLAlchemy. Ainda **não
> publicada** no PyPI: instale a partir do repositório. Vocabulário em
> `docs/glossario.md`; decisões em `docs/architecture.md` e `docs/adr/`.

## Exemplo

```python
import os

from memory_lifecycle import Memoria, ProvedorDeEmbeddingsFalso
from memory_lifecycle.connection.dsn import ProvedorDSN

memoria = Memoria(
    conexao=ProvedorDSN(os.environ["DATABASE_URL"]),
    embeddings=ProvedorDeEmbeddingsFalso(),  # troque pelo seu provedor de embeddings
    tenant_id="org-1",
)
memoria.migrar()  # schema próprio dentro do seu banco; idempotente

v1 = memoria.lembrar("agente-7", "Prefere respostas curtas", categoria="preferencia")
memoria.substituir("agente-7", v1.memoria_id, "Prefere respostas detalhadas")

agora = memoria.recuperar("agente-7", consulta="estilo de resposta", contextos=[None])
entao = memoria.recuperar("agente-7", como_em=v1.registrado_em)
sabido = memoria.recuperar("agente-7", sabido_em=v1.registrado_em)
print([r.versao.conteudo for r in agora])   # ['Prefere respostas detalhadas']
print([r.versao.conteudo for r in entao])   # ['Prefere respostas curtas']
print([r.versao.conteudo for r in sabido])  # ['Prefere respostas curtas']

memoria.esquecer("agente-7", tudo=True)  # apagamento físico de toda versão
```

## Conceitos

Toda memória tem **dois eixos de tempo**: quando o fato era verdade
(`valido_de`, `valido_ate`) e quando o sistema acreditava nele (`registrado_em`,
`substituido_em`). Uma linha nunca é reescrita: a única mudança possível é fechar
o seu tempo de registro.

| operação | quando usar | o que fica |
|---|---|---|
| `encerrar` | o fato era verdade e deixou de ser | a validade termina; o passado continua |
| `substituir` | um fato novo toma o lugar do antigo | o antigo até o instante da troca, o novo dali em diante |
| `corrigir` | o fato nunca foi verdade | o certo no lugar do errado; o errado só em `sabido_em` |
| `esquecer` | um pedido de privacidade | nada: toda versão do alvo é apagada |

`recuperar` responde em três modos: **agora**, **`como_em=D`** (o que era verdade
em D, pelo que sabemos hoje) e **`sabido_em=D`** (o que, em D, sabíamos ser
verdade em D — o que o agente sabia quando respondeu).

O **escopo é da aplicação e é estrito**: `contextos` e `entidades` listam os ids
ativos na consulta, e `None` na lista inclui as memórias sem contexto ou sem
entidade. Tirar um id do escopo não apaga nada. O escopo também é o que mantém a
busca vetorial barata em donos com muitas memórias (ADR 0009).

## Conexão

A biblioteca nunca abre um segundo pool: ela recebe um provedor de conexão.

| provedor | extra | modo de transação |
|---|---|---|
| `ProvedorDSN(dsn)` | `psycopg` | própria: commit por operação |
| `ProvedorPoolPsycopg(pool)` | `psycopg` | própria, com uma conexão do pool do app |
| `ProvedorDjango(alias)` | `django` | participar: a escrita entra no `atomic()` do request (fora de um, faz commit sozinha) |
| `ProvedorSQLAlchemy(engine)` | `sqlalchemy` | própria |
| `ProvedorSQLAlchemy.de_sessao(sessao)` | `sqlalchemy` | participar: um savepoint por operação; vale no `sessao.commit()` |

`carregar_provedor()` lê `MEMORY_LIFECYCLE_PROVEDOR_CONEXAO` (`pacote.modulo:funcao`)
quando o app prefere configurar por ambiente. O núcleo não tem dependência
obrigatória; cada adaptador importa a sua sob demanda.

## Desenvolvimento

Veja `docs/development-workflow.md`. Versão curta:

```bash
make install && make hooks && make db-up && cp .env.example .env
make quality
```
