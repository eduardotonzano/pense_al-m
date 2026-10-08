# Migração da duplicidade lógica — Café Brasil

**Status: concluída e validada.** O registro canônico é `asset_id=1`, com `codigo_cetip=CRA022009VM`, `isin=BRECOACRABX0`, emissão `190` e série interna `1`. A descrição de apresentação é **Série única (1ª série)**; ela não representa uma série distinta.

## Causa identificada

O `AssetRepository.upsert` anterior só encontrava conflito pelo texto exato de `codigo_cetip`. Quando a configuração foi alterada para usar o ISIN `BRECOACRABX0` também como `codigo_cetip`, o upsert criou `asset_id=6`, embora o cadastro `asset_id=1` já representasse o mesmo ativo. O schema então não tinha unicidade por ISIN.

O histórico Git confirma que a configuração original usava `CRA022009VM` e série `unica`; em 21/09/2026, o commit `7dbe497c408bf45c59f046ec65a023bda557ef76` adicionou ISIN ao schema e alterou a linha piloto para `BRECOACRABX0`/`BRECOACRABX0`/série `1`. A divergência foi corrigida mantendo CETIP e ISIN em colunas separadas.

## Cadastros e contagens antes da migração

| Campo | asset_id=1 (canônico) | asset_id=6 (duplicado) |
|---|---|---|
| `codigo_cetip` | `CRA022009VM` | `BRECOACRABX0` (ISIN usado indevidamente como CETIP) |
| `isin` | `BRECOACRABX0` | `BRECOACRABX0` |
| tipo / securitizadora | CRA / Eco Securitizadora | CRA / Eco Securitizadora |
| CNPJ da securitizadora | `10.753.164/0001-43` | `10.753.164/0001-43` |
| emissão / série | `190` / `unica` | `190` / `1` |
| devedor | Café Brasil Indústria Comércio Importação e Exportação S.A. | Café Brasil Indústria Comércio Importação e Exportação S.A. |
| CNPJ do devedor | `01.486.546/0001-67` | `01.486.546/0001-67` |
| ativo / criado em | sim / `2026-09-17T18:15:01.067150+00:00` | sim / `2026-09-18T18:55:14.283555+00:00` |
| documents | 0 | 124 |
| document_versions indiretas | 0 | 2 |
| collection_attempts | 0 | 6 |
| alerts | 0 | 0 |

`assets` não armazena `run_id` de criação; a execução de criação provável foi inferida pela proximidade do timestamp:

| Ativo | execução provável | início | estado |
|---|---|---|---|
| `asset_id=1` | `782165cbde024c22805bdfb0c01b9088` | `2026-09-17T18:15:01.060565+00:00` | success |
| `asset_id=6` | `52895e9627de42c4935f8d808c52a067` | `2026-09-18T18:55:14.278661+00:00` | success |

## Migração transacional e preservação

A função `migrate_cafe_brasil_duplicate_asset` executou `BEGIN IMMEDIATE`, validou os cadastros, verificou colisões documentais antes de modificar qualquer relacionamento e aplicou todas as atualizações na mesma transação:

| Verificação/alteração | Resultado |
|---|---:|
| document key (`source_document_id` + `source`) duplicada entre os ativos | 0 |
| colisões de `file_hash` não vazio | 0 |
| colisões de URL, categoria ou data de referência | 0 |
| documents movidos para `asset_id=1` | 124 |
| documentos equivalentes mesclados | 0 |
| document_versions preservadas via `document_id` | 2 |
| collection_attempts movidas | 6 |
| alerts movidos | 0 |
| referências diretas em outras tabelas | 0 |
| asset duplicado removido | sim (`asset_id=6`) |

Não houve perda de documentos ou histórico. Os documentos históricos tinham `run_id` nulo; seus valores, datas de coleta e identificadores permaneceram intactos. Os dois arquivos físicos foram verificados antes da transação quanto à existência, tamanho e SHA-256 e não foram movidos nem apagados. A validação também confirmou zero referências remanescentes para `asset_id=6`.

## Proteção contra nova duplicidade

- `AssetRepository.upsert` normaliza CETIP/ISIN (trim, uppercase e remoção de whitespace/caracteres invisíveis), converte identificadores vazios em ausência para comparação e valida o formato do ISIN.
- Procura primeiro por ISIN e também por CETIP; se apontarem para linhas diferentes, interrompe com conflito explícito. Atualiza a linha existente, preserva identificadores omitidos e normaliza `unica` para série interna `1`.
- Não usa nome/devedor para identificar ativos e rejeita `codigo_cetip` igual ao ISIN.
- Foram adicionados índices únicos parciais normalizados para ISIN e CETIP não vazios. Em bancos legados, a migração de duplicidades precisa preceder a criação dos índices.
- A linha Café Brasil em `config/ativos_piloto.csv` agora mantém CETIP `CRA022009VM` e ISIN `BRECOACRABX0` separados. O Almeida Junior também usa o CETIP `24G2100031`, conforme o cadastro aprovado anteriormente, e mantém ISIN `BRRBRACRIP13`.

## Resultado atual

- Ativos: 2 no banco; exatamente 1 com o ISIN Café Brasil e exatamente 1 com o CETIP Café Brasil, ambos `asset_id=1`.
- Cadastro canônico: CRA / Eco Securitizadora / emissão `190` / série `1`.
- Café Brasil: 126 documentos Fundos.NET, 0 duplicidade por `(source_document_id, source)`; 2 versões válidas/atuais, 2 arquivos físicos e 2 hashes distintos; 0 versões sem hash; 12 tentativas operacionais associadas ao ativo canônico.
- O total era 124 documentos antes da coleta solicitada. A resposta atual do Fundos.NET trouxe 2 novas publicações; o total passou a 126, sem duplicar linhas. O banco tem 168 documentos no total (126 Café Brasil + 42 Almeida Junior).
- A coleta seguinte manteve as 126 linhas: `inserted=0`, `updated=4`, `unchanged=122`, `errors=0`. Os quatro metadados atualizados vieram diferentes no retorno atual do Fundos.NET; não houve nova inserção.
- Amostra final: `inserted=0`, `updated=0`, `unchanged=2`, `new_version=0`, `failed=0`.
- Fundação: `healthy`, `error_count=0`. Suíte completa: **67 testes aprovados**.

Uma primeira tentativa da amostra após descobrir documentos mais recentes expirou durante a navegação da grade. O seletor foi ajustado para preferir versões físicas previamente verificadas e a execução final da amostra passou.

Relatório estruturado: [`duplicate_assets_diagnostic.json`](duplicate_assets_diagnostic.json).
