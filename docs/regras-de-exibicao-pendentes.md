# Regras de exibição a definir

Lista para fecharmos, em equipe, como cada produto deve aparecer no site da plataforma. Cada item tem um ID para facilitar a discussão. O layout publicado já aplica as regras que o projeto define (fonte e data em cada valor, histórico preservado, conflitos visíveis, nada estimado) e marca em cada página o que ainda depende de decisão.

Base: README da raiz, README do Fábio (contrato de integração), ADRs, exports de debêntures (14/09/2026) e relatórios CRI/CRA do Enrico.

## Geral

- **G-01** Formato de datas, números e moeda: casas decimais do VN e do PU, separadores e arredondamento sem perder o valor coletado (hoje o VN da PETR27 tem 5 casas).
- **G-02** Como exibir a proveniência: coluna sempre visível, ícone com detalhe ou os dois. E o que mostrar quando a fonte não traz a data (o cadastro dos ativos não traz).
- **G-03** Como exibir o nível de confiança do dado (hoje só existe "reported") e se ele aparece para o usuário.
- **G-04** Como exibir conflitos entre fontes: aviso na ficha, painel lateral ou os dois valores lado a lado. Hoje todos os ativos têm 0 conflitos abertos.
- **G-05** Prazo para marcar um dado como desatualizado (quantos dias desde a última coleta) e como sinalizar.
- **G-06** Ativo vencido ou inativo: some da lista, fica com marca ou vai para uma aba própria. Exemplo real: CEPEA1 venceu em 15/10/2026 e ainda consta como ativo na coleta de 11/09.
- **G-07** Campos da listagem x campos da ficha, ordenação padrão e filtros de cada produto.
- **G-08** Busca global: quais campos entram (código, ISIN, emissor, CNPJ) e como tratar ativos com mais de um identificador.
- **G-09** Como exibir relacionamentos entre entidades (grupo econômico, controle, emissão) vindos da camada compartilhada.
- **G-10** Alertas de preço e de notícias: onde aparecem, quem recebe e o limiar de variação anormal. Ainda não existe código.
- **G-11** Maiores altas e maiores quedas da home: quais carteiras entram, qual métrica (variação do PU?), período e fonte. Hoje não há variação coletada, os valores da home são ilustrativos.
- **G-12** Perfis e acesso: uso interno da equipe, quem edita manualmente (com log de auditoria) e quem só consulta.
- **G-13** Identidade visual final: logo da Multiplica, tipografia oficial e paleta.

## Debêntures

- **D-01** PU real x PU par: fórmula, fonte de cada PU, data-base e como mostrar a diferença. Hoje só existe o valor nominal; nenhum PU é coletado.
- **D-02** Valor nominal: quando mostrar o da emissão e quando mostrar o atual, e como exibir o histórico (a PETR27 tem dois valores coletados, em 11/09 e 14/09).
- **D-03** Busca por empresa: resultado por emissor ou por ativo, e como agrupar as debêntures do mesmo emissor.
- **D-04** Remuneração: o spread só foi coletado para a CEPEA1 (valor 100, unidade "percentual", sem indicar se é spread sobre o DI ou % do DI) e o rating não é coletado. Definir se entram na ficha e a fonte (CVM e ANBIMA estão previstas).
- **D-05** Como destacar incentivada (Lei 12.431), resgate antecipado e classe: selo, filtro ou coluna.
- **D-06** Agente fiduciário: texto simples ou link para o cadastro da entidade.
- **D-07** Agenda de eventos (juros, amortização, repactuação): não é coletada. Definir se entra na ficha.
- **D-08** Data dos campos de identificação (código, ISIN, emissor): o export não traz a data do cadastro.

## Securitizados

- **S-01** Garantias: como exibir (lista, tipo, valor, documento de origem). Não há coleta estruturada hoje.
- **S-02** Covenants: como exibir, com situação de cumprimento e data da verificação. Não há coleta estruturada hoje.
- **S-03** Histórico de documentos: ordem, agrupamento pelas 9 categorias, versões e destaque do mais recente.
- **S-04** Documento sem arquivo baixado ou com falha no download: como mostrar o estado.
- **S-05** Categoria "Outro": como exibir os documentos ainda não classificados (no inventário inicial do Café Brasil, os 124 documentos estavam nela).
- **S-06** Leitura rápida dos documentos por agente: formato do resumo, citação da página de origem e aviso de que é resumo automático.
- **S-07** Operações com várias séries e ativos que tiveram o mesmo ISIN em mais de um cadastro (já aconteceu com o Café Brasil): como mostrar as séries.
- **S-08** Securitizadora ou devedor sem CNPJ (caso do CRI Almeida Junior): rótulo do dado ausente e se bloqueia a ficha.
- **S-09** Informe mensal: quais indicadores extrair do XML e exibir.
- **S-10** Rating: o relatório de rating é uma categoria de documento, mas a nota não é extraída. Definir exibição.
- **S-11** Diferenças entre CRI e CRA na ficha (lastro, devedor, setor).

