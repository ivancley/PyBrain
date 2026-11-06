-- 0002: índice da ordenação de `recuperar` sem consulta
-- (reports/sql-perf-recuperar-volume.md e reports/sql-perf-escritas.md). Com ele,
-- `ORDER BY registrado_em DESC, versao_id LIMIT n` lê só n linhas sem Sort, mesmo
-- quando muitas versões dividem o mesmo `registrado_em` (`substituir` e
-- `invalidar_contexto` gravam várias no mesmo instante): um empate de 5 000 linhas
-- caiu de 2,4–3,1 ms para 0,02 ms. Sem CONCURRENTLY: o executor aplica dentro de uma
-- transação, onde ele não é permitido; numa tabela já grande, crie-o à mão com
-- CONCURRENTLY antes de migrar, e este IF NOT EXISTS vira nada.

CREATE INDEX IF NOT EXISTS ix_versoes_ordem_registro
  ON {schema}.versoes_de_memoria (tenant_id, dono_id, registrado_em DESC, versao_id);
