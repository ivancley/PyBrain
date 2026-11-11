# Conceitos

O que a memory-lifecycle guarda, como ela pensa o tempo e o que cada operação
faz. Os termos vêm de `docs/glossario.md` (prosa em português, identificadores do
código em inglês); as decisões e as alternativas que perderam, de `docs/adr/`.

Os trechos de código deste guia rodam em sequência na suíte
(`tests/integration/test_guides.py`), contra um PostgreSQL de verdade. Neles,
`memory` é uma `Memory` já migrada e `clock` é um relógio de teste que
avançamos à mão; em produção, a biblioteca usa a hora atual.

## Memória, versão e quem é dono

Uma **memória** é um fato sobre alguém: "prefere respostas curtas", "trabalha no
projeto X". Ela pertence a um **dono** (`owner_id`: um usuário, um agente) dentro
de um **tenant** (a organização), e pode ser sobre uma **entidade** (`entity_id`)
e valer num **contexto** (`context_id`). Entidade e contexto são ids opacos: a
biblioteca não sabe o que significam, só filtra por eles.

Cada mudança numa memória vira uma **versão** nova. Uma versão nunca é
reescrita: o único campo que muda numa linha, depois de gravada, é o fim do seu
tempo de registro.

```python
v1 = memory.remember("owner-1", "prefere respostas curtas", kind="preference")
assert v1.previous_version_id is None
assert v1.valid_to is None and v1.superseded_at is None  # aberta nos dois eixos
```

## Os dois eixos de tempo

Toda versão responde a duas perguntas diferentes:

| eixo | campos | pergunta |
|---|---|---|
| **validade** | `valid_from`, `valid_to` | quando o fato era verdade no mundo? |
| **registro** | `recorded_at`, `superseded_at` | quando o sistema acreditava nesta versão? |

`None` num fim quer dizer **aberto**, nunca "desconhecido". Os intervalos são
semiabertos: `[valid_from, valid_to)`. No instante exato de uma troca, vale a
versão nova.

Os dois eixos se separam quando a aplicação fica sabendo de algo depois que
aconteceu: em julho, descobre-se que um fato deixou de valer em março. A
validade termina em março; o registro mostra que até julho o sistema não sabia.

## As três operações

Três situações que parecem iguais de longe, e que a biblioteca trata de jeitos
diferentes. As três fecham o registro da versão vigente e inserem versões novas.

| operação | situação | o que fica |
|---|---|---|
| `expire` (encerrar) | o fato era verdade e deixou de ser | uma cópia da vigente com `valid_to` |
| `supersede` (substituir) | um fato novo toma o lugar do antigo | a cópia com `valid_to`, e a nova a partir dali |
| `correct` (corrigir) | o fato nunca foi verdade: foi gravado errado | a certa, com os mesmos limites de validade |

```python
clock.advance(days=150)  # junho
v2 = memory.supersede("owner-1", v1.memory_id, "prefere respostas detalhadas")
original, copy, new = memory.history("owner-1", v1.memory_id)
assert original.superseded_at == clock()   # a original saiu do registro em junho
assert copy.valid_to == clock()            # a cópia diz: valeu até junho
assert new == v2 and v2.previous_version_id == copy.version_id
```

Um fato que deixa de valer sem dar lugar a outro é um `expire`:

```python
lives = memory.remember("owner-1", "mora em Lisboa", kind="fact")
clock.advance(days=30)  # julho
expired = memory.expire("owner-1", lives.memory_id)
assert expired.valid_to == clock()
```

E um fato gravado errado é um `correct`: a validade não muda, só o registro.

```python
wrong = memory.remember("owner-1", "nasceu em 1990", kind="fact")
clock.advance(days=10)
right = memory.correct("owner-1", wrong.memory_id, "nasceu em 1991")
assert (right.valid_from, right.valid_to) == (wrong.valid_from, wrong.valid_to)
```

## Os três modos de consulta

`recall` responde em um de três modos:

| modo | pergunta |
|---|---|
| agora (sem argumento) | o que é verdade agora? |
| `as_of=D` (como em) | o que era verdade em D, pelo que sabemos hoje? |
| `known_at=D` (sabido em) | o que, em D, o sistema sabia ser verdade em D? |

