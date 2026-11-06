# ADR 0009 — Busca vetorial exata na 0.1, sem índice aproximado

- **Status:** aceito
- **Data:** 2026-11-06
- **Regra tocada:** regra 1 do `CLAUDE.md` (filtros obrigatórios); Definição de Pronto 1
- **Módulos afetados:** `retrieval`, `migrations`

## Contexto

`recuperar` com `consulta` ordena por distância de cosseno, sempre depois dos
filtros obrigatórios (tenant, dono, modo, escopo, categoria). O índice HNSW do
pgvector faz a busca aproximada **antes** desses filtros e descarta o que não
passa neles. Com filtros seletivos, ele devolve menos que o `limite` pedido, sem
erro. O volume esperado por dono é de milhares de versões.

## Decisão

Na 0.1 não há índice vetorial. Os índices B-tree de tenant e dono cortam o
conjunto, e a distância é calculada sobre as linhas que restam. O resultado é
exato e respeita o `limite`. A pontuação é `1 - distância_cosseno / 2`, em `[0, 1]`.

## Consequências

**Fica mais fácil**
- Recall exato; nenhum parâmetro de índice (`ef_search`, listas) para ajustar.
- Uma migração a menos para mudar quando o modelo de embedding muda.

**Fica mais difícil**
- O custo cresce linearmente com as versões de um dono.

## Alternativas consideradas

### HNSW na primeira migração
- **Prós:** sublinear para volumes grandes.
- **Contras:** filtra depois da busca aproximada; devolve menos que o `limite` com
  filtros seletivos, um bug silencioso.
- **Rejeitada porque:** a 0.1 não tem o volume que o justifique.

### HNSW com `hnsw.iterative_scan` (pgvector ≥ 0.8)
- **Prós:** corrige o problema do filtro.
- **Contras:** exige pgvector recente e configuração de sessão na conexão do app.
- **Rejeitada para a 0.1:** mexer na sessão da conexão do app contraria a regra 5.

## Revisitar quando

O agente `sql-performance` medir `recuperar` acima de 50 ms, ou um dono passar de
50 mil versões.

## Adendo — medição de 2026-11-06

Medido pelo agente `sql-performance` (`reports/sql-perf-recuperar-volume.md`), com
100 mil versões de 1536 dimensões e 50 donos de 2 mil versões. A decisão continua;
o gatilho de revisão fica mais preciso.

| cenário | pior caso de `recuperar` com consulta |
|---|---|
| dono de 2 mil versões, cache quente | 9 ms de SQL, 11 ms ponta a ponta |
| mesmo dono, `shared_buffers` frio | mediana 30–47 ms, p90 76–148 ms |
| dono de 50 mil versões, cache quente | 166 ms |

- O custo é linear, cerca de 4,6 ms por mil versões vigentes, porque o vetor mora
  no TOAST e é lido para cada linha que passa nos filtros.
- O filtro de escopo (`contextos`, `entidades`) é a alavanca: com ele, o pior caso
  caiu para menos de 1 ms.
- **Gatilho revisado:** reabrir esta decisão quando um dono passar de **10 mil
  versões vigentes consultadas sem escopo**, ou quando o p90 medido com cache frio
  passar de 50 ms num consumidor real. A alternativa a medir primeiro é
  `hnsw.iterative_scan` com `SET LOCAL` dentro da transação da biblioteca.

