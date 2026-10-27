# Decisões em aberto que bloqueiam trabalho

Registro das quatro decisões que a Fase 0 do plano de ação (`docs/regras-de-exibicao-pendentes.md`) lista como bloqueadoras: **R-01**, **D-04**, **G-06** e **R-08**.

Este documento não escolhe. Cada decisão traz a pergunta, o que foi verificado no repositório, as opções que se enxergam e o impacto de cada uma nas fases. O campo **Decisão** fica em branco para ser preenchido por quem decide.

As fases são as do plano de ação: 0 preparação, 1 debêntures, 2 CRI/CRA, 3 camada compartilhada, 4 renda fixa, 5 fundos, 6 transversais.

A parte **Fundos: decisões da Fase 0**, no fim, é diferente: registra oito decisões da frente de Fundos que já foram tomadas, aprovadas pelo Gui em 27/10/2026. As quatro decisões acima continuam em aberto.

---

## R-01. Responsável e fonte de dados de Renda Fixa

**Pergunta:** quem cuida da frente de Renda Fixa e de onde vêm os dados?

**O que se sabe (verificado):**
- O `README.md` é contraditório: a tabela de responsáveis (linha 274) diz "Eduardo Tonzano: Debêntures (e agora renda fixa)", enquanto o quadro de frentes (linha 48) traz "A definir" e o roadmap (linha 245) lista "definição do responsável por Renda fixa".
- Não existe código nem banco de Renda Fixa. O README e o plano a descrevem como "não iniciada".
- O plano cita fontes candidatas (Banco Central para indicadores dos bancos, ANBIMA para curvas e taxas, páginas dos bancos para taxas ofertadas) e diz que o acesso e os termos de uso de nenhuma foram confirmados.

**Opções**
- **A. Eduardo assume Renda Fixa**, além de Debêntures.
- **B. Outra pessoa assume** (a indicar).
- **C. Adiar a frente** até uma data ou condição definida.
- Em qualquer caso, a **fonte** é uma segunda decisão: Banco Central, ANBIMA, páginas dos bancos, ou combinação, dependendo da validação de acesso e de termos.

**Impacto por fase**

| Fase | A (Eduardo) | B (outra pessoa) | C (adiar) |
|---|---|---|---|
| 0 | atualizar README para uma só versão | atualizar README com o nome | registrar a data de revisão |
| 1 | debêntures e renda fixa disputam a mesma agenda | sem efeito | sem efeito |
| 3 | bancos entram como entidades na camada compartilhada quando a frente começar | idem | sem bancos como entidades por ora |
| 4 | pode começar após a escolha da fonte | pode começar após a pessoa e a fonte | não começa |
| 6 | G-11 e G-10 podem incluir renda fixa depois | idem | G-11 e G-10 só com debêntures e CRI/CRA |
| Site | R-02 a R-07 ficam sem dado até a Fase 4 em todas as opções | | |

**Decisão:** _______________________  **Data:** __________

---

## D-04. Spread e rating das debêntures

**Pergunta:** o spread (e o rating) entram na ficha da debênture? Se sim, o que significa o valor coletado e qual é a fonte?

**O que se sabe (verificado nos exports de 14/09/2026):**
- O spread existe só para a CEPEA1: valor `100`, unidade `percentual`, fonte SND, coletado em 11/09/2026. O indexador da CEPEA1 é `DI`. A coleta não indica se é spread sobre o DI ou percentual do DI.
- PETR27 (IPCA) e SBSPC9 (PRÉ) não têm spread coletado.
- O rating não é coletado para nenhum ativo.
- A fonte `ANBIMA_API` está cadastrada como inativa; a CVM está cadastrada como ativa, mas o plano a trata como fonte prevista.

**Opções para o significado do valor da CEPEA1**
- **A.** Tratar como spread sobre o DI.
- **B.** Tratar como percentual do DI.
- **C.** Não exibir o spread enquanto não houver fonte oficial que confirme o significado.

**Opções para a fonte de spread e rating**
- **D.** CVM.
- **E.** ANBIMA (exige ativar `ANBIMA_API`).
- **F.** CVM e ANBIMA, com a hierarquia de fontes do projeto.
- **G.** Não coletar rating nesta etapa.

**Impacto por fase**
- **Fase 0:** o ADR-006 trata spread e rating como campos do catálogo; sem decisão, saem como `ausente` (`nunca_coletado`) para os ativos sem coleta.
- **Fase 1:** A e B exigem padronizar a unidade e regravar a observação. C não exige. D, E e F exigem conectar a fonte; E e F exigem ativar `ANBIMA_API` e confirmar acesso. G elimina o trabalho de rating.
- **Fase 2:** sem efeito direto. S-10 (rating de CRI/CRA) tem decisão própria.
- **Fase 3:** a fonte escolhida entra na hierarquia de prioridade da camada compartilhada.
- **Site:** A e B definem o rótulo da coluna; C mantém o campo ausente para a CEPEA1 também.
- **Risco comum:** interpretar errado o 100 mostraria remuneração incorreta, o que a regra "nada estimado" não admite.

