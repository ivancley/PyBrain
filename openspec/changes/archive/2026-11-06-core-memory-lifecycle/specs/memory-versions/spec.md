# Spec Delta

## Purpose
Como uma memória é registrada e como as suas versões imutáveis e o status derivado são expostos à aplicação.

## ADDED Requirements

### Requirement: Lembrar cria uma memória com uma primeira versão aberta
A biblioteca DEVE registrar uma memória de um dono como primeira versão com conteúdo, categoria, entidade, contexto e origem opcionais, tempo de validade começando no instante dado ou no atual e aberto salvo quando dado, e tempo de registro começando agora e aberto.

#### Scenario: lembrar com padrões
- **WHEN** a aplicação lembra um conteúdo com uma categoria para um dono, sem dar tempo de validade
- **THEN** uma versão é devolvida com um id de memória estável, válida do instante atual sem fim, registrada no instante atual sem substituição, e sem versão anterior

#### Scenario: lembrar com validade explícita
- **WHEN** a aplicação lembra um conteúdo com válido de no passado e válido até no futuro
- **THEN** a versão devolvida carrega exatamente esses limites e recuperar como em um instante entre eles a devolve

#### Scenario: conteúdo vazio é recusado
- **WHEN** a aplicação lembra um conteúdo vazio
- **THEN** um erro de argumento inválido é levantado e nada é registrado

#### Scenario: datetime sem fuso é recusado
- **WHEN** a aplicação passa um datetime sem fuso a qualquer operação
- **THEN** um erro de argumento inválido é levantado

### Requirement: Versões são imutáveis
A biblioteca DEVE nunca alterar uma versão armazenada, salvo fechar o seu tempo de registro; o fim da validade também é registrado como versão nova.

#### Scenario: histórico depois de substituir
- **WHEN** uma memória é substituída
- **THEN** o histórico da memória ainda contém a primeira versão com o seu conteúdo original

### Requirement: Status é derivado, nunca armazenado
A biblioteca DEVE derivar o status de uma versão (ativa, encerrada, substituída, corrigida) dos seus limites de tempo e da sua sucessora, com uma função que a aplicação pode chamar sobre as versões devolvidas pelo histórico.

#### Scenario: status ao longo de uma cadeia
- **WHEN** uma memória foi lembrada, depois substituída, depois a sucessora foi corrigida
- **THEN** o histórico tem quatro versões (a original, a cópia encerrada, a substituta e a correção), e derivar o status de cada uma com a sua sucessora dá substituída, substituída, corrigida e ativa, nessa ordem

### Requirement: Histórico devolve a cadeia de uma memória
A biblioteca DEVE devolver toda versão de uma memória para o tenant e o dono, da mais antiga à vigente, sendo a última a vigente.

#### Scenario: histórico de uma memória desconhecida
- **WHEN** a aplicação pede o histórico de um id de memória que não existe para este tenant e dono
- **THEN** um erro de não encontrado é levantado
