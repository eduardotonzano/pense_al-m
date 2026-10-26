# ADR-008: Importação de debêntures como instrumento

## Status

Proposta. Implementada no ramo `feat/shared-adapter-debentures`; passa a aceita com a revisão do pull request.

## Contexto

O ADR-005 criou o padrão de integração gradual com o módulo legado de debêntures (registro intermediário, adaptador, serviço de importação, leitura sob `PRAGMA query_only`, lote com relatório) e o aplicou ao emissor. O ADR-007 define que a debênture entra na camada compartilhada como `Entity` do tipo `DEBENTURE`, com `ISIN` e `ASSET_CODE` como identificadores e a relação `ISSUES` ligando o emissor ao instrumento.

Este ADR define como a importação do instrumento funciona: o que lê, como converte, quando liga a uma entidade existente e quando para sem gravar.

## Decisão

Reaproveitar o padrão do ADR-005 com os componentes abaixo, em `src/pense_alm/shared/integration/`:

| Componente | Papel |
|---|---|
| `DebentureInstrumentRecord` (`records.py`) | registro intermediário; a camada não depende das classes do módulo legado |
| `LegacyDebentureInstrumentReader` | lê `debentures` com `LEFT JOIN issuers` sob `PRAGMA query_only`, em lotes ordenados por id |
| `DebentureInstrumentAdapter` | converte o registro em `Entity` e monta a relação `ISSUES` |
| `DebentureInstrumentImportService` | decide, registro a registro, entre criar, corresponder, revisar e bloquear |
| `DebentureInstrumentBatchImportService` | percorre o legado, continua após erro individual e devolve o relatório |
| `InstrumentImportResult`, `InstrumentImportReason` (`import_result.py`) | resultado auditável com o motivo de cada pendência |
| `parse_legacy_datetime` (`legacy_datetime.py`) | leitura de timestamps legados, extraída do adaptador de emissores, que agora delega a ela |

Reaproveitados sem mudança: `EntityImportAction`, `BatchImportReport`, `BatchImportError`, `EntityMatcher`.

## Registro intermediário

Campos: identificador legado, `asset_code`, `isin`, `status`, identificador legado do emissor, CNPJ do emissor, data de criação e de atualização.

Valida como o schema legado: ao menos um entre código e ISIN; código em maiúsculas e sem espaços; ISIN com 12 caracteres alfanuméricos; status entre `unknown`, `active`, `inactive`, `matured` e `cancelled`; CNPJ do emissor com 14 dígitos e só junto do identificador do emissor.

## Conversão

- Tipo `DEBENTURE`, país `BR`, origem `SPECIALIZED`, referência legada `debenture:{legacy_id}`.
- `legal_name` recebe o código do ativo, ou o ISIN quando não há código.
- Identificadores `ASSET_CODE` e `ISIN`, cada um como primário do seu tipo.
- Status: `active` vira `ACTIVE`; `inactive`, `matured` e `cancelled` viram `INACTIVE`; `unknown` vira `UNKNOWN`. O mapeamento perde a distinção entre vencida, cancelada e inativa.
- Datas: como no ADR-005 (sem fuso, UTC; com fuso, convertidas; atualização anterior à criação é rejeitada). `collected_at` e `reference_date` recebem `updated_at`.
- Relação: `ISSUES`, emissor na origem, instrumento no destino, status `ACTIVE`, sem datas de vigência (a data de emissão não está no registro), mesma proveniência do instrumento.

## Identidade determinística

- `entity_id` = `uuid5(NAMESPACE_URL, "pense-alm:debenture-instrument:{legacy_id}")`.
- `relationship_id` = `uuid5(NAMESPACE_URL, chave canônica da relação)`, de modo que regravar a mesma relação é um upsert e não `DuplicateRelationshipError`.

## Matching conservador

Nenhuma etapa compara nomes. O instrumento só é ligado a uma entidade por identificador inequívoco: ISIN, código do ativo ou CNPJ do emissor já registrado. As regras valem nesta ordem e **só `CREATED` e `MATCHED` gravam algo**:

