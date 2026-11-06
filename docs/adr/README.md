# Registros de Decisão de Arquitetura

Um arquivo por decisão, `NNNN-titulo-em-kebab-case.md` (nome de arquivo em inglês,
como os demais), escrito com a skill `adr`. Um ADR aceito nunca é reescrito: um
novo o substitui.

| ADR | decisão | status |
|---|---|---|
| [0001](0001-memory-model.md) | Modelo de memória: ids opacos, versões imutáveis, status derivado | aceito |
| [0002](0002-temporal-semantics.md) | Dois eixos de tempo, três operações, três modos de consulta | aceito |
| [0003](0003-scope-owned-by-the-app.md) | O escopo é do app e é estrito; sair do escopo não é invalidação | aceito |
| [0004](0004-connection-provider-and-transaction-modes.md) | O app é dono da conexão; dois modos de transação | aceito |
| [0005](0005-sync-first.md) | Síncrono primeiro; assíncrono depois sobre o mesmo núcleo | aceito |
| [0006](0006-forget-is-the-only-physical-delete.md) | Esquecer é o único delete físico | aceito |
| [0007](0007-driver-compatible-sql-vectors-as-text.md) | SQL para psycopg2 e psycopg 3; vetores como texto | aceito |
| [0008](0008-append-only-migrations.md) | Migrações SQL que só acrescentam, com tabela de versão | aceito |
| [0009](0009-exact-vector-search.md) | Busca vetorial exata na 0.1, sem índice aproximado | aceito |

São as decisões da Etapa 1 de `.data/planejamento-macro.md`, escritas em
2026-11-06. todas foram aceitas pelo dono em 2026-11-06, com a aprovação da Etapa 2; a
visão geral que as amarra é `docs/architecture.md`.
