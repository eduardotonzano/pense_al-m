# Plataforma CRI/CRA: o que entrou em 03 e 04/11/2026

Branch `enricosuman27-e1-auditoria-informes`, PR #21 → `main`. Continua `resumo_do_projeto_2026-11-03.md`.

## Em uma frase
Além do Informe da CVM para o mercado inteiro, agora há **documentos do Fundos.NET catalogados para quase todas as emissões vivas**
e **covenants apurados todo mês** (exigido × apurado × situação) para as emissões de seis securitizadoras, num formato único que
alimenta o módulo Covenants do MVP.

## Entregas
| Frente | Cobertura | Onde |
|---|---|---|
| Fundos.NET, mercado inteiro | 2.959 ativos e 206 mil documentos catalogados; 2.887 de 2.905 emissões vivas (99,4%); 12.605 documentos baixados dos 663 ativos com sinal de triagem | `data/cri_cra.db`, `logs/mercado_*.log` |
| Garantias e covenants do Termo | 14 tipos de garantia e 6 covenants com limite, com trecho e página | `reports/garantias_covenants.md` |
| Covenants apurados (Opea) | 1.926 relatórios mensais, 23 mil itens; 2.297 não atendidos em 864 emissões | `reports/opea_monitoramentos.md` |
| Covenants apurados (Vert, Leverage, Canal, Bari) | 153, 106, 176 e 91 relatórios | `reports/{vert,leverage,canal,bari}_monitoramentos.md` |
| Acompanhamento da Eco | 164 relatórios de gestão, 34 de acompanhamento (garantias × saldo, carteira vencida, aderência ao Termo) | `reports/eco_relatorios_mensais.md` |
| Riza | "Default" no portal × Informe da CVM (40 operações divergentes) | `reports/riza_status_vs_cvm.md` |
| Base única de covenants | 2.768 CETIPs com valor apurado, 34% do saldo da lista do mercado | `reports/covenants_mensais.{md,csv}` |
| Alertas por ativo | 1.365 ativos com sinal; 18 em duas ou mais fontes | `reports/alertas_por_ativo.md` |
| Atas pelos portais | 2.107 documentos desde 01/08/2026 (Opea 1.794, Eco 248, Vert 40, Riza 25) com assunto e decisão; 97 eventos graves decididos em ata, 409 só no texto; 281 lidos por OCR | `reports/atas_portais.{md,csv}` |

## Como operar todo mês
```powershell
cd Enrico\cri_cra_platform
python scripts/run_monthly_market.py --dry-run              # confere sem gravar
python scripts/run_monthly_market.py --commit --portais     # CVM + relatórios mensais e atas dos portais + consolidados
```
Sem `--portais` a rotina só relê os relatórios já baixados. A coleta da Opea leva horas (~10 s por emissão). Cada coletor também
roda sozinho (`scripts/collect_<securitizadora>_reports.py --dry-run|--commit|--parse-only`).

## Achados para leitura (não são conclusões)
- **Opea:** Oncoclínicas II com dívida/EBITDA de 4,27 contra o máximo de 3,5; Bluecap com LTV de 66% e 90% (máximo de 60%);
  Tenda com índice de cobertura de 121% (mínimo de 165%); Tourmalet com LTV de 115% (máximo de 70%).
- **Vert:** Solfácil com as três razões de cobertura abaixo do mínimo; You Inc com razão de garantia de 1,02 (mínimo de 1,60);
  Lifestyle Barigui com fundo de reserva abaixo do mínimo.
- **Canal:** HBX ED 4 com razão de garantia de 0,33 (mínimo de 1,24), em reestruturação; Tocantins Energias com ICSD de 0,36
  (mínimo de 1,15).