| # | Condição | Ação | Motivo |
|---|---|---|---|
| 1 | a debênture não tem emissor no legado | `REVIEW` | `issuer_missing` |
| 2 | o emissor não tem CNPJ | `REVIEW` | `issuer_without_cnpj` |
| 3 | nenhuma entidade tem o CNPJ do emissor | `REVIEW` | `issuer_not_registered` |
| 4 | ISIN e código apontam para duas entidades diferentes | `BLOCKED` | `conflicting_candidates` |
| 5 | nenhuma entidade tem o ISIN ou o código | `CREATED` (entidade e relação) | |
| 5a | exceto se o `entity_id` já existe com outros identificadores | `BLOCKED` | `identifier_conflict` |
| 6 | a entidade achada não é `DEBENTURE` | `BLOCKED` | `not_an_instrument` |
| 7 | o matcher não dá `AUTO_MATCH` (ISIN ou código divergente) | `BLOCKED` | `identifier_conflict` |
| 8 | a relação `ISSUES` existente vem de outro emissor | `BLOCKED` | `issuer_mismatch` |
| 9 | demais casos | `MATCHED`; cria a relação se faltar | |

`REVIEW` é o "pendente de revisão": faltou evidência para ligar o instrumento a um emissor. `BLOCKED` é o caso em que a evidência se contradiz. Os dois deixam o repositório intacto.

O serviço **nunca cria o emissor**. Quem cria é a importação de emissores (ADR-005), que deve rodar antes. Isso evita um cadastro paralelo e uma segunda regra de matching de empresas.

O emissor pode ser uma entidade de qualquer tipo com aquele CNPJ (por exemplo, um banco que emite debêntures), exceto de tipo instrumento.

## Idempotência e falha parcial

- Reexecutar com o mesmo legado gera `MATCHED` para o que já foi importado, sem nova entidade nem nova relação.
- Entidade e relação são salvas em repositórios diferentes, em transações separadas. Se a segunda gravação falhar, o instrumento fica sem a relação. A reexecução acha o instrumento pelo ISIN ou código, vê que falta a relação e a cria (`relationship_created=True`).
- Um identificador novo no legado que a entidade existente não tem (por exemplo, o ISIN que passou a existir) **não é incorporado**: o ADR-005 proíbe atualizar entidade existente sem regra de precedência. O resultado lista o identificador em `unmerged_identifiers`.
- Se o mesmo `legacy_id` volta com ISIN e código diferentes dos importados, a entidade não é sobrescrita: `BLOCKED` (regra 5a).

## Leitura e lote

- O leitor devolve a linha inválida como `LegacyInstrumentReadError`, em vez de interromper a leitura. O lote a conta como erro e continua.
- O lote usa `BatchImportReport` e `BatchImportError` sem alteração: a soma dos resultados é igual ao total lido. Os casos `REVIEW` e `BLOCKED` vêm numa lista à parte (`InstrumentBatchOutcome.pending`), com o motivo, para a saída da CLI (ADR-009).
- O parâmetro `dry_run` do lote só identifica o relatório. A simulação sem gravar depende de repositórios descartáveis, entregues por quem chama (ADR-009).

## Alternativas consideradas

1. **Criar o emissor quando ele não existir.** Descartada: duplica o serviço de emissores e dá ao instrumento uma regra de matching de empresas própria.
2. **Ligar o emissor por nome quando falta o CNPJ.** Descartada: a regra central do projeto é que nome não basta (ADR-001, ADR-005).
3. **Criar o instrumento sem relação quando o emissor não é resolvido, e ligar depois.** Descartada: o ativo apareceria na busca sem emissor, e a pendência deixaria de ser visível no relatório.
4. **Reaproveitar o fluxo de nome do serviço de emissores.** Descartada: o nome do instrumento é o próprio código, e a comparação por nome não acrescenta evidência.

## Consequências positivas

- o instrumento passa a existir na camada compartilhada, com ISIN, código e relação de emissão, sem alterar o módulo legado;
- tudo que não for inequívoco fica fora e visível, com motivo;
- a reexecução é segura e repara a falha parcial;
- o CRI/CRA reaproveita o desenho com outro leitor e outro adaptador.

## Limitações

- a fila de revisão continua não persistente: as pendências aparecem no relatório de cada execução;
- debêntures cujo emissor não tem CNPJ ficam pendentes até haver outro identificador inequívoco;
- o status na camada é o da data da importação e não é atualizado (ADR-005); a fonte do status é o módulo de debêntures;
- identificadores novos e mudanças de código ou ISIN no legado exigem decisão humana;
- o ISIN é validado só pelo formato.

## Fora do escopo

- execução, `--commit` e backup (ADR-009);
- CRI e CRA;
- índice de busca global e contrato de leitura (ADR-006);
- fila persistente de revisão;
- atualização de entidades existentes e precedência entre fontes.
