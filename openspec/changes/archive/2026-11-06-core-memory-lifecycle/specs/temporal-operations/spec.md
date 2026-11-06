# Spec Delta

## Purpose
As três operações que mudam o que é verdade ou o que se acreditava, o seu efeito nos dois eixos de tempo, e o que acontece quando dois escritores competem.

## ADDED Requirements

### Requirement: Toda operação fecha o registro da vigente e insere
A biblioteca DEVE executar encerrar, corrigir e substituir fechando o tempo de registro da versão vigente e inserindo versões novas, e DEVE nunca alterar outro campo de uma versão armazenada, de modo que o que o sistema sabia num instante nunca seja reescrito depois dele.

#### Scenario: encerramento retroativo não reescreve o que se sabia
- **WHEN** uma memória lembrada em janeiro é encerrada em julho com válido até em março
- **THEN** recuperar como em abril não a devolve, e recuperar sabido em maio a devolve

### Requirement: Encerrar registra o fim da validade numa versão nova
A biblioteca DEVE fechar o registro da versão vigente e inserir uma cópia dela com válido até no instante dado ou no atual.

#### Scenario: memória encerrada sai do presente e fica no passado
- **WHEN** uma memória lembrada em janeiro é encerrada em junho
- **THEN** recuperar agora não a devolve, recuperar como em março devolve a cópia encerrada, recuperar sabido em maio devolve a versão de janeiro, e o histórico tem duas versões

#### Scenario: encerrar duas vezes conflita
- **WHEN** a versão vigente já tem válido até fechado e a aplicação a encerra de novo
- **THEN** um erro de conflito é levantado

### Requirement: Corrigir fecha o tempo de registro e mantém o de validade
A biblioteca DEVE fechar o tempo de registro da versão vigente e inserir uma versão nova com o conteúdo dado e os mesmos limites de validade, ligada à corrigida.

#### Scenario: fato corrigido some do passado e fica no registro
- **WHEN** uma memória lembrada em janeiro com conteúdo errado é corrigida em junho
- **THEN** recuperar agora devolve o conteúdo certo, recuperar como em março devolve o conteúdo certo, e recuperar sabido em maio devolve o conteúdo errado

### Requirement: Substituir encerra a antiga e liga a versão nova
A biblioteca DEVE fechar o registro da versão vigente e inserir a cópia dela com válido até no instante dado ou no atual e uma versão nova válida desde esse instante, ligada à cópia, herdando categoria, entidade, contexto e origem quando não dados.

#### Scenario: fato substituído muda o presente e mantém o passado
- **WHEN** uma memória lembrada em janeiro é substituída em junho com conteúdo novo
- **THEN** recuperar agora devolve o conteúdo novo, recuperar como em março devolve o conteúdo antigo, e recuperar sabido em maio devolve o conteúdo antigo

#### Scenario: substituir herda o escopo da versão antiga
- **WHEN** uma memória com entidade e contexto é substituída sem dá-los
- **THEN** a versão nova tem a mesma entidade e o mesmo contexto

### Requirement: Invalidar contexto encerra toda versão vigente de um contexto
A biblioteca DEVE encerrar no instante dado, ou no atual, toda crença atual do dono no contexto que ainda valeria depois dele — inclusive a que só começaria depois, que é retirada sem nunca ter valido — e devolver quantas encerrou; DEVE alcançar a versão que uma substituição concorrente acabou de gravar; é uma escrita explícita e nunca uma consequência de uma recuperação.

#### Scenario: um contexto acaba
- **WHEN** um dono tem duas memórias vigentes num contexto e uma em outro, e a aplicação invalida o primeiro contexto
- **THEN** duas são encerradas, recuperar agora devolve só a terceira, e recuperar como em antes da invalidação devolve as três

#### Scenario: memória que ainda não começou
- **WHEN** um contexto tem uma memória válida a partir do dia 10 e a aplicação invalida o contexto no dia 0
- **THEN** uma é encerrada e recuperar como em dia 20 não a devolve

#### Scenario: invalidação retroativa preserva o que se sabia
- **WHEN** no dia 100 a aplicação invalida um contexto com fim no dia 30
- **THEN** recuperar como em dia 60 não devolve a memória, e recuperar sabido em dia 60 ainda devolve

### Requirement: Fechar um limite já fechado conflita
A biblioteca DEVE tornar todo fechamento de um limite de tempo condicional a esse limite estar aberto e DEVE levantar um erro de conflito quando não estava, de modo que dois escritores concorrentes nunca tenham ambos sucesso.

#### Scenario: duas substituições da mesma versão
- **WHEN** dois escritores seguram o mesmo id de versão vigente e ambos substituem esperando-o
- **THEN** o primeiro tem sucesso, o segundo levanta um erro de conflito, e o histórico tem só as versões da primeira substituição (a original, a cópia e a nova)

#### Scenario: operação sobre uma memória desconhecida
- **WHEN** a aplicação substitui, corrige ou encerra um id de memória que não tem versão vigente para este tenant e dono
- **THEN** um erro de não encontrado é levantado
