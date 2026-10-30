# Universo de CRA e CRI (chave: ISIN da série)

Fonte: dados abertos da CVM (`data/cvm_open.db`). Só leitura; nada entra no catálogo sem aprovação.

## CRA (competência de referência 2026-08-01)

- Códigos de certificado na base: 1263; emissões depois de unir os códigos duplicados: **1209** (54 eram a mesma emissão com dois códigos).
- ISINs de série distintos: **2077**; emissões com informe recente: **630**.
- Já no catálogo do projeto (por ISIN): 34 ISINs (BRAPCSCRA0N4, BRAPCSCRA0T1, BRAPCSCRA0U9, BRAPCSCRA1B7, BRAPCSCRA1Y9, BRAPCSCRA2S9, BRAPCSCRA2Y7, BRCASCCRA0A6...).

Candidatos ao lote-piloto (15): ver `config/lote_piloto_candidatos.csv`.

## CRI (competência de referência 2026-08-01)

- Códigos de certificado na base: 4039; emissões depois de unir os códigos duplicados: **3813** (226 eram a mesma emissão com dois códigos).
- ISINs de série distintos: **6836**; emissões com informe recente: **2369**.
- Já no catálogo do projeto (por ISIN): 40 ISINs (BRAPCSCRIAU8, BRAPCSCRICG3, BRAPCSCRIIE5, BRAPCSCRIIR7, BRAPCSCRIIZ0, BRAPCSCRIJI4, BRAPCSCRIJL8, BRAPCSCRIQK5...).

Candidatos ao lote-piloto (15): ver `config/lote_piloto_candidatos.csv`.

## Candidatos ao lote-piloto

Critério: pontuação de triagem > 0, informe recente, saldo ≥ R$ 10 mi, ISIN presente, fora do catálogo, até 4 por securitizadora e 15 por tipo. **Pesos:** `em_atraso`=5, `vencido_com_saldo_adimplente`=4, `informe_defasado`=3, `vencimento_fora_mes_base`=2, `isin_repetido`=3, `serie_sem_isin`=1, `identificador_duplicado`=1, `isin_invalido`=2, `saldo_incompativel`=3, `situacao_mista_na_classe`=3.

| Tipo | Código | ISIN | Securitizadora | Emissão | Saldo (R$ mi) | Pontos | Sinais |
|---|---|---|---|---|---|---|---|
| CRA | BRVERTCRA344 | BRVERTCRA344 | Vert Companhia Securitizadora | 79 | 506.5 | 5 | em_atrasox1 |
| CRA | CRA017002GX | BRBSIPCRA004 | BSI CAPITAL SECURITIZADORA S/A | 1 | 47.7 | 5 | em_atrasox1 |
| CRA | CRA0220093U | BRECOACRABO9 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 196 | 47.2 | 5 | em_atrasox1 |
| CRA | CRA022005K3 | BRIMWLCRA457 | RIZA SECURITIZADORA S.A. | 96 | 47.0 | 5 | em_atrasox1 |
| CRA | CRA01600023 | BRECOACRA1K5 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 1 | 27.6 | 5 | em_atrasox2 |
| CRA | CRA019002S6 | BRECOACRA440 | Eco Securitizadora de Direitos Creditórios do Agronegócio | 11 | 24.8 | 5 | em_atrasox1 |
| CRA | CRA02300R5T | BRAPCSCRA2A7 | OPEA SECURITIZADORA S.A | 76 | 23.5 | 5 | em_atrasox1 |
| CRA | CRA0210039M | BRECOACRA853 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 105 | 23.4 | 5 | em_atrasox1 |
| CRA | CRA024001JP | BRLSECCRA026 | Leverage Companhia Securitizadora | 4 | 21.1 | 5 | em_atrasox2 |
| CRA | CRA025004MP | BRTSSACRA0Q5 | Travessia Securitizadora S.A | 23 | 117.7 | 4 | vencido_com_saldo_adimplentex2 |
| CRA | CRA026005EH | BRCASCCRA1M9 | CANAL COMPANHIA DE SECURITIZAÇÃO | 208 | 110.9 | 4 | vencido_com_saldo_adimplentex1 |
| CRA | CRA025008SP | BRIMWLCRAB15 | RIZA SECURITIZADORA S.A. | 275 | 106.3 | 4 | vencido_com_saldo_adimplentex2 |
| CRA | CRA0210046X | BRIMWLCRA2L2 | RIZA SECURITIZADORA S.A. | 67 | 80.1 | 4 | vencido_com_saldo_adimplentex4 |
| CRA | CRA02100471 | BRIMWLCRA2P3 | RIZA SECURITIZADORA S.A. | 68 | 80.1 | 4 | vencido_com_saldo_adimplentex4 |
| CRA | CRA021002C2 | BRVERTCRA2E9 | VERT Companhia Securitizadora | 54 | 65.7 | 4 | vencido_com_saldo_adimplentex1 |
| CRI | 23B0493519 | BRCASCCRI0D2 | CANAL COMPANHIA DE SECURITIZAÇÃO | 33 | 28.2 | 7 | em_atrasox3; vencimento_fora_mes_basex3 |
| CRI | 22E1273339 | BRCASCCRI018 | CANAL COMPANHIA DE SECURITIZAÇÃO | 2 | 157.3 | 6 | vencido_com_saldo_adimplentex1; isin_invalidox1 |
| CRI | 16B0742429 | BRPLSCCRI0J1 | POLO CAPITAL SECURITIZADORA S.A. | 1 | 14.9 | 6 | vencido_com_saldo_adimplentex2; isin_invalidox2 |
| CRI | 19H0235501 | BRAPCSCRI5T2 | OPEA SECURITIZADORA S.A | 1 | 397.8 | 5 | em_atrasox1 |
| CRI | 23F2545080 | BRFSECCRIJZ1 | FORTE SECURITIZADORA S.A. | 5 | 394.8 | 5 | em_atrasox4 |
| CRI | 22L1668224 | BRAPCSCRIGE9 | OPEA SECURITIZADORA S.A | 111 | 264.9 | 5 | em_atrasox1 |
| CRI | 21G0064620 | BRFSECCRIFB0 | FORTE SECURITIZADORA S.A. | 1 | 235.8 | 5 | em_atrasox2 |
| CRI | 20F0736267 | BRFSECCRIB25 | FORTE SECURITIZADORA S.A. | 1 | 226.7 | 5 | em_atrasox7 |
| CRI | 21F0568504 | BRIMWLCRI7B4 | RIZA SECURITIZADORA S.A. | 4 | 199.8 | 5 | em_atrasox2 |
| CRI | 21G0613844 | BRBSIPCRI098 | BSI CAPITAL SECURITIZADORA S/A | 1 | 171.9 | 5 | em_atrasox3 |
| CRI | 21I0183215 | BRFSECCRIH37 | FORTE SECURITIZADORA S.A. | 1 | 159.6 | 5 | em_atrasox2 |
| CRI | 13F0034990 | BRHBSCCRI0M7 | HABITASEC SECURITIZADORA S.A. | 1 | 152.5 | 5 | em_atrasox2 |
| CRI | 24D0781832 | BRCASCCRI372 | CANAL COMPANHIA DE SECURITIZAÇÃO | 88 | 126.5 | 5 | em_atrasox2 |
| CRI | 16H0156564 | BRHBSCCRI1J1 | HABITASEC SECURITIZADORA S.A. | 1 | 122.8 | 5 | em_atrasox1 |
| CRI | 12J0017777 | BRHBSCCRI0A2 | HABITASEC SECURITIZADORA S.A. | 1 | 120.8 | 5 | em_atrasox3 |