**Decisão:** _______________________  **Data:** __________

---

## G-06. Ativo vencido ou inativo na plataforma

**Pergunta:** o que acontece com o ativo vencido ou inativo na listagem e na busca?

**O que se sabe (verificado):**
- A CEPEA1 vence em 2026-10-15 e o export de 11/09/2026 a traz com `status = active`.
- O schema aceita os status `unknown`, `active`, `inactive`, `matured` e `cancelled`. O único caminho atual para `matured` é o parser do SND (`parsers/snd_parser.py`), que traduz a situação "vencida" informada pela própria fonte; nenhuma rotina compara `data_vencimento` com a data de hoje.
- A última coleta da CEPEA1 é de 11/09/2026, antes do vencimento, e nenhuma coleta posterior foi registrada nos exports; o status só mudaria numa nova coleta em que o SND a marque como vencida. O plano prevê uma rotina que compare `data_vencimento` com a data de hoje e registre a mudança no `audit_log`.

**Opções**
- **A.** O ativo some da lista e só aparece por busca direta ou link.
- **B.** O ativo permanece na lista com marca (por exemplo, "vencida").
- **C.** O ativo vai para uma aba própria (vencidos e inativos).
- Decisão associada: se a coleta continua atualizando ativos vencidos.

**Impacto por fase**
- **Fase 0:** o ADR-006 já prevê `status` e o filtro `incluir_inativos`; o padrão do filtro depende desta decisão (A: falso; B: verdadeiro; C: dois conjuntos).
- **Fase 1:** em todas as opções, vale a rotina de `matured`, porque a exibição depende do status correto. A diferença é o que o site faz com ele.
- **Fase 3:** A e C exigem que a busca global (G-08) encontre também os vencidos; B não.
- **Fase 6:** G-11 (maiores altas e quedas) deve excluir vencidos em A e C; em B precisa filtrar explicitamente.
- **Site:** C acrescenta uma tela; B acrescenta um rótulo e um filtro; A é o menor esforço de tela, mas esconde o histórico por padrão.

**Decisão:** _______________________  **Data:** __________

---

## R-08. Títulos públicos (Tesouro Direto)

**Pergunta:** os títulos públicos entram na plataforma?

**O que se sabe (verificado):**
- O plano de ação registra que o escopo original não cita Tesouro Direto. Esse escopo está no arquivo `Escopo - Projeto Pense Além.docx`, que não foi relido para este documento.
- Não há código, banco nem fonte definida para títulos públicos.
- R-01 (responsável e fonte de Renda Fixa) está em aberto.

**Opções**
- **A.** Entram no escopo de Renda Fixa.
- **B.** Não entram.
- **C.** Entram em uma etapa posterior, com data ou condição a definir.
- Se entrarem (A ou C): definir a fonte e a ficha (R-05), e se compartilham a calculadora de marcação a mercado (R-03).

**Impacto por fase**
- **Fase 0:** atualizar o escopo e a lista de produtos do contrato de leitura (ADR-006) conforme a opção.
- **Fase 3:** em A e C, o Tesouro Nacional entra como entidade na camada compartilhada e os títulos precisam de identificador próprio.
- **Fase 4:** em A, acrescenta produto, fonte e ficha; em C, fica fora do primeiro ciclo; em B, não há trabalho.
- **Fase 6:** G-11 e G-10 só consideram títulos públicos em A, e em C a partir da etapa posterior.
- **Dependência:** qualquer opção diferente de B depende de R-01.

**Decisão:** _______________________  **Data:** __________

---

## Resumo do que cada decisão bloqueia

| Decisão | Fase 1 | Fase 2 | Fase 3 | Fase 4 | Fase 5 | Fase 6 |
|---|---|---|---|---|---|---|
| R-01 | | | bancos como entidades | toda a fase | | renda fixa em G-10 e G-11 |
| D-04 | spread e rating | | prioridade de fontes | | | |
| G-06 | rotina de `matured` | | busca de vencidos | | | filtro de G-11 |
| R-08 | | | Tesouro como entidade | produto, fonte e ficha | | G-10 e G-11 |

---

## Fundos: decisões da Fase 0

Fechamento da Fase 0 do plano da frente de Fundos. Ao contrário das quatro decisões acima, estas oito já foram tomadas: o Gui aprovou todas em 27/10/2026, por mensagem, conforme a sugestão enviada a ele, e Eduardo as registrou aqui. As perguntas de origem são as regras F-01 a F-06 de `docs/regras-de-exibicao-pendentes.md` e os pontos que a seção 8 de `docs/fundos-descoberta.md` deixava em aberto. Os números citados são da amostra de 09/2026 (seção 10 de `docs/fundos-descoberta.md`).

