# Design

Etapa 2 (Arquitetura) da change `core-memory-lifecycle`. Lê-se junto com
`proposal.md`, as specs e os ADRs 0001–0008. Termos e identificadores de
`docs/glossario.md`.

## Context

Hoje o pacote tem só contratos: `api.py` (`Memoria` com os nove métodos),
`model.py` (`VersaoDeMemoria`, `ResultadoDeRecuperacao`, `Status`,
`derivar_status`), `exceptions.py` (os erros tipados), `connection/__init__.py`
(`ProvedorDeConexao`, `ModoDeTransacao`, a fatia DB-API) e
`embeddings/__init__.py` (`ProvedorDeEmbeddings`, `ProvedorDeEmbeddingsFalso`).
Todo corpo levanta `NotImplementedError`. Os 16 cenários de aceitação e os 7 testes
de status estão escritos contra essa API e marcados `xfail(strict=True)`.

Esta change preenche os corpos e cria os módulos que o `CLAUDE.md` já planeja:

| módulo | papel |
|---|---|
| `temporal.py` | funções puras: os predicados dos modos, a validação de instantes, as regras de fechamento, a resolução de `agora` |
| `store.py` | as escritas: uma função por operação, montando as instruções a partir de `temporal.py` e conferindo `rowcount` |
| `retrieval.py` | as leituras: `recuperar` e `historico` |
| `_sql.py` | o nome do schema validado e citado, a lista de colunas, a tradução de SQLSTATE para os erros tipados |
| `connection/_unidade.py` | a unidade de trabalho: pede a conexão ao provedor, aplica o modo de transação, recusa autocommit |
| `migrations/` | o executor e `0001_inicial.sql` |
| `embeddings/__init__.py` | o corpo do `ProvedorDeEmbeddingsFalso` |
| `connection/dsn.py` | o primeiro adaptador (extra `psycopg`), para scripts e para a suíte |

Os adaptadores `psycopg_pool`, `django` e `sqlalchemy` são da Etapa 6 do plano e
entram como fatias próprias desta change, depois do núcleo.

## Goals / Non-Goals

**Goals:**
- Os 16 cenários de aceitação passam contra PostgreSQL 16 + pgvector real, com
  psycopg 3 e com psycopg2 (paridade de driver).
- Toda instrução filtra `tenant_id` e `dono_id`; toda escrita condicional confere
  `rowcount`; nenhum adaptador de tipo é registrado na conexão do app.
- `recuperar` no modo agora responde em menos de 50 ms com 100 mil versões por
  tenant e 2 mil por dono (meta a medir com o agente `sql-performance`).
- `migrar()` idempotente, append-only, seguro contra duas chamadas simultâneas.

**Non-Goals:**
- Índice vetorial aproximado (HNSW/IVFFlat) na 0.1. Ver D5.
- Superfície assíncrona, embedding em lote, combinação de `como_em` com `sabido_em`
  numa mesma chamada (fora da 0.1 pela Etapa 1).
- Esquecer por contexto, metadados JSON, limpar entidade ou contexto ao substituir.

## Decisions

### D1. Semântica temporal: só `substituido_em` fecha (ADR 0002 revisado)

**O que se achou.** A primeira versão do ADR 0002 mandava `substituir` fechar
`valido_ate` **e** `substituido_em` da antiga. Como `como_em(D)` exige
`substituido_em IS NULL`, a versão de janeiro sumia de "como era em março" depois
de uma substituição, e o cenário aprovado falhava. Além disso, `sabido_em(D)`
ignorava a validade e devolvia fatos que já não valiam em D.

**Decisão do dono em 2026-11-06: opção A, e `sabido_em` sobre o próprio D.** A
única mutação de uma linha é fechar `substituido_em`. Toda operação fecha o
registro da vigente e insere:

| operação | na versão vigente | insere |
|---|---|---|
| `encerrar(V)` | fecha `substituido_em = agora` | a cópia limitada, com `valido_ate = V` |
| `substituir(V)` | fecha `substituido_em = agora` | a cópia limitada com `valido_ate = V`, e a nova com `valido_de = V` |
| `corrigir` | fecha `substituido_em = agora` | a certa, com os mesmos `valido_de` e `valido_ate` |

| modo | predicado |
|---|---|
| agora | `como_em(agora)` |
| `como_em(D)` | `substituido_em IS NULL AND valido_de <= D AND (valido_ate IS NULL OR valido_ate > D)` |
| `sabido_em(D)` | `registrado_em <= D AND (substituido_em IS NULL OR substituido_em > D) AND valido_de <= D AND (valido_ate IS NULL OR valido_ate > D)` |

