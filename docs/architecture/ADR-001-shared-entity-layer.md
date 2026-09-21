# ADR-001: Shared Entity Layer

## Status

Aceita para implementação inicial.

## Contexto

Os módulos de Renda Fixa, Debêntures, FIDCs, FIAGROs e Securitizados precisam compartilhar informações sobre bancos, empresas, fundos, gestoras, securitizadoras e outros participantes do mercado.

Manter cadastros separados causaria:

- duplicidade de registros;
- divergência de nomes e identificadores;
- repetição de demonstrações financeiras;
- repetição de ratings e documentos;
- dificuldade para relacionar produtos;
- retrabalho entre as verticais;
- risco de análises inconsistentes.

## Decisão

Criar uma entidade universal na camada compartilhada do PENSE_AL-M.

O pacote inicial será:

src/pense_alm/shared/entities/

A implementação começará por contratos de domínio sem dependência de banco de dados.

## Componentes iniciais

- Entity;
- EntityType;
- EntityStatus;
- EntityIdentifier;
- IdentifierType;
- DataProvenance;
- validações e normalizações básicas.

## Consequências positivas

- identidade única;
- reutilização entre domínios;
- centralização da proveniência;
- compartilhamento de ratings e financials;
- integração futura dos motores de inteligência;
- possibilidade de construir um grafo de relacionamentos.

## Riscos

- conflito com modelos legados de emissores;
- duplicidade durante a migração;
- correspondência incorreta entre entidades;
- dependência excessiva da camada compartilhada;
- criação prematura de uma estrutura complexa.

## Controles

- migração incremental;
- adaptadores para os módulos legados;
- CNPJ como identificador forte quando disponível;
- regras explícitas de matching;
- preservação dos valores originais;
- testes unitários;
- versionamento dos contratos;
- manutenção da baseline de 417 testes.

## Compatibilidade

A criação da Shared Entity Layer não altera inicialmente:

- o banco do módulo de Debêntures;
- os coletores existentes;
- os scripts de automação;
- os modelos de Securitizados;
- as rotinas de FIDCs e FIAGROs;
- os códigos de saída;
- o funcionamento de dry-run e commit.

## Restrição de layout

A implementação visual permanece fora do escopo.

O layout será retomado somente depois do levantamento e da consolidação dos requisitos de toda a equipe.
