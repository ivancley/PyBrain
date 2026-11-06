# ADR 0002 — Semântica temporal: dois eixos, três operações, três modos de consulta

- **Status:** aceito
- **Data:** 2026-11-06
- **Regra tocada:** regra 2 do `CLAUDE.md`
- **Módulos afetados:** `temporal`, `model`, `store`, `retrieval`

## Contexto

Etapa 1, decisão 2. Três situações diferentes parecem iguais de longe: "a
preferência mudou", "o fato deixou de ser verdade", "registramos errado". Um
único `update` perde a diferença e, com ela, a capacidade de responder "o que o
agente sabia quando respondeu no mês passado?".

## Decisão

Dois eixos por versão. **Tempo de validade** (`valido_de`, `valido_ate`): quando
o fato era verdade no mundo. **Tempo de registro** (`registrado_em`,
`substituido_em`): quando o sistema acreditava nesta versão. `NULL` significa
aberto. Os intervalos são semiabertos: `[valido_de, valido_ate)` e
`[registrado_em, substituido_em)`.

**A única mutação de uma linha é fechar `substituido_em`.** Toda operação fecha o
registro da versão vigente (a de registro aberto com o maior `valido_de`) e insere:

| operação | na vigente | insere |
|---|---|---|
| `encerrar(V)` | `substituido_em = agora` | a **cópia limitada**: mesma versão com `valido_ate = V` |
| `substituir(V)` | `substituido_em = agora` | a cópia limitada com `valido_ate = V`, e a nova com `valido_de = V` |
| `corrigir` | `substituido_em = agora` | a certa, com os mesmos `valido_de` e `valido_ate` |

`versao_anterior_id` aponta para a linha cujo registro a operação fechou: a cópia
aponta para a vigente fechada, e a nova de `substituir` aponta para a cópia.

Três modos de consulta em `recuperar`, mutuamente exclusivos na 0.1:

| modo | pergunta | predicado |
|---|---|---|
| agora | o que é verdade agora? | `como_em(agora)` |
| `como_em(D)` | o que era verdade em D, pelo que sabemos hoje? | `substituido_em IS NULL AND valido_de <= D AND (valido_ate IS NULL OR valido_ate > D)` |
| `sabido_em(D)` | o que, em D, sabíamos ser verdade em D? | `registrado_em <= D AND (substituido_em IS NULL OR substituido_em > D) AND valido_de <= D AND (valido_ate IS NULL OR valido_ate > D)` |

Status, derivado por `derivar_status(versao, agora=, sucessora=)`:

| status | quando |
|---|---|
| `ATIVA` | registro aberto, sem sucessora, válida em `agora` |
| `ENCERRADA` | registro aberto, sem sucessora, `valido_ate <= agora` |
| `SUBSTITUIDA` | registro aberto com sucessora (um fato novo veio depois), ou registro fechado e a sucessora muda a validade |
| `CORRIGIDA` | registro fechado e a sucessora tem os mesmos `valido_de` e `valido_ate` |

Fechar o registro é **condicional** (`WHERE … AND substituido_em IS NULL`) e a
contagem de linhas é verificada; zero linhas é `ErroDeConflito`. `encerrar` e
`substituir` exigem a vigente com validade aberta. O instante "agora" vem de um
relógio injetável, lido uma vez por operação. Todo `datetime` que cruza a API tem
fuso.

## Consequências

**Fica mais fácil**
- Depois de `encerrar` ou `substituir`, "como era em março?" ainda responde; depois
  de `corrigir`, não devolve mais o fato errado, e "o que sabíamos em março?" ainda
  devolve.
- `sabido_em` é exato mesmo com mudanças retroativas (`valido_de` e `valido_ate` no
  passado): nenhuma linha que já existiu em D muda depois de D.
- Concorrência uniforme: toda operação fecha condicionalmente o mesmo limite.

**Fica mais difícil**
- Mais linhas: `substituir` insere duas, `encerrar` e `invalidar_contexto` uma cópia
  por versão.
- `historico` e a contagem de `esquecer` incluem as cópias; o app rotula com
  `derivar_status`.
- Quem chama precisa escolher a operação certa; as docstrings carregam esta tabela.

## Alternativas consideradas

### Substituir fechando os dois eixos da antiga (a primeira versão deste ADR)
- **Prós:** uma linha a menos.
- **Contras:** `como_em` exige registro aberto, então a versão de janeiro some de
  "como era em março" depois de uma substituição. Contradiz o próprio cenário.
- **Rejeitada porque:** a contradição foi achada na Etapa 2 (design.md § D1) em
  2026-11-06.

### Fechar a validade no lugar (opção B)
- **Prós:** menos linhas; status trivial.
- **Contras:** o `valido_ate` de hoje sobrescreve o que se sabia antes; um
  encerramento retroativo reescreve `sabido_em`.
- **Rejeitada porque:** "o que o agente sabia quando respondeu" é o diferencial;
  decisão do dono em 2026-11-06.

### `sabido_em` ignorando o tempo de validade
- **Prós:** devolve tudo em que o sistema acreditava em D.
- **Contras:** mistura fatos que já não valiam em D com os que valiam; a pergunta
  do produto é sobre D.
- **Rejeitada porque:** decisão do dono em 2026-11-06.


### Só tempo de validade (um eixo)
- **Prós:** modelo mais simples, menos limites.
- **Contras:** uma correção é indistinguível de uma mudança; sem auditoria do que
  o agente sabia.
- **Rejeitada porque:** "no que acreditávamos" é requisito declarado
  (`.data/inicio.txt` § 4).

### Uma operação `update` com uma coluna de motivo
- **Prós:** um método.
- **Contras:** o motivo é consultivo; os limites que ele fecha não são impostos.
- **Rejeitada porque:** os limites que cada operação toca são a semântica.

## Em aberto

- Consulta bitemporal livre (o que se sabia em K sobre a validade em outro
  instante A) — fora da 0.1; `sabido_em` responde sobre o próprio D.
- Corrigir uma versão histórica (já substituída) — fora da 0.1; só a versão
  vigente pode ser corrigida.

## Revisitar quando

Um consumidor precisar perguntar, num instante K, sobre a validade em outro
instante A; ou o volume de cópias limitadas pesar no `historico`.
