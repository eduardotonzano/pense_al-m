# ADR-002: Relacionamentos entre entidades

## Status

Aceita para implementação inicial.

## Contexto

A identificação isolada dos participantes não é suficiente para analisar estruturas de crédito.

A plataforma precisa representar relações como:

- controle societário;
- administração de fundos;
- emissão de ativos;
- originação;
- cessão de recebíveis;
- garantias;
- distribuição;
- prestação de serviços;
- sucessão empresarial.

## Decisão

Os relacionamentos serão representados por uma estrutura direcionada, temporal, auditável e imutável.

O modelo será:

src/pense_alm/shared/entities/relationships.py

## Direção

Toda relação possui uma origem e um destino.

Exemplo:

Holding A controla Empresa B.

A direção inversa não será criada automaticamente nesta primeira versão.

Isso evita efeitos indiretos e mantém cada operação explícita.

## Temporalidade

Os relacionamentos podem possuir:

- data inicial;
- data final;
- vigência aberta;
- consulta histórica.

Uma relação só será considerada ativa quando:

- o status for active;
- a data consultada não for anterior ao início;
- a data consultada não for posterior ao encerramento.

## Proveniência

Todo relacionamento deve possuir proveniência.

A origem da informação, o momento da coleta e o estado de validação devem ser preservados.

## Confiança

Cada relacionamento possui um confidence_score entre zero e cem.

A confiança específica da relação é separada da confiança geral da fonte.

## Revisão e divergência

Relacionamentos com status:

- pending_review;
- disputed;
- inactive;
- unknown;

não serão tratados como relações canônicas ativas.

## Identidade da relação

A chave canônica será formada por:

source_entity_id
relationship_type
target_entity_id

A direção faz parte da identidade.

Portanto:

A controla B

é diferente de:

B controla A

## Autorrelacionamento

Uma entidade não poderá se relacionar consigo mesma nesta primeira versão.

Exceções futuras deverão ser avaliadas e documentadas explicitamente.

## Relação inversa

A criação automática de relações inversas permanece fora do escopo inicial.

Um serviço específico poderá ser criado futuramente para essa função.

## Consequências positivas

- representação de grupos econômicos;
- visão de estruturas de fundos;
- ligação entre cedentes e FIDCs;
- representação de emissões securitizadas;
- análise histórica de vínculos;
- base para um Knowledge Graph;
- melhoria futura dos motores de risco.

## Riscos

- relações duplicadas;
- conflitos entre fontes;
- direção incorreta;
- vigência desatualizada;
- interpretação excessiva de vínculos.

## Controles

- proveniência obrigatória;
- chave canônica;
- validação temporal;
- status de revisão e divergência;
- confiança explícita;
- modelos imutáveis;
- testes unitários;
- nenhuma inferência automática nesta etapa.

## Fora do escopo

- persistência em banco;
- criação automática de relações inversas;
- inferência de relacionamentos;
- visualização em grafo;
- integração com módulos existentes;
- coletores automáticos;
- layout.