A **vigente** de uma memória é a linha de registro aberto com o maior `valido_de`.
A opção B (fechar a validade no lugar) foi rejeitada porque um encerramento
retroativo reescreveria `sabido_em`. ADR 0002, ADR 0001, specs, docstrings, testes
e a skill `bitemporal-model` foram atualizados no mesmo dia, e a Etapa 1
foi reaberta para nova aprovação.

**Encadeamento.** `versao_anterior_id` aponta sempre para a linha cujo
registro foi fechado pela operação (a cópia aponta para a vigente fechada; a nova
de `substituir` aponta para a cópia). `historico` devolve todas as linhas da
memória por `registrado_em`, depois `valido_de`.

**Status** (`derivar_status(versao, agora=, sucessora=)`):
- registro fechado e sucessora com os mesmos `valido_de` e `valido_ate`: `CORRIGIDA`;
- registro fechado e sucessora que muda a validade, ou registro aberto com
  sucessora: `SUBSTITUIDA`;
- registro aberto sem sucessora: `ENCERRADA` se `valido_ate <= agora`, senão `ATIVA`.

### D2. API pública

Os nove métodos ficam como em `api.py`. Cada um, com a regra de validação e o erro:

| método | valida antes da conexão | erros |
|---|---|---|
| `migrar()` | nome do schema `^[a-z_][a-z0-9_]{0,62}$` | `ErroDeConfiguracao` (pgvector ausente sem privilégio), `ErroDeMigracao`, `ErroDeDimensaoDeEmbedding` |
| `lembrar` | conteúdo não vazio, `categoria` não vazia, datetimes com fuso, `valido_ate > valido_de` | `ErroDeArgumentoInvalido`, `ErroDeEmbedding`, `ErroDeDimensaoDeEmbedding`, `ErroDeConfiguracao` |
| `substituir` | conteúdo, fuso, `valido_de` | + `ErroNaoEncontrado`, `ErroDeConflito`; `ErroDeArgumentoInvalido` se `valido_de <= vigente.valido_de` |
| `corrigir` | conteúdo | + `ErroNaoEncontrado`, `ErroDeConflito` |
| `encerrar` | fuso | `ErroNaoEncontrado`, `ErroDeConflito` (validade já fechada), `ErroDeArgumentoInvalido` (`valido_ate <= valido_de`) |
| `invalidar_contexto` | fuso | nenhum além de configuração; devolve a contagem |
| `esquecer` | exatamente um alvo | `ErroDeArgumentoInvalido` |
| `recuperar` | `limite >= 1`, no máximo um entre `como_em` e `sabido_em`, fuso | `ErroDeArgumentoInvalido`, `ErroDeEmbedding` |
| `historico` | — | `ErroNaoEncontrado` |

`substituir` e `encerrar` exigem a vigente com validade aberta ou fechando depois
do novo limite. Caso contrário, `ErroDeConflito` com a mensagem "a memória já
estava encerrada; use lembrar". Isso mantém "fechar só o que está aberto".

### D3. Dados — `0001_inicial.sql`

Schema próprio, `memory_lifecycle` por padrão. Três tabelas:

```sql
CREATE TABLE IF NOT EXISTS {schema}.versoes_de_memoria (
  versao_id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  memoria_id         uuid        NOT NULL,
  tenant_id          text        NOT NULL,
  dono_id            text        NOT NULL,
  categoria          text        NOT NULL CHECK (categoria <> ''),
  conteudo           text        NOT NULL CHECK (conteudo <> ''),
  entidade_id        text,
  contexto_id        text,
  origem             text,
  embedding          vector({dimensao}) NOT NULL,
  modelo_embedding   text        NOT NULL,
  valido_de          timestamptz NOT NULL,
  valido_ate         timestamptz CHECK (valido_ate IS NULL OR valido_ate > valido_de),
  registrado_em      timestamptz NOT NULL,
  substituido_em     timestamptz CHECK (substituido_em IS NULL OR substituido_em >= registrado_em),
  versao_anterior_id uuid        REFERENCES {schema}.versoes_de_memoria (versao_id)
);
CREATE TABLE IF NOT EXISTS {schema}.versao_do_schema (
  numero int PRIMARY KEY, nome text NOT NULL, sha256 text NOT NULL, aplicada_em timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS {schema}.configuracao (chave text PRIMARY KEY, valor text NOT NULL);
```

Índices:

