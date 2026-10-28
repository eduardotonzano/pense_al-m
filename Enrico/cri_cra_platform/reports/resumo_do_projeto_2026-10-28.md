# Plataforma CRI/CRA: resumo do que foi feito até 28/10/2026

Branch: `enricosuman27-e1-auditoria-informes`. Projeto: `Enrico/cri_cra_platform`.
Dados reais ficam só local (`data/cri_cra.db`, `data/documents/`, `data/backups/`) e não vão para o Git.

## Linha do tempo da semana (20 a 28/10/2026)

Fonte: histórico do Git da branch (34 commits em seu nome na frente CRI/CRA) e as conversas desta sessão.
Os commits de Eduardo (debêntures, Fundos, documentação) entraram na branch pelos merges de 22/10 e 27/10 e
estão resumidos no fim desta seção.

### Terça 21/10: base técnica do CRI/CRA
- **Classificação de documentos:** "Demonstrações Financeiras" passa a ser classificada como `Outro` antes
  dos termos genéricos de informe (`946b9c1`), com migration pontual para reclassificar o que já estava
  no banco (`35b2a38`). Ajuste anterior de prioridade em 14/10 (`f8d9b22`).
- **Download por identificador:** a amostra de Informes Mensais pode ser baixada por `source_document_id`
  explícito (`1030262`, `217c714`).
- **Diagnóstico estrutural do XML** do Informe Mensal de CRA e o **primeiro golden set** com amostra de
  reenvio (`89eb065`, `a1ad479`, `03f592b`).
- **Migrations numeradas** para o CRI/CRA, com `apply_migration.py` (backup, transação e verificação antes
  de confirmar), feitas por Eduardo (`5f39283`).

### Quarta 22/10: catálogo
- Catálogo completo de documentos com os campos oficiais da grade do Fundos.NET, classificador estrito de
  categoria com prévia e reclassificação, aviso de migration pendente sem erro de traceback, e documentação
  (todos de Eduardo; migration `001_document_catalog.sql`).
- Pull requests #3 a #7 integrados à `main`.

### Segunda 26/10: extração, comparação e alertas (Café Brasil e Alibem)
- **Golden sets** do Informe Mensal CRA aprovados por você (itens do Café Brasil e do Alibem).
- **Piloto multissérie Alibem** criado; **52 Informes Mensais do Café Brasil** baixados e diagnóstico estendido.
- **Tabelas de extração bruta** e extrator v0; depois **mapeamento 0.1.0** com extração guiada (extrator 0.2.0)
  e **0.1.1** (total do passivo com a redução do valor da emissão em sinal invertido).
- **Revisão de relatórios** e seleção da versão vigente; **comparação entre períodos**; **alertas de qualidade
  de dado** (regras 0.1.0 aprovadas, com triagem dos alertas do Café Brasil).
- **Termo de Securitização do Café Brasil:** extração de cláusulas candidatas e fluxo de revisão; **14
  parâmetros contratuais aprovados**.
- **Relatórios do agente fiduciário (2022 a 2025) e fato relevante** baixados; análise de garantias.
- **Fatos reportados e alertas contratuais** do Café Brasil.
- **Atas e comunicados** (32 atas/editais e 12 comunicados): parâmetros versionados por vigência e regra de
  prazo de obrigações.

### Terça 27/10: assembleias, Alibem e CRI Almeida Junior
- Aprovação dos 15 parâmetros das assembleias e da regra de prazos; fatos das DFs do Patrimônio Separado
  do Café Brasil (6) e fatos do **resgate antecipado anunciado** (7).
- **Merge da `main`** na branch, com resolução de conflitos (modelo de documento, coletor, `run_document_catalog`
  sem a lista fixa de pilotos, testes ajustados).
- **Página de revisão pendente** (HTML com trecho literal e link para a página do PDF).
- **Alibem:** informes completos (10), Termo, AF, DFs e comunicado; 91 parâmetros e 99 fatos (aprovados);
  análise com divergências e o erro de classes no Informe de jun/2026.
