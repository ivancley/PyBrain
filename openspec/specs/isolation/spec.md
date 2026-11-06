# isolation Specification

## Purpose
Nada de um tenant ou de um dono é jamais visível para outro, nem alterável por ele.

## Requirements

### Requirement: Toda operação filtra tenant e dono
A biblioteca DEVE ligar o tenant no construtor e receber o dono em toda operação, e DEVE aplicar os dois como filtros em toda leitura e escrita.

#### Scenario: dois tenants, mesmo id de dono
- **WHEN** duas memórias com o mesmo id de dono são lembradas por duas instâncias de Memoria de tenants diferentes
- **THEN** recuperar por cada instância devolve só a sua própria memória, em todo modo de consulta

#### Scenario: dois donos, mesmo tenant
- **WHEN** dois donos de um tenant lembram uma memória cada
- **THEN** recuperar para um dono nunca devolve a memória do outro, e o histórico do id de memória do outro levanta um erro de não encontrado

#### Scenario: escrita entre donos é recusada
- **WHEN** um dono substitui, corrige ou encerra um id de memória que pertence a outro dono
- **THEN** um erro de não encontrado é levantado e a memória do outro dono fica inalterada

#### Scenario: esquecer o que é alheio não apaga nada
- **WHEN** um dono esquece um id de memória, uma entidade ou tudo, e as memórias com esse id, essa entidade ou esse contexto pertencem a outro dono ou a outro tenant
- **THEN** zero é devolvido, sem dizer se o alvo existe em outro lugar, e as memórias alheias ficam inalteradas

### Requirement: A existência não vaza
A biblioteca DEVE levantar o mesmo erro de não encontrado quer o id de memória seja desconhecido, pertença a outro dono ou pertença a outro tenant.

#### Scenario: sondagem entre tenants
- **WHEN** um id de memória de um tenant é usado pela instância de outro
- **THEN** o erro levantado é indistinguível do erro para um id que nunca existiu
