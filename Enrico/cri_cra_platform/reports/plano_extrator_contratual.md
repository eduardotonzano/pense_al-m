# Extrator contratual padronizado: proposta (29/10/2026)

Status: **proposta para sua revisão**. Nada aqui aprova parâmetro. O catálogo e o relatório de cobertura já existem (só leitura).

## Por que
Os parâmetros contratuais são a base dos alertas que importam. Nos 3 pilotos eu li cada Termo à mão e cada ativo ficou
com um conjunto diferente de nomes e de campos. Para o mercado inteiro precisamos da mesma lista de campos em todo ativo,
com o sistema propondo os candidatos e você revisando só o que importa.

## O que já está pronto
- **Catálogo** `config/contract_terms/standard_fields.json` (proposto): 36 campos em 9 grupos, cada um com importância
  (core, important, complementary), escopo (emissão ou série) e os nomes que já usamos nos 223 parâmetros aprovados.
- **Cobertura** `scripts/report_contract_coverage.py` → `reports/contract_field_coverage.{md,csv}`: por ativo e campo, mostra
  aprovado, pendente ou faltando, e lista parâmetros que nenhum campo reconhece. Só lê o banco.
- Todos os 223 parâmetros aprovados caem em algum campo padrão; nenhum ficou sem campo e nenhum nome casa com dois campos.

## O que a cobertura mostrou
| Ativo | Core aprovados | Core faltando | Important faltando |
|---|---|---|---|
| CRI Almeida Junior | 23 | 0 | 2 |
| CRA Alibem | 21 | 2 | 7 |
| CRA Café Brasil | 12 | 11 | 8 |

- **Café Brasil** é o menos coberto: o trabalho dele foi centrado em garantias e assembleias. Faltam 11 campos core de
  identificação e estrutura (ISIN, número da emissão, devedor, lastro, data de emissão, quantidade, periodicidade, rating,
  limites de vencimento antecipado e cascata de pagamentos). A maioria está no Termo e no CDCA, é só extrair e revisar.
- **Alibem:** faltam número da emissão e razão mínima de garantia. A razão mínima provavelmente **não se aplica** (o Termo
  não tem garantia sobre os CRA); isso precisa ser registrado como "não se aplica" com o trecho literal, não como lacuna.
- **CRI:** tudo core coberto; faltam restrições (dividendos/capex) e waiver fee, que podem não existir no Termo.

## Regra importante: faltando ≠ não se aplica
Um campo sem parâmetro pode ser (a) algo que ainda não extraímos ou (b) algo que o documento diz que não existe. O estado
"não se aplica" só entra com trecho literal, como já fazemos hoje com os "Não há garantia flutuante" do CRI.

## Etapas propostas
1. **Aprovar o catálogo** (esta lista de campos): você ajusta nomes, importância e escopo.
2. **Ligar cada campo a termos de busca** em `config/contract_terms/termo_securitizacao.json` (hoje 9 temas), para o
   localizador de cláusulas cobrir todos os 36 campos. Sem interpretar valor: devolve o trecho literal.
3. **Rodar nos 3 pilotos** para os campos faltantes e entregar candidatos pendentes, com página e link do PDF, na mesma
   página de revisão que você já usa.
4. **Comparar o mesmo campo entre documentos** (Termo, prospecto, relatório do AF, assembleias): concordância sobe a
   confiança; divergência vira item prioritário para você (como o vencimento do Café Brasil: 2026 no Termo × assembleia).
5. **Fila de revisão priorizada** para o mercado inteiro: primeiro campos core divergentes ou ausentes, depois os demais;
   amostragem dos que concordam entre documentos.
6. **Só então** abrir para novos ativos, usando a fila de download já aprovada.

## Limites que continuam valendo
- Parâmetro contratual só vale com evidência literal e revisão humana (regra do handoff). IA não alimenta alerta numérico.
- O extrator propõe e o humano aprova; fonte de menor prioridade complementa, nunca sobrescreve.
- Termos com redação diferente do padrão vão cair em "pendente de leitura" em vez de serem forçados num campo.

## Decisões que preciso de você
1. O catálogo de 36 campos está certo? Falta algum campo que você considera essencial (ex.: eventos de inadimplemento
   específicos, regras de subordinação por série, taxa de administração da securitizadora)? Algum core que seria só "important"?
2. Posso seguir para as etapas 2 e 3 (ligar buscas e extrair os faltantes dos 3 pilotos para revisão)?

## Andamento (29/10/2026)
- Etapas 1 a 3: catálogo de 36 campos, relatório de cobertura e extração dos campos faltantes do Café Brasil (15) e do Alibem (1),
  pendentes de revisão.
- Etapa 4 (comparação entre documentos): `scripts/report_cross_document_checks.py` → `reports/cross_document_checks.{md,csv}`.
  Compara só número, data e código (texto livre fica de fora). Resultado de hoje:

| Ativo | Concordam | Divergem | Uma fonte só |
|---|---|---|---|
| CRI Almeida Junior | 8 | 0 | 0 |
| CRA Alibem | 18 | 4 | 2 |
| CRA Café Brasil | 0 | 0 | 3 |

  As 4 divergências do Alibem são a mesma já conhecida e documentada em `cra02500c1d_analise.md`: o Relatório do AF de 2025
  traz "quantidade emitida 0" nas séries 1, 2, 4 e 5, contra o Termo, o Anúncio e o Comunicado de Oferta.
  O comparador reencontrou sozinho um achado que eu tinha visto à mão.
- **Textos curtos (feito):** remuneração (por série e da emissão) e devedor passam a ser comparados por fichas: indexador,
  multiplicador (100% do DI), taxa/spread, CNPJ e palavras do nome. Veredito: *concordam*, *compatíveis* (uma fonte traz só parte
  do que a outra diz) ou *divergem* (mesmo campo com valores diferentes). É triagem; o texto original sempre aparece no relatório.
  - **Alibem, 1ª série:** o Relatório do AF diz "CDI"; o Termo diz prefixada 14,80% a.a. Divergência real, ainda sem explicação
    nos documentos lidos; vale conferir o Termo (p.81) e a ficha da série no AF (p.3).
  - **Café Brasil:** a remuneração (100% do DI + 4,5% a.a.) concorda no Termo e nas três DFs.
  - **CRI:** o Termo traz só "100% da Taxa DI + spread (tabela)" e o AF só "CDI + 1,5%": compatíveis, não divergentes.
- **Informe Mensal como fonte (feito):** vencimento, classe, ISIN, número da emissão, taxa e quantidades por série do Informe
  entram na comparação. Resultado e evidências na pesquisa `reports/divergencias_pesquisa_2026-10-29.md` (7 divergências, 2 delas
  de alta gravidade no Alibem e no Café Brasil).
