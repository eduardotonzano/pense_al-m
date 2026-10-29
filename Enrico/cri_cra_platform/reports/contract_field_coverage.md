# Cobertura dos campos contratuais padrão

Catálogo `0.1.0` (proposto; aguarda revisão). Gerado só a partir de `contract_parameters`.

| Ativo | Core aprovados | Core pendentes | Core faltando | Important aprovados | Important faltando |
|---|---|---|---|---|---|
| 24G2100031 | 23 | 0 | 0 | 9 | 2 |
| CRA022009VM | 12 | 0 | 11 | 3 | 8 |
| CRA02500C1D | 21 | 0 | 2 | 4 | 7 |

## 24G2100031

**Campos sem parâmetro:**
- `covenants.restricoes` (important): Restrições (dividendos, capex, mútuos)
- `resgate.waiver_fee` (important): Waiver fee e prêmios

## CRA022009VM

**Campos sem parâmetro:**
- `identificacao.isin` (core): ISIN
- `identificacao.numero_emissao` (core): Número da emissão
- `identificacao.numero_series` (important): Número de séries
- `identificacao.devedor` (core): Devedor / cedente / avalista
- `identificacao.agente_fiduciario` (complementary): Agente fiduciário e remuneração
- `identificacao.lastro` (core): Lastro (créditos que originam os CRI/CRA)
- `identificacao.classe_serie` (core): Classe da série (sênior, mezanino, subordinada)
- `emissao.data_emissao` (core): Data de emissão
- `emissao.quantidade_titulos` (core): Quantidade de CRI/CRA
- `remuneracao.periodicidade` (core): Periodicidade de pagamento
- `remuneracao.primeira_data_pagamento` (important): Primeira data de pagamento
- `remuneracao.atualizacao_monetaria` (important): Atualização monetária
- `remuneracao.encargos_moratorios` (complementary): Encargos moratórios
- `garantias.liberacao` (important): Liberação e substituição de garantias
- `vencimento_antecipado.limites_e_prazos` (core): Limites (cross default, protesto) e prazos de cura
- `vencimento_antecipado.pagamento_e_quorum` (important): Pagamento após vencimento antecipado e quórum de não declaração
- `vencimento_antecipado.liquidacao_ps` (important): Eventos de liquidação do patrimônio separado
- `obrigacoes.rating` (core): Obrigação de rating
- `obrigacoes.destinacao_recursos` (important): Destinação de recursos
- `governanca.quorum_assembleia` (important): Convocação, instalação e quóruns de assembleia
- `governanca.ordem_pagamentos` (core): Ordem de pagamentos e alocação (cascata)

## CRA02500C1D

**Campos sem parâmetro:**
- `identificacao.numero_emissao` (core): Número da emissão
- `identificacao.numero_series` (important): Número de séries
- `remuneracao.encargos_moratorios` (complementary): Encargos moratórios
- `garantias.razao_minima` (core): Razão mínima de garantia
- `garantias.liberacao` (important): Liberação e substituição de garantias
- `garantias.fundo_reserva_retencao` (important): Fundo de reserva, retenção ou liquidez
- `covenants.restricoes` (important): Restrições (dividendos, capex, mútuos)
- `resgate.waiver_fee` (important): Waiver fee e prêmios
- `obrigacoes.destinacao_recursos` (important): Destinação de recursos
- `governanca.quorum_assembleia` (important): Convocação, instalação e quóruns de assembleia
