# Universo de CRA e CRI (chave: ISIN da série)

Fonte: dados abertos da CVM (`data/cvm_open.db`). Só leitura; nada entra no catálogo sem aprovação.

## CRA (competência de referência 2026-08-01)

- Códigos de certificado na base: 1263; emissões depois de unir os códigos duplicados: **1195** (68 eram a mesma emissão com dois códigos).
- ISINs de série distintos: **2103**; emissões com informe recente: **628**.
- Já no catálogo do projeto (por ISIN): 6 ISINs (BRECOACRABX0, BRECOACRALJ8, BRECOACRALK6, BRECOACRALL4, BRECOACRALM2, BRECOACRALN0).

Candidatos ao lote-piloto (15): ver `config/lote_piloto_candidatos.csv`.

## CRI (competência de referência 2026-08-01)

- Códigos de certificado na base: 4039; emissões depois de unir os códigos duplicados: **3690** (349 eram a mesma emissão com dois códigos).
- ISINs de série distintos: **6929**; emissões com informe recente: **2312**.
- Já no catálogo do projeto (por ISIN): 1 ISINs (BRRBRACRIP13).

Candidatos ao lote-piloto (15): ver `config/lote_piloto_candidatos.csv`.

## Candidatos ao lote-piloto

Critério: pontuação de triagem > 0, informe recente, saldo ≥ R$ 10 mi, ISIN presente, fora do catálogo, até 4 por securitizadora e 15 por tipo. **Pesos:** `em_atraso`=5, `vencido_com_saldo_adimplente`=4, `informe_defasado`=3, `vencimento_fora_mes_base`=2, `isin_repetido`=3, `serie_sem_isin`=1, `identificador_duplicado`=1, `isin_invalido`=2.

