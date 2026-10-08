# Execução de download da amostra

- Run ID: `bd034834859c4b2ab0c6afe959f4893a`
- Ativo: `CRA022009VM` / `BRECOACRABX0`
- Dry run: **False**
- Categorias encontradas: Informe Mensal, Ata/Edital
- Categorias ausentes: Termo de Securitização, Aditamento
- Observação de categorias: Termo de Securitização e Aditamento não identificados automaticamente; as categorias persistidas no catálogo são Outro. Nenhuma categoria foi inventada; requer análise posterior dos nomes e conteúdos.
- Linhas da grade verificadas para ISIN: 2
- Todas as linhas selecionadas verificadas: True

## Documentos selecionados

- `1300722` — Informe Mensal — Informe Mensal de CRA — `data/documents/CRA022009VM/informes_mensais/2026-08-26_1300722_Informe_Mensal_de_CRA.<extensao_detectada>`
- `1319505` — Ata/Edital — AGO/E — `data/documents/CRA022009VM/atas_editais/2026-09-15_1319505_AGO_E.<extensao_detectada>`

## Arquivos

- `1300722`: unchanged, XML / 11212 bytes, SHA-256 `78e08103f6e4cfd010241512b774958145186904d95a5bba8eb489409f4503ab`, `data/documents/CRA022009VM/informes_mensais/2026-08-26_1300722_Informe_Mensal_de_CRA.xml`
- `1319505`: unchanged, PDF / 227832 bytes, SHA-256 `8779765c21b61e550d4ecf9399232773e042f4d5136003196846a149743149b2`, `data/documents/CRA022009VM/atas_editais/2026-09-15_1319505_AGO_E.pdf`

## Métricas

- inserted: 0
- updated: 0
- unchanged: 2
- new_version: 0
- duplicate_content: 0
- failed: 0
- tentativas operacionais registradas: 2
- temporários removidos: 2
- diretório temporário removido: True
- duração: 75.6879s

## Erros

- Nenhum.

## Migração do ativo canônico

- Ativo canônico: `asset_id=1`, CETIP `CRA022009VM`, ISIN `BRECOACRABX0`, emissão `190`, série `1` (exibição: **Série única (1ª série)**).
- Migrados de `asset_id=6`: 124 documentos, 2 versões documentais (por meio dos documentos) e 6 tentativas operacionais.
- Colisões documentais por `(source_document_id, source)`, hash, URL, categoria e data de referência: nenhuma.
- `asset_id=6`: removido após verificação de zero referências restantes.
- Antes da coleta atual havia 124 documentos do Café Brasil; a coleta real encontrou 126 e adicionou 2 publicações do Fundos.NET. Após a coleta, existem 126 documentos do ativo e 168 documentos no banco (incluindo 42 do Almeida Junior). A segunda coleta manteve as 126 linhas, sem inserções; 4 metadados foram atualizados pelo retorno corrente do Fundos.NET.
- Total após a migração: 2 versões válidas/atuais, 2 arquivos físicos, 2 hashes distintos, 0 versões sem hash e 12 tentativas associadas ao ativo canônico.
- Fundação: `healthy`, 0 erros. Suíte: **67 testes aprovados**.
- A primeira tentativa de amostra após a coleta dos documentos mais recentes expirou ao abrir a grade. O seletor foi ajustado para priorizar documentos com versão física já validada; a repetição final registrada acima terminou sem erros e sem criar versões.
