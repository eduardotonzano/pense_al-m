# Pesquisa das divergências entre documentos (29/10/2026)

Origem: `reports/cross_document_checks.md` (comparação do mesmo dado em Termo, oferta, AF, DFs e Informe Mensal).
Nada aqui altera dados nem aprova fato. Cada item traz as fontes, o que elas dizem e o que ainda falta para fechar.
Onde há interpretação minha, está marcada como **hipótese**.

## Resumo

| # | Ativo | Dado | Quem destoa | Gravidade |
|---|---|---|---|---|
| 1 | Alibem | Vencimento das 5 séries | Informe Mensal (todas as séries, todos os meses) | alta |
| 2 | Alibem | Quantidade emitida das séries 1, 2, 4 e 5 | Relatório do AF 2025 (diz 0) | alta |
| 3 | Alibem | Remuneração da 1ª série | Relatório do AF 2025 (diz "CDI") | média |
| 4 | Alibem | Classe da 4ª série | Informe Mensal (diz Mezanino) | média, já em aberto |
| 5 | Alibem | Fim da 5ª série nas DFs (17/12/2035) | DFs 2026 | baixa |
| 6 | Café Brasil | Vencimento no Informe (30/09/2027) | Informe Mensal (47 meses) | alta |
| 7 | Café Brasil | Classe da série | meu parâmetro pendente × Informe | baixa (correção minha) |

CRI Almeida Junior: nenhuma divergência (9 verificações concordam, 1 compatível).

## 1. Alibem: vencimento por série no Informe

| Série | Termo / Lâmina / Prospecto def. / AF | Informe (todos os 10 meses, dez/2025 a set/2026) |
|---|---|---|
| 1ª | 18/12/2030 | 16/07/2029 |
| 2ª | 18/12/2030 | 15/07/2032 |
| 3ª | 18/12/2030 | 16/07/2035 |
| 4ª | 17/12/2032 | 15/07/2030 |
| 5ª | 19/12/2035 | 15/07/2030 |

- Cinco documentos independentes dão as mesmas datas: Termo (p.66), Lâmina (p.6-7), Prospecto definitivo (p.15), Relatório do AF
  (p.3, 6 e 7) e, indiretamente, as Notas Comerciais (2 dias antes de cada CRA, por desenho).
- As datas do Termo conferem com a conta de dias corridos da Data de Emissão (15/12/2025 + 1.829 dias = 18/12/2030;
  + 2.559 = 17/12/2032; + 3.656 = 19/12/2035).
- As datas do Informe não têm relação com as do Termo (mês de julho em todas, ordem diferente) e não mudam em nenhum mês.
- **Confirmado na tela (imagem enviada por Enrico em 29/10/2026):** a visualização do Informe no Fundos.NET mostra as mesmas datas
  (16/07/2029, 15/07/2032, 16/07/2035, 15/07/2030, 15/07/2030), então não é erro da nossa extração: o dado foi assim informado.
- **Incoerência interna do próprio Informe:** o mesmo quadro diz periodicidade semestral com "mês base da apuração: Junho e Dezembro",
  mas todos os vencimentos caem em julho. As datas do Termo (18/12, 17/12, 19/12) casam com o mês base de dezembro.
- **Hipótese:** campo preenchido de modo errado no cadastro do Informe e nunca corrigido. Os documentos não explicam.
- **Para fechar:** o registro do vencimento na B3/ANBIMA para os ISINs BRECOACRALJ8, LK6, LL4, LM2 e LN0.
  **ENRICO, FAÇA VC MESMO** (a consulta é em sistema da B3/ANBIMA ou da CVM).
- **Impacto:** qualquer alerta ou cálculo de prazo que use o vencimento do Informe fica errado para o Alibem. Usar o Termo.

## 2. Alibem: quantidade emitida no Relatório do AF

- O AF 2025 (doc 1175590, p.3-7) traz "Quantidade emitida 0 / Volume R$ 0,00" nas séries 1, 2, 4 e 5 e 250.000 só na 3ª.
- Contra isso: o **Anúncio de Encerramento de 22/12/2025** (doc 1068059, p.2) informa a distribuição integral: 233.142, 16.858,
  250.000, 100.000 e 150.000 CRA (total 750.000), sem distribuição parcial; o Informe de dez/2025 em diante e o Termo trazem as mesmas
  quantidades.
