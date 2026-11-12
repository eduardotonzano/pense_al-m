# ADR-013: Gestora pessoa física, classe, situação e "investe em" derivado (Fundos na camada compartilhada)

**Status:** Aceita em 12/11/2026 (rascunho de 12/11/2026, com a medição no banco de teste; aceita pelo Eduardo, que conduz o projeto, junto com as decisões sobre D7 e D9 de 17:01; não implementada)
**Autores:** Eduardo e Claude
**Decide:** Eduardo (condução do projeto)
**Relacionados:** ADR-002 (relações), ADR-005 (matching), ADR-012 (prestadores de fundos e "investe em"), levantamento da FU7.1 (documento do projeto, fora do repositório)

> **Como ler.** O ADR-012 deixou D5, D6, D7 e D9 para decisão à parte. Este ADR os decide. Cada decisão traz a regra, o que se perde e o que não foi medido. As contagens vêm do banco de teste de Fundos (cadastro da CVM de 27/10/2026, informes de FIDC e FIAGRO de 09/2026), aberto só para leitura, com o hash igual antes e depois; só contagens, nenhum CNPJ.

## 1. Contexto

O adaptador de fundos (FU7.2) liga fundos a gestoras, administradoras e custodiantes (ADR-012) e, depois da FU6.1, um fundo aos fundos em que investe. Faltam quatro regras para o adaptador não decidir sozinho: o que fazer com gestora sem CNPJ, como tratar a classe da CVM 175, como mapear a situação do fundo e quando a relação "investe em" deixa de valer.

**Limites da medição.** Banco de teste, não real. O cadastro só carregou FIDC e FIAGRO. O `registro_subclasse.csv` e as tabelas `tab_VIII` e `tab_X_4` do FIDC não foram carregados. Este banco não tem tabela de posições nem coleta de CDA, então nada do CDA foi medido. O loader do cadastro descarta antes de gravar a classe cujo fundo não entrou na carga, então "classe sem fundo" dá zero por construção e não prova nada.

## 2. Decisões

### D5. Gestora pessoa física: não criar entidade, só contar

- A camada nunca guarda CPF (decisão 3 de `docs/decisoes-em-aberto.md`) e a `Entity` pede nome. Sem CPF, o único identificador seria o nome, que nunca une entidades (regra do ADR-005).
- O adaptador de fundos não cria entidade nem relação `MANAGES` para gestora pessoa física. Ele conta quantas encontrou e informa no relatório (no cadastro de teste são 225).
- O que se perde: a gestora pessoa física some da camada. Quem precisar dela lê o módulo de Fundos.
- Reabrir se a camada passar a guardar um identificador forte de pessoa física.

### D6. Classe: um CNPJ, uma entidade; sem relação classe-fundo por ora

**Medição.**
- 5.839 CNPJs de classe e 8.044 de fundo. Dos 5.839 CNPJs de classe, 5.811 também aparecem como CNPJ de fundo: 5.810 são o CNPJ do próprio fundo da classe (99,5%) e 1 é o CNPJ de outro fundo. Só 28 classes têm CNPJ que não é de nenhum fundo.
- Fundos por número de classes: 5.819 têm 1, 5 têm 2, 2 têm 3, 1 tem 4 (8 com mais de uma) e 2.217 não têm nenhuma (1.605 deles não adaptados à CVM 175 e 612 adaptados).
- Nos informes: FIDC, 4.394 classes e 31 fundos como veículo (4.384 dessas classes têm CNPJ também em `funds`); FIAGRO, 308 classes e nenhum fundo (307 com CNPJ também em `funds`).

**Regra.**
- A camada guarda um CNPJ em uma só entidade (ADR-001, `canonical_key` única). Por isso, quando a classe tem o mesmo CNPJ do fundo (99,5% dos casos), classe e fundo são **uma entidade só**. Para os 28 CNPJs que só aparecem como classe, o adaptador cria uma entidade própria, com o tipo do módulo (`FIDC` ou `FIAGRO`).
- Não há relação classe-fundo por ora: `BELONGS_TO_GROUP` seria uso forçado e nenhum leitor consome essa ligação hoje. Se aparecer um consumidor, criar um tipo de relação próprio (por exemplo `CLASS_OF`) em ADR novo; os cerca de 29 casos em que o CNPJ da classe difere do do fundo são a base para isso.
- A classe cujo CNPJ é o de outro fundo (1 caso) vira simplesmente a entidade desse outro fundo; o adaptador conta o caso no relatório e não cria ligação.

**O que se perde.** Quando classe e fundo têm o mesmo CNPJ, a camada não distingue um do outro (o módulo de Fundos distingue). Os fundos com mais de uma classe aparecem como entidades separadas, sem ligação entre elas.

**Não medido.** O CDA: o pacote do Gui diz que ele identifica o veículo pelo CNPJ da classe, e este banco não tem CDA. Com 99,5% de CNPJ igual, a regra acima não muda se o CDA usar o da classe ou o do fundo, mas isso fica sem medição até haver CDA. Também não medido: por que 612 fundos adaptados à CVM 175 não têm classe.

