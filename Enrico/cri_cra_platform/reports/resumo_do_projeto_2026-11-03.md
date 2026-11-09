# Plataforma CRI/CRA: encerramento (03/11/2026)

Branch `enricosuman27-e1-auditoria-informes`, PR #21 → `main`. Continua `resumo_do_projeto_2026-10-29.md`; o histórico detalhado
está em `plano_escala_mercado.md` (seções "Andamento").

## Em uma frase
A plataforma cobre o **mercado inteiro de CRA e CRI** com o Informe Mensal dos dados abertos da CVM (triagem, eventos de crédito,
devedores, securitizadoras, DFs dos patrimônios separados), e **70 ativos priorizados** com documentos do Fundos.NET lidos
(Termo × Informe, fichas contratuais, decisões das atas, acompanhamento de crédito), tudo numa rotina mensal de um comando.

## O que está entregue
| Camada | Cobertura | Onde |
|---|---|---|
| Mercado inteiro (CVM) | 1.208 emissões de CRA e 3.845 de CRI desde 2019; competência mais recente set/2026 | `data/cvm_open.db`, `data/cvm_dfin.db`, `reports/market_*.md`, `reports/painel_mercado.html` |
| Documentos | 70 ativos, ~5.800 documentos catalogados, ~2.350 baixados com texto por página (OCR marcado) | `data/cri_cra.db`, `data/documents/` |
| Leitura de documentos | Termo × Informe, 36 campos contratuais com trecho e página, assuntos e decisões das atas | `reports/termo_vs_cvm.md`, `reports/fichas_contratuais/`, `reports/assembleias_topicos.md` |
| Acompanhamento | 70 ativos em 5 níveis de gravidade, cada motivo com a fonte | `reports/acompanhamento_credito.md`, `reports/fichas/` |
| Pilotos (Café Brasil, Alibem, 24G2100031) | Parâmetros e fatos com trecho literal; 704 fatos aprovados por Enrico | `config/reported_facts/`, `config/contract_parameters/` |

Testes: 426 (CRI/CRA) e 285 (camada compartilhada), todos passando em 03/11/2026.

## Como operar todo mês
```powershell
cd Enrico\cri_cra_platform
python scripts/run_monthly_market.py --dry-run     # confere sem gravar
python scripts/run_monthly_market.py --commit      # ingestão da CVM + todos os relatórios + painel (~8 min)
python scripts/market_asset_history.py --isin <ISIN>   # histórico de uma emissão
```
Novo lote de ativos com documentos: lista em `config/ativos_loteN.csv` → `run_document_catalog.py --dry-run` → backup →
`run_document_catalog.py` → `run_download_queue.py --enqueue/--run` (sempre `--dry-run` antes) → `extract_document_text.py` →
`ocr_document_pages.py` → rotina mensal. Os lotes 1 e 2 seguiram esse roteiro (ver plano).

## Retrato de set/2026
- **44 séries de CRA entraram em atraso** (12 em ago/2026). Maiores: Opea BRAPCSCRA0M6 (R$ 1,17 bi) e Eco BRECOACRA8A1 (R$ 738 mi).
- Acompanhamento: 11 ativos no nível 1 (evento grave nas atas: recuperação judicial ou extrajudicial da Raízen, Prime Agro, Patense,
  Grupo Formoso; vencimento antecipado declarado; dação em pagamento) e 33 no nível 2 (atraso no Informe).
- **Café Brasil:** Informe de 09/2026 ainda "Em atraso" (saldo R$ 45,7 mi). O resgate antecipado anunciado para 29/10/2026 e a taxa de
  waiver de 0,5% (31/10) **não estão confirmados**; conferir no Informe de 10/2026 ou em comunicado da Eco.

## Correção feita no encerramento
O leitor de CSV da CVM perdia registros sem erro quando um campo abria aspa sem fechar (17 registros do CRI de 2019 a 2022) e
falhou no CRI de 2026. Corrigido e relido com `ingest_cvm_open_data.py --commit --reparse`, com backup e verificação.

## O que depende de pessoas
1. **Revisão e merge do PR #21** (Enrico com o Eduardo).
2. **Fila de revisão dos pilotos** (`fila_revisao_priorizada.md`): 187 itens, 18 no nível 1; 158 fatos pendentes. Nada é aprovado
   sem revisão humana com escopo explícito.
3. **Parâmetros de triagem ainda provisórios:** pesos do ranking (atraso 5, vencido com saldo 4, informe defasado 3, ISIN repetido 3,
   saldo incompatível 3, situação mista 3) e prazo de 90 dias para a DF do patrimônio separado (muitas saem entre 91 e 120 dias).
4. **Regras pendentes** (contratuais do Alibem e do CRI, cadastro do Informe × Termo): só rodam com `--preview` até aprovação.
5. Vencimento da 5ª série do Alibem (B3/ANBIMA/CVM) e confirmação do resgate do Café Brasil.
6. Próximo lote: `build_market_universe.py` já sugere 15 candidatos por tipo em `config/lote_piloto_candidatos.csv`.

## Limites conhecidos
- O dado da CVM é o do Informe: erros de preenchimento vêm junto. A triagem aponta candidatos, não conclusões.
- Regras de texto (Termo × CVM, fichas, decisões das atas) e OCR são triagem com trecho e página; conferir no PDF antes de usar como fato.
- Universo da CVM e catálogo se cruzam só por ISIN, em relatório; a integração com a camada compartilhada (`src/pense_alm/shared`)
  ainda não foi feita para o universo da CVM.
- Arquivos sem leitura: documento 4122 (fila 2363, acima de 25 MB) e 451412 (PDF corrompido, relatório do AF de 2022 do 21L0967403).
- Bancos, documentos baixados e backups ficam fora do Git (`data/`); recriá-los exige rodar as ingestões.
- Interface e layout fora do escopo até o levantamento de requisitos da equipe (ADR-001).
