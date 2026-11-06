# ADR 0004 — O app é dono da conexão: protocolo de provedor, dois modos de transação

- **Status:** aceito
- **Data:** 2026-11-06
- **Regra tocada:** regras 4 e 5 do `CLAUDE.md`
- **Módulos afetados:** `connection`, `api`, `store`, `retrieval`

## Contexto

Etapa 1, decisão 4; esta era a principal questão em aberto do plano. O primeiro
consumidor é uma aplicação Django com pool próprio. Um segundo pool dobra as
conexões ao mesmo banco e deixa a escrita de memória fora da transação da
requisição, de modo que uma requisição que falha pode deixar uma memória escrita
pela metade. Um objeto pool não viaja por variável de ambiente.

## Decisão

A biblioteca recebe um **`ProvedorDeConexao`**: um gerenciador de contexto
`conexao()` que entrega uma conexão DB-API, mais um `modo_de_transacao`.

- `PARTICIPAR`: a biblioteca nunca faz commit nem rollback; a escrita entra com a
  transação do app (requisição Django, sessão SQLAlchemy). Se a conexão entregue
  estiver em **autocommit**, não há transação para participar: a biblioteca
  levanta `ErroDeConfiguracao` antes de qualquer escrita, porque uma operação de
  várias instruções (`substituir` fecha a vigente e insere a nova) ficaria pela
  metade. O adaptador Django evita esse erro envolvendo a operação em `atomic()`,
  que vira savepoint dentro de uma transação e transação curta fora dela.
- `PROPRIA`: a biblioteca faz commit no sucesso e rollback no erro (scripts,
  jobs, testes).

O núcleo entrega só o protocolo. Os adaptadores (`dsn`, `psycopg_pool`, `django`,
`sqlalchemy`) são extras opcionais que importam sua dependência sob demanda e
levantam `ErroExtraNaoInstalado` nomeando o extra. A variável de ambiente
`MEMORY_LIFECYCLE_PROVEDOR_CONEXAO` pode nomear uma fábrica sem argumentos por
caminho pontuado; ela nunca carrega um pool. A conexão é mantida por uma única
operação e é obtida **depois** de calcular o embedding.

## Consequências

**Fica mais fácil**
- Um pool por app; atomicidade com a requisição em `PARTICIPAR`.
- A mesma suíte de integração roda contra todo adaptador (Definição de Pronto 1).

**Fica mais difícil**
- Em `PARTICIPAR`, um `ErroDeConflito` deixa a transação do app no estado em que
  o driver a deixou; o app decide o rollback. Documentado por adaptador.
- O provedor é mais um objeto que o app precisa construir na inicialização.

## Alternativas consideradas

### Pool da biblioteca a partir de um DSN
- **Prós:** zero integração; funciona em todo lugar.
- **Contras:** segundo pool; escritas fora da transação do app.
- **Rejeitada porque:** regra 5. Sobrevive como o adaptador `dsn` para scripts e
  testes, em modo `PROPRIA`.

### Pool por variável de ambiente
- **Prós:** cara de twelve-factor.
- **Contras:** um pool é um objeto vivo; só um caminho para uma fábrica pode
  viajar.
- **Rejeitada porque:** impossível como enunciada; a variante por caminho
  pontuado fica.

### `PARTICIPAR` em autocommit: confiar no app
- **Prós:** nenhuma checagem por operação.
- **Contras:** uma configuração errada vira meia escrita silenciosa.
- **Rejeitada porque:** falhar alto e cedo é mais barato que uma memória sem
  versão vigente descoberta semanas depois (decisão do dono em 2026-11-06).

### `PARTICIPAR` em autocommit: abrir transação própria em silêncio
- **Prós:** funciona sem configuração.
- **Contras:** quem pediu `PARTICIPAR` recebe `PROPRIA` sem saber; esconde o erro
  de configuração.
- **Rejeitada porque:** o modo pedido deve ser o modo executado.

### Provedor assíncrono primeiro
- **Prós:** cabe em apps ASGI.
- **Contras:** o primeiro consumidor é síncrono; duas superfícies de uma vez
  dobram a Etapa 6.
- **Rejeitada para a 0.1:** veja o ADR 0005.

## Em aberto

- Savepoints dentro da transação do app para operações com várias instruções.

## Revisitar quando

Um consumidor rodar numa stack assíncrona, ou um adaptador precisar de mais do
que a fatia do DB-API em `connection/__init__.py`.

## Adendo — revisão de 2026-11-06

A revisão completa da 0.1 (`reports/review-change-core.md`) achou dois buracos na
regra, sem mudar a decisão:

- **O modo é normalizado pelo enum.** Um provedor que declarava
  `modo_de_transacao = "propria"` era tratado como `PARTICIPAR`, e a escrita sumia
  sem commit e sem erro. A unidade de trabalho e `carregar_provedor` agora passam o
  valor por `ModoDeTransacao(...)`, e um valor fora dele é `ErroDeConfiguracao`.
- **A sessão do SQLAlchemy ganha um savepoint por operação** (`begin_nested`), como
  o `atomic()` do Django. Sem ele, um erro de banco da biblioteca abortava a
  transação da sessão, e o `sessao.commit()` seguinte desfazia tudo em silêncio.

