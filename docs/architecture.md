# Arquitetura — as decisões da Etapa 1 em uma página

O que a biblioteca é, as nove decisões que a moldam e por quê, e o que fica fora
da 0.1. Cada decisão tem um ADR em `docs/adr/` com as alternativas que perderam;
esta página é o mapa. Os contratos públicos estão em `src/memory_lifecycle/`
(`api.py`, `model.py`, `exceptions.py`, `connection/`, `embeddings/`) e o
comportamento em `openspec/specs/`. O vocabulário
é o de `docs/glossario.md`.

## A forma

```text
aplicação (dona da conexão, do escopo e do domínio)
    │  Memoria(conexao, embeddings, tenant_id)
    ▼
memory_lifecycle
    api.py        Memoria: lembrar · substituir · corrigir · encerrar · invalidar_contexto
                           esquecer · migrar   (_leituras.py: recuperar · historico;
                           _nucleo.py: filtro, schema, embedding, vigente, reescrita)
    model.py      VersaoDeMemoria, ResultadoDeRecuperacao, Status, derivar_status
    temporal.py   regras puras de tempo: Momento, validações e o oráculo vale_em
    _sql.py       schema citado, colunas, predicados dos modos, tradução de SQLSTATE
    store.py      escritas     retrieval.py   leituras (escopo estrito, modos, similaridade)
    connection/   ProvedorDeConexao, unidade de trabalho; dsn · psycopg_pool · django · sqlalchemy
    embeddings/   ProvedorDeEmbeddings, ProvedorDeEmbeddingsFalso, vetorizar
    migrations/   0001_inicial.sql, 0002_ordem_por_registro.sql + executor
    │
    ▼
PostgreSQL + pgvector, schema `memory_lifecycle` dentro do banco do app
```

## As nove decisões

| # | decisão | por quê, em uma linha | ADR |
|---|---|---|---|
| 1 | Ids opacos, versões imutáveis, status derivado | o ciclo de vida é o produto; um status armazenado diverge dos limites | [0001](adr/0001-memory-model.md) |
| 2 | Dois eixos, três operações, três modos; só `substituido_em` fecha | "mudou", "deixou de valer" e "estava errado" são fatos diferentes | [0002](adr/0002-temporal-semantics.md) |
| 3 | Escopo estrito, passado pelo app em `recuperar` | participação é dado oficial que a biblioteca não tem como saber | [0003](adr/0003-scope-owned-by-the-app.md) |
| 4 | Protocolo de provedor, transação `PARTICIPAR` ou `PROPRIA` | um pool por app; a escrita entra com a requisição | [0004](adr/0004-connection-provider-and-transaction-modes.md) |
| 5 | Síncrono primeiro | o primeiro consumidor é síncrono; o assíncrono reutiliza o núcleo puro depois | [0005](adr/0005-sync-first.md) |
| 6 | `esquecer` é o único delete físico | um pedido de privacidade precisa apagar a trilha de auditoria também | [0006](adr/0006-forget-is-the-only-physical-delete.md) |
| 7 | SQL para psycopg2 e psycopg 3, vetores como texto | nunca registrar um adaptador numa conexão que é do app | [0007](adr/0007-driver-compatible-sql-vectors-as-text.md) |
| 8 | Migrações SQL que só acrescentam, com tabela de versão | o histórico do schema precisa ser legível e idempotente | [0008](adr/0008-append-only-migrations.md) |
| 9 | Busca vetorial exata na 0.1 | o HNSW filtra depois e devolve menos que o limite | [0009](adr/0009-exact-vector-search.md) |

## Uma linha do tempo resolvida

Toda operação fecha o registro da vigente e insere; nada mais muda numa linha (ADR 0002).

```text
lembrar("prefere respostas curtas")             v1   válida jan→aberta  registrada jan
substituir(v1, "prefere respostas detalhadas")  v1   válida jan→aberta  registrada jan, fechada jun
  (em junho)                                    v1'  válida jan→jun     registrada jun   ← cópia limitada
                                                v2   válida jun→aberta  registrada jun
corrigir(v2, "… detalhadas, com fontes")        v2   válida jun→aberta  registrada jun, fechada jul
  (em julho)                                    v3   válida jun→aberta  registrada jul

recuperar()                       → v3
recuperar(como_em=março)          → v1'  (era verdade em março, pelo que sabemos hoje)
recuperar(como_em=15 de junho)    → v3   (v2 nunca foi verdade; o registro estava errado)
recuperar(sabido_em=maio)         → v1   (em maio, sabíamos isto, e sem fim)
recuperar(sabido_em=15 de junho)  → v2   (em 15 de junho, era nisso que acreditávamos)
esquecer(memoria_id)              → apaga as quatro linhas; nada sobrevive, em nenhum modo
```

## O escopo em `recuperar`

O escopo é **estrito**: `contextos` e `entidades` listam os ids que entram nesta
consulta, e nada fora da lista é devolvido. O app diz explicitamente o que entra.

| argumento | o que devolve naquele eixo |
|---|---|
| `contextos=None` | não filtra |
| `contextos=["p-2027"]` | só versões com `contexto_id == "p-2027"` |
| `contextos=["p-2027", None]` | as de `p-2027` **e** as sem contexto |
| `contextos=[]` | nada |

Mesma regra para `entidades`. Sair do escopo não é uma escrita: a memória fica, e
volta quando o app passa o id de novo.

## Regras que toda instrução obedece

- `tenant_id` e `dono_id` em todo `WHERE`; o tenant é fixado na construção, o
  dono a cada chamada.
- Fechar um limite é condicional a ele estar aberto; zero linhas é `ErroDeConflito`.
- Embedding primeiro, conexão depois; a conexão vive por uma operação.
- `recuperar` tem `limite` e um instante de referência, sempre.
- Todo `datetime` tem fuso, na entrada e na saída.

## Fora da 0.1

Explicitamente fora do primeiro lançamento, cada item com o motivo:

- **Extração por LLM, política de memória, consolidação, grafos de relações** —
  Etapa 10; o ciclo de vida precisa estar estável antes de algo decidir o que entra nele.
- **Superfície assíncrona** — ADR 0005; ainda sem consumidor assíncrono.
- **Consulta bitemporal completa** (`como_em` e `sabido_em` juntos) — ADR 0002; os
  três modos respondem às perguntas conhecidas.
- **Corrigir uma versão histórica** — só a versão vigente pode ser corrigida ou
  substituída.
- **Esquecer por contexto** — ADR 0006; o fim de um contexto é um `encerrar`.
- **JSON de metadados numa versão** — ADR 0001; `categoria` e `origem` cobrem as
  necessidades conhecidas.
- **Embedding em lote ou adiado** — embeddings são calculados na escrita, de forma síncrona.
- **API HTTP, servidor MCP, CLI** além de `Memoria.migrar()` — a biblioteca é embutida.
- **Permissões além de tenant e dono** — da aplicação.
- **Limpar `entidade_id` ou `contexto_id` ao substituir** — uma memória nova via `lembrar`.

## Questões em aberto depois da 0.1

- Duas embeddings com dimensões diferentes no mesmo banco (ADR 0008).
- Busca vetorial aproximada para donos com mais de 10 mil versões vigentes sem
  escopo (adendo do ADR 0009).
- Prazo na trava de `migrar` e classificação transitória × permanente de
  `ErroDeEmbedding` (`.claude/review.md`, seção 2).