| índice | definição | serve |
|---|---|---|
| `ux_versoes_vigente` | `UNIQUE (memoria_id, valido_de) WHERE substituido_em IS NULL` | integridade: duas crenças vigentes não começam no mesmo instante |
| `ix_versoes_crenca_atual` | `(tenant_id, dono_id, valido_de) WHERE substituido_em IS NULL` | agora, `como_em`, `invalidar_contexto` |
| `ix_versoes_registro` | `(tenant_id, dono_id, registrado_em)` | `sabido_em` |
| `ix_versoes_memoria` | `(memoria_id, registrado_em)` | vigente de uma memória, `historico`, `esquecer` por memória |
| `ix_versoes_entidade` | `(tenant_id, dono_id, entidade_id)` | `esquecer` por entidade, filtro de escopo |

O índice parcial passa a ser `WHERE substituido_em IS NULL`, sem `valido_ate IS
NULL`. O `como_em` precisa das versões já encerradas, e o predicado só usa um
índice parcial que case com ele. A regra `migrations.md` e a skill
`postgres-patterns` já foram alinhadas.

`{schema}` e `{dimensao}` são renderizados pelo executor: o schema validado por
regex e citado como identificador, a dimensão como `int`. O hash é do arquivo cru,
não do renderizado. Os ids vêm de `gen_random_uuid()`, nativo desde o PostgreSQL 13.
São enviados e lidos como texto (`%s::uuid`, `versao_id::text`) porque o psycopg2 não
adapta `uuid.UUID` sem registrar um adaptador.

### D4. As instruções

Todas pela mesma lista de colunas e pelo mesmo filtro `tenant_id = %s AND dono_id = %s`.

- **Vigente:** `SELECT … WHERE tenant_id, dono_id, memoria_id = %s AND substituido_em IS NULL ORDER BY valido_de DESC LIMIT 1`.
  Sem linha, `ErroNaoEncontrado`. Uma `versao_esperada_id` diferente da vigente dá `ErroDeConflito`.
- **Fechar registro:** `UPDATE … SET substituido_em = %s WHERE versao_id = %s AND tenant_id, dono_id AND substituido_em IS NULL`.
  `rowcount != 1` dá `ErroDeConflito`. Esta é a trava de concorrência: o segundo escritor
  espera o lock da linha e, depois do commit do primeiro, reavalia o `WHERE` e afeta zero linhas.
- **Cópia limitada:** `INSERT INTO … SELECT gen_random_uuid(), memoria_id, …, embedding, modelo_embedding, valido_de, %s, %s, NULL, versao_id FROM … WHERE versao_id = %s RETURNING …`.
  O vetor não faz ida e volta.
- **Inserir versão nova:** `INSERT … VALUES (…, %s::vector, …) RETURNING …`.
- **`invalidar_contexto`:** um CTE `UPDATE … RETURNING` que fecha o registro das vigentes
  com validade aberta do contexto e começadas antes de V, seguido de `INSERT … SELECT` das
  cópias. O retorno é a contagem.
- **`esquecer`:**
  - por memória: `DELETE … WHERE tenant_id, dono_id, memoria_id`;
  - por entidade: `DELETE … WHERE tenant_id, dono_id AND memoria_id IN (SELECT memoria_id … WHERE entidade_id = %s)`.
    Apaga a memória inteira se qualquer versão dela citar a entidade, o que é a escolha
    segura para privacidade;
  - tudo: `DELETE … WHERE tenant_id, dono_id`.
  - A chave estrangeira de `versao_anterior_id` é checada no fim da instrução, e a cadeia
    inteira sai na mesma instrução.
- **`recuperar`:**

```sql
SELECT <colunas> [, 1 - (embedding <=> %s::vector) / 2 AS pontuacao]
FROM {schema}.versoes_de_memoria
WHERE tenant_id = %s AND dono_id = %s AND <predicado do modo>
  [AND (contexto_id = ANY(%s::text[]) OR (%s AND contexto_id IS NULL))]
  [AND (entidade_id = ANY(%s::text[]) OR (%s AND entidade_id IS NULL))]
  [AND categoria = %s]
ORDER BY [embedding <=> %s::vector |] registrado_em DESC
LIMIT %s
```

  O escopo `["p-2027", None]` vira `ids=["p-2027"], incluir_nulo=True`, e `[]` vira
  `ids=[], incluir_nulo=False`, que não devolve nada. A distância de cosseno vai de 0 a 2,
  e `pontuacao = 1 - d/2` fica em `[0, 1]`.

### D5. Busca vetorial exata na 0.1

Sem índice HNSW. Os filtros de tenant, dono e modo cortam para as versões de um
dono, na casa dos milhares, e a distância é calculada nessas linhas. O resultado é
exato. O HNSW do pgvector filtra **depois** da busca aproximada, e com filtros
seletivos devolve menos que o `limite`, o que vira um bug silencioso de recall.
A decisão é revista quando a medição do `sql-performance` passar de 50 ms ou um dono
passar de 50 mil versões. Registrada no ADR 0009.

