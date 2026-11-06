# Desenho do Programa: ciclo de vida central da memória (0.1.0)

Etapa 3 da change `core-memory-lifecycle`. Parte do `design.md` aprovado (D1–D9)
e dos ADRs 0001–0009. Aqui ficam as decisões que a implementação tomaria em
silêncio: quem é dono de cada função, qual erro, qual instrução carrega tenant e
dono, qual número de migração.

## Arquivos

| arquivo | estado | por que vive ali |
|---|---|---|
| `src/memory_lifecycle/api.py` | muda | orquestra: valida, gera embedding, abre a unidade de trabalho, chama `store`/`retrieval`; nada de SQL |
| `src/memory_lifecycle/model.py` | muda | corpo de `derivar_status` |
| `src/memory_lifecycle/temporal.py` | novo | regras puras de tempo: fuso, `agora`, `Momento`, validações de limite e o oráculo `vale_em` (o predicado de cada modo em Python); sem SQL, sem conexão |
| `src/memory_lifecycle/_sql.py` | novo | o único lugar com texto SQL compartilhado: nome do schema validado e citado, lista de colunas, predicados dos modos, conversão de linha e de vetor, tradução de SQLSTATE |
| `src/memory_lifecycle/store.py` | novo | as escritas, uma função por instrução, todas recebendo `Filtro` (tenant + dono) |
| `src/memory_lifecycle/retrieval.py` | novo | as leituras (`recuperar`, `historico`) e a montagem do escopo estrito |
| `src/memory_lifecycle/connection/_unidade.py` | novo | a unidade de trabalho: conexão do provedor, recusa de autocommit, cursor, commit/rollback pelo modo, tradução de erro |
| `src/memory_lifecycle/connection/dsn.py` | novo | `ProvedorDSN` (extra `psycopg`), modo `PROPRIA`, para scripts e para a suíte |
| `src/memory_lifecycle/embeddings/__init__.py` | muda | corpo do `ProvedorDeEmbeddingsFalso` e `vetorizar` (chama o provedor, embrulha falhas, confere a dimensão) |
| `src/memory_lifecycle/migrations/__init__.py` | novo | o executor: descobre, confere hash, aplica com trava |
| `src/memory_lifecycle/migrations/0001_inicial.sql` | novo | schema, extensão, as três tabelas e os cinco índices do `design.md` § D3 |
| `tests/conftest.py` | muda | schema isolado por teste, `ProvedorDSN` no lugar do provedor de teste, provedor psycopg2 para a paridade |
| `tests/unit/test_temporal.py` | novo | as regras puras e o oráculo |
| `tests/unit/test_sql.py` | novo | schema, vetor, tradução de erro |
| `tests/unit/test_embeddings_falsos.py` | novo | determinismo e norma |
| `tests/integration/test_*.py` | novo | migração, transação, concorrência, paridade, coerência SQL × oráculo |
| `tests/guards/test_tenant_filter.py` | novo | toda instrução de `store`/`retrieval` filtra tenant e dono (guarda planejada no `CLAUDE.md`) |
| `tests/guards/test_migrations_append_only.py` | novo | um arquivo de migração listado no manifesto de hashes não muda |
| `src/memory_lifecycle/migrations/aplicadas.txt` | novo | manifesto `numero sha256` das migrações publicadas, lido só pela guarda |

`pyproject.toml` ganha `psycopg2-binary` só no grupo de dev, para a paridade. O
core continua sem dependência obrigatória.

## Tipos e assinaturas