- O mesmo relatório do AF tem outros defeitos: ISIN "-" em todas as séries, 2ª série ausente da tabela de ativos em circulação,
  saldo da 1ª série incompatível com 233.142 CRA e a ficha da 5ª série desalinhada (p.7).
- **Hipótese:** o AF preencheu o relatório com dados parciais do dia da primeira integralização (19/12/2025). Não afeta o ativo, afeta a
  confiança nesse relatório como fonte.
- **Para fechar:** pedir ao AF (Vórtx) a versão corrigida, ou aceitar o relatório como não confiável para quantidade.

## 3. Alibem: remuneração da 1ª série no AF

- AF 2025 (p.3): "Remuneração CDI". Termo (p.81), Comunicado de oferta, Lâmina e Informe: **prefixada 14,80% a.a.** (Informe: "PRÉ 14,8000 % a.a").
  Na mesma tabela, as séries 2 a 5 do AF batem com o Termo (108% CDI; CDI+1,5%; CDI+2,5%; IPCA+8,88%).
- Cinco fontes dizem prefixada. O AF destoa (mesmo relatório do item 2).
- **Hipótese:** erro de preenchimento do AF. Sem impacto na remuneração real.

## 4. Alibem: classe da 4ª série (já em aberto)

- Termo, Lâmina e prospectos: 4ª série **Subordinada**. Informe: **Mezanino** (3ª e 4ª). As DFs variam de nota para nota.
- A comparação automática reencontrou o mesmo ponto. A decisão de qual classe vale continua sua (`asset_series.classe_termo` × `classe_informe`).

## 5. Alibem: fim da 5ª série nas DFs

- DFs (doc 1328400, p.10): "de 15 de dezembro de 2025 a **17 de dezembro de 2035**". Termo, Lâmina e AF: 19/12/2035.
- **Hipótese forte:** as DFs citam o vencimento da **Nota Comercial** da 5ª série, que vence em 17/12/2035 (Prospecto def. p.88), dois dias
  antes do CRA. Mesmo padrão nas séries 1 (16/12/2030) e 4 (15/12/2032). Falta ver se as DFs dizem isso em outro trecho.

## 6. Café Brasil: vencimento no Informe

- O Informe traz **30/09/2027** em todos os 47 meses (out/2022 a ago/2026), inclusive depois da assembleia de 14/03/2024.
- A ata 619771 aprovou novo fluxo com último pagamento em **30/12/2026** (tabela vista na imagem; a ata não escreve a nova data por extenso)
  e o resgate total foi anunciado para 29/10/2026.
- O parâmetro aprovado `data_vencimento_final_cdca_cra` é 30/12/2026. O Termo original (30/09/2027) agora está registrado como
  parâmetro à parte, vigente só até 13/03/2024.
- **Hipótese:** o Informe e as DFs não foram atualizados depois da assembleia. Não há documento que o confirme.
- **Impacto:** o vencimento do Informe não serve para prazo do Café Brasil.

## 7. Café Brasil: classe da série (correção minha)

- O parâmetro pendente `classe_serie_1` ("Série única; o Termo não divide em classes") é uma inferência minha do silêncio do Termo.
- O Informe diz **Sênior**. O Termo nada diz sobre classe. Uma inferência minha não deve ficar ao lado de um dado real.
- **Proposta:** rejeitar o parâmetro 269 e, se quiser a classe, registrar "Sênior (Informe)" como fonte de menor prioridade. Aguardo você.

## O que isso muda no projeto
- O Informe Mensal tem campos cadastrais errados ou desatualizados em 2 dos 3 ativos (vencimento no Alibem e no Café Brasil). O
  mesmo vale para a classe da 4ª série. Faz sentido um alerta de qualidade "dado cadastral do Informe diverge do Termo", a propor numa
  próxima etapa.
- Relatórios de AF também erram (itens 2 e 3). Convém tratá-los como fonte secundária para dados cadastrais.