## Renda Fixa

- **R-01** Responsável e fonte de dados: o README da raiz cita Eduardo "e agora renda fixa", enquanto o contrato de integração e o roadmap ainda dizem "a definir". Sem fonte definida, não há o que exibir.
- **R-02** Acompanhar taxas: por banco, por prazo e por indexador, com histórico e fonte.
- **R-03** Calculadora de marcação a mercado: entradas, curva usada, saída e aviso de premissas.
- **R-04** Indicadores dos bancos: quais, periodicidade e fonte.
- **R-05** Campos da ficha de cada produto (prazo, liquidez, cobertura do FGC, valor mínimo, indexador).
- **R-06** LF Sênior e LF Subordinada: uma página com filtro ou duas páginas.
- **R-07** Comparação entre emissores do mesmo produto.
- **R-08** Títulos públicos: o escopo original não cita Tesouro Direto. Confirmar se entra, a fonte e a ficha.

## Fundos

- **F-01** Fonte e coleta: a frente (Gui) não foi iniciada, então ainda não há dado de fundos.
- **F-02** FIDCs da casa x mercado: quais fundos são "da casa", quais métricas comparam (rentabilidade, spread, subordinação) e como mostrar.
- **F-03** Ficha do fundo: gestora, administradora, custodiante, cotas, subordinação, carteira de recebíveis e cedentes.
- **F-04** FIC-FIDC: como exibir as cotas de FIDC em que o fundo investe.
- **F-05** FIAGRO: variantes (FIDC, FII, FIP) na mesma página ou em páginas separadas.
- **F-06** Relacionamentos (gestora, administradora, cedentes) vindos da camada compartilhada.

---

# Plano de ação: levar ao banco de dados o que falta

Este plano transforma as regras acima em trabalho de banco e de coleta. Parte das regras é só decisão de interface (G-01 a G-05, G-07, G-12, G-13 e a maior parte das regras de "como mostrar") e não exige banco. As demais dependem de dado que ainda não existe, e é a elas que o plano se refere.

## 1. Ferramenta: VS Code, Claude Code ou os dois

| Alternativa | Como funciona | Vantagem | Limite |
|---|---|---|---|
| **A. VS Code com a extensão do Claude Code (recomendada)** | Você segue no VS Code e o Claude Code trabalha no mesmo repositório, com plano antes de editar e testes rodando no terminal integrado | Não muda seu ambiente; cada pessoa usa na própria máquina; o histórico fica no Git | Uma sessão por vez, a menos que use worktrees |
| **B. Claude Code no terminal, com sessões paralelas** | `claude --worktree <nome>` cria um checkout isolado em uma branch própria, e cada frente roda sua sessão sem colidir | Debêntures, CRI/CRA, Renda Fixa e Fundos avançam ao mesmo tempo | Exige disciplina de branch e pull request |
| **C. Só o VS Code, sem agente (como hoje)** | Escrever migration, coletor e teste na mão | Controle total | É o mais lento e o que mais deixa a documentação atrasada em relação ao código |

**Recomendação:** A no dia a dia e B quando duas frentes andarem juntas. Em nenhuma das duas o banco é alterado sem aprovação.

Recursos do Claude Code que valem para este projeto (confirmados na documentação oficial):
- **CLAUDE.md na raiz do repositório.** O repositório ainda não tem. É o arquivo que o Claude lê no início de toda sessão. Deve conter os princípios de dados do README (não inventar dado, fonte e data em todo valor, histórico preservado, conflito registrado, fonte oficial primeiro), o aviso de nunca rodar `--commit` sem aprovação, a proibição de versionar `*.db`, `.env` e documentos baixados, e os comandos para rodar os testes de cada frente.
- **Modo plano** (`claude --permission-mode plan`, ou Shift+Tab na sessão). O Claude lê o código e propõe o plano; só edita depois da aprovação. Usar sempre antes de migration.
- **Worktrees** (`claude --worktree <nome>`), para frentes em paralelo.
- **Subagentes**, para pesquisar uma fonte (por exemplo, a documentação de dados abertos da CVM) sem encher o contexto da sessão principal.
- **Modo não interativo** (`claude -p`), útil depois para tarefas repetidas, como revalidar o banco.