`known_at` é a pergunta da auditoria: o que o agente sabia quando respondeu.
Uma correção muda `as_of` para trás; não muda `known_at`.

```python
def contents(**moment):
    return {r.version.content for r in memory.recall("owner-1", **moment)}

march, mid_june = clock.at(days=60), clock.at(days=160)
assert "prefere respostas curtas" in contents(as_of=march)        # era verdade em março
assert "prefere respostas detalhadas" in contents()               # é verdade agora
assert "mora em Lisboa" in contents(as_of=mid_june)               # morava entre junho e julho
assert "mora em Lisboa" not in contents()                         # não mora mais

yesterday = clock.at(days=185)   # entre a gravação errada e a correção
assert "nasceu em 1991" in contents(as_of=yesterday)     # pelo que sabemos hoje
assert "nasceu em 1990" in contents(known_at=yesterday)  # o que se sabia então
```

`as_of` e `known_at` juntos são recusados com `InvalidArgumentError`.

## O escopo é da aplicação

Quais contextos e entidades estão ativos numa conversa é um dado da aplicação,
não da memória. `recall` recebe esse **escopo** e filtra por ele, de forma
estrita:

| argumento | o que entra naquele eixo |
|---|---|
| `contexts=None` (padrão) | tudo: não filtra |
| `contexts=["p-2027"]` | só as versões do contexto `p-2027` |
| `contexts=["p-2027", None]` | as de `p-2027` e as sem contexto |
| `contexts=[]` | nada |

A mesma regra vale para `entities`. Tirar um id do escopo não apaga nem encerra
nada: a memória volta quando o id volta. Para dizer que um contexto **acabou**,
há uma escrita explícita, `invalidate_context`.

```python
memory.remember("owner-1", "o período 2026 teve atraso", kind="note", context_id="p-2026")
assert not any(
    r.version.context_id == "p-2026"
    for r in memory.recall("owner-1", contexts=["p-2027", None])
)
assert memory.invalidate_context("owner-1", "p-2026") == 1
```

## Status, histórico e esquecer

O status de uma versão (`ACTIVE`, `EXPIRED`, `SUPERSEDED`, `CORRECTED` — ativa,
encerrada, substituída, corrigida) nunca é guardado: `derive_status` o calcula a
partir dos limites e da versão seguinte, que é a que aponta para ela em
`previous_version_id`.

```python
from memory_lifecycle import Status, derive_status

history = memory.history("owner-1", wrong.memory_id)
successors = {v.previous_version_id: v for v in history}
statuses = [derive_status(v, now=clock(), successor=successors.get(v.version_id)) for v in history]
assert statuses == [Status.CORRECTED, Status.ACTIVE]
```

`forget` (esquecer) é o único apagamento físico, para pedidos de privacidade:
apaga toda versão do alvo, inclusive o histórico de auditoria. O alvo é
exatamente um entre uma memória (`memory_id`), uma entidade (`entity_id`) ou tudo
do dono (`everything=True`).

```python
assert memory.forget("owner-1", memory_id=wrong.memory_id) == 2
assert "nasceu em 1990" not in contents(known_at=yesterday)
```

## Concorrência e erros

Duas escritas sobre a mesma versão nunca vencem as duas: a segunda levanta
`ConflictError`. Para garantir que você substitui o que leu, passe
`expected_version_id`.

| erro | quando | o que fazer |
|---|---|---|
| `InvalidArgumentError` | entrada que o contrato proíbe | corrigir a chamada |
| `NotFoundError` | id desconhecido, de outro dono ou de outro tenant | não diz qual, de propósito |
| `ConflictError` | outra escrita chegou antes, ou a vigente já estava encerrada | reler com `history` e decidir |
| `EmbeddingError` | o provedor de embeddings falhou | tentar de novo ou desistir |
| `EmbeddingDimensionError` | o provedor gera outra dimensão que a do schema | usar o provedor original ou outro schema |
| `ConfigurationError` | schema não migrado, autocommit, pgvector ausente | seguir a mensagem |
| `MigrationError` | migração aplicada mudou ou é desconhecida | atualizar a biblioteca; nunca editar migração |

Todos herdam de `MemoryLifecycleError`. As entradas inválidas são recusadas antes
de qualquer instrução no banco, para não abortar a transação da aplicação. As
mensagens de erro são em inglês.