### D6. Conexão e transação

`connection/_unidade.py` concentra a regra. Uma operação faz:
1. calcula o embedding, se houver;
2. abre `provedor.conexao()`;
3. confere `getattr(conexao, "autocommit", False)`: verdadeiro em qualquer modo dá
   `ErroDeConfiguracao` antes de escrever (ADR 0004). A recusa vale também em
   `PROPRIA`, porque uma operação de várias instruções precisa de transação nos dois
   modos. Conexões sem o atributo são aceitas, e cada adaptador garante o estado;
4. abre um cursor, executa e fecha o cursor num `finally`;
5. em `PROPRIA`, faz `commit` no sucesso e `rollback` em qualquer exceção. Em
   `PARTICIPAR`, não faz nenhum dos dois. A exceção sobe, e o app decide o rollback
   da transação dele.

Na primeira operação de cada `Memoria`, lê `configuracao.dimensao` uma vez e guarda
em cache. Tabela ausente (SQLSTATE `42P01`) dá `ErroDeConfiguracao` com "rode
migrar()". Dimensão diferente de `embeddings.dimensao` dá `ErroDeDimensaoDeEmbedding`.
O SQLSTATE é lido de `getattr(e, "sqlstate", None) or getattr(e, "pgcode", None)`,
que cobre psycopg 3 e psycopg2. `23505` vira `ErroDeConflito`. `42501` em
`CREATE EXTENSION` vira `ErroDeConfiguracao`, com o comando a rodar como superusuário.

`migrar()` segue o mesmo caminho e toma `pg_advisory_xact_lock` com uma chave
derivada do nome do schema. Duas chamadas simultâneas ficam em série.

### D7. Tempo

`agora` é lido **uma vez** por operação, de `relogio()` ou de `datetime.now(UTC)`, e
vale para `registrado_em` e `substituido_em`. O relógio do banco (`now()`) nunca é
usado, para que os testes congelem o tempo e `sabido_em` seja testável. Os intervalos
são semiabertos, `[valido_de, valido_ate)` e `[registrado_em, substituido_em)`. No
instante exato da troca, vale a versão nova.

### D8. Provedor de embeddings falso

`gerar(textos)`: para cada texto, os blocos de `sha256(f"{i}:{texto}")` viram floats
em `[-1, 1]`, depois normalizados para norma 1. É determinístico, sem rede, e textos
iguais dão vetores iguais. `ErroDeEmbedding` envolve qualquer exceção de um provedor
real. `ErroDeDimensaoDeEmbedding` é levantado antes da conexão quando
`len(vetor) != dimensao`.

### D9. Externo

- **Extras:** `psycopg` (adaptador `dsn` e `psycopg_pool`), `django`, `sqlalchemy`.
  O core continua sem dependência. O psycopg2 entra no grupo de dev, só para a
  paridade de driver.
- **Variáveis de ambiente (nomes):** `MEMORY_LIFECYCLE_PROVEDOR_CONEXAO` e
  `MEMORY_LIFECYCLE_DSN_TESTE`.
- **Banco:** PostgreSQL ≥ 13 (alvo 16) e pgvector ≥ 0.5.


## Risks / Trade-offs

- **Mais linhas por operação.** Substituir escreve duas, encerrar e invalidar
  escrevem uma cópia por versão. Mitigação: as cópias reaproveitam o vetor no banco,
  e o volume esperado por dono é de milhares de linhas.
- **`historico` e a contagem de `esquecer` incluem as cópias.** O app vê mais
  versões do que fez operações. Mitigação: `derivar_status` rotula as linhas. Um
  `historico` resumido pode vir depois, sem quebrar nada.
- **Busca exata não escala para donos enormes.** Mitigação: a meta de 50 ms medida
  na fatia de recuperar e o gatilho do ADR 0009.
- **Autocommit detectado por atributo.** Uma conexão sem o atributo `autocommit`
  passa sem checagem. Mitigação: os quatro adaptadores da biblioteca garantem o
  estado, e só um provedor feito à mão escapa.
- **`PARTICIPAR` e um `ErroDeConflito` no meio.** A transação do app fica abortada
  pelo driver (Postgres). Mitigação: documentado, e o app faz rollback como faria
  com qualquer erro de banco.
- **`esquecer` por entidade apaga a memória inteira.** Isso inclui versões de outra
  entidade, se a memória mudou de entidade. É a escolha segura para privacidade e
  vai documentada na docstring.
- **`gen_random_uuid()` e `vector` exigem PostgreSQL 13 ou mais e pgvector
  instalado.** Mitigação: `migrar()` verifica e explica o que falta.
