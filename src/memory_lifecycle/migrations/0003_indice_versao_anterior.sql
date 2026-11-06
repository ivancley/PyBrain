-- 0003: índice da chave estrangeira auto-referente `versao_anterior_id`
-- (reports/sql-perf-escritas.md). Sem ele, cada linha apagada por `esquecer` faz o
-- Postgres varrer a tabela para conferir a FK: 8,3 ms por linha com 100 mil versões,
-- e `esquecer(tudo=True)` de um dono de 2 131 versões levava 21,9 s; com ele, 26 ms.
-- Parcial porque a primeira versão de toda memória não tem anterior.

CREATE INDEX IF NOT EXISTS ix_versoes_anterior
  ON {schema}.versoes_de_memoria (versao_anterior_id)
  WHERE versao_anterior_id IS NOT NULL;