### D7. Situação: só entra na camada o fundo em funcionamento normal; o resto fica em espera (backlog)

**Decisão do Eduardo (12/11/2026, 17:01):** os fundos que não estiverem ativos, ou que não operam, ficam no backlog; como o portal é atualizado diariamente, quando esses fundos entram em circulação eles saem do backlog e entram no portal.

**Medição** (a situação só existe no cadastro; nenhum informe traz situação ou status; 5.837 das 5.839 classes têm a mesma situação do fundo, e as 2 que diferem estão "Fase Pré-Operacional" em fundo "Em Funcionamento Normal"):

| Situação da CVM | Fundos | Classes | Destino |
|---|---|---|---|
| Em Funcionamento Normal | 4.634 | 4.634 | entra na camada, com `EntityStatus` ativa |
| Fase Pré-Operacional | 809 | 812 | backlog |
| Em Liquidação | 436 | 393 | backlog |
| Cancelado | 2.162 | 0 | backlog |
| Incorporação | 2 | 0 | backlog |
| Em Situação Especial | 1 | 0 | backlog |

**Regra.**
- O adaptador de fundos importa para a camada só o fundo (ou a classe, D6) cuja situação é "Em Funcionamento Normal", com `EntityStatus` ativa. Os demais não viram entidade nem relação: ficam só no módulo de Fundos, que é a fonte da situação.
- O backlog não tem tabela própria. É o conjunto de fundos do cadastro que não foram importados. A cada execução diária o adaptador lê o cadastro inteiro e importa quem passou a "Em Funcionamento Normal" (a importação é idempotente), então quem sai do backlog entra no portal na execução seguinte.
- Quando o CNPJ é o mesmo de fundo e classe (D6), vale a situação do fundo (`registro_fundo.Situacao`); para os CNPJs que só existem como classe, vale a da classe.
- Relação de prestadora (ADR-012) só é criada se o fundo entrou; prestadora sem nenhum fundo importado não vira entidade por causa dele.
- Valor novo de situação da CVM, fora da tabela, fica no backlog e é contado no relatório.
- Relatório do adaptador: quantos fundos entraram, quantos ficaram no backlog por situação, e quantos saíram do backlog nesta execução.

**Fundo que já entrou e deixa de operar.** A camada não atualiza entidade existente (ADR-007), então o `EntityStatus` guardado é o do momento da entrada e pode ficar desatualizado (fundo que entra ativo e depois entra em liquidação ou é cancelado). Como o `entity_type` no ADR-012, o `EntityStatus` de um fundo de Fundos é informativo e nenhum leitor pode usá-lo para saber a situação atual; a situação vem do módulo de Fundos. Atualizar o status na camada fica para ADR novo.

**O que se perde.**
- Fundos em liquidação, cancelados, incorporados e pré-operacionais (3.410 dos 8.044) não existem na camada enquanto não entrarem em funcionamento normal. Um fundo em liquidação que nunca esteve em funcionamento normal na camada não tem entidade, e nenhuma relação com ele (administradora, custodiante, "investe em") é criada.
- Um fundo investido que esteja fora do funcionamento normal não aparece no "investe em" (D9): a relação só existe se os dois fundos entraram.

### D9. "Investe em" derivado: quando deixa de ser ativo

**Aprovado pelo Eduardo em 12/11/2026, 17:01.**

- A posição que some numa reapresentação só é contada no módulo de Fundos (decisão do Gui de 05/11/2026). Esta regra trata só a relação `INVESTS_IN` da camada.
- A relação fica ativa enquanto o par (fundo detentor, fundo investido) aparece no CDA completo mais recente do detentor. Quando o par some de um CDA posterior completo, a relação recebe `valid_to` com a data de referência desse CDA e status inativo. Se o par volta, reabre (mesma regra de reabertura do D4 do ADR-012).
- "Completo" é a mesma definição do D4 do ADR-012: execução concluída com sucesso em `collection_runs` e arquivo lido até o fim, sem erro de leitura. CDA parcial ou com falha não fecha nada.
- Posição confidencial (só consolidada) não tem investido conhecido e não gera relação (ADR-012).
- O que se perde: a relação não guarda valor nem série; a série de posições fica em `holdings` (F-06).

## 3. Consequências

- O adaptador de fundos sabe o que fazer nos quatro casos sem decidir sozinho.
- A camada fica sem gestora pessoa física e sem relação classe-fundo; quem precisar lê o módulo de Fundos.
- Só o fundo em funcionamento normal entra na camada; os demais ficam no backlog e entram quando passam a operar (D7).
- Nenhuma migration de schema: os enums são texto sem `CHECK`.

## 4. Fora do escopo

- Identificador forte para pessoa física.
- Relação classe-fundo e série histórica de prestadores (gatilho para ADR novo).
- Atualizar o `EntityStatus` de fundo já importado (gatilho para ADR novo).
- Unificar o `fundos.cnpj` do módulo de Fundos com o `normalize_cnpj` da camada (ADR-011).
- Medir o CDA quando houver banco com ele; explicar os 612 fundos adaptados sem classe.
