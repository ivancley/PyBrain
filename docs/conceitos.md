# Conceitos

O que a memory-lifecycle guarda, como ela pensa o tempo e o que cada operação
faz. Os termos vêm de `docs/glossario.md`; as decisões e as alternativas que
perderam, de `docs/adr/`.

Os trechos de código deste guia rodam em sequência na suíte
(`tests/integration/test_guias.py`), contra um PostgreSQL de verdade. Neles,
`memoria` é uma `Memoria` já migrada e `relogio` é um relógio de teste que
avançamos à mão; em produção, a biblioteca usa a hora atual.

## Memória, versão e quem é dono

Uma **memória** é um fato sobre alguém: "prefere respostas curtas", "trabalha no
projeto X". Ela pertence a um **dono** (um usuário, um agente) dentro de um
**tenant** (a organização), e pode ser sobre uma **entidade** e valer num
**contexto**. Entidade e contexto são ids opacos: a biblioteca não sabe o que
significam, só filtra por eles.

Cada mudança numa memória vira uma **versão** nova. Uma versão nunca é
reescrita: o único campo que muda numa linha, depois de gravada, é o fim do seu
tempo de registro.

```python
v1 = memoria.lembrar("dono-1", "prefere respostas curtas", categoria="preferencia")
assert v1.versao_anterior_id is None
assert v1.valido_ate is None and v1.substituido_em is None  # aberta nos dois eixos
```

## Os dois eixos de tempo

Toda versão responde a duas perguntas diferentes:

| eixo | campos | pergunta |
|---|---|---|
| **validade** | `valido_de`, `valido_ate` | quando o fato era verdade no mundo? |
| **registro** | `registrado_em`, `substituido_em` | quando o sistema acreditava nesta versão? |

`None` num fim quer dizer **aberto**, nunca "desconhecido". Os intervalos são
semiabertos: `[valido_de, valido_ate)`. No instante exato de uma troca, vale a
versão nova.

Os dois eixos se separam quando a aplicação fica sabendo de algo depois que
aconteceu: em julho, descobre-se que um fato deixou de valer em março. A
validade termina em março; o registro mostra que até julho o sistema não sabia.

## As três operações

Três situações que parecem iguais de longe, e que a biblioteca trata de jeitos
diferentes. As três fecham o registro da versão vigente e inserem versões novas.

| operação | situação | o que fica |
|---|---|---|
| `encerrar` | o fato era verdade e deixou de ser | uma cópia da vigente com `valido_ate` |
| `substituir` | um fato novo toma o lugar do antigo | a cópia com `valido_ate`, e a nova a partir dali |
| `corrigir` | o fato nunca foi verdade: foi gravado errado | a certa, com os mesmos limites de validade |

```python
relogio.avancar(days=150)  # junho
v2 = memoria.substituir("dono-1", v1.memoria_id, "prefere respostas detalhadas")
original, copia, nova = memoria.historico("dono-1", v1.memoria_id)
assert original.substituido_em == relogio()   # a original saiu do registro em junho
assert copia.valido_ate == relogio()          # a cópia diz: valeu até junho
assert nova == v2 and v2.versao_anterior_id == copia.versao_id
```

Um fato que deixa de valer sem dar lugar a outro é um `encerrar`:

```python
mora = memoria.lembrar("dono-1", "mora em Lisboa", categoria="fato")
relogio.avancar(days=30)  # julho
encerrada = memoria.encerrar("dono-1", mora.memoria_id)
assert encerrada.valido_ate == relogio()
```

E um fato gravado errado é um `corrigir`: a validade não muda, só o registro.

```python
errada = memoria.lembrar("dono-1", "nasceu em 1990", categoria="fato")
relogio.avancar(days=10)
certa = memoria.corrigir("dono-1", errada.memoria_id, "nasceu em 1991")
assert (certa.valido_de, certa.valido_ate) == (errada.valido_de, errada.valido_ate)
```

## Os três modos de consulta

`recuperar` responde em um de três modos:

| modo | pergunta |
|---|---|
| agora (sem argumento) | o que é verdade agora? |
| `como_em=D` | o que era verdade em D, pelo que sabemos hoje? |
| `sabido_em=D` | o que, em D, o sistema sabia ser verdade em D? |

`sabido_em` é a pergunta da auditoria: o que o agente sabia quando respondeu.
Uma correção muda `como_em` para trás; não muda `sabido_em`.

