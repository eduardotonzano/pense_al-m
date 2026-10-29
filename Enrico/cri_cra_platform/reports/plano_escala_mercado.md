# Plano para escalar ao mercado inteiro de CRI e CRA (29/10/2026)

## O que mudou
Até aqui cada ativo foi lido a fundo, documento por documento, com revisão humana de cada item. Isso gerou boa qualidade e três pilotos
sólidos, mas não escala. A CVM publica nos **dados abertos** o Informe Mensal estruturado de **todos** os CRA e CRI:

| Conjunto | Fonte | 2026 (até set/2026) |
|---|---|---|
| Informe Mensal de CRA | `dados.cvm.gov.br/dados/SECURIT/DOC/INF_MENSAL_CRA/DADOS/` | 737 emissões, 1.323 séries (ISIN), 22 securitizadoras |
| Informe Mensal de CRI | `dados.cvm.gov.br/dados/SECURIT/DOC/INF_MENSAL_CRI/DADOS/` | 2.586 emissões, 5.042 séries (ISIN), 36 securitizadoras |

- Um ZIP por ano desde 2019; 16 arquivos, **35,7 MB** no total (conferido por `--dry-run`); sem navegador, sem fila, sem limite de taxa.
- Os 5 papéis dos pilotos aparecem lá com os mesmos valores que extraímos do XML (vencimento, classe, taxa, quantidade). A fonte é o mesmo
  Informe Mensal: os erros do Informe (ex.: vencimentos do Alibem) vêm junto.
- Já traz o universo de emissões e ISINs: **a lista de ativos do mercado deixa de depender de você mandar**.

## Três camadas
1. **Mercado inteiro, sem revisão humana por ativo (dados abertos da CVM).**
   Ingestão em banco próprio `data/cvm_open.db` (valor original preservado, proveniência por arquivo, recarga idempotente, todas as
   versões guardadas, view da versão vigente). Sobre ela rodam alertas de qualidade em massa: coerência cadastral, situação × atraso,
   conciliação de saldo, rentabilidade fora do padrão, vencimento passado com saldo. O resultado é uma lista priorizada de ativos.
2. **Documentos só para os ativos priorizados (Fundos.NET).** Usa a fila de download aprovada (migration 003): Termo, AF, DFs, assembleias.
3. **Contratual só para os ativos priorizados.** Catálogo de 36 campos, localizador de cláusulas (recall de 89% nos pilotos) e fila de revisão
   priorizada. Aqui a revisão humana continua obrigatória.

## Demonstração (leitura dos arquivos de 2026, sem gravar no projeto)
Regras simples sobre a última competência (set/2026), por série. São **candidatos para triagem**, não conclusões:

| Regra | CRA (286 séries) | CRI (296 séries) |
|---|---|---|
| Mês do vencimento fora do mês-base de pagamento (semestral/anual) | 14 de 101 testadas | 0 de 1 testada (campo pouco preenchido) |
| Vencimento anterior à competência, saldo > 0 e "Adimplente" | 2 | 16 |
| ISIN repetido em mais de um certificado | 3 | 0 |

Em segundos o mesmo método que levou dias nos três pilotos aponta candidatos no mercado todo. Ex.: BRECOACRAHL2 (vencimento em agosto,
pagamentos em abril e outubro), o mesmo padrão do Alibem.

## Próximos passos
1. Aprovação para rodar `scripts/ingest_cvm_open_data.py --commit` (banco novo, 35,7 MB, fonte pública). Dry-run já feito.
2. Alertas de mercado sobre `cvm_open.db`, com as regras acima e as do projeto, em modo `--preview` primeiro.
3. Ranking dos ativos a aprofundar (camadas 2 e 3).
4. Reconciliar as emissões da CVM com a tabela `assets` pelo ISIN, sem criar cadastro paralelo (regra 1 do CLAUDE.md).

## Limites
- O dado da CVM é o do Informe: não corrige erro de preenchimento nem traz cláusulas do Termo, garantias, covenants ou eventos.
- Informes de uma competência podem ter várias versões; a view usa a maior.
- Campos como `Pagamento_Mes_Base` no CRI vêm em formato inconsistente (valor numérico de data); as regras precisam tratar isso.
