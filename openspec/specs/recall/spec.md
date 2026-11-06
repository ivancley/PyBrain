# recall Specification

## Purpose
Devolver as memórias certas para o escopo que a aplicação passa e o momento sobre o qual ela pergunta.

## Requirements

### Requirement: O escopo é passado pela aplicação, é estrito e filtra sem escrever
A biblioteca DEVE devolver uma versão só quando o seu contexto está nos contextos passados e a sua entidade está nas entidades passadas; uma versão sem contexto (ou sem entidade) só entra quando o eixo correspondente inclui `None` como membro; não passar nada num eixo significa nenhum filtro nele; passar uma lista vazia não devolve nada naquele eixo. Recuperar nunca escreve.

#### Scenario: entidade sai e volta ao escopo
- **WHEN** existe uma memória sobre uma entidade e a aplicação recupera com essa entidade fora das entidades passadas, depois recupera de novo com ela dentro
- **THEN** a primeira recuperação não a devolve, a segunda devolve, e o histórico da memória não muda entre as duas

#### Scenario: contexto de um período anterior
- **WHEN** existem memórias num contexto de um período e a aplicação recupera passando só o contexto do período seguinte
- **THEN** nenhuma memória do período anterior é devolvida, e recuperar com o contexto anterior as devolve

#### Scenario: memória sem contexto só entra quando o escopo inclui None
- **WHEN** existe uma memória sem contexto e a aplicação recupera com `contextos=["p-2027"]`, depois com `contextos=["p-2027", None]`, depois com `contextos=None`
- **THEN** a primeira recuperação não a devolve, a segunda devolve e a terceira devolve

#### Scenario: lista vazia não devolve nada naquele eixo
- **WHEN** existem memórias com e sem contexto e a aplicação recupera com `contextos=[]`
- **THEN** nenhuma memória é devolvida

#### Scenario: mesma regra para entidades
- **WHEN** existe uma memória sem entidade e a aplicação recupera com `entidades=["e-1"]`, depois com `entidades=["e-1", None]`
- **THEN** a primeira recuperação não a devolve e a segunda devolve

### Requirement: Três modos de consulta
A biblioteca DEVE responder "o que é verdade agora" quando nenhum instante é dado, "o que era verdade no instante, pelo que se sabe hoje" com como em, e "o que, naquele instante, o sistema sabia ser verdade naquele instante" com sabido em; dar os dois DEVE levantar um erro de argumento inválido.

#### Scenario: os três modos discordam sobre um histórico
- **WHEN** uma memória foi lembrada em janeiro, substituída em junho e a sucessora corrigida em julho
- **THEN** recuperar agora devolve o conteúdo corrigido, recuperar como em março devolve o conteúdo de janeiro, recuperar como em 15 de junho devolve o conteúdo corrigido, recuperar sabido em maio devolve o conteúdo de janeiro, e recuperar sabido em 15 de junho devolve só o conteúdo da substituição

#### Scenario: os dois instantes dados
- **WHEN** a aplicação recupera com como em e sabido em juntos
- **THEN** um erro de argumento inválido é levantado

### Requirement: Similaridade, filtros, limite e ordenação
A biblioteca DEVE ordenar por similaridade com a consulta quando uma é dada, carregando uma pontuação por resultado, e por instante de registro decrescente caso contrário; DEVE filtrar por categoria quando dada; e DEVE sempre aplicar um limite positivo.

#### Scenario: recuperar com consulta
- **WHEN** a aplicação recupera com um texto de consulta
- **THEN** todo resultado carrega uma pontuação entre zero e um e os resultados vêm ordenados por pontuação decrescente

#### Scenario: recuperar sem consulta
- **WHEN** a aplicação recupera sem consulta
- **THEN** nenhum resultado tem pontuação e os resultados vêm ordenados por instante de registro decrescente

#### Scenario: limite não positivo
- **WHEN** a aplicação recupera com limite zero
- **THEN** um erro de argumento inválido é levantado