```python
# temporal.py ---------------------------------------------------------------
Modo = Literal["como_em", "sabido_em"]

@dataclass(frozen=True, slots=True)
class Momento:
    """O instante e o modo de uma leitura; `agora` é `como_em(agora)`."""
    modo: Modo
    instante: datetime

def exigir_fuso(nome: str, instante: datetime | None) -> None: ...
    # ErroDeArgumentoInvalido(f"{nome} precisa de fuso")
def resolver_agora(relogio: Callable[[], datetime] | None) -> datetime: ...
    # lido uma vez por operação; exige fuso também do relógio injetado
def resolver_momento(agora: datetime, como_em: datetime | None,
                     sabido_em: datetime | None) -> Momento: ...
    # os dois juntos -> ErroDeArgumentoInvalido
def exigir_intervalo(valido_de: datetime, valido_ate: datetime | None) -> None: ...
    # valido_ate <= valido_de -> ErroDeArgumentoInvalido
def exigir_fechamento_de_validade(vigente: VersaoDeMemoria, novo_fim: datetime) -> None: ...
    # vigente.valido_ate is not None -> ErroDeConflito("já estava encerrada; use lembrar")
    # novo_fim <= vigente.valido_de -> ErroDeArgumentoInvalido
def vale_em(versao: VersaoDeMemoria, momento: Momento) -> bool: ...
    # o predicado do modo, em Python; oráculo dos testes de coerência com o SQL

# model.py ------------------------------------------------------------------
def derivar_status(versao: VersaoDeMemoria, *, agora: datetime,
                   sucessora: VersaoDeMemoria | None = None) -> Status: ...

# _sql.py -------------------------------------------------------------------
COLUNAS: Final[str]          # "versao_id::text, memoria_id::text, tenant_id, …, versao_anterior_id::text"
PREDICADO: Final[Mapping[Modo, str]]   # texto com %s; cada modo usa o instante 2 ou 4 vezes

@dataclass(frozen=True, slots=True)
class Filtro:
    """Tenant e dono de toda instrução, e a tabela já citada."""
    tabela: str              # '"memory_lifecycle"."versoes_de_memoria"'
    tenant_id: str
    dono_id: str

def validar_schema(nome: str) -> str: ...          # ErroDeConfiguracao fora de ^[a-z_][a-z0-9_]{0,62}$
def citar(schema: str, objeto: str) -> str: ...     # '"schema"."objeto"', só após validar
def vetor_como_texto(vetor: Sequence[float]) -> str: ...   # "[0.1,0.2]" com repr de float
def linha_para_versao(linha: Sequence[Any]) -> VersaoDeMemoria: ...
def sqlstate(erro: BaseException) -> str | None: ...       # .sqlstate (psycopg 3) ou .pgcode (psycopg2)
def traduzir(erro: BaseException) -> ErroMemoryLifecycle | None: ...
    # 23505 -> ErroDeConflito; 42P01/3F000 -> ErroDeConfiguracao("rode migrar()");
    # 22000 com "dimensions" -> ErroDeDimensaoDeEmbedding; 42501 -> ErroDeConfiguracao

# connection/_unidade.py -----------------------------------------------------
@contextmanager
def unidade_de_trabalho(provedor: ProvedorDeConexao) -> Iterator[Cursor]: ...
    # autocommit verdadeiro -> ErroDeConfiguracao, antes do primeiro execute
    # PROPRIA: commit no sucesso, rollback em qualquer exceção; PARTICIPAR: nenhum dos dois
    # exceção do driver -> traduzir(); sem tradução, sobe a original (nunca engolida)

# connection/dsn.py -----------------------------------------------------------
class ProvedorDSN:
    modo_de_transacao: ModoDeTransacao      # sempre PROPRIA
    def __init__(self, dsn: str) -> None: ...   # import psycopg aqui; ausente -> ErroExtraNaoInstalado
    def conexao(self) -> AbstractContextManager[Conexao]: ...   # autocommit=False, fecha ao sair

# embeddings/__init__.py ------------------------------------------------------
def vetorizar(provedor: ProvedorDeEmbeddings, textos: Sequence[str]) -> list[list[float]]: ...
    # exceção do provedor -> ErroDeEmbedding (from erro); contagem ou tamanho errado -> ErroDeDimensaoDeEmbedding

# store.py ------------------------------------------------------------------
def inserir(cur: Cursor, f: Filtro, *, memoria_id: str | None, conteudo: str, categoria: str,
            entidade_id: str | None, contexto_id: str | None, origem: str | None,
            vetor: str, modelo: str, valido_de: datetime, valido_ate: datetime | None,
            registrado_em: datetime, versao_anterior_id: str | None) -> VersaoDeMemoria: ...
def buscar_vigente(cur: Cursor, f: Filtro, memoria_id: str) -> VersaoDeMemoria: ...   # ErroNaoEncontrado
def fechar_registro(cur: Cursor, f: Filtro, versao_id: str, agora: datetime) -> None: ...  # rowcount != 1 -> ErroDeConflito
def inserir_copia_limitada(cur: Cursor, f: Filtro, origem_id: str, valido_ate: datetime,
                           agora: datetime) -> VersaoDeMemoria: ...
def encerrar_contexto(cur: Cursor, f: Filtro, contexto_id: str, valido_ate: datetime,
                      agora: datetime) -> int: ...
def apagar(cur: Cursor, f: Filtro, *, memoria_id: str | None, entidade_id: str | None,
           tudo: bool) -> int: ...
def ler_dimensao(cur: Cursor, schema: str) -> int: ...     # tabela ausente -> ErroDeConfiguracao

# retrieval.py ----------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class EixoDeEscopo:
    ids: tuple[str, ...]
    incluir_nulo: bool

def montar_eixo(valores: Sequence[str | None] | None) -> EixoDeEscopo | None: ...
    # None -> None (sem filtro); [] -> EixoDeEscopo((), False); ["a", None] -> (("a",), True)
def recuperar(cur: Cursor, f: Filtro, momento: Momento, *, vetor_consulta: str | None,
              contextos: EixoDeEscopo | None, entidades: EixoDeEscopo | None,
              categoria: str | None, limite: int) -> list[ResultadoDeRecuperacao]: ...
def historico(cur: Cursor, f: Filtro, memoria_id: str) -> list[VersaoDeMemoria]: ...  # vazio -> ErroNaoEncontrado

# migrations/__init__.py --------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Migracao:
    numero: int
    nome: str
    sha256: str              # do arquivo cru
    sql: str

def descobrir() -> list[Migracao]: ...          # importlib.resources; número repetido -> ErroDeMigracao
def aplicar(cur: Cursor, schema: str, dimensao: int) -> int: ...
    # pg_advisory_xact_lock(hashtext(schema)); hash divergente -> ErroDeMigracao;
    # dimensão registrada != dimensao -> ErroDeDimensaoDeEmbedding

# api.py (só o que muda além dos corpos) ----------------------------------------
class Memoria:
    _filtro_tabela: str                 # citada uma vez no __init__ (schema validado ali)
    _dimensao_conferida: bool           # a primeira operação lê `configuracao.dimensao` e guarda
```

