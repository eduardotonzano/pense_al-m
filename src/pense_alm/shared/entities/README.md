# Shared Entity Layer

## Objetivo

A Shared Entity Layer será a fonte única de identificação dos participantes do mercado cobertos pelo PENSE_AL-M.

A camada evitará que Renda Fixa, Debêntures, FIDCs, FIAGROs e Securitizados criem cadastros independentes para uma mesma instituição, empresa, fundo ou participante.

## Entidades cobertas inicialmente

- bancos;
- empresas;
- holdings;
- instituições financeiras;
- cooperativas;
- gestoras;
- fundos;
- FIDCs;
- FIAGROs;
- securitizadoras;
- entidades governamentais.

## Responsabilidades

A camada será responsável por:

- identidade única;
- razão social e nome comercial;
- identificadores, como CNPJ e código BACEN;
- classificação por tipo;
- situação cadastral;
- proveniência dos dados;
- relacionamentos entre entidades;
- identificação de possíveis duplicidades.

## Princípios

1. Nenhum domínio deve criar um cadastro paralelo de entidades.
2. Todo dado deve possuir proveniência.
3. Fontes oficiais possuem prioridade sobre fontes complementares.
4. Dados de fontes diferentes devem ser preservados antes da reconciliação.
5. O código legado continuará funcionando durante a integração.
6. A migração será incremental e reversível.

## Hierarquia de fontes

1. BACEN;
2. CVM;
3. ANBIMA;
4. plataformas especializadas;
5. sites institucionais.

Uma fonte de menor prioridade pode complementar uma fonte oficial, mas não deve sobrescrevê-la automaticamente.

## Fora do escopo da primeira entrega

- persistência em banco de dados;
- migração dos emissores de Debêntures;
- coletores do BACEN;
- Financial Layer;
- Health Score;
- Risk Score;
- Opportunity Score;
- interface e layout.
