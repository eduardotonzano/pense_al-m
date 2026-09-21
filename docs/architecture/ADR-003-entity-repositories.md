# ADR-003: Repositórios da Shared Entity Layer

## Status

Aceita para implementação inicial.

## Contexto

A Shared Entity Layer já possui contratos de domínio para:

- entidades;
- identificadores;
- proveniência;
- matching;
- relacionamentos.

Esses objetos precisam ser armazenados e consultados sem criar dependência antecipada de uma tecnologia específica de banco de dados.

## Decisão

Criar contratos de repositório independentes de infraestrutura:

- EntityRepository;
- RelationshipRepository.

Também serão mantidas implementações em memória:

- InMemoryEntityRepository;
- InMemoryRelationshipRepository.

## Objetivo das implementações em memória

Os repositórios em memória permitem:

- validar regras de armazenamento;
- testar consultas;
- testar idempotência;
- testar deduplicação;
- validar atualização de índices;
- desenvolver serviços antes da criação do banco definitivo.

Os dados armazenados em memória não são permanentes e desaparecem ao encerrar o processo.

## Repositório de entidades

O EntityRepository permite:

- salvar uma entidade;
- buscar por UUID;
- buscar por identificador oficial;
- listar entidades;
- filtrar por tipo;
- contar entidades;
- verificar existência.

## Índice de identificadores

Os identificadores das entidades possuem um índice próprio.

Uma chave canônica de identificador não pode pertencer a duas entidades diferentes.

Exemplo:

cnpj:12345678000190

A tentativa de associar a mesma chave a outra entidade deve ser bloqueada.

## Atualização de entidade

Quando uma entidade já existente é salva novamente:

- o mesmo UUID é preservado;
- identificadores removidos deixam o índice;
- identificadores novos são adicionados ao índice;
- o total de entidades não aumenta.

## Repositório de relacionamentos

O RelationshipRepository permite:

- salvar um relacionamento;
- buscar por UUID;
- buscar por chave canônica;
- listar por entidade de origem;
- listar por entidade de destino;
- consultar relacionamentos ativos em uma data;
- filtrar e contar por tipo.

## Identidade do relacionamento

A chave canônica é composta por:

source_entity_id
relationship_type
target_entity_id

Duas relações com a mesma chave canônica não podem ser armazenadas como relacionamentos independentes.

## Idempotência

Salvar novamente o mesmo objeto não cria duplicidade.

Essa decisão é necessária para permitir:

- reprocessamento de dados;
- importações repetidas;
- coletores idempotentes;
- recuperação segura após falhas.

## Protocolos

Os contratos utilizam Protocol para evitar dependência direta das implementações em memória.

Serviços futuros poderão depender dos contratos e receber diferentes implementações, como:

- memória;
- SQLite;
- PostgreSQL;
- outro mecanismo de persistência.

## Ordenação

As consultas retornam tuplas determinísticas.

Entidades são ordenadas por razão social e UUID.

Relacionamentos são ordenados por tipo, origem e destino.

## Validação

Os repositórios rejeitam:

- objetos de tipos incorretos;
- UUIDs inválidos;
- tipos de entidade inválidos;
- tipos de relacionamento inválidos;
- consultas temporais sem timezone;
- chaves canônicas vazias;
- identificadores duplicados;
- relacionamentos duplicados.

## Consequências positivas

- separação entre domínio e infraestrutura;
- testes rápidos;
- comportamento de persistência definido antes do banco;
- substituição simples da implementação;
- deduplicação centralizada;
- base para serviços compartilhados.

## Limitações

As implementações em memória:

- não são persistentes;
- não suportam concorrência distribuída;
- não oferecem transações;
- não possuem controle de acesso;
- não substituem o banco definitivo.

## Fora do escopo

- schema de banco;
- migrações;
- transações persistentes;
- integração com módulos antigos;
- APIs;
- coletores;
- interface e layout.