- **CRI Almeida Junior:** mapeamento do Informe de CRI (rascunho por analogia ao CRA, depois aprovado como
  `cri-0.1.1`), extração dos 26 informes, golden set de 17 itens, 94 parâmetros e 105 fatos do Termo, AF, DFs
  e atas, regras de qualidade e primeiros alertas.
- Todas as decisões abertas foram respondidas por você (escala do CRI, set/2026, campos pendentes, identidade
  do ativo Alibem).
- **Migration 002 e script de séries** escritos e testados em cópia do banco.

### Quarta 28/10
- Migration 002 aplicada no banco real com backup e verificação, e 7 séries cadastradas como pendentes.
- Este resumo.

### Correção de rota registrada
- O comunicado 1358128 (resgate antecipado do Café Brasil) foi baixado antes de ser lido, e por isso o
  anúncio de resgate só apareceu depois. Corrigido em 27/10.

### Trabalho de Eduardo integrado à branch (para contexto)
- 20/10: README do projeto, `CLAUDE.md`, ADR-006 e decisões em aberto da Fase 0.
- 21/10: ajustes do contrato de leitura de debêntures e migration `debenture_events` na versão de debêntures.
- 26 a 27/10: descoberta da frente de Fundos (FIDC, FIC-FIDC, FIAGRO), amostras de 09/2026, decisões da
  Fase 0 aprovadas em 27/10 e sonda da grade do Fundos.NET (PRs #10 a #15).

## 1. Objetivo e regras que guiam tudo

Coletar documentos do Fundos.NET, versionar cada arquivo por SHA-256, extrair dados com rastreabilidade,
comparar períodos e gerar alertas. Primeiro três pilotos, depois o mercado inteiro.

Regras do handoff, seguidas em todas as etapas:
- não inventar dado; não escolher em silêncio entre ambiguidades;
- SQLite é a fonte de verdade, CSV é só exportação; preservar histórico;
- todo valor aponta para a fonte; nunca sobrescrever preenchido com vazio;
- separar fato de interpretação; falha de coleta não vira versão de documento;
- não misturar dados sintéticos com o banco real;
- revisão humana obrigatória para casos incertos e parâmetros contratuais;
- IA só em texto livre, nunca alimentando alerta numérico; `Decimal`, nunca float;
- ausente ≠ vazio ≠ zero.

Regra operacional do projeto: nenhum `--commit` sem sua aprovação explícita; sempre `--dry-run` antes;
backup antes de qualquer migration.

## 2. Ativos acompanhados

| Ativo | Código / ISIN | Devedor | Informes | Situação do trabalho |
|---|---|---|---|---|
| CRA Café Brasil (190ª, 1ª série) | CRA022009VM / BRECOACRABX0 | Café Brasil | 52 documentos de Informe | Informes, Termo, AF 2022–2025, atas 2023–2026, DFs 2023–2026 e comunicados lidos; revisão humana pendente (ver seção 11) |
| CRA Alibem (426ª, 5 séries) | CRA02500C1D / BRECOACRALJ8 (1ª série) | Alibem Alimentos | 10 (dez/2025–set/2026) | Termo, AF, DFs, informes e documentos de oferta lidos; revisão humana pendente (ver seção 11) |
| CRI Almeida Junior (301ª, 1ª série) | 24G2100031 / BRRBRACRIP13 | Almeida Junior | 26 (ago/2024–set/2026) | Informes, Termo, AF, DFs, atas e alertas |

## 3. O que foi construído

1. **Coleta e catálogo:** documentos do Fundos.NET baixados e versionados por SHA-256, com texto por página
   (`document_text_pages`). Catálogo local com 197 documentos, 194 com versão física válida (3 ainda sem download: ver seção 11).
2. **Extração de XML dos Informes Mensais** guiada por mapeamento versionado:
   - CRA: mapeamento `0.1.1`, aprovado.
   - CRI: mapeamento `cri-0.1.1` (novo, derivado do CRA), aprovado em 27/10. O serviço de extração agora
     lê a raiz do leiaute (`InformeMensalCRA` ou `InformeMensalCRI`).
3. **Golden sets** (itens do XML conferidos por humano contra o arquivo bruto): Café Brasil, Alibem e
   CRI Almeida Junior (17 itens). A extração confere com 56/56 itens.
4. **Revisão e vigência dos relatórios:** a versão vigente do mês é a de maior versão aprovada.
5. **Comparação entre períodos** para os três ativos, com indicadores por leiaute (CRA e CRI).
6. **Alertas:**
   - qualidade de dado: situação × atraso, conciliação de saldo, rentabilidade fora do padrão, mudança de
     parte relevante (regras CRA e CRI aprovadas);
   - contratuais: regras do Café Brasil. O script de alertas agora recusa regras sem aprovação.
7. **Parâmetros contratuais** com trecho literal, página e link para o PDF, versionados por vigência
   (`valid_from`, `valid_to`, `supersedes`). **Fatos reportados** com trecho literal conferido na página.
8. **Página de revisão** local (`scripts/export_pending_review.py`): lista pendências com trecho e link
   para a página do PDF.
9. **Migration 002** (tabela `asset_series`) com script `load_asset_series.py`: séries de cada ativo com
   código, ISIN, classe do Informe e classe do Termo, evidência e revisão humana.

## 4. Números do que está aprovado

- Café Brasil: 14 parâmetros do Termo (26/10) + 15 de assembleias (27/10); 6 fatos das DFs do Patrimônio
  Separado e 7 do resgate antecipado.
- Alibem: 91 parâmetros e 99 fatos (aprovados em 27/10).
- CRI Almeida Junior: 94 parâmetros e 105 fatos (aprovados em 27/10); 25 informes aprovados, set/2026 rejeitado.
- 7 séries cadastradas, todas pendentes de revisão (5 Alibem, 1 CRI, 1 Café Brasil).
- Testes: 267 passam. Banco: `integrity_check` ok, `foreign_key_check` vazio.

## 5. Principais achados

### Café Brasil (CRA022009VM)
- Evento de crédito: em 30/12/2025 a devedora não pagou integralmente a parcela; houve assembleias,
  repactuação e amortizações extraordinárias em 2026.
- Em 31/12/2025, cessão fiduciária + conta garantia = R$ 2,40 mi, abaixo do mínimo de R$ 10 mi (descumprimento).
  A razão de garantia ficou em 292% (conforme).
- O Informe diz "sem garantias reais" e zera inadimplência em mar/2026, mas o AF e as DFs trazem garantias
  e R$ 7,089 mil vencidos e não pagos.
- Resgate antecipado total anunciado para 29/10/2026 (comunicado 1358128): PU total R$ 463,31143486,
  projeção de R$ 46,33 mi. Anunciado, **não confirmado**. A taxa de waiver de 0,5% (cerca de R$ 231,7 mil)
  não aparece no comunicado e continua sem evidência.

### Alibem (CRA02500C1D)
- Emissão de R$ 750 mi em 5 séries: 1ª e 2ª Sênior, 3ª Mezanino, 4ª e 5ª Subordinadas (pelo Termo).
- Sem garantias sobre os CRA e sem índice mínimo de subordinação; covenants de liquidez corrente ≥ 1,20 e
  Dívida Líquida/EBITDA ≤ 3,0x sobre as DFs do avalista, que não estão no Fundos.NET.
- O Informe de jun/2026 lançou os pagamentos por classe de forma errada (confirmado pelas DFs por série).
  Pelo Termo: Sênior ≈ R$ 17,07 mi, Mezanino ≈ R$ 18,79 mi, Subordinada ≈ R$ 14,44 mi; total R$ 50,30 mi confere.
- A 4ª série é Subordinada no Termo e Mezanino no Informe.
- Ativo total em set/2026: R$ 786,46 mi; saldo dos CRA R$ 785,53 mi, dividido em terços entre as classes
  do Termo. Caixa zerado no Informe contra R$ 95 mil nas DFs; carteira do Informe R$ 847 mil acima da DF.
- Decisão de 27/10: o ativo representa a emissão inteira; BRECOACRALJ8 é o ISIN da 1ª série.

### CRI Almeida Junior (24G2100031)
- Série única de R$ 230 mi, CDI + 1,50% a.a. (2,75% a partir de 29/08/2030), juros mensais, amortização
  a partir de set/2027, vencimento em 2036. Lastro em debêntures, via CCI.
- Garantias: alienação fiduciária de parte do Shopping Neumarkt (LTV máx. 60%) e cessão fiduciária de
  aluguéis (ICSD mín. 1,20x). O AF 2025 marca as duas como **não constituídas**; as DFs dizem que a emissão
  "conta com" elas.
- Rating anual da Fitch exigido pelo Termo; AF e DFs dizem que não há rating contratado.
- Informe de set/2026 se contradiz (séries vazias, carteira e passivo zerados, 230.000 CRI e rendimentos).
  Nenhum documento explica; tratado como erro de preenchimento.
- 6 alertas abertos: rentabilidade 0 no primeiro mês (ago/2024) e 5 conciliações de saldo com resíduo de
  0,10%–0,12%, logo acima da tolerância de 0,10%.
- O relatório anual do AF de 2024 é um PDF em imagem, sem texto extraível: nenhum fato dele.

## 6. Decisões suas registradas

| Data | Decisão |
|---|---|
| 26/10 | Aprovação dos parâmetros do Termo e das regras de extração CRA |
| 27/10 | Aprovação das assembleias do Café Brasil e dos prazos de obrigação |
| 27/10 | Aprovação do Alibem (91 + 99), do mapeamento CRI e das 94 + 105 do CRI |
| 27/10 | Regra de escala do CRI usa o saldo do passivo (o campo de PU não serve) |
| 27/10 | Relação carteira/emissão do CRI como fração; duration só como literal |
| 27/10 | Set/2026 do CRI rejeitado como erro de preenchimento |
| 27/10 | Ativo do Alibem = emissão inteira |
| 28/10 | Migration 002 e cadastro das 7 séries aplicados no banco real |

## 7. Mudanças no banco real

- Migration 001 (catálogo de documentos), já existente, e **002 (asset_series)**, aplicada em 28/10 com backup
  `data/backups/cri_cra_20261028T174650_747190Z.sqlite3` (SHA-256 `7c1655a7…438f`).
- Tabelas antigas do projeto ainda usam o mecanismo de `ALTER` no `initialize_database`; converter para
  migrations numeradas é opcional e ainda não foi feito.

## 8. Commits na branch (mais recentes primeiro)

`6c1e5f2` migration 002 e séries · `5bbfadb` decisões do CRI, comparação e alertas ·
`cfb7c0b` parâmetros e fatos do CRI · `f7c15ce` regras de qualidade do CRI e trava de aprovação ·
`75bb1f2` extração do CRI e golden set · `5aa1ac8` parâmetros e fatos do Alibem ·
`422ac58` informes do Alibem e rascunho do mapeamento CRI · `dfdd09d` página de revisão ·
`0ca94fa` resgate antecipado do Café Brasil. Tudo enviado ao GitHub.
Abertura do PR (feita por você):
https://github.com/eduardotonzano/pense_al-m/compare/main...enricosuman27-e1-auditoria-informes

## 9. Pendências e próximos passos

- **Revisão sua:** aprovar as 7 séries (a 4ª do Alibem tem classe divergente: Termo Subordinada, Informe Mezanino).
- **A partir de 30/10:** atualizar o catálogo do Café Brasil e confirmar o resgate de 29/10 e a taxa de 0,5%;
  verificar se as DFs da devedora (prazo 30/05/2026) foram entregues.
- **Ata da 2ª convocação do CRI** (28/10 às 14:30): baixar quando for publicada.
- **Alertas do CRI:** decidir se os 5 de conciliação de saldo são descartados ou se a tolerância é ajustada.
- **Alibem:** DFs do avalista (covenants) não estão no Fundos.NET; relatório de gestão do patrimônio separado
  não foi recebido pelo AF.
- **CRI:** esclarecer a ausência de garantias constituídas e do rating; set/2026 aguarda documento.
- **Qualidade de extração:** o PDF do AF 2024 do CRI exige OCR; trechos de tabelas desalinhadas em PDFs
  (Alibem p.35, CRI spread e prêmios de resgate) merecem conferência visual.
- **Depois dos pilotos:** estender a coleta ao mercado inteiro.

## 10. Onde está cada coisa

| O quê | Onde |
|---|---|
| Análises por ativo | `reports/cra022009vm_analise_garantias.md`, `reports/cra02500c1d_analise.md`, `reports/24g2100031_informes_cri.md` |
| Páginas de revisão | `reports/*_revisao_pendente.html` |
| Mapeamentos | `config/xml_mappings/` |
| Regras de alerta | `config/alert_rules/` |
| Golden sets | `config/golden_sets/` |
| Parâmetros e fatos propostos | `config/contract_parameters/`, `config/reported_facts/` |
| Séries e comparações | `reports/*_serie_indicadores.csv`, `reports/*_mudancas_entre_periodos.csv`, `reports/*_alertas_qualidade.csv` |
| Migrations | `migrations/` e `scripts/apply_migration.py` |

## 11. Revisão de 28/10: o que não tinha sido lido, e o que foi feito

Você perguntou se eu tinha repetido nos CRAs o erro de baixar documento sem lê-lo. Tinha, de três formas.

**1. Baixados, mas sem registro:** comunicado 1140992 (19/03/2026), que retifica a alocação das amortizações de 03/02 e
26/02 (totais inalterados); comunicados de reuniões trimestrais; comunicado 1090229 com quadro financeiro da Devedora
(não registrado: colunas desalinhadas, exige conferência visual).

**2. Catalogados e nunca baixados:** 23 documentos do Café Brasil, 7 do Alibem e 7 do CRI. Baixados em 28/10: 34 arquivos
(23 + 6 + 5, ISIN conferido na grade, texto extraído com o novo `scripts/extract_document_text.py`). Continuam sem
download: Prospecto definitivo do CRI 727241 (passa do limite de 25 MB do serviço) e os Anúncios de Encerramento
(categoria fora da amostra aprovada) do CRI e do Alibem.

**3. Sem texto (imagem):** AF 2024 do CRI (199 páginas). Li as páginas 1 a 8 visualmente; não vira fato, porque o
carregador exige trecho literal em texto extraído. Não há OCR instalado.

**Carregado como pendente em 28/10** (nada aprovado; decisão sua):

| Ativo | Fatos pendentes | Parâmetros pendentes | Conteúdo |
|---|---|---|---|
| Café Brasil | 183 | 9 | atas 2023–2024 (66 fatos, 9 parâmetros), DFs 2023–2025 e comunicados (103), comunicados 2025–2026 (14) |
| Alibem | 218 | 0 | oferta (Aviso, Lâmina, Anúncio, 3 prospectos) e Termo da oferta |
| CRI Almeida Junior | 110 | 0 | oferta (Aviso, 2 Lâminas, Anúncio, Prospecto preliminar) |

**Principais descobertas**
- Café Brasil: a assembleia de 14/03/2024 mudou o vencimento final para 30/12/2026 e aprovou o cronograma de amortização
  (R$ 30 mi, R$ 30,002 mi, R$ 39,998 mi), com waiver fee de 0,75%. Isso explica a divergência de datas do vencimento
  e o evento de 30/12/2025. O problema de recomposição de garantia vem desde 2024.
- Alibem: nenhum documento da oferta nem o Termo chama a 4ª série de Mezanino; o Informe chama. A declaração do agente
  fiduciário diz "1 subclasse Mezanino e 2 subclasses Subordinadas Júniores", coerente com 3ª Mezanino e 4ª e 5ª Subordinadas.
  Decisão sobre a classe continua sua.
- CRI: a cessão fiduciária nasce sob condição suspensiva e a alienação fiduciária depende de Termo de Liberação
  averbado (51% do imóvel já alienados em 2021); compatível com o "não constituída" do AF 2025, mas só matrículas
  e cartório confirmam. O rating nos documentos é sempre o preliminar AA-(EXP)sf(bra).

**Limites da leitura:** os prospectos (539 a 1.140 páginas) foram lidos em parte e o restante por palavra-chave; as páginas
lidas estão em `reports/cra02500c1d_oferta_vs_termo.md` e `reports/24g2100031_oferta_vs_termo.md`. O prospecto definitivo
do CRI não foi lido.