### 1. Dono da frente de Fundos (F-01)

**Pergunta:** quem é o dono da frente de Fundos? Era um dos pontos em aberto de F-01 na seção 8 de `docs/fundos-descoberta.md`.

**Decisão:** o Gui é o dono da frente de Fundos. O módulo fica em pasta própria no repositório.

**Situação:** decidida, aprovada pelo Gui em 27/10/2026, registrada por Eduardo.

**Pendência:** o nome da pasta do módulo, que será definido na primeira tarefa de implementação do módulo de Fundos (FU2.1 do plano da frente de Fundos).

**O que depende dela:** a Fase 5 (Fundos), que o plano de ação só inicia depois de F-01 (item 4, "Ordem sugerida", de `docs/regras-de-exibicao-pendentes.md`).

**Continua em aberto:** em F-01, a normalização do CNPJ (seção 8 de `docs/fundos-descoberta.md`). A sonda do Fundos.NET, que também constava aqui, foi feita em 27/10/2026 (seção 11 de `docs/fundos-descoberta.md`); o que ela não confirma, como ligar documento e classe sem CNPJ na linha da grade, está na seção 11.8.

### 2. "Fundo da casa" (F-02)

**Pergunta:** quais fundos são "da casa"? É a primeira parte de F-02; a seção 7 de `docs/fundos-descoberta.md` propõe a tabela.

**Decisão:** "fundo da casa" é definido por uma lista manual, por CNPJ da classe, mantida em tabela interna fora do Git.

**Situação:** decidida, aprovada pelo Gui em 27/10/2026, registrada por Eduardo.

**O que depende dela:** a tabela de classificação "da casa" da Fase 5 e o comparativo casa x mercado. O local da tabela é a decisão 4.

**Continua em aberto:** em F-02, as métricas comparadas, os grupos de comparação, os valores da coluna `relacao_com_a_casa` (seção 7 de `docs/fundos-descoberta.md`) e a forma de exibir.

### 3. CPF e dados pessoais (F-03)

**Pergunta:** o que fazer com o CPF e com os dados de pessoa natural que a CVM publica? A seção 10.8 de `docs/fundos-descoberta.md` encontrou CPF nos cedentes do informe de FIDC (120 valores em 69 classes), no campo do gestor pessoa física (225) e no campo do auditor (8), e nome de pessoa natural em `registro_fundo.Diretor`.

**Decisão:** o CPF nunca é gravado. O CPF aparece nos cedentes dos FIDCs, no campo do gestor pessoa física e no campo do auditor. Só CNPJ entra, e um teste automático garante isso. Os campos de pessoa natural (por exemplo o diretor) e os de contato (e-mail, site, atendimento) não são carregados.

**Situação:** decidida, aprovada pelo Gui em 27/10/2026, registrada por Eduardo.

**Pendência:** a confirmar com o Gui se a regra também vale para o arquivo original da CVM. Proposta, ainda não aprovada: o banco e o registro de coletas (`raw_records`) guardam só o manifesto do arquivo (nome, tamanho, SHA-256 e número de linhas), nunca o conteúdo; os arquivos originais ficam fora do Git, em pasta de acesso restrito.

**O que depende dela:** o coletor e o adaptador da Fase 5, o teste automático que garante que nenhum CPF é gravado, a ficha (F-03) e os papéis em `party_observations` (seção 5 de `docs/fundos-descoberta.md`), que só recebem CNPJ.

**Continua em aberto:** como aparece o papel de gestor, auditor ou cedente pessoa física, que fica sem identificador (seção 5), e o tratamento dos 7 valores de cedente de 11 dígitos que também são CNPJ válido com zeros à esquerda (seção 10.8).

### 4. Pasta interna dos fundos da casa (F-02)

**Pergunta:** onde fica a tabela interna dos fundos da casa? A seção 7 de `docs/fundos-descoberta.md` deixava o local "a ser definido pela equipe".

**Decisão:** a pasta interna fica fora dos clones Git, com acesso restrito. O caminho vai só na variável de ambiente `PENSE_INTERNAL_DIR`, nunca no código nem nos documentos.

**Situação:** decidida, aprovada pelo Gui em 27/10/2026, registrada por Eduardo.

**Pendência:** a criação da pasta interna, que cabe ao Eduardo com a TI.

**O que depende dela:** a tabela da decisão 2 e o comparativo casa x mercado, que precisam da pasta criada.

### 5. Licença ODbL dos dados da CVM

