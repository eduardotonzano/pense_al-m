# Universo de CRA e CRI (chave: ISIN da série)

Fonte: dados abertos da CVM (`data/cvm_open.db`). Só leitura; nada entra no catálogo sem aprovação.

## CRA (competência de referência 2026-08-01)

- Códigos de certificado na base: 1263; emissões depois de unir os códigos duplicados: **1209** (54 eram a mesma emissão com dois códigos).
- ISINs de série distintos: **2077**; emissões com informe recente: **630**.
- Já no catálogo do projeto (por ISIN): 20 ISINs (BRAPCSCRA0N4, BRAPCSCRA0T1, BRAPCSCRA0U9, BRAPCSCRA1Y9, BRCASCCRA0K5, BRECOACRAB97, BRECOACRABX0, BRECOACRAC13...).

Candidatos ao lote-piloto (15): ver `config/lote_piloto_candidatos.csv`.

## CRI (competência de referência 2026-08-01)

- Códigos de certificado na base: 4039; emissões depois de unir os códigos duplicados: **3813** (226 eram a mesma emissão com dois códigos).
- ISINs de série distintos: **6836**; emissões com informe recente: **2369**.
- Já no catálogo do projeto (por ISIN): 16 ISINs (BRAPCSCRICG3, BRAPCSCRIIE5, BRAPCSCRIIR7, BRAPCSCRIJL8, BRBASECRI115, BRBASECRI131, BRFSECCRID64, BRFSECCRIJN7...).

Candidatos ao lote-piloto (15): ver `config/lote_piloto_candidatos.csv`.

## Candidatos ao lote-piloto

Critério: pontuação de triagem > 0, informe recente, saldo ≥ R$ 10 mi, ISIN presente, fora do catálogo, até 4 por securitizadora e 15 por tipo. **Pesos:** `em_atraso`=5, `vencido_com_saldo_adimplente`=4, `informe_defasado`=3, `vencimento_fora_mes_base`=2, `isin_repetido`=3, `serie_sem_isin`=1, `identificador_duplicado`=1, `isin_invalido`=2, `saldo_incompativel`=3, `situacao_mista_na_classe`=3.

