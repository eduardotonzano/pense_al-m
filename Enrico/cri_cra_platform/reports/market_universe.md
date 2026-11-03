# Universo de CRA e CRI (chave: ISIN da série)

Fonte: dados abertos da CVM (`data/cvm_open.db`). Só leitura; nada entra no catálogo sem aprovação.

## CRA (competência de referência 2026-09-01)

- Códigos de certificado na base: 1263; emissões depois de unir os códigos duplicados: **1208** (55 eram a mesma emissão com dois códigos).
- ISINs de série distintos: **2077**; emissões com informe recente: **630**.
- Já no catálogo do projeto (por ISIN): 34 ISINs (BRAPCSCRA0N4, BRAPCSCRA0T1, BRAPCSCRA0U9, BRAPCSCRA1B7, BRAPCSCRA1Y9, BRAPCSCRA2S9, BRAPCSCRA2Y7, BRCASCCRA0A6...).

Candidatos ao lote-piloto (15): ver `config/lote_piloto_candidatos.csv`.

## CRI (competência de referência 2026-09-01)

- Códigos de certificado na base: 4072; emissões depois de unir os códigos duplicados: **3845** (227 eram a mesma emissão com dois códigos).
- ISINs de série distintos: **6916**; emissões com informe recente: **2421**.
- Já no catálogo do projeto (por ISIN): 40 ISINs (BRAPCSCRIAU8, BRAPCSCRICG3, BRAPCSCRIIE5, BRAPCSCRIIR7, BRAPCSCRIIZ0, BRAPCSCRIJI4, BRAPCSCRIJL8, BRAPCSCRIQK5...).

Candidatos ao lote-piloto (15): ver `config/lote_piloto_candidatos.csv`.

## Candidatos ao lote-piloto

Critério: pontuação de triagem > 0, informe recente, saldo ≥ R$ 10 mi, ISIN presente, fora do catálogo, até 4 por securitizadora e 15 por tipo. **Pesos:** `em_atraso`=5, `vencido_com_saldo_adimplente`=4, `informe_defasado`=3, `vencimento_fora_mes_base`=2, `isin_repetido`=3, `serie_sem_isin`=1, `identificador_duplicado`=1, `isin_invalido`=2, `saldo_incompativel`=3, `situacao_mista_na_classe`=3.