## Pilha de chamadas

`f` é `Filtro(tabela, tenant_id, dono_id)`. Toda instrução abaixo termina com
`AND tenant_id = %s AND dono_id = %s`, exceto as de migração.

**lembrar**
1. `temporal.exigir_fuso` × 2; conteúdo e categoria não vazios; `agora = resolver_agora`;
   `valido_de = valido_de or agora`; `exigir_intervalo`.
2. `vetorizar(embeddings, [conteudo])` → `vetor_como_texto`. **Antes da conexão.**
3. `with unidade_de_trabalho(provedor) as cur:` → `_conferir_dimensao(cur)` (só na primeira vez) →
   `store.inserir(...)`:
   `INSERT INTO {t} (memoria_id, tenant_id, dono_id, categoria, conteudo, entidade_id, contexto_id, origem, embedding, modelo_embedding, valido_de, valido_ate, registrado_em, versao_anterior_id) VALUES (COALESCE(%s::uuid, gen_random_uuid()), %s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s, %s::uuid) RETURNING {COLUNAS}`

**substituir**
1. Fuso, conteúdo; `agora`; `inicio = valido_de or agora`.
2. `vetorizar` do conteúdo novo. **Antes da conexão.**
3. Na unidade:
   - `vigente = store.buscar_vigente` →
     `SELECT {COLUNAS} FROM {t} WHERE memoria_id = %s::uuid AND substituido_em IS NULL AND tenant_id = %s AND dono_id = %s ORDER BY valido_de DESC LIMIT 1`.
   - Se `versao_esperada_id` diverge, `ErroDeConflito`.
   - `temporal.exigir_fechamento_de_validade(vigente, inicio)`.
   - `store.fechar_registro(vigente.versao_id, agora)` →
     `UPDATE {t} SET substituido_em = %s WHERE versao_id = %s::uuid AND substituido_em IS NULL AND tenant_id = %s AND dono_id = %s`.
     `rowcount != 1` dá `ErroDeConflito`.
   - `copia = store.inserir_copia_limitada(vigente.versao_id, inicio, agora)` →
     `INSERT INTO {t} (…) SELECT memoria_id, tenant_id, dono_id, categoria, conteudo, entidade_id, contexto_id, origem, embedding, modelo_embedding, valido_de, %s, %s, versao_id FROM {t} WHERE versao_id = %s::uuid AND tenant_id = %s AND dono_id = %s RETURNING {COLUNAS}`.
   - `store.inserir(memoria_id=vigente.memoria_id, …herdados…, valido_de=inicio, valido_ate=None, registrado_em=agora, versao_anterior_id=copia.versao_id)`.
