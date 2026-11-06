# Spec Delta

## Purpose
O único delete físico: um pedido de privacidade apaga toda versão do alvo, inclusive a sua trilha de auditoria.

## ADDED Requirements

### Requirement: Esquecer apaga toda versão do alvo em uma transação
A biblioteca DEVE apagar toda versão do alvo — uma memória, toda memória sobre uma entidade, ou tudo do dono — para o tenant e o dono, atomicamente, e devolver quantas versões apagou.

#### Scenario: esquecer uma memória
- **WHEN** uma memória com três versões é esquecida por id de memória
- **THEN** três é devolvido, o seu histórico levanta não encontrado, e recuperar agora, como em qualquer instante e sabido em qualquer instante nunca a devolvem

#### Scenario: esquecer por entidade
- **WHEN** um dono tem memórias sobre duas entidades e esquece uma entidade
- **THEN** só as memórias da outra entidade permanecem, em todo modo de consulta

#### Scenario: esquecer tudo de um dono
- **WHEN** um dono esquece tudo
- **THEN** nenhuma versão desse dono permanece, e outro dono do mesmo tenant fica intocado

### Requirement: Esquecer exige exatamente um alvo
A biblioteca DEVE recusar um esquecer sem alvo ou com mais de um.

#### Scenario: esquecer sem alvo
- **WHEN** a aplicação chama esquecer sem id de memória, sem entidade e sem tudo
- **THEN** um erro de argumento inválido é levantado e nada é apagado

#### Scenario: esquecer um alvo desconhecido
- **WHEN** a aplicação esquece um id de memória que não existe para este tenant e dono
- **THEN** zero é devolvido e nenhum erro é levantado
