# Lote 2: prévia do catálogo (dry-run de 30/10/2026)

Consulta ao Fundos.NET sem gravar nada (`run_document_catalog.py --dry-run`), aprovada por Enrico em 30/10/2026. Lista: `config/lote_piloto_candidatos.csv` (29 ativos; o BRVERTCRA344 fica fora porque o código CETIP é igual ao ISIN). Nenhum documento existe hoje no catálogo para esses ativos.

| Ativo | Tipo | Securitizadora | Saldo (R$ mi) | Documentos | Situação |
|---|---|---|---|---|---|
| CRA024000GP | CRA | OPEA Securitizadora S.A. | 90.7 | 66 | ok depois da correção na lista (ver abaixo) |
| CRA019000XD | CRA | RIZA SECURITIZADORA S.A. | 64.6 | 138 | ok |
| CRA024003PF | CRA | RIZA SECURITIZADORA S.A. | 40.3 | 65 | ok |
| CRA022008NB | CRA | OPEA SECURITIZADORA S.A | 2,414.6 | 101 | ok |
| CRA023000040H | CRA | Eco Securitizdora de Direitos Creditórios do Agronegócio | 120.3 | 79 | ok |
| CRA01500002 | CRA | Eco Securitizdora de Direitos Creditórios do Agronegócio | 100.6 | 120 | ok |
| CRA0230018I | CRA | CANAL COMPANHIA DE SECURITIZAÇÃO | 96.0 | 96 | ok |
| CRA022001JL | CRA | Eco Securitizdora de Direitos Creditórios do Agronegócio | 87.9 | 130 | ok |
| CRA02300VY3 | CRA | CANAL COMPANHIA DE SECURITIZAÇÃO | 85.3 | 116 | ok |
| CRA024002S4 | CRA | CANAL COMPANHIA DE SECURITIZAÇÃO | 79.1 | 70 | ok |
| CRA02400E1M | CRA | Eco Securitizdora de Direitos Creditórios do Agronegócio | 74.0 | 46 | ok |
| CRA02000130 | CRA | FORTE SECURITIZADORA S.A. | 70.2 | 138 | ok |
| CRA024004XT | CRA | OPEA SECURITIZADORA S.A | 66.7 | 59 | ok |
| CRA024006N5 | CRA | CANAL COMPANHIA DE SECURITIZAÇÃO | 64.8 | 112 | ok |
| 23I0096173 | CRI | FORTE SECURITIZADORA S.A. | 611.9 | 69 | ok |
| 24E2535171 | CRI | BASE SECURITIZADORA S.A. | 506.4 | 51 | ok |
| 23H1097588 | CRI | BASE SECURITIZADORA S.A. | 465.9 | 67 | ok |
| 23G1576657 | CRI | FORTE SECURITIZADORA S.A. | 407.4 | 77 | ok |
| 21H1002745 | CRI | OPEA Securitizadora S.A. | 66.3 | 126 | ok |
| 25F8582172 | CRI | CANAL COMPANHIA DE SECURITIZAÇÃO | 42.6 | 26 | ok |
| 23F2472075 | CRI | OPEA Securitizadora S.A. | 26.4 | 76 | ok |
| 23F1829746 | CRI | Companhia Província de Securitização | 19.4 | 83 | ok |
| 24L2327181 | CRI | RIZA SECURITIZADORA S.A. | 15.7 | 56 | ok |
| 24J0943210 | CRI | OPEA SECURITIZADORA S.A | 317.1 | 55 | ok |
| 23H1186528 | CRI | OPEA Securitizadora S.A. | 373.8 | 77 | ok |
| 20H0225976 | CRI | FORTE SECURITIZADORA S.A. | 604.2 | 168 | ok |
| 14L0157828 | CRI | RIZA II SECURITIZADORA S.A. | 487.2 | 135 | ok depois da correção na lista (ver abaixo) |
| 21H0769214 | CRI | FORTE SECURITIZADORA S.A. | 435.9 | 126 | ok |

**Sem a Leverage: 28 ativos, 2.528 documentos novos.**

## Leverage: as 11 emissões que a CVM juntava num certificado (pedido de Enrico: monitorar todas)

O "certificado" 25C3273266 da lista era, na verdade, 11 emissões diferentes da Leverage unidas pelo placeholder de ISIN "00000" na triagem do mercado (erro da união, corrigido em `market_checks.real_isin`). Cada emissão virou um ativo, identificado no Fundos.NET pelo código do certificado. Dry-run de 30/10/2026:

| Ativo (CETIP da 1ª série com ISIN) | Certificado | Emissão | Nome | Saldo (R$ mi) | Documentos |
|---|---|---|---|---|---|
| 24E2495042 | BRLSECCRI0Q9 | 11 | Yvy Supreme | 12.9 | 44 |
| 25C3273266 | BRLSECCRI2L6 | 32 | Longitude | 44.8 | 33 |
| 25K3156592 | BRLSECCRI3R1 | 58 | Meraki | 15.0 | 16 |
| 25L2378911 | BRLSECCRI3V3 | 62 | Rottas | 30.1 | 15 |
| 25L3279335 | BRLSECCRI441 | 65 | Genesis | 7.8 | 16 |
| 26D2618959 | BRLSECCRI4I8 | 72 | Brio | 35.8 | 20 |
| 26D4402695 | BRLSECCRI4P3 | 75 | Teriva | 19.8 | 9 |
| 26D7086699 | BRLSECCRI4V1 | 56 | Cajamar | 70.9 | 8 |
| 26F3681477 | BRLSECCRI5H7 | 96 | Bauten Tekoa | 7.9 | 5 |
| 26G2446032 | BRLSECCRI5R6 | 94 | Huma Brooklin | 9.0 | 7 |

- A 11ª, **TKN003LEVE001** (8ª emissão, CRI Haute, R$ 15,2 mi), é um token sem ISIN: o coletor localiza a emissão por ISIN, então ela fica fora até haver outro jeito de identificá-la no Fundos.NET.

**Total do lote 2 (`config/lote2_ativos.csv`, congelado): 38 ativos e 2.701 documentos novos.**

## Correções e bloqueio

- **CRA024000GP (Opea, 82ª emissão):** o Fundos.NET lista a emissão pelo código da 2ª série, BRAPCSCRA2S9 (que a CVM também traz para a emissão), e não pelo ISIN da 1ª série, BRAPCSCRA2R1. A lista passou a usar BRAPCSCRA2S9.
- **14L0157828 (ex-Cibrasec):** o nome da securitizadora vem da CVM com erro de digitação ("RIZA II SECUTIRIZADORA S.A"). Corrigido para "RIZA II SECURITIZADORA S.A." na lista; o CNPJ 02.105.040/0001-23 não muda.
- **25C3273266 (Leverage):** resolvido acima; o bloqueio do coletor estava certo (o ISIN era da emissão 32, a lista dizia 11).

A lista de candidatos (`config/lote_piloto_candidatos.csv`) é regerada pela triagem e mudou com a correção da união; o lote 2 aprovado para dry-run fica congelado em `config/lote2_ativos.csv` (ativo=false).

Próximo passo, com aprovação: gravar os 38 ativos no catálogo (`--commit`) e, depois, baixar os 2.701 documentos pela fila.