4. Devolve a nova.

**corrigir.** Como substituir, sem a cópia. Insere a certa com `vigente.valido_de`,
`vigente.valido_ate` e `versao_anterior_id = vigente.versao_id`.

**encerrar.** Sem embedding. Na unidade: `buscar_vigente`, depois a conferência de
`versao_esperada_id`, depois `exigir_fechamento_de_validade(vigente, fim)`, depois
`fechar_registro`, depois `inserir_copia_limitada(fim)`. Devolve a cópia.

**invalidar_contexto.** Sem embedding, uma instrução:
```sql
WITH fechadas AS (
  UPDATE {t} SET substituido_em = %(agora)s
  WHERE contexto_id = %(ctx)s AND substituido_em IS NULL AND valido_ate IS NULL
    AND valido_de < %(fim)s AND tenant_id = %(tenant)s AND dono_id = %(dono)s
  RETURNING *)
INSERT INTO {t} (…) SELECT memoria_id, …, valido_de, %(fim)s, %(agora)s, versao_id FROM fechadas
RETURNING 1
```
Devolve `cur.rowcount`.

**esquecer.** Primeiro valida que há exatamente um alvo. Depois, uma instrução:
- por memória: `DELETE FROM {t} WHERE memoria_id = %s::uuid AND tenant_id = %s AND dono_id = %s`. Um id que não é uuid devolve `0` sem ir ao banco;
- por entidade: `DELETE FROM {t} WHERE memoria_id IN (SELECT memoria_id FROM {t} WHERE entidade_id = %s AND tenant_id = %s AND dono_id = %s) AND tenant_id = %s AND dono_id = %s`;
- tudo: `DELETE FROM {t} WHERE tenant_id = %s AND dono_id = %s`.

Devolve `cur.rowcount`.

**recuperar.** Primeiro valida `limite >= 1` e o fuso. Depois `momento = resolver_momento`
e os escopos `montar_eixo` × 2. Com `consulta`, faz `vetorizar` **antes da conexão**.
Na unidade, `retrieval.recuperar` monta:
```sql
SELECT {COLUNAS}[, 1 - (embedding <=> %s::vector) / 2]
FROM {t} WHERE tenant_id = %s AND dono_id = %s AND {PREDICADO[modo]}
  [AND (contexto_id = ANY(%s::text[]) OR (%s AND contexto_id IS NULL))]
  [AND (entidade_id = ANY(%s::text[]) OR (%s AND entidade_id IS NULL))]
  [AND categoria = %s]
ORDER BY [embedding <=> %s::vector,] registrado_em DESC, versao_id
LIMIT %s
```
`versao_id` no fim do `ORDER BY` desempata e torna a ordem determinística.