| Tipo | Código | ISIN | Securitizadora | Emissão | Saldo (R$ mi) | Pontos | Sinais |
|---|---|---|---|---|---|---|---|
| CRA | CRA023000B5 | BRCASCCRA0K5 | CANAL COMPANHIA DE SECURITIZAÇÃO | 3 | 235.4 | 17 | em_atrasox1; vencido_com_saldo_adimplentex1; vencimento_fora_mes_basex8; serie_sem_isinx10; isin_invalidox1; isin_repetidox1 |
| CRA | CRA019003V3 | BRAPCSCRA0N4 | OPEA SECURITIZADORA S.A | 6 | 1,391.9 | 7 | em_atrasox2; vencimento_fora_mes_basex2 |
| CRA | CRA02300JR5 | BRAPCSCRA1Y9 | OPEA SECURITIZADORA S.A | 73 | 1,102.4 | 7 | vencimento_fora_mes_basex3; em_atrasox2 |
| CRA | CRA020001P8 | BRAPCSCRA0U9 | OPEA SECURITIZADORA S.A | 10 | 1,061.1 | 7 | em_atrasox1; vencimento_fora_mes_basex1 |
| CRA | CRA020001P7 | BRAPCSCRA0T1 | OPEA SECURITIZADORA S.A | 10 | 513.2 | 7 | em_atrasox1; vencimento_fora_mes_basex1 |
| CRA | CRA022007VI | BRIMWLCRA4Q7 | RIZA SECURITIZADORA S.A. | 55 | 28.9 | 7 | vencimento_fora_mes_basex3; isin_invalidox1; isin_repetidox1 |
| CRA | CRA021000S9 | BRIMWLCRA1C3 | RIZA SECURITIZADORA S.A. | 33 | 114.9 | 6 | vencido_com_saldo_adimplentex1; vencimento_fora_mes_basex2 |
| CRA | CRA02100001 | BRIMWLCRA0U7 | RIZA SECURITIZADORA S.A. | 23 | 95.4 | 6 | vencido_com_saldo_adimplentex1; vencimento_fora_mes_basex1 |
| CRA | CRA0210026F | BRIMWLCRA1R1 | RIZA SECURITIZADORA S.A. | 41 | 70.8 | 6 | vencido_com_saldo_adimplentex1; vencimento_fora_mes_basex1 |
| CRA | BRVERTCRA344 | BRVERTCRA344 | Vert Companhia Securitizadora | 79 | 506.5 | 5 | em_atrasox1 |
| CRA | CRA02300TBL | BRECOACRAF93 | Eco Securitizadora de Direitos Creditórios do Agronegócio | 223 | 421.1 | 5 | em_atrasox2 |
| CRA | CRA022009C1F | BRECOACRAC13 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 186 | 339.5 | 5 | em_atrasox2 |
| CRA | CRA0230005N | BRECOACRACJ7 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 231 | 217.7 | 5 | em_atrasox2 |
| CRA | CRA022008C4 | BRECOACRAB97 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 185 | 120.6 | 5 | em_atrasox3 |
| CRA | CRA024007PW | BRVERTCRA4C9 | Vert Companhia Securitizadora | 97 | 118.3 | 5 | em_atrasox2 |
| CRI | 23H1753231 | BRHBSCCRIAB3 | HABITASEC SECURITIZADORA S.A. | 1 | 692.2 | 12 | serie_sem_isinx5; em_atrasox1; isin_invalidox1; vencido_com_saldo_adimplentex1 |
| CRI | 23H1487992 | BRAPCSCRIJL8 | OPEA Securitizadora S.A. | 193 | 41.2 | 10 | em_atrasox1; serie_sem_isinx2; vencido_com_saldo_adimplentex1 |
| CRI | 13D0358495 | BRTSSACRI0K0 | Travessia Securitizadora S.A | 1 | 27.6 | 8 | em_atrasox2; serie_sem_isinx1; isin_invalidox1 |
| CRI | 21L0967403 | BRHBSCCRI452 | HABITASEC SECURITIZADORA S.A. | 1 | 103.3 | 7 | vencido_com_saldo_adimplentex10; isin_repetidox2 |
| CRI | 23E2052239 | BRAPCSCRIIE5 | OPEA SECURITIZADORA S.A | 176 | 60.0 | 7 | em_atrasox1; vencimento_fora_mes_basex2 |
| CRI | 15L0790665 | BRIMWLCRI0G8 | RIZA SECURITIZADORA S.A. | 2 | 12.9 | 7 | em_atrasox2; vencimento_fora_mes_basex2 |
| CRI | 22D0836679 | BRAPCSCRICG3 | OPEA SECURITIZADORA S.A | 11 | 11.1 | 7 | em_atrasox1; vencimento_fora_mes_basex1 |
| CRI | 23F2454937 | BRAPCSCRIIR7 | OPEA Securitizadora S.A. | 192 | 938.9 | 6 | vencido_com_saldo_adimplentex1; vencimento_fora_mes_basex3 |
| CRI | 21A0870788 | BRPVSCCRI1D0 | Companhia Província de Securitização | 3 | 89.2 | 6 | vencido_com_saldo_adimplentex1; vencimento_fora_mes_basex1 |
| CRI | 21K0660418 | BRIMWLCRIA26 | RIZA SECURITIZADORA S.A. | 4 | 22.5 | 6 | vencido_com_saldo_adimplentex1; vencimento_fora_mes_basex3 |
| CRI | 20L0504499 | BRFSECCRID64 | FORTE SECURITIZADORA S.A. | 1 | 924.6 | 5 | em_atrasox6 |
| CRI | 24D3466320 | BRFSECCRIKK1 | FORTE SECURITIZADORA S.A. | 8 | 731.9 | 5 | em_atrasox1 |
| CRI | 23I1698089 | BRBASECRI115 | BASE SECURITIZADORA S.A. | 5 | 704.5 | 5 | em_atrasox1 |
| CRI | 23K2122788 | BRBASECRI131 | BASE SECURITIZADORA S.A. | 6 | 699.0 | 5 | em_atrasox1 |
| CRI | 23C1835265 | BRFSECCRIJN7 | FORTE SECURITIZADORA S.A. | 3 | 652.5 | 5 | em_atrasox12 |
