-- 0001: the version record, the settings and the indexes (design.md § D3).
-- Rendered by the runner: {schema} is the already validated and quoted name; {dimension}
-- is an integer. Once published, this file never changes: the fix is the next one (ADR 0008).
-- PT: 0001: o registro de versões, a configuração e os índices (design.md § D3).
-- PT: Renderizado pelo executor: {schema} é o nome já validado e citado; {dimension} é
-- PT: um inteiro. Publicado, este arquivo nunca muda: a correção é o seguinte (ADR 0008).

CREATE TABLE IF NOT EXISTS {schema}.settings (
  key   text PRIMARY KEY,
  value text NOT NULL
);

INSERT INTO {schema}.settings (key, value)
VALUES ('dimension', '{dimension}')
ON CONFLICT (key) DO NOTHING;

-- One row per version. Once written, the only thing that changes in a row is
-- `superseded_at` closing (ADR 0002).
-- PT: Uma linha por versão. Depois de escrita, a única coisa que muda numa linha é
-- PT: `superseded_at` fechar (ADR 0002).
CREATE TABLE IF NOT EXISTS {schema}.memory_versions (
  version_id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_id           uuid        NOT NULL,
  tenant_id           text        NOT NULL,
  owner_id            text        NOT NULL,
  kind                text        NOT NULL CHECK (kind <> ''),
  content             text        NOT NULL CHECK (content <> ''),
  entity_id           text,
  context_id          text,
  source              text,
  embedding           vector({dimension}) NOT NULL,
  embedding_model     text        NOT NULL,
  valid_from          timestamptz NOT NULL,
  valid_to            timestamptz CHECK (valid_to IS NULL OR valid_to > valid_from),
  recorded_at         timestamptz NOT NULL,
  superseded_at       timestamptz CHECK (superseded_at IS NULL OR superseded_at >= recorded_at),
  previous_version_id uuid        REFERENCES {schema}.memory_versions (version_id)
);

-- Current beliefs: the path of `now` and `as_of`. No `valid_to IS NULL` in the
-- predicate, because `as_of` reads versions that already expired.
-- PT: Crenças atuais: o caminho de `now` e `as_of`. Sem `valid_to IS NULL` no
-- PT: predicado, porque `as_of` lê versões já encerradas.
CREATE INDEX IF NOT EXISTS ix_versions_current_belief
  ON {schema}.memory_versions (tenant_id, owner_id, valid_from)
  WHERE superseded_at IS NULL;

-- Integrity: two current beliefs of the same memory do not start at the same instant.
-- PT: Integridade: duas crenças atuais da mesma memória não começam no mesmo instante.
CREATE UNIQUE INDEX IF NOT EXISTS ux_versions_current
  ON {schema}.memory_versions (memory_id, valid_from)
  WHERE superseded_at IS NULL;

-- `known_at`, and the ordering of `recall` without a query. With it,
-- `ORDER BY recorded_at DESC, version_id LIMIT n` reads only n rows with no Sort, even
-- when many versions share the same `recorded_at` (`supersede` and `invalidate_context`
-- store several at the same instant): a 5,000-row tie dropped from 2.4–3.1 ms to 0.02 ms
-- (reports/sql-perf-recuperar-volume.md and reports/sql-perf-escritas.md). It replaces a
-- plain (tenant_id, owner_id, recorded_at) index, which the planner never preferred.
-- PT: `known_at`, e a ordenação de `recall` sem consulta. Com ele,
-- PT: `ORDER BY recorded_at DESC, version_id LIMIT n` lê só n linhas sem Sort, mesmo
-- PT: quando muitas versões dividem o mesmo `recorded_at` (`supersede` e
-- PT: `invalidate_context` gravam várias no mesmo instante): um empate de 5 000 linhas
-- PT: caiu de 2,4–3,1 ms para 0,02 ms (reports/sql-perf-recuperar-volume.md e
-- PT: reports/sql-perf-escritas.md). Substitui um índice simples
-- PT: (tenant_id, owner_id, recorded_at), que o planner nunca preferia.
CREATE INDEX IF NOT EXISTS ix_versions_record_order
  ON {schema}.memory_versions (tenant_id, owner_id, recorded_at DESC, version_id);

-- A memory's current version, `history`, `forget` by memory.
-- PT: Vigente de uma memória, `history`, `forget` por memória.
CREATE INDEX IF NOT EXISTS ix_versions_memory
  ON {schema}.memory_versions (memory_id, recorded_at);

-- `forget` by entity and the scope filter.
-- PT: `forget` por entidade e o filtro de escopo.
CREATE INDEX IF NOT EXISTS ix_versions_entity
  ON {schema}.memory_versions (tenant_id, owner_id, entity_id);

-- The self-referencing foreign key `previous_version_id` (reports/sql-perf-escritas.md).
-- Without it, every row deleted by `forget` makes Postgres scan the table to check the
-- FK: 8.3 ms per row with 100k versions, and `forget(everything=True)` for an owner with
-- 2,131 versions took 21.9 s; with it, 26 ms. Partial because the first version of every
-- memory has no previous one.
-- PT: A chave estrangeira auto-referente `previous_version_id` (reports/sql-perf-escritas.md).
-- PT: Sem ele, cada linha apagada por `forget` faz o Postgres varrer a tabela para conferir
-- PT: a FK: 8,3 ms por linha com 100 mil versões, e `forget(everything=True)` de um dono de
-- PT: 2 131 versões levava 21,9 s; com ele, 26 ms. Parcial porque a primeira versão de toda
-- PT: memória não tem anterior.
CREATE INDEX IF NOT EXISTS ix_versions_previous
  ON {schema}.memory_versions (previous_version_id)
  WHERE previous_version_id IS NOT NULL;

-- No vector index in 0.1: exact search after the filters (ADR 0009).
-- PT: Sem índice vetorial na 0.1: busca exata depois dos filtros (ADR 0009).