## 2. Decisão de arquitetura do banco

1. **Manter um SQLite por frente, com adaptadores para a camada compartilhada**, como já decidido nos ADRs. Não migrar para outro banco agora; revisar quando existir a plataforma única.
2. **Debêntures não precisa de migration para os campos novos.** A tabela `observations` guarda qualquer `field_name`, com tipo, unidade, fonte e data. PU real, PU par, spread, rating e a data do cadastro entram como novas observações. O que precisa de tabela nova é só a agenda de eventos (D-07).
3. **CRI/CRA precisa de tabelas novas** para dado estruturado extraído de documento (garantias, covenants, ratings, indicadores do informe mensal), cada linha apontando para o documento e a página de origem.
4. **Renda Fixa e Fundos nascem com o mesmo esqueleto do módulo de debêntures** (`sources`, `collection_runs`, `raw_records`, `observations`, `data_conflicts`, `audit_log`), que já provou o padrão de proveniência e histórico.
5. **Tabelas transversais** (carteiras, série de preços, alertas) ficam num módulo próprio, para não pertencerem a nenhuma frente.
6. **Toda alteração de schema** segue o fluxo: plano aprovado, migration numerada, backup antes, teste de migration, dry-run, aplicação, verificação de integridade.

## 3. Fases

Esforço relativo: P (pequeno), M (médio), G (grande). Os donos seguem a divisão do README.

### Fase 0. Preparação (P) · todos
- Criar o `CLAUDE.md` e a regra de branch por frente com pull request para a `main`.
- Fechar as decisões que travam o resto: **R-01** (quem cuida de Renda Fixa e qual a fonte), **D-04** (o que significa "100 percentual" no spread da CEPEA1), **G-06** (ativo vencido) e **R-08** (títulos públicos entram?).
- Definir o contrato de leitura para o site: uma consulta somente leitura por produto, com listagem e ficha, devolvendo cada valor com fonte, data e confiança (**G-02**, **G-07**).
- Limpar os imports soltos em `run_collection.py` (`from ast import arguments`, `from unittest import result`).

### Fase 1. Debêntures · Eduardo (M)
| Regra | O que entra no banco | Como |
|---|---|---|
| D-08 | Data de observação dos campos de identificação | Gravar código, ISIN e emissor também como observações |
| G-06 | Status `matured` para o ativo vencido (já permitido pelo schema) | Rotina que compara `data_vencimento` com a data de hoje e registra a mudança no `audit_log`. CEPEA1 é o primeiro caso |
| D-04 | Spread e rating para todos os ativos | Padronizar a unidade do spread; ativar a fonte `ANBIMA_API` (hoje inativa) e avaliar a CVM como fonte oficial |
| D-01 | PU real e PU par | Definir fórmula e fonte com a equipe; gravar como observações `pu_real` e `pu_par` em BRL, com a data-base |
| D-07 | Agenda de eventos (juros, amortização, repactuação) | Tabela nova `debenture_events`, com data, tipo, valor e fonte |
Aceite: os 3 ativos atuais com todos os campos ou com "sem dado" explícito, 0 conflitos não tratados, testes verdes.

### Fase 2. CRI e CRA · Enrico (G)
| Regra | O que entra no banco | Como |
|---|---|---|
| S-03, S-04 | Catálogo completo de documentos e estado do download | Persistir no banco principal e rodar o download em escala (pendência já listada no README) |
| S-05 | Categoria de cada documento | Classificador por nome e campos da grade; hoje quase tudo cai em "Outro" |
| S-08 | CNPJ da securitizadora (Opea) e do devedor (Almeida Junior) | Buscar na CVM e no Fundos.NET; registrar a fonte; sem preenchimento por inferência |
| S-07 | Séries e ISIN único | Os índices únicos já existem; falta modelar multissérie |
| S-09 | Indicadores do informe mensal | Parser do XML para a tabela `informe_indicators`, com referência ao documento |
| S-10 | Rating | Tabela `ratings` (agência, nota, data, documento de origem) |
| S-01, S-02 | Garantias e covenants | Tabelas `guarantees` e `covenants`, preenchidas por extração do Termo de Securitização com a página de origem |
| S-06 | Leitura por agente | Tabela `extractions` com texto citado, página, modelo usado e `status` (`pending_review`, `verified`); nada vai para a ficha sem revisão humana |
Aceite: ativo piloto com todas as categorias presentes ou marcadas como ausentes; cada garantia e covenant com documento e página; os 67 testes atuais continuam passando.