**Pergunta:** o que a licença ODbL, declarada em todas as páginas de dados abertos da CVM, exige do banco de Fundos? A seção 2 de `docs/fundos-descoberta.md` registrava que as obrigações não foram analisadas.

**Decisão:** o banco de Fundos é tratado como interno por enquanto.

**Situação:** aprovada (pelo Gui em 27/10/2026, registrada por Eduardo). Ajuste de redação registrado por Eduardo em 27/10/2026: a conferência da licença não bloqueia nenhuma etapa do uso interno; só vale antes de publicar o banco ou dado derivado dele fora da casa (obrigações a conferir: citar a fonte e manter a mesma licença).

**Pendência:** nenhuma para o uso interno. Antes de publicar o banco ou dado derivado dele fora da casa, conferir as obrigações da ODbL (citar a fonte e manter a mesma licença).

**O que depende dela:** a publicação do banco de Fundos ou de dado derivado dele fora da casa, que espera a conferência das obrigações da licença. O uso interno não depende dela.

### 6. Identificação do FIC-FIDC (F-04)

**Pergunta:** como identificar um FIC-FIDC? A seção 10.4 de `docs/fundos-descoberta.md` mostrou que nenhum campo do cadastro ou do informe o marca.

**Decisão:** o sinal é a parcela do ativo em cotas de FIDC no informe mensal de FIDC (`TAB_I2H_VL_COTA_FIDC` sobre `TAB_I_VL_ATIVO`, na `tab_I`). Corte inicial: 95% ou mais classifica como FIC-FIDC (518 classes em 09/2026); de 67% a menos de 95% vai para revisão manual (374 classes em 09/2026, das 892 com 67% ou mais). É uma regra de corte, não um dado da CVM. Nunca classificar pelo nome.

**Situação:** decidida, aprovada pelo Gui em 27/10/2026, registrada por Eduardo.

**O que depende dela:** a classificação de FIC-FIDC na Fase 5 e a fila de revisão manual.

**Continua em aberto:** em F-04, a forma de exibir as cotas de FIDC investidas; a lista dos FIDCs investidos continua dependendo do CDA, não lido.

### 7. Variante do FIAGRO (F-05)

**Pergunta:** como tratar a variante do FIAGRO (FII, FIDC ou FIP)? As seções 9 e 10.5 de `docs/fundos-descoberta.md` mostraram que nem o informe de FIAGRO nem o cadastro a trazem.

**Decisão:** mostrar "variante não informada" até haver uma segunda fonte confirmada. Nunca deduzir a variante pelo nome.

**Situação:** decidida, aprovada pelo Gui em 27/10/2026, registrada por Eduardo.

**O que depende dela:** a ficha e a listagem de FIAGRO.

**Continua em aberto:** a segunda fonte (o regulamento, no Fundos.NET, e a ANBIMA são candidatos não consultados) e, em F-05, se as variantes ficam na mesma página ou em páginas separadas.

### 8. Sênior e subordinada (F-02, F-03)

**Pergunta:** como classificar as séries em sênior, mezanino e subordinada? A subordinação não é publicada e precisa ser calculada das cotas por série (seções 4, 5 e 10.6 de `docs/fundos-descoberta.md`).

**Decisão:** o rótulo da série (`tab_X_2.TAB_X_CLASSE_SERIE`) tem um padrão fixo. O mapa `quota_class_map` é curado e revisado pela equipe a partir desse padrão. Onde o rótulo não diz o subtipo (599 linhas em 09/2026, só com `Subclasse Subordinada`), o subtipo aparece como "ausente" e nada é estimado.

**Situação:** decidida, aprovada pelo Gui em 27/10/2026, registrada por Eduardo.

**O que depende dela:** o cálculo da subordinação na ficha (F-03) e no comparativo da casa (F-02).

**Continua em aberto:** a ordem entre duas subordinadas da mesma classe, que o rótulo não diz (20 classes em 09/2026).

### Resumo das decisões de Fundos

| Nº | Assunto | Regra | Situação | Pendência |
|---|---|---|---|---|
| 1 | Dono da frente | F-01 | decidida | nome da pasta do módulo, na criação do módulo de Fundos |
| 2 | "Fundo da casa" | F-02 | decidida | |
| 3 | CPF e dados pessoais | F-03 | decidida | confirmar com o Gui o alcance da regra do CPF (arquivo original) |
| 4 | Pasta interna | F-02 | decidida | criação da pasta, pelo Eduardo com a TI |
| 5 | Licença ODbL | | aprovada | conferir a licença (citar a fonte e manter a mesma licença) só antes de publicar fora da casa; não bloqueia o uso interno |
| 6 | FIC-FIDC | F-04 | decidida | |
| 7 | Variante do FIAGRO | F-05 | decidida | |
| 8 | Sênior e subordinada | F-02, F-03 | decidida | |
