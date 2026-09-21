# ADR-004: Persistência compartilhada em SQLite

## Status

Aceita para implementação inicial.

## Contexto

A Shared Entity Layer já possui modelos de domínio e repositórios em memória.

Os dados precisam sobreviver ao encerramento do processo e manter:

- entidades;
- identificadores;
- proveniência;
- relacionamentos;
- integridade;
- idempotência;
- consulta histórica.

## Decisão

Adotar SQLite como primeira implementação persistente da camada compartilhada.

A escolha não altera os contratos:

- EntityRepository;
- RelationshipRepository.

As implementações persistentes serão:

- SQLiteEntityRepository;
- SQLiteRelationshipRepository.

## Componentes

A infraestrutura inicial contém:

- SQLiteConnectionManager;
- MigrationRunner;
- migrações versionadas;
- serialização dos objetos;
- repositórios SQLite;
- testes de integração.

## Schema

O schema inicial possui:

- schema_migrations;
- data_provenance;
- entities;
- entity_identifiers;
- entity_relationships.

## Transações

Operações de gravação são executadas dentro de transações.

Quando a operação é concluída:

- commit é realizado.

Quando ocorre erro:

- rollback é realizado;
- nenhuma alteração parcial permanece.

## Migrações

As alterações do schema são versionadas.

Cada migração possui:

- versão;
- nome;
- instruções SQL;
- momento de aplicação.

Uma migração aplicada não é executada novamente.

## Proveniência

A proveniência recebe uma identidade determinística calculada a partir de seu conteúdo.

Proveniências equivalentes produzem a mesma chave persistente.

Isso permite reutilização sem duplicação desnecessária.

## Integridade

O banco protege:

- unicidade dos identificadores;
- unicidade das chaves canônicas;
- referências entre tabelas;
- confiança entre zero e cem;
- autorrelacionamentos inválidos;
- períodos temporais incoerentes;
- país com duas letras.

## Entidades

O SQLiteEntityRepository permite:

- salvar;
- atualizar;
- buscar por UUID;
- buscar por identificador;
- listar;
- filtrar;
- contar;
- verificar existência.

A entidade, sua proveniência e seus identificadores são persistidos na mesma transação.

## Relacionamentos

O SQLiteRelationshipRepository permite:

- salvar;
- atualizar;
- buscar por UUID;
- buscar por chave canônica;
- listar por origem;
- listar por destino;
- consultar vigência histórica;
- filtrar;
- contar.

Origem e destino precisam existir antes da gravação da relação.

## Idempotência

Salvar novamente o mesmo objeto não cria duplicidade.

Essa propriedade permite:

- reprocessamentos;
- coletores repetidos;
- recuperação após falhas;
- execução segura de rotinas automáticas.

## Compatibilidade

Os repositórios SQLite preservam o comportamento definido pelos repositórios em memória.

Os serviços futuros poderão depender dos contratos, sem acoplamento direto ao SQLite.

## Consequências positivas

- persistência real;
- banco portátil;
- baixo custo operacional;
- testes de integração simples;
- transações;
- integridade referencial;
- migrações versionadas;
- caminho para integração gradual.

## Limitações

SQLite não será considerado automaticamente a solução definitiva para:

- acesso distribuído;
- alta concorrência;
- múltiplos serviços;
- grandes volumes simultâneos;
- permissões avançadas.

A migração futura para PostgreSQL permanece possível porque os contratos são independentes.

## Fora do escopo

- integração com módulos existentes;
- APIs;
- autenticação;
- controle de acesso;
- coletores compartilhados;
- scores;
- interface e layout.
