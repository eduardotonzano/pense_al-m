# ADR-005: Integração gradual de emissores de Debêntures

## Status

Aceita para implementação inicial.

## Contexto

A Shared Entity Layer possui:

- entidades universais;
- identificadores normalizados;
- proveniência;
- matching conservador;
- repositórios em memória;
- persistência SQLite.

Os módulos legados devem ser integrados gradualmente, sem reescrita imediata e sem dependência direta da camada compartilhada sobre suas classes internas.

O primeiro domínio escolhido foi o cadastro de emissores do módulo de Debêntures.

## Decisão

Criar uma camada intermediária de integração contendo:

- DebentureIssuerRecord;
- DebentureIssuerAdapter;
- DebentureIssuerImportService;
- EntityImportResult;
- EntityImportAction.

O módulo legado não será modificado nesta fase.

## Registro intermediário

O DebentureIssuerRecord representa os dados necessários do emissor:

- identificador legado;
- razão social;
- nome comercial;
- CNPJ;
- data de criação;
- data de atualização.

Essa estrutura impede que a Shared Entity Layer dependa diretamente da classe IssuerRecord do módulo de Debêntures.

## Conversão

O DebentureIssuerAdapter converte o registro intermediário em Entity.

O mapeamento utiliza:

- razão social como legal_name;
- nome comercial como trade_name;
- CNPJ como identificador primário;
- tipo COMPANY;
- país BR;
- origem SPECIALIZED;
- referência legada no formato issuer:{legacy_id}.

## Identidade determinística

O UUID da entidade é calculado de maneira determinística a partir do identificador legado.

Importações repetidas do mesmo legacy_id produzem o mesmo entity_id.

## Datas legadas

Timestamps SQLite sem timezone são interpretados como UTC.

Timestamps com timezone são convertidos para UTC.

Datas de atualização anteriores às datas de criação são rejeitadas.

## Matching

O serviço de importação adota comportamento conservador:

- mesmo CNPJ gera correspondência automática;
- mesmo nome sem identificador compartilhado exige revisão;
- conflito de identificador bloqueia a importação;
- ausência de evidência cria uma nova entidade.

## Atualização de dados

Uma correspondência automática não sobrescreve imediatamente a entidade existente.

A atualização automática exigirá regras futuras de precedência e confiança entre fontes.

## CNPJ opcional

Emissores sem CNPJ podem ser convertidos.

Esses registros não são unidos automaticamente apenas pelo nome.

Coincidências por nome são direcionadas para revisão.

## Compatibilidade

O serviço depende do contrato EntityRepository.

A implementação pode utilizar:

- InMemoryEntityRepository;
- SQLiteEntityRepository;
- outra implementação compatível.

## Consequências positivas

- primeira integração real com módulo legado;
- ausência de alteração destrutiva no módulo de Debêntures;
- desacoplamento entre os modelos;
- importações auditáveis;
- matching conservador;
- comportamento idempotente;
- base reutilizável para outros módulos.

## Limitações

Nesta primeira versão:

- não há leitura direta do banco legado;
- não há importação em lote;
- não há fila persistente de revisão;
- não há atualização automática de entidades existentes;
- não há integração de Debêntures como ativos;
- apenas emissores são convertidos.

## Fora do escopo

- alterações no módulo legado;
- migração do banco de Debêntures;
- CRI e CRA;
- FIDC;
- FIAGRO;
- coletores;
- interface e layout.
