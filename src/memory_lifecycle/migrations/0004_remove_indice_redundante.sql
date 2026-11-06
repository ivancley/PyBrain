-- 0004: remove `ix_versoes_registro` (0001), que ficou redundante com
-- `ix_versoes_ordem_registro` (0002): o planner usa o da 0002 em todos os modos com
-- os mesmos buffers e tempo (reports/sql-perf-escritas.md), e manter os dois custava
-- 4,9 MB por 100 mil versões e ~12% do WAL de inserção sem vetor.

DROP INDEX IF EXISTS {schema}.ix_versoes_registro;
