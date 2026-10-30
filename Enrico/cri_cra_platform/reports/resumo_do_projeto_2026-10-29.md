# Plataforma CRI/CRA: o que mudou em 29/10/2026 (escala para o mercado inteiro)

Branch `enricosuman27-e1-auditoria-informes`, PR #21. Continua o resumo de 28/10 (`resumo_do_projeto_2026-10-28.md`).

## Em uma frase
A plataforma passou de 3 ativos lidos à mão para **o mercado inteiro de CRA e CRI** (base de dados abertos da CVM), com triagem,
eventos de crédito, exposição por devedor, placar de securitizadoras e um primeiro lote de 29 ativos com documentos baixados e
comparados automaticamente com o que a securitizadora informa à CVM.

## 1. Mercado inteiro (dados abertos da CVM)
- **Fonte:** Informe Mensal de CRA e CRI publicado pela CVM (2019 a 2026, 16 arquivos, 35,7 MB), carregado em `data/cvm_open.db`
  (banco separado, valor original preservado, SHA-256 por arquivo, recarga idempotente, todas as versões guardadas).
- **Validação:** nos 3 pilotos, 96,4% dos valores por série batem com a nossa extração do XML; a diferença é a rentabilidade do CRI,
  que a CVM publica arredondada.
- **Universo (chave = ISIN da série; a mesma emissão às vezes aparece com dois códigos):** 1.195 emissões de CRA (2.103 séries)
  e 3.690 de CRI (6.929 séries) desde 2019; em ago/2026, 628 CRAs (R$ 160 bi) e 2.312 CRIs (R$ 168 bi) com informe recente.
- **Erros de dado encontrados na própria base:** séries com saldo incompatível com o integralizado (41; ex.: uma série da Leverage com
  R$ 340 bi contra R$ 16,5 mi integralizados), quase metade dos vínculos de devedor sem devedor informado (só 4,5% com CNPJ de fato inválido), ISIN inválido ou repetido.

## 2. O que a plataforma calcula todo mês (`scripts/run_monthly_market.py`, cerca de 40 s)
| Relatório | O que mostra |
|---|---|
| `market_ranking.md` | Emissões ordenadas por sinais (atraso, vencido com saldo, informe defasado, vencimento fora do mês-base, ISIN, saldo incompatível) |
| `market_events.md` | Eventos do mês série a série: entrou/saiu de atraso, rating, vencimento, taxa, saldo caindo sem amortização, saldo zerado. Ago/2026: 12 séries de CRA e 46 de CRI entraram em atraso |
| `market_debtors.md` | Exposição por devedor (CNPJ) somando todas as emissões; **13 devedores com contágio** (uma emissão em atraso e outra ainda adimplente) |
| `market_securitizadoras.md` | Placar por securitizadora: atraso de entrega do Informe, reenvios, erros cadastrais, saldo em atraso |
| `painel_mercado.html` | Painel local com tudo acima, tabelas ordenáveis e filtro |
| `market_asset_history.py --isin` | Histórico mês a mês de uma emissão |

## 3. Lote 1: 29 ativos novos com documentos
- Escolhidos pela triagem (maiores sinais e saldos, até 4 por securitizadora; 10 securitizadoras). Catálogo gravado com backup e
  verificação; ~1.170 documentos baixados pela fila (Termos, aditamentos, relatórios do AF, atas, fatos relevantes, comunicados).
- **Termo × Informe da CVM** (`termo_vs_cvm.md`): extrator determinístico lê do Termo data de emissão, vencimentos (separando o do
  lastro), remuneração, devedor (CNPJ), valor total, quantidade e VNU. Nos pilotos acerta 16 de 16 parâmetros aprovados. Em 31 ativos:
  data de emissão 29/30, remuneração 73/81, vencimento 63/91 (+3 em que o Informe traz a data do lastro), devedor 10/15, VNU 27/30.
- **Assembleias e fatos** (`assembleias_topicos.md`): assunto de cada ata/fato/comunicado (vencimento antecipado, waiver, prorrogação,
  garantias, inadimplência, resgate, troca de prestador).
- **Fichas por ativo** (`reports/fichas/`): uma página por ativo juntando tudo, com índice por séries em atraso e divergências.

## 4. Achados que pedem leitura humana (exemplos)
- **Café Brasil:** o Informe indica como devedor o CNPJ 31.943.818/0001-71, que não aparece no Termo (devedora: 01.486.546/0001-67).
- **Alibem:** vencimentos do Informe diferentes do Termo, do AF, da oferta e das DFs (resolvido com base nas DFs; 5ª série em aberto).
- **Remuneração diferente entre Termo e Informe** em 8 séries (ex.: 23H1753231: Termo 12,68% × Informe 10,68%/14,68%).
- **CRA da Opea** com 5 emissões do mesmo devedor em atraso e uma ainda adimplente (R$ 6,5 bi de exposição estimada).

## 5. Infraestrutura
- Fila de download em lotes (migration 003) com grupos por sessão de navegador, retomada, limite de taxa e paradas automáticas;
  uma falha da sessão inteira conta como uma falha seguida.
- Coletor localiza securitizadoras de nome parecido (Vert, Travessia).
- Testes: 391.

## 6. O que depende de Enrico
- Revisar o PR #21 com o Eduardo.
- Pesos do ranking (hoje: atraso 5, vencido com saldo 4, informe defasado 3, ISIN repetido 3, saldo incompatível 3).
- Aprovar as regras de alerta "cadastro do Informe × Termo" e os itens da fila de revisão (nível 1).
- Consultar o vencimento da 5ª série do Alibem (B3/ANBIMA/CVM).
- Escolher o próximo lote (o `build_market_universe.py` já sugere candidatos).
