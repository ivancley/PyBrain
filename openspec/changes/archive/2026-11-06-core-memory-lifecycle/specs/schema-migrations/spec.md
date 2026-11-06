# Spec Delta

## Purpose
Inicializar e evoluir o schema próprio da biblioteca dentro do banco da aplicação.

## ADDED Requirements

### Requirement: Migrar inicializa o schema de forma idempotente
A biblioteca DEVE criar o seu schema e aplicar as migrações pendentes em ordem, devolver quantas aplicou, e não aplicar nada numa segunda chamada.

#### Scenario: migrar duas vezes
- **WHEN** migrar corre num banco vazio e depois de novo
- **THEN** a primeira chamada devolve uma contagem positiva, a segunda devolve zero, e o schema é idêntico depois das duas

#### Scenario: operação antes de migrar
- **WHEN** um lembrar corre contra um banco onde migrar nunca correu
- **THEN** um erro de configuração é levantado dizendo que o schema não foi inicializado

### Requirement: Migrações são só de acréscimo
A biblioteca DEVE registrar uma impressão digital de toda migração aplicada e DEVE recusar-se a correr quando uma migração aplicada mudou ou duas migrações têm o mesmo número.

#### Scenario: uma migração aplicada mudou
- **WHEN** uma migração já aplicada tem conteúdo diferente em disco e migrar corre
- **THEN** um erro de migração é levantado e nada é aplicado

### Requirement: A dimensão do vetor é fixada na inicialização
A biblioteca DEVE tomar a dimensão do vetor do provedor de embeddings no primeiro migrar, registrá-la, e recusar um provedor posterior de outra dimensão.

#### Scenario: migrar com uma segunda dimensão
- **WHEN** migrar correu com um provedor de embeddings de uma dimensão e corre de novo com outro
- **THEN** um erro de dimensão de embedding é levantado
