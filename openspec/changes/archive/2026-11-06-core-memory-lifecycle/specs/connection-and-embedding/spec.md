# Spec Delta

## Purpose
As duas fronteiras com o mundo: a conexão que a aplicação empresta e o provedor de embeddings que ela escolhe.

## ADDED Requirements

### Requirement: A aplicação é dona da conexão
A biblioteca DEVE obter uma conexão do provedor só pela duração de uma operação, DEVE fazer commit no sucesso e rollback no erro só quando o modo de transação do provedor é própria, DEVE nunca fazer commit nem rollback quando é participar, e DEVE recusar o modo participar quando a conexão entregue está em autocommit.

#### Scenario: modo participar deixa o commit com o app
- **WHEN** uma memória é lembrada por um provedor em modo participar e a aplicação faz rollback da sua transação
- **THEN** recuperar não devolve a memória

#### Scenario: modo participar em autocommit é recusado
- **WHEN** um provedor em modo participar entrega uma conexão em autocommit e a aplicação chama lembrar
- **THEN** um erro de configuração é levantado antes de qualquer escrita e nada é registrado

#### Scenario: modo própria faz commit
- **WHEN** uma memória é lembrada por um provedor em modo própria
- **THEN** uma conexão nova a vê

#### Scenario: modo própria faz rollback no erro
- **WHEN** uma operação falha no meio por um provedor em modo própria
- **THEN** nenhuma versão parcial fica visível depois

### Requirement: O embedding é calculado antes de obter a conexão
A biblioteca DEVE chamar o provedor de embeddings para o conteúdo (na escrita) ou para a consulta (na recuperação) antes de pedir uma conexão ao provedor de conexão, e DEVE não segurar uma conexão durante uma chamada ao provedor de embeddings.

#### Scenario: falha do provedor de embeddings não custa conexão
- **WHEN** o provedor de embeddings levanta erro num lembrar
- **THEN** um erro de embedding é levantado, nada é registrado, e nenhuma conexão foi pedida ao provedor de conexão

### Requirement: Dimensão divergente é um erro permanente
A biblioteca DEVE recusar um vetor cujo comprimento difere da dimensão registrada no schema com um erro de dimensão de embedding, nunca uma conversão silenciosa.

#### Scenario: outro provedor de embeddings contra o mesmo schema
- **WHEN** o schema foi criado com um provedor de embeddings de uma dimensão e um lembrar corre com um provedor de outra
- **THEN** um erro de dimensão de embedding é levantado e nada é registrado

### Requirement: Dependências opcionais são extras
A biblioteca DEVE ser importável sem nenhum pacote de terceiros, e um adaptador cuja dependência falta DEVE levantar um erro que nomeia o extra a instalar.

#### Scenario: importar sem nada instalado
- **WHEN** o pacote é importado num ambiente só com a biblioteca padrão
- **THEN** a importação tem sucesso e nenhum módulo de driver ou de framework é carregado
