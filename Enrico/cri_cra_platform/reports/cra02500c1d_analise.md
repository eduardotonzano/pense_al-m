# CRA Alibem (CRA02500C1D / BRECOACRALJ8): estrutura e divergências

- Data: 2026-10-27
- Fontes (Fundos.NET, texto por página em `document_text_pages`): Termo de Securitização 1065416
  (aditamento pp.1–27 + Termo consolidado, Anexo D, pp.28–183) e 1040836 (versão da oferta);
  Relatório Anual do Agente Fiduciário 1175590 (base 2025); DFs do Patrimônio Separado 1328400
  (15/12/2025 a 30/06/2026, BDO, R$ mil); Comunicado 1064843 (bookbuilding, 16/12/2025);
  Informes Mensais dez/2025–set/2026 (10, vigentes).
- Parâmetros: `config/contract_parameters/cra02500c1d_termo_1065416.json` (91, **aprovados em 2026-10-27**).
  Fatos: `config/reported_facts/cra02500c1d_documentos_2025_2026.json` (99, **aprovados em 2026-10-27**).
  Página de revisão: `reports/cra02500c1d_revisao_pendente.html`.

## Estrutura (Termo 1065416)

| Série | Qtde | Classe | Remuneração | Vencimento |
|---|---|---|---|---|
| 1ª | 233.142 | Sênior | prefixada 14,80% a.a. | 18/12/2030 |
| 2ª | 16.858 | Sênior | 108% do DI | 18/12/2030 |
| 3ª | 250.000 | Mezanino | DI + 1,50% a.a. | 18/12/2030 |
| 4ª | 100.000 | Subordinada | DI + 2,50% a.a. | 17/12/2032 |
| 5ª | 150.000 | Subordinada | IPCA + 8,88% a.a. | 19/12/2035 |

- Emissão de R$ 750 mi (VNU R$ 1.000) em 15/12/2025; devedora única Alibem Alimentos S.A.
- Juros semestrais, 1º pagamento 17/06/2026 para todas as séries; amortização semestral a partir de
  17/06/2027 (séries 1–3) e 17/12/2027 (séries 4–5).
- Subordinação apenas por ordem de pagamento (Sênior > Mezanino > Subordinada); **sem índice mínimo**.
- **Sem garantias sobre os CRA**; aval da Carlos Lee Participações só sobre as Notas Comerciais 1ª–3ª.
- Fundo de despesas: R$ 295.000 inicial, mínimo R$ 95.000; sem fundo de reserva.
- Covenants (p.95): Liquidez Corrente ≥ 1,20; Dívida Líquida/EBITDA ≤ 3,0x (com exceção por liquidez),
  calculados sobre as DFs do Avalista.

## Divergências

1. **Pagamentos por classe no Informe de jun/2026.** O Informe lança Sênior R$ 15.837.891,87,
   Mezanino R$ 1.233.313,41 e Subordinada Júnior R$ 33.227.608,12. As DFs (1328400 p.17/p.20) trazem
   os juros pagos por série: 15.838 / 1.233 / 18.790 / 8.019 / 6.419 mil. Logo o Informe lançou só a 1ª
   série como Sênior, a 2ª (Sênior) como Mezanino e a soma 3ª+4ª+5ª como Júnior. Pelo Termo seria
   Sênior ≈ 17.071 mil, Mezanino ≈ 18.790 mil, Subordinada ≈ 14.438 mil. O total (R$ 50,30 mi) confere
   com os recebimentos.
2. **Classe da 4ª série:** Subordinada no Termo; Mezanino no próprio Informe (bloco de séries);
   "Subordinada Júnior" e "Subordinada" em notas diferentes das DFs.
3. **Identidade do ativo:** BRECOACRALJ8 / CRA02500C1D é o código só da 1ª série (Termo p.71; AF pp.3–7);
   o Informe Mensal, o Termo e as DFs cobrem a emissão inteira (5 séries).
4. **Relatório do AF (base 2025):** 2ª série ausente da tabela de ativos em circulação; saldo da 1ª
   série R$ 895.564,63, incompatível com 233.142 CRA; quantidade emitida 0 nas séries 1, 2, 4 e 5;
   remuneração da 1ª como "CDI"; relatório de gestão do Patrimônio Separado não recebido pelo AF.
5. **Erros materiais no Termo:** data de vencimento da 5ª série definida como "dos CRA da 4ª Série"
   (p.37); amortização da 5ª termina "na Data de Vencimento dos CRA da 3ª Série" (p.30).
6. **Datas:** término da 5ª série 17/12/2035 nas DFs (p.10) e 19/12/2035 no Termo; rating em
   14/11/2025 no Comunicado e 17/12/2025 nas DFs.

7. **Balanço do Informe de jun/2026 × DFs (1328400 p.7, p.17, p.20).** Os saldos por série e o total dos CRA
   conferem (Informe R$ 759.072.111,53; DFs R$ 759.072 mil). Divergem:
   - caixa: Informe `CaixaEquivalentes = 0` em todos os meses; DFs R$ 95 mil (aplicação do fundo de despesas,
     igual ao mínimo de R$ 95.000 do Termo);
   - direitos creditórios: Informe R$ 759.919.460,42; DFs R$ 759.072 mil. Os R$ 847.348,89 a mais são
     compensados no passivo do Informe por `ReducaoVlrEmissao = -847348.89`;
   - total do ativo: Informe R$ 759.919 mil; DFs R$ 759.167 mil.

## Lacunas

- Covenants dependem das DFs do Avalista, que não estão no Fundos.NET.
- O AF não analisa covenants nem traz inadimplência.