- **Bari:** 13 itens não atendidos em 9 relatórios: fundo de reserva abaixo do mínimo (1ª emissão 84ª série GPA, 63ª, 64ª e 67ª emissões), ICM de 1,29 contra 1,30 (52ª, Mitre), Índice de Término de Obras de 81,67% e 85,9% contra 105% (60ª; 64ª com waiver até 24/12/2026). O relatório da 42ª traz o Código IF da 64ª (cópia de modelo).
- **Eco:** em vários CRAs de revenda de insumos a própria Eco informa a carteira de recebíveis 100% vencida (Agrícola Panorama,
  Nativa, Tecplante, Coopernorte). Três pares de emissões trazem o bloco de saldo devedor idêntico (169 × 252, 229 × 271,
  413 × 439), provável cópia de modelo no relatório.
- **Riza:** 40 operações em "Default" no portal aparecem "Adimplente" no Informe da CVM (GPA, Uniggel, Lermen, Rovaris...).
- **Atas (Opea):** liquidação do patrimônio separado aprovada pelo único titular na CRA 71ª (ALG, 16/10/2026, saldo da CPR-F de
  R$ 42,99 mi; conferida na imagem do PDF); CRI 257ª (Axis II, 20/10/2026) teve os efeitos de um vencimento antecipado automático
  **sustados** sob condição resolutiva até 31/12/2026 (não é declaração de vencimento antecipado). Waivers e não declarações de
  vencimento antecipado em Eco (Bem Brasil, Nativa, Solubio, Coplana) e Opea (General Shopping, Aikon, Bevap III, Caeté...).
- **Almeida Junior (24G2100031):** as AGTs de 19/10 e 28/10/2026 não foram instaladas (pauta de rotina).

## Limites e pendências
- Sites de securitizadora são a fonte de menor prioridade: complementam a CVM, nunca a corrigem, e nada disso é gravado no banco.
  A situação é a que a securitizadora informa, sem dedução; waiver citado em nota de rodapé não muda o "Desenquadrado".
- **Atas, conferência:** ata cuja reunião é posterior à data da coleta é minuta (texto de modelo "aprovou(aram)") e sai como
  `minuta_reuniao_futura`, sem decisão (3 casos, entre eles MZ Log e JFL Lorena); o classificador distingue "sustação dos efeitos" de
  declaração de vencimento antecipado. Amostra de 6 atas conferida contra o PDF (4 pelo texto, 2 pela imagem); não é revisão completa.
  Riza só rendeu 25 documentos antes do 403.
- **Riza** passou a responder 403 (acesso recusado) em 04/11/2026; os coletores param na hora e não tentam contornar.
- **Bari** (2,3% do saldo): leitor por regras de posição sobre vários modelos de relatório; 58 dos 91 relatórios com item lido (os
  outros 33 não trazem quadro com situação); quadro ambíguo não vira item. Província, Forte, Habitasec e Travessia não publicam covenant apurado (só Informe da CVM ou relatório anual do agente fiduciário).
- Vert: leitor heurístico sobre layouts variados, corrigido em dois casos de razão de garantia. Conferência em 14 relatórios
  sorteados (39 valores): todos existem no PDF, na coluna e no item certos, com a mesma situação; feita pelo mesmo autor do
  leitor, não por terceiro. Limite: 59 dos 177 itens de covenant (13 relatórios) ficam sem data de apuração; em 11 desses
  relatórios o PDF (painel Power BI) não informa a data, e em 2 ela está no cabeçalho e não foi lida ("Realizado 2025",
  "31/03/2026"). Índices anuais ou trimestrais podem ser bem anteriores ao mês do relatório (ex.: 31/12/2023 em 09/2026).
  Leverage conferida de forma independente (79 itens iguais ao PDF).
- A cadeia do Fundos.NET segue em segundo plano: texto e OCR dos prioritários; depois download dos demais, texto e remoção do PDF
  (só com hash conferido e todas as páginas com texto). Disco com 25 GB livres.

## O que depende de pessoas
1. Revisão e merge do PR #21 (Enrico com o Eduardo).
2. Fila de revisão dos pilotos (`fila_revisao_priorizada.md`) e confirmação do resgate do Café Brasil (Informe de 10/2026).
3. Decidir com a equipe as regras de exibição do MVP (G-01..G-13, S-01..S-11). Há uma proposta para as de Securitizados em
   `reports/proposta_regras_exibicao_securitizados.md`, com cinco pontos que só as pessoas decidem.
