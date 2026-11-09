# Proposta para as regras de exibição de Securitizados (S-01..S-11) e gerais ligadas a elas

Rascunho para decidir com a equipe; nada aqui está aprovado. Layout segue fora do escopo (ADR-001): a proposta diz **o que**
mostrar e **com que dado**, não como desenhar. Números de 04/11/2026, base `data/cri_cra.db` e `reports/`.

## Onde o dado está hoje

| Módulo do MVP | Dado pronto | Arquivo |
|---|---|---|
| Análise de garantias | 417 garantias do Termo em 66 ativos (14 tipos), com trecho e página; revisão humana pendente | `garantias_covenants.csv` |
| Covenants | 24.160 itens: exigido × apurado × situação × data, de 6 securitizadoras (2.768 ativos, 34% do saldo) e 28 limites do Termo | `covenants_mensais.csv` |
| Histórico de documentos | 206.119 documentos de 2.959 ativos em 8 categorias; 13.112 baixados | banco, tabela `documents` |
| Leitura rápida por agente | fichas contratuais com trecho literal e página (36 campos), atas com decisão e trecho | `fichas_contratuais/`, `atas_portais.csv` |

## Securitizados

**S-01 Garantias.** Uma linha por garantia: tipo (14 tipos padronizados), descrição curta, valor quando o documento traz,
documento de origem com página e o trecho literal ao abrir. Situação de revisão visível ("lida no Termo, não revisada" ×
"revisada"), porque nenhuma das 417 foi revisada ainda. Ordem: garantias reais, fidejussórias, fundos.
*Decidir:* mostrar garantia não revisada para todos ou só para quem revisa.

**S-02 Covenants.** Uma linha por item: o que o contrato exige, o apurado, a situação **como a fonte informa** (atendido,
não atendido, não verificado, não se aplica) e a data da verificação. Quando houver as duas fontes, mostrar o limite do
Termo ao lado do exigido informado pela securitizadora, sem recalcular a situação. Destaque para "não atendido" (2.549
itens hoje) e para waiver citado pela fonte.
- Item sem data de apuração: mostrar a competência do relatório com o rótulo "data da apuração não informada". Na Vert,
  índice anual pode ser de 31/12/2023 num relatório de 09/2026.
- Mínimo marcado pela própria securitizadora como gerencial (Bari): rótulo "não contratual".
*Decidir:* se a ficha mostra só a última apuração ou o histórico mês a mês (o dado existe só para o mês coletado; o
histórico depende de coletar todo mês).

**S-03 Histórico de documentos.** Agrupar pelas categorias do Fundos.NET (hoje 8 no banco: Informe Mensal, Ata/Edital,
Outro, Relatório do Agente Fiduciário, Termo de Securitização, Relatório de Rating, Anúncio de Encerramento, Fato
Relevante), mais recente primeiro dentro do grupo, com data de referência e de publicação. Versões do mesmo documento
recolhidas sob a mais nova. Informe Mensal (62% dos documentos) recolhido por padrão.
*Decidir:* a lista de 9 categorias do MVP contra as 8 do banco (falta definir a 9ª).

**S-04 Documento sem arquivo.** Três estados com rótulo: "catalogado, não baixado" (192.998 hoje: a política é baixar só o
que tem sinal de triagem), "falhou no download" (9) e "baixado". O link para o Fundos.NET aparece em todos; o SHA-256 só no
baixado.

**S-05 Categoria "Outro".** 16.525 documentos (8%). Mostrar como grupo próprio, ao fim, com a descrição original do
Fundos.NET (tipo e espécie), que costuma dizer o que é. Reclassificação manual fica registrada
(`document_category_changes`).

**S-06 Leitura rápida por agente.** Todo resumo com: a frase "resumo automático, confira no documento", o trecho literal
e a página de cada afirmação, e o documento com SHA-256. Sem trecho, não mostra. Atas: assunto, resultado (aprovada, não
instalada, suspensa) e eventos graves com a origem ("decidido em ata" × "só no texto"). Ata de reunião futura é minuta e
não mostra decisão.

**S-07 Várias séries e ISIN repetido.** Ficha por série (CETIP), com as demais séries da mesma emissão listadas e
indicação da classe (sênior, mezanino, subordinada) quando houver. Hoje nenhum ISIN aparece em dois ativos no banco; o
caso do Café Brasil já foi unificado. Item de covenant e relatório da securitizadora são da emissão (patrimônio separado)
e aparecem em todas as séries, com essa nota.

**S-08 CNPJ ausente.** Rótulo "CNPJ não informado pela fonte", sem bloquear a ficha. Hoje só 1 securitizadora sem CNPJ,
mas **2.958 dos 2.959 ativos não têm o CNPJ do devedor** no cadastro do catálogo. O CNPJ existe no Informe Mensal da CVM:
`cnpj_devedor_cvm.md` liga 1.298 ativos a um único CNPJ de devedor (79 são pulverizados, sem "o" devedor), com a fonte, para a
camada compartilhada preencher a ficha. Pela regra 6, sem CNPJ não há junção
automática de devedor entre ativos.

**S-09 Informe Mensal.** Mostrar o que está no XML e na base aberta da CVM: saldo devedor, PU, situação de pagamento
(adimplente / em atraso), vencimento, classe e quantidade de séries, rentabilidade e as mudanças contra o mês anterior
(entrou em atraso, saldo caiu sem amortização, vencimento mudou). O dado da CVM é o do Informe: erro de preenchimento vem
junto, por isso exibir a fonte e a competência em cada valor.

**S-10 Rating.** 2.335 relatórios de rating catalogados, nota não extraída. Proposta para o MVP: mostrar o documento mais
recente (agência, data) sem a nota; extrair a nota é uma etapa à parte. Algumas securitizadoras publicam a nota no
relatório mensal (ex.: Vert, "brAA-") e ela pode entrar com a fonte.

**S-11 CRI × CRA.** Mesma ficha; mudam os rótulos do lastro (crédito imobiliário × direitos creditórios do agronegócio),
o campo de imóvel/empreendimento (CRI) e de produto/safra (CRA). Devedor e cedente com os mesmos campos.

## Gerais que dependem desse dado

- **G-02 Proveniência:** ícone com detalhe em cada valor (fonte, documento, página, data da coleta); a coluna da fonte
  sempre visível só em Covenants e Garantias, onde a fonte muda a leitura (Termo × securitizadora × CVM).
- **G-04 Conflitos:** os dois valores lado a lado com a hierarquia de fontes (BACEN > CVM > ANBIMA > plataformas >
  sites); o site da securitizadora nunca substitui a CVM. Exemplo real: 40 operações em "Default" no portal da Riza
  aparecem "Adimplente" no Informe da CVM.
- **G-05 Desatualizado:** Informe com mais de 45 dias da competência; relatório mensal da securitizadora com mais de 60
  dias (a Canal publica com 5 a 7 meses de atraso e ficaria sempre marcada).
- **G-06 Inativo:** ativo vencido ou com saldo zerado vai para aba própria, mantendo documentos e histórico.
- **G-08 Busca:** CETIP, ISIN, código do portal da securitizadora, nome do devedor e CNPJ (quando houver).

## O que precisa de decisão das pessoas

1. Garantias sem revisão: aparecem para todos? (S-01)
2. Covenants: última apuração ou histórico? (S-02)
3. A 9ª categoria do histórico de documentos. (S-03)
4. Prazos de "desatualizado" por fonte. (G-05)
5. Quem revisa garantias e covenants do Termo e registra a revisão (G-12).