**historico.** `SELECT {COLUNAS} FROM {t} WHERE memoria_id = %s::uuid AND tenant_id = %s AND dono_id = %s ORDER BY registrado_em, valido_de, versao_id`.
Sem linhas, `ErroNaoEncontrado`.

**migrar.** `validar_schema` já rodou no `__init__`. Na unidade:
1. `SELECT pg_advisory_xact_lock(hashtext(%s))`.
2. `SELECT 1 FROM pg_extension WHERE extname = 'vector'`. Se não houver,
   `CREATE EXTENSION IF NOT EXISTS vector`, e `42501` vira `ErroDeConfiguracao`.
3. `CREATE SCHEMA IF NOT EXISTS "{schema}"` e a tabela `versao_do_schema`.
4. Lê as aplicadas. Hash divergente dá `ErroDeMigracao`.
5. Para cada pendente, executa o SQL renderizado (`{schema}` citado, `{dimensao}` como int)
   e grava em `versao_do_schema`. A `0001` grava `configuracao('dimensao', N)` e
   `ON CONFLICT DO NOTHING`.
6. Confere a dimensão registrada contra `embeddings.dimensao`.
7. Devolve quantas aplicou.

## Plano de testes

Unidade, sem banco (rodam sempre):

| teste | afirma |
|---|---|
| `test_temporal.py::test_datetime_sem_fuso_e_recusado` | `exigir_fuso` levanta `ErroDeArgumentoInvalido` |
| `…::test_como_em_e_sabido_em_juntos_sao_recusados` | `resolver_momento` levanta |
| `…::test_sem_instante_e_como_em_agora` | o modo agora é `como_em(agora)` |
| `…::test_intervalos_sao_semiabertos` | `vale_em` na borda de `valido_ate` e de `substituido_em` |
| `…::test_encerrar_vigente_ja_encerrada_conflita` | `exigir_fechamento_de_validade` levanta `ErroDeConflito` |
| `…::test_fim_antes_do_inicio_e_argumento_invalido` | idem com `ErroDeArgumentoInvalido` |
| `test_status_derivation.py` (existe, 7 casos) | a tabela do ADR 0002 |
| `test_sql.py::test_schema_invalido_e_recusado` | `validar_schema('x; drop')` levanta `ErroDeConfiguracao` |
| `…::test_vetor_vai_como_texto_sem_perder_precisao` | ida e volta de float por `repr` |
| `…::test_sqlstate_de_psycopg2_e_psycopg3` | os dois atributos lidos |
| `…::test_unique_violation_vira_conflito` | `traduzir` de `23505` |
| `test_embeddings_falsos.py::test_mesmo_texto_mesmo_vetor` | determinismo |
| `…::test_vetor_tem_norma_um_e_a_dimensao_pedida` | norma e tamanho |
| `…::test_falha_do_provedor_vira_erro_de_embedding` | `vetorizar` embrulha e encadeia |
| `…::test_tamanho_errado_vira_erro_de_dimensao` | `vetorizar` confere |
| `test_migrations.py::test_numero_repetido_e_recusado` | `descobrir` levanta `ErroDeMigracao` |

Integração, contra Postgres (`MEMORY_LIFECYCLE_DSN_TESTE`; cada teste num schema
próprio, apagado no teardown):