| Tipo | Código | ISIN | Securitizadora | Emissão | Saldo (R$ mi) | Pontos | Sinais |
|---|---|---|---|---|---|---|---|
| CRA | CRA0210059T | BRECOACRA8A1 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 124 | 914.6 | 5 | em_atrasox2 |
| CRA | BRVERTCRA344 | BRVERTCRA344 | Vert Companhia Securitizadora | 79 | 506.5 | 5 | em_atrasox1 |
| CRA | CRA017002GX | BRBSIPCRA004 | BSI CAPITAL SECURITIZADORA S/A | 1 | 68.2 | 5 | em_atrasox1 |
| CRA | CRA02200E1N | BRAPCSCRA1M4 | OPEA SECURITIZADORA S.A. | 46 | 56.1 | 5 | em_atrasox1 |
| CRA | CRA0220093U | BRECOACRABO9 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 196 | 47.2 | 5 | em_atrasox1 |
| CRA | CRA022005K3 | BRIMWLCRA457 | RIZA SECURITIZADORA S.A. | 96 | 47.0 | 5 | em_atrasox1 |
| CRA | CRA02200CCK | BRECOACRACE8 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 216 | 40.0 | 5 | em_atrasox1 |
| CRA | CRA01600023 | BRECOACRA1K5 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 1 | 27.8 | 5 | em_atrasox2 |
| CRA | CRA02300R5T | BRAPCSCRA2A7 | OPEA SECURITIZADORA S.A | 76 | 22.7 | 5 | em_atrasox1 |
| CRA | CRA024001JP | BRLSECCRA026 | Leverage Companhia Securitizadora | 4 | 21.6 | 5 | em_atrasox2 |
| CRA | CRA02300A16 | BRAPCSCRA1S1 | OPEA SECURITIZADORA S.A. | 60 | 15.3 | 5 | em_atrasox1 |
| CRA | CRA025004MP | BRTSSACRA0Q5 | Travessia Securitizadora S.A | 23 | 117.7 | 4 | vencido_com_saldo_adimplentex2 |
| CRA | CRA025008SP | BRIMWLCRAB15 | RIZA SECURITIZADORA S.A. | 275 | 106.2 | 4 | vencido_com_saldo_adimplentex2 |
| CRA | CRA021002C2 | BRVERTCRA2E9 | VERT Companhia Securitizadora | 54 | 66.2 | 4 | vencido_com_saldo_adimplentex1 |
| CRA | CRA02300B41 | BRTSSACRA0H4 | Travessia Securitizadora S.A | 16 | 55.1 | 4 | vencido_com_saldo_adimplentex1 |
| CRI | 22E1321751 | BRAPCSCRIDX6 | OPEA SECURITIZADORA S.A. | 37 | 45.2 | 12 | em_atrasox1; vencido_com_saldo_adimplentex1; situacao_mista_na_classex1 |
| CRI | 20E0107293 | BRAPCSCRI7N1 | OPEA SECURITIZADORA S.A. | 1 | 72.1 | 11 | vencido_com_saldo_adimplentex1; vencimento_fora_mes_basex2; em_atrasox1 |
| CRI | 25G0658366 | BRRBRACRIW55 | OPEA SECURITIZADORA S.A. | 470 | 623.3 | 10 | em_atrasox2; vencimento_fora_mes_basex4; situacao_mista_na_classex1 |
| CRI | 23C2830574 | BRAPCSCRIHI8 | OPEA SECURITIZADORA S.A. | 146 | 45.7 | 10 | vencimento_fora_mes_basex5; em_atrasox3; situacao_mista_na_classex1 |
| CRI | 10L0027006 | BRBSCSCRI4Y1 | BSEC COMPANHIA DE SECURITIZAÇÃO | 1 | 10.7 | 10 | em_atrasox2; saldo_incompativelx1; isin_invalidox1 |
| CRI | 13G0253578 | BRCBSCCRI2O4 | Riza II Securitizadora S.A | 2 | 76.0 | 9 | vencido_com_saldo_adimplentex1; em_atrasox1 |
| CRI | 23B0493519 | BRCASCCRI0D2 | CANAL COMPANHIA DE SECURITIZAÇÃO | 33 | 28.2 | 7 | em_atrasox3; vencimento_fora_mes_basex3 |
| CRI | 22E1273339 | BRCASCCRI018 | CANAL COMPANHIA DE SECURITIZAÇÃO | 2 | 157.4 | 6 | vencido_com_saldo_adimplentex1; isin_invalidox1 |
| CRI | 16B0742429 | BRPLSCCRI0J1 | POLO CAPITAL SECURITIZADORA S.A. | 1 | 15.0 | 6 | vencido_com_saldo_adimplentex2; isin_invalidox2 |
| CRI | 15E0109160 | BRAPCSCRI1E3 | OPEA SECURITIZADORA S.A. | 1 | 521.0 | 5 | em_atrasox1 |
| CRI | 23F2545080 | BRFSECCRIJZ1 | FORTE SECURITIZADORA S.A. | 5 | 399.8 | 5 | em_atrasox4 |
| CRI | 21G0064620 | BRFSECCRIFB0 | FORTE SECURITIZADORA S.A. | 1 | 238.0 | 5 | em_atrasox2 |
| CRI | 20F0736267 | BRFSECCRIB25 | FORTE SECURITIZADORA S.A. | 1 | 228.9 | 5 | em_atrasox7 |
| CRI | 21F0568504 | BRIMWLCRI7B4 | RIZA SECURITIZADORA S.A. | 4 | 199.8 | 5 | em_atrasox2 |
| CRI | 21G0613844 | BRBSIPCRI098 | BSI CAPITAL SECURITIZADORA S/A | 1 | 175.1 | 5 | em_atrasox3 |
