# Decisões em aberto que bloqueiam trabalho

Registro das quatro decisões que a Fase 0 do plano de ação (`docs/regras-de-exibicao-pendentes.md`) lista como bloqueadoras: **R-01**, **D-04**, **G-06** e **R-08**.

Este documento não escolhe. Cada decisão traz a pergunta, o que foi verificado no repositório, as opções que se enxergam e o impacto de cada uma nas fases. O campo **Decisão** fica em branco para ser preenchido por quem decide.

As fases são as do plano de ação: 0 preparação, 1 debêntures, 2 CRI/CRA, 3 camada compartilhada, 4 renda fixa, 5 fundos, 6 transversais.

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
