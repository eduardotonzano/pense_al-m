# ADR-007: Instrumento (debênture) como entidade da camada compartilhada

## Status

Proposta. Implementada no ramo `feat/shared-adapter-debentures`; passa a aceita com a revisão do pull request.

## Contexto

A Shared Entity Layer nasceu para os participantes do mercado (ADR-001: bancos, empresas, fundos, gestoras, securitizadoras). O ADR-005 integrou só o emissor das debêntures e deixou o instrumento de fora ("Debêntures ainda não são integradas como ativos").

Sem o instrumento na camada compartilhada não há:

- a busca global por código, ISIN, emissor e CNPJ (G-08);
- a relação de emissão entre o emissor e o ativo (G-09, F-06);
- um lugar para o adaptador de CRI/CRA (roadmap item 2) resolver o ISIN que aparece em dois ativos no banco do Enrico.

O banco legado de debêntures identifica o instrumento por `asset_code` (único) e `isin` (único, 12 caracteres), com `issuer_id` apontando para o emissor. Pelo menos um dos dois identificadores existe (`CHECK` do schema).

## Lacunas encontradas

Comparação entre o que o instrumento precisa e o que a camada oferece em `src/pense_alm/shared/entities/`:

| O instrumento precisa de | A camada tem? | Mudança proposta |
|---|---|---|
| Um tipo de entidade para o ativo | Não. `EntityType` lista participantes (banco, empresa, holding, fundo, FIDC, FIAGRO, securitizadora...) | `EntityType.DEBENTURE` |
| Um tipo de identificador para o ISIN | Não. `IdentifierType`: CNPJ, BACEN, CVM, ANBIMA, LEI, INTERNAL, OTHER | `IdentifierType.ISIN` |
| Um tipo de identificador para o código do ativo (B3/CETIP) | Não | `IdentifierType.ASSET_CODE` |
| Que o matching trate ISIN e código como identificadores fortes | Não. `_STRONG_IDENTIFIER_TYPES` tem CNPJ, BACEN, CVM, ANBIMA e LEI | incluir `ISIN` e `ASSET_CODE` |
| Uma relação emissor → ativo | **Sim.** `RelationshipType.ISSUES` (o ADR-002 cita "emissão de ativos") | nenhuma |
| Persistência dos novos valores | **Sim.** `entity_type` e `identifier_type` são `TEXT` sem `CHECK` (`v001_initial_schema.py`) | nenhuma migration |

## Decisão

Fazer a menor mudança que fecha as lacunas:

1. Acrescentar `EntityType.DEBENTURE`, `IdentifierType.ISIN` e `IdentifierType.ASSET_CODE`.
2. Incluir `ISIN` e `ASSET_CODE` entre os identificadores fortes do `EntityMatcher`: valor igual gera `AUTO_MATCH`; valor diferente para o mesmo tipo gera `BLOCKED`, como já ocorre com o CNPJ.
3. Representar a emissão como `ISSUES`, com o emissor na origem e o instrumento no destino.
4. Tratar o instrumento como `Entity`. O conceito passa a ser "participante **ou instrumento identificável**".

O que **não** muda:

- nenhuma migration, tabela ou repositório novo;
- nenhum `RelationshipType` novo;
- os atributos da debênture (valor nominal, vencimento, indexador, spread...) continuam em `observations` no módulo de debêntures. A camada compartilhada guarda a identidade, os identificadores, a proveniência e a relação com o emissor.

## Identificadores

- O valor segue a normalização que já existe para identificadores que não são CNPJ: texto sem espaços nas pontas e em maiúsculas.
- A chave canônica (`isin:BR...`, `asset_code:ALFA11`) é única em todo o banco da camada. Se o mesmo ISIN ou código aparecer em outra entidade, a gravação falha (`DuplicateEntityError`) em vez de fundir. Um código repetido entre produtos diferentes (por exemplo, uma debênture e um CRI) vira conflito visível, nunca fusão silenciosa.
- O ISIN é validado só pelo formato (12 caracteres alfanuméricos), como o legado. A conferência do dígito verificador não faz parte desta decisão.

## Alternativas consideradas

1. **`EntityType.SECURITY` genérico.** Um tipo para todos os produtos. Descartada: a distinção entre debênture, CRI e CRA iria para `sector`/`subsector`, que são texto livre sem contrato, e `list_all(tipo)` deixaria de servir de filtro para o índice de busca. Com um tipo por produto, cada adaptador seguinte acrescenta uma linha ao enum.
2. **Modelo `Instrument` próprio, com tabela e repositório.** Mantém `Entity` só para participantes. Descartada: exige migration, repositório novo e uma segunda forma de relacionar emissor e ativo (`ISSUES` é entre entidades), e repete identificadores, proveniência e relacionamentos que a camada já oferece. É o cadastro paralelo que o princípio 1 da camada proíbe.
3. **Usar `IdentifierType.OTHER` ou `INTERNAL` para ISIN e código.** Não exige mudança de enum. Descartada: ISIN e código ficariam indistinguíveis na chave canônica (`other:...`) e o matcher não os trataria como fortes.

## Consequências positivas

- o instrumento passa a ter identidade única, proveniência e relação de emissão na mesma camada dos participantes;
- ISIN e código ficam disponíveis para a busca global (G-08);
- o adaptador de CRI/CRA reaproveita `ISIN`, `ASSET_CODE` e `ISSUES`; precisa só de `EntityType.CRI` e `EntityType.CRA`;
- sem migration, sem risco para os bancos já gravados.

## Riscos e limitações

- `Entity.legal_name` é obrigatório e, para o instrumento, recebe o código (ou o ISIN, se não houver código). Não é uma razão social.
- `EntityStatus` não tem "vencida" nem "cancelada"; o status do instrumento na camada é uma fotografia da importação e não é atualizado automaticamente (ADR-005). A fonte do status continua sendo o módulo de debêntures (G-06, ADR-006).
- `list_all()` sem tipo passa a devolver também instrumentos. Quem precisa só de participantes deve filtrar por tipo (o serviço de importação de emissores já filtra por `COMPANY`).
- Um banco da camada gravado com `debenture`, `isin` ou `asset_code` não é lido por uma versão anterior do código (`EntityType("debenture")` falha). Atualizar o código antes de abrir esses bancos.
- O mesmo código em dois produtos só aparece como conflito na gravação; a política de resolução é decisão futura.

## Fora do escopo

- o adaptador, o serviço de importação e a CLI do instrumento (ADR-008 e ADR-009);
- CRI e CRA;
- o índice de busca global;
- atualização de entidades existentes e precedência entre fontes.