### Fase 3. Camada compartilhada · Fábio (M)
- Adaptador de debêntures (instrumento) e adaptador de CRI/CRA, resolvendo o ISIN duplicado (roadmap itens 1 e 2).
- **G-08:** índice de busca global por código, ISIN, emissor e CNPJ.
- **G-09, F-06:** relacionamentos (controle, administração, emissão, cessão) com proveniência.
- Entregar a consulta de leitura definida na Fase 0.

### Fase 4. Renda Fixa · responsável a definir (G)
Só começa depois de R-01.
- Fontes candidatas, a validar antes de qualquer código: dados do Banco Central para os indicadores dos bancos (**R-04**), ANBIMA para curvas e taxas, e as páginas dos próprios bancos para taxas ofertadas, que são frágeis para coletar. Não confirmei acesso nem termos de uso de nenhuma delas.
- Tabelas: ofertas por produto, banco, prazo, indexador, taxa e data da coleta (**R-02**); curvas de juros para a calculadora de marcação a mercado (**R-03**).
- Os bancos entram como entidades na camada compartilhada, sem cadastro paralelo.

### Fase 5. Fundos · Gui (G)
- Reaproveitar o coletor do Fundos.NET que o Enrico já validou, em vez de escrever outro, e avaliar os dados abertos da CVM para cadastro e informes.
- Tabelas: fundos (via camada compartilhada), observações do fundo, gestora, administradora, custodiante, cotas e subordinação (**F-03**), cotas investidas (**F-04**).
- **F-02:** tabela de classificação "da casa", que é dado interno da Multiplica e não pode ir para o repositório público.

### Fase 6. Transversais (M a G)
| Regra | O que entra no banco |
|---|---|
| G-11 | `portfolios` e `positions` (carteiras da casa, dado interno) e `price_series` (PU diário por ativo) para calcular as maiores altas e quedas |
| G-10 | `alert_rules`, `alerts` e `news_items`; aproveitar o pipeline de notícias por empresa e tópico que você já construiu |
| G-05 | Visão com a data da última coleta por ativo e por campo |
| G-12 | Usuários e papéis; edição manual sempre com registro no `audit_log` |

## 4. Ordem sugerida

1. Fase 0, em paralelo com as Fases 1 e 2, porque elas não dependem das decisões abertas, exceto D-04 e G-06.
2. Fase 3 assim que debêntures e CRI/CRA estiverem completos, para o site ler tudo por uma consulta só.
3. Fases 4 e 5 em paralelo, depois das decisões R-01 e F-01.
4. Fase 6 por último, porque G-11 e G-10 precisam de série de preços e de carteiras.

## 5. Como conduzir cada tarefa com o Claude Code

1. Abrir a sessão na branch da tarefa e pedir primeiro um plano, em modo plano, citando o ID da regra (por exemplo, "plano para D-07").
2. Revisar o plano: tabelas, campos, fonte e como a proveniência será gravada.
3. Pedir a migration e os testes juntos; rodar a suíte da frente.
4. Rodar a coleta em `--dry-run`, conferir o resultado e só então aprovar a gravação.
5. Fazer backup do banco antes de aplicar a migration.
6. Abrir pull request com o ID da regra, o que mudou no schema e o resultado dos testes; um colega revisa antes do merge.

## 6. Riscos

- **Fonte instável ou bloqueada** (SND e Fundos.NET são scrapers): manter `raw_records` para reprocessar sem nova consulta e cobrir o parser com fixtures.
- **Extração automática de garantias e covenants errada:** por isso a revisão humana obrigatória e a página de origem em cada linha.
- **Dado inventado para preencher a tela:** valor ausente fica "sem dado"; nenhum campo é completado por estimativa.
- **Dado interno da casa no repositório público** (carteiras, fundos "da casa"): manter fora do Git e do banco versionado.
- **Documentação desatualizada em relação ao código:** conferir o código atual antes de agir, como pede o README.
