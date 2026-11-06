# Status: ciclo de vida central da memória (0.1.0)

- Idioma: português em tudo (decisão de 2026-11-06, docs/glossario.md).
- Etapa 1 — Produto: APROVADA 2026-11-06 (reaberta e reaprovada no mesmo dia: design.md § D1)
- Etapa 2 — Arquitetura: APROVADA 2026-11-06 (ADRs 0001–0009 aceitos)
- Etapa 3 — Desenho do programa: APROVADA 2026-11-06
- Etapa 4 — Plano de fatias: APROVADA 2026-11-06 — construção CONCLUÍDA (16 fatias)

## Entrevista grill-me

Concluída em 2026-11-06. Confirmado pelo dono: tenant no construtor; escopo
estrito em `recuperar` (`None` na lista inclui as versões sem contexto ou sem
entidade); `como_em` e `sabido_em` exclusivos; `versao_esperada_id` opcional;
`esquecer` com exatamente um alvo (`memoria_id` | `entidade_id` | `tudo`);
`categoria` obrigatória e texto livre; herança em `substituir`/`corrigir` sem
como limpar; embedding na escrita, síncrono; `historico()` por memória, sem flag
em `recuperar`; licença MIT; `PARTICIPAR` em autocommit recusado com
`ErroDeConfiguracao`. Detalhes e porquês em `refinement.md`.

## Fatias
(espelho dos grupos do tasks.md — a lista canônica é o tasks.md)

1. bala traçante: lembrar + recuperar no Postgres — CONCLUÍDA 2026-11-06 (55 passam, 23 xfail estrito)
2. lembrar completo, escopo, categoria, historico — CONCLUÍDA 2026-11-06
3. três modos + oráculo — CONCLUÍDA 2026-11-06 (coerência com 60 memórias × 60 instantes)
4. encerrar, invalidar_contexto, derivar_status — CONCLUÍDA 2026-11-06
5. substituir + concorrência — CONCLUÍDA 2026-11-06
6. corrigir — CONCLUÍDA 2026-11-06
7. esquecer — CONCLUÍDA 2026-11-06 (os 16 cenários de aceitação passam)
8. similaridade + medição — CONCLUÍDA 2026-11-06 (meta atendida com cache quente; adendo no ADR 0009; migração 0002)
9. migração robusta — CONCLUÍDA 2026-11-06
10. transação e tradução de erros — CONCLUÍDA 2026-11-06 (revisão silent-failure: 4 P1 corrigidos)
11. paridade psycopg2 — CONCLUÍDA 2026-11-06
12. adaptador pool psycopg — CONCLUÍDA 2026-11-06
13. adaptador Django — CONCLUÍDA 2026-11-06
14. adaptador SQLAlchemy + carregar_provedor — CONCLUÍDA 2026-11-06 (292 testes)
15. fechamento da change — CONCLUÍDA 2026-11-06 (revisão completa: reports/review-change-core.md)
16. correções da revisão — CONCLUÍDA 2026-11-06 (342 testes; bloqueadores verificados por mutação)

## Notas para uma sessão nova

- Esta mudança é toda a superfície 0.1.0: as Etapas 2–7 de
  `.data/planejamento-macro.md` são as suas fatias. `refinement.md` responde às
  perguntas abertas do plano, todas confirmadas pelo dono na entrevista.
- As assinaturas públicas já existem em `src/memory_lifecycle/` (corpos levantam
  `NotImplementedError`) e os cenários de aceitação em `tests/acceptance/` estão
  escritos contra elas, marcados `xfail(strict=True)` até as fatias chegarem. Esse
  é o critério de conclusão da Etapa 1 no plano.
- Nove ADRs em `docs/adr/` estão `aceito`; `docs/architecture.md` é a visão
  geral. ADR 0003, specs e cenários de aceitação já seguem o escopo estrito.
- Ações pendentes do dono fora desta mudança: commit inicial, branch `dev`,
  reserva do nome no PyPI.
- Fatia 1 (2026-11-06): o Postgres da suíte sobe com `docker compose up -d postgres`
  fora do sandbox; de dentro do sandbox a conexão na porta 5433 funciona. Rode a
  suíte com `MEMORY_LIFECYCLE_DSN_TESTE=postgresql://memory:memory@localhost:5433/memory_lifecycle`.
  Desvios pequenos do program-design: `temporal.resolver_agora` e `exigir_fuso`
  entraram já na Fatia 1; `versao_do_schema` é criada pelo executor, não pela 0001;
  `vetorizar` usa `ErroDeEmbedding` (e não de dimensão) quando a contagem de
  vetores difere da de textos; D401 desligado no ruff (heurística do inglês).
- 2026-11-06: o dono autorizou construir todas as fatias (2 a 15) em sequência, sem
  a parada "vamos para a fatia N+1?" entre elas. O gate completo contra o Postgres
  continua obrigatório ao fim de cada fatia.
- Fatias 4–7: três cenários chamavam encerrar/substituir no mesmo instante do
  lembrar com o relógio parado, o que pediria validade de duração zero (recusada
  pelo ADR 0002 e pelo CHECK); os cenários passaram a avançar o relógio um dia,
  sem mudar asserção. O teste de coerência exige ≥ 30 registros fechados e ≥ 15
  cópias, para não ficar verde engolindo erros.