| Tipo | Código | ISIN | Securitizadora | Emissão | Saldo (R$ mi) | Pontos | Sinais |
|---|---|---|---|---|---|---|---|
| CRA | CRA024000GP | BRAPCSCRA2S9 | OPEA Securitizadora S.A. | 82 | 90.7 | 8 | em_atrasox1; situacao_mista_na_classex1 |
| CRA | CRA019000XD | BRIMWLCRA093 | RIZA SECURITIZADORA S.A. | 3 | 64.6 | 6 | vencido_com_saldo_adimplentex1; vencimento_fora_mes_basex1 |
| CRA | CRA024003PF | BRIMWLCRA7Y4 | RIZA SECURITIZADORA S.A. | 196 | 40.3 | 6 | vencido_com_saldo_adimplentex1; vencimento_fora_mes_basex2 |
| CRA | CRA022008NB | BRAPCSCRA1B7 | OPEA SECURITIZADORA S.A | 38 | 2,414.6 | 5 | em_atrasox2 |
| CRA | BRVERTCRA344 | BRVERTCRA344 | Vert Companhia Securitizadora | 79 | 506.5 | 5 | em_atrasox1 |
| CRA | CRA023000040H | BRECOACRACX8 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 237 | 120.3 | 5 | em_atrasox1 |
| CRA | CRA01500002 | BRECOACRA0Q4 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 1 | 100.6 | 5 | em_atrasox1 |
| CRA | CRA0230018I | BRCASCCRA0A6 | CANAL COMPANHIA DE SECURITIZAÇÃO | 32 | 96.0 | 5 | em_atrasox1 |
| CRA | CRA022001JL | BRECOACRA9K8 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 137 | 87.9 | 5 | em_atrasox2 |
| CRA | CRA02300VY3 | BRCASCCRA0S8 | CANAL COMPANHIA DE SECURITIZAÇÃO | 76 | 85.3 | 5 | em_atrasox2 |
| CRA | CRA024002S4 | BRCASCCRA0V2 | CANAL COMPANHIA DE SECURITIZAÇÃO | 89 | 79.1 | 5 | em_atrasox2 |
| CRA | CRA02400E1M | BRECOACRAIF2 | Eco Securitizdora de Direitos Creditórios do Agronegócio | 376 | 74.0 | 5 | em_atrasox3 |
| CRA | CRA02000130 | BRFSECCRA010 | FORTE SECURITIZADORA S.A. | 3 | 70.2 | 5 | em_atrasox2 |
| CRA | CRA024004XT | BRAPCSCRA2Y7 | OPEA SECURITIZADORA S.A | 91 | 66.7 | 5 | em_atrasox2 |
| CRA | CRA024006N5 | BRCASCCRA0Y6 | CANAL COMPANHIA DE SECURITIZAÇÃO | 103 | 64.8 | 5 | em_atrasox2 |
| CRI | 23I0096173 | BRFSECCRIKC8 | FORTE SECURITIZADORA S.A. | 7 | 611.9 | 8 | em_atrasox1; situacao_mista_na_classex1 |
| CRI | 24E2535171 | BRBASECRI198 | BASE SECURITIZADORA S.A. | 9 | 506.4 | 8 | em_atrasox1; situacao_mista_na_classex1 |
| CRI | 23H1097588 | BRBASECRI0X9 | BASE SECURITIZADORA S.A. | 3 | 465.9 | 8 | em_atrasox3; situacao_mista_na_classex1 |
| CRI | 23G1576657 | BRFSECCRIK73 | FORTE SECURITIZADORA S.A. | 4 | 407.4 | 8 | em_atrasox3; situacao_mista_na_classex1 |
| CRI | 21H1002745 | BRAPCSCRIAU8 | OPEA Securitizadora S.A. | 1 | 66.3 | 8 | em_atrasox1; situacao_mista_na_classex1 |
| CRI | 25F8582172 | BRCASCCRI5V3 | CANAL COMPANHIA DE SECURITIZAÇÃO | 147 | 42.6 | 8 | em_atrasox1; situacao_mista_na_classex1 |
| CRI | 23F2472075 | BRAPCSCRIIZ0 | OPEA Securitizadora S.A. | 181 | 26.4 | 8 | em_atrasox1; situacao_mista_na_classex1 |
| CRI | 23F1829746 | BRPVSCCRI2E6 | Companhia Província de Securitização | 29 | 19.4 | 8 | em_atrasox1; situacao_mista_na_classex1 |
| CRI | 24L2327181 | BRIMWLCRILH5 | RIZA SECURITIZADORA S.A. | 172 | 15.7 | 8 | em_atrasox1; situacao_mista_na_classex1 |
| CRI | 23B0493519 | BRCASCCRI0D2 | CANAL COMPANHIA DE SECURITIZAÇÃO | 33 | 28.2 | 7 | em_atrasox3; vencimento_fora_mes_basex3 |
| CRI | 23H1186528 | BRAPCSCRIJI4 | OPEA Securitizadora S.A. | 208 | 373.8 | 6 | vencido_com_saldo_adimplentex1; vencimento_fora_mes_basex3 |
| CRI | 22E1273339 | BRCASCCRI018 | CANAL COMPANHIA DE SECURITIZAÇÃO | 2 | 157.3 | 6 | vencido_com_saldo_adimplentex1; isin_invalidox1 |
| CRI | 16B0742429 | BRPLSCCRI0J1 | POLO CAPITAL SECURITIZADORA S.A. | 1 | 14.9 | 6 | vencido_com_saldo_adimplentex2; isin_invalidox2 |
| CRI | 20H0225976 | BRFSECCRIC65 | FORTE SECURITIZADORA S.A. | 1 | 604.2 | 5 | em_atrasox8 |
| CRI | 14L0157828 | BRCBSCCRI3B9 | RIZA II SECUTIRIZADORA S.A | 2 | 487.2 | 5 | em_atrasox4 |