```python
def conteudos(**momento):
    return {r.versao.conteudo for r in memoria.recuperar("dono-1", **momento)}

marco, meados_de_junho = relogio.em(days=60), relogio.em(days=160)
assert "prefere respostas curtas" in conteudos(como_em=marco)        # era verdade em março
assert "prefere respostas detalhadas" in conteudos()                 # é verdade agora
assert "mora em Lisboa" in conteudos(como_em=meados_de_junho)        # morava entre junho e julho
assert "mora em Lisboa" not in conteudos()                           # não mora mais

ontem = relogio.em(days=185)   # entre a gravação errada e a correção
assert "nasceu em 1991" in conteudos(como_em=ontem)    # pelo que sabemos hoje
assert "nasceu em 1990" in conteudos(sabido_em=ontem)  # o que se sabia então
```

`como_em` e `sabido_em` juntos são recusados com `ErroDeArgumentoInvalido`.

## O escopo é da aplicação

Quais contextos e entidades estão ativos numa conversa é um dado da aplicação,
não da memória. `recuperar` recebe esse **escopo** e filtra por ele, de forma
estrita:

| argumento | o que entra naquele eixo |
|---|---|
| `contextos=None` (padrão) | tudo: não filtra |
| `contextos=["p-2027"]` | só as versões do contexto `p-2027` |
| `contextos=["p-2027", None]` | as de `p-2027` e as sem contexto |
| `contextos=[]` | nada |

A mesma regra vale para `entidades`. Tirar um id do escopo não apaga nem encerra
nada: a memória volta quando o id volta. Para dizer que um contexto **acabou**,
há uma escrita explícita, `invalidar_contexto`.

```python
memoria.lembrar("dono-1", "o período 2026 teve atraso", categoria="nota", contexto_id="p-2026")
assert not any(
    r.versao.contexto_id == "p-2026"
    for r in memoria.recuperar("dono-1", contextos=["p-2027", None])
)
assert memoria.invalidar_contexto("dono-1", "p-2026") == 1
```

## Status, histórico e esquecer

O status de uma versão (`ATIVA`, `ENCERRADA`, `SUBSTITUIDA`, `CORRIGIDA`) nunca é
guardado: `derivar_status` o calcula a partir dos limites e da versão seguinte,
que é a que aponta para ela em `versao_anterior_id`.

```python
from memory_lifecycle import Status, derivar_status

historico = memoria.historico("dono-1", errada.memoria_id)
sucessoras = {v.versao_anterior_id: v for v in historico}
status = [derivar_status(v, agora=relogio(), sucessora=sucessoras.get(v.versao_id)) for v in historico]
assert status == [Status.CORRIGIDA, Status.ATIVA]
```

`esquecer` é o único apagamento físico, para pedidos de privacidade: apaga toda
versão do alvo, inclusive o histórico de auditoria. O alvo é exatamente um entre
uma memória, uma entidade ou tudo do dono.

```python
assert memoria.esquecer("dono-1", memoria_id=errada.memoria_id) == 2
assert "nasceu em 1990" not in conteudos(sabido_em=ontem)
```

## Concorrência e erros

Duas escritas sobre a mesma versão nunca vencem as duas: a segunda levanta
`ErroDeConflito`. Para garantir que você substitui o que leu, passe
`versao_esperada_id`.

| erro | quando | o que fazer |
|---|---|---|
| `ErroDeArgumentoInvalido` | entrada que o contrato proíbe | corrigir a chamada |
| `ErroNaoEncontrado` | id desconhecido, de outro dono ou de outro tenant | não diz qual, de propósito |
| `ErroDeConflito` | outra escrita chegou antes, ou a vigente já estava encerrada | reler com `historico` e decidir |
| `ErroDeEmbedding` | o provedor de embeddings falhou | tentar de novo ou desistir |
| `ErroDeDimensaoDeEmbedding` | o provedor gera outra dimensão que a do schema | usar o provedor original ou outro schema |
| `ErroDeConfiguracao` | schema não migrado, autocommit, pgvector ausente | seguir a mensagem |
| `ErroDeMigracao` | migração aplicada mudou ou é desconhecida | atualizar a biblioteca; nunca editar migração |

Todos herdam de `ErroMemoryLifecycle`. As entradas inválidas são recusadas antes
de qualquer instrução no banco, para não abortar a transação da aplicação.