| teste | afirma |
|---|---|
| `test_migracao.py::test_aplicar_do_zero_duas_vezes` | 1ª chamada devolve 1, 2ª devolve 0, `pg_catalog` igual |
| `…::test_hash_alterado_e_recusado` | grava hash falso em `versao_do_schema`, `migrar` levanta `ErroDeMigracao` |
| `…::test_outra_dimensao_e_recusada` | `migrar` com `dimensao=16` depois de 8 levanta `ErroDeDimensaoDeEmbedding` |
| `…::test_operar_sem_migrar_e_erro_de_configuracao` | `lembrar` num schema vazio |
| `…::test_duas_migracoes_simultaneas` | duas threads, uma aplica e a outra devolve 0 |
| `test_transacao.py::test_participar_com_autocommit_e_recusado` | `ErroDeConfiguracao`, nada gravado |
| `…::test_propria_com_autocommit_e_recusado` | idem |
| `…::test_participar_some_com_o_rollback_do_app` | o app faz rollback, `recuperar` não acha |
| `…::test_propria_faz_rollback_no_erro_do_meio` | falha injetada entre o `UPDATE` e o `INSERT` de `substituir` não deixa nada pela metade |
| `…::test_embedding_antes_da_conexao` | provedor espião: `gerar` falha e `conexao()` nunca foi chamada |
| `test_concorrencia.py::test_duas_substituicoes_em_duas_conexoes` | duas threads presas numa barreira; uma vence, a outra `ErroDeConflito`; `historico` tem 3 linhas |
| `test_coerencia.py::test_sql_concorda_com_o_oraculo` | 200 históricos aleatórios (semente fixa) × instantes aleatórios: `recuperar` devolve exatamente as versões com `vale_em` verdadeiro, nos três modos |
| `test_paridade.py` | o módulo `tests/acceptance` roda parametrizado com psycopg 3 e psycopg2 |
| `tests/acceptance/*` (16 cenários, existem) | isolamento, cada operação × três modos, escopo, conflito, esquecer |

Guardas (rodam sempre):

| teste | afirma |
|---|---|
| `test_tenant_filter.py` | toda string SQL em `store.py` e `retrieval.py` com `FROM {`, `UPDATE {`, `INSERT INTO {` ou `DELETE FROM {` contém `tenant_id` e `dono_id`; varre por AST |
| `test_migrations_append_only.py` | todo arquivo listado em `aplicadas.txt` tem o hash registrado; um número no manifesto sem arquivo falha |

A paridade de adaptadores (Django, SQLAlchemy, pool) entra nas fatias da Etapa 6,
com o mesmo módulo de aceitação parametrizado.

## Decisões em que tenho menos confiança

1. **Oráculo em Python (`temporal.vale_em`) duplicando o predicado SQL.** É uma
   segunda implementação da mesma regra. A alternativa é testar só pelos cenários. Eu
   mantenho: o teste de coerência com 200 históricos aleatórios acha bordas que 16
   cenários não acham. O preço é manter os dois em sincronia, e o próprio teste
   garante isso.
2. **`ErroDeConflito` quando se substitui uma memória já encerrada.** Um app pode
   achar natural "reabrir com conteúdo novo". Escolhi a recusa, com mensagem
   "use lembrar", para manter "só se fecha o que está aberto".
3. **`esquecer` por memória com id que não é uuid devolve 0 sem ir ao banco.** Isso
   evita o erro `22P02` do Postgres. A alternativa é levantar
   `ErroDeArgumentoInvalido`. Escolhi o 0 pela spec ("alvo desconhecido devolve
   zero").
4. **Manifesto `aplicadas.txt` para a guarda append-only.** A guarda não tem banco,
   então precisa de um registro no repo dos hashes publicados. O manifesto é
   atualizado na fatia de release, e esquecer de atualizar deixa a guarda cega para
   o arquivo novo.
5. **Schema isolado por teste.** Criar e apagar um schema por teste custa cerca de
   30 ms. São cerca de 60 testes de integração, o que soma 2 s. A alternativa,
   rollback por teste, não funciona com o modo `PROPRIA` nem com a concorrência.
6. **`ORDER BY registrado_em DESC` sem consulta.** Isso põe primeiro a crença
   registrada mais recentemente, e não a de `valido_de` mais recente. Num
   encerramento retroativo, a cópia aparece antes de memórias mais novas no mundo.
   É aceitável para uma lista sem consulta textual.
