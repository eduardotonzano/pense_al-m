# ADR-012: Prestadores de serviço de fundos e relação "investe em" na camada compartilhada

**Status:** Aceita em 12/11/2026 (rascunho de 12/11/2026, revisado após os comentários do Fábio (13:16 e 13:28); confirmado pelo Gui em 12/11/2026, 13:31; aceita pelo Eduardo, que conduz o projeto; não implementada)
**Autores:** Eduardo e Claude, a partir do levantamento da FU7.1 e das inclinações do Fábio (12/11/2026, 13:00)
**Decide:** Fábio (camada compartilhada), com o Gui (frente de Fundos)
**Relacionados:** ADR-002 (relações), ADR-005 (matching), ADR-007 a 009 (adaptador de debêntures), ADR-011 (CNPJ alfanumérico), levantamento da FU7.1 (documento do projeto, fora do repositório)

> **Como ler.** Cada decisão tem duas partes: **Inclinação do Fábio** (o que ele escreveu em 12/11/2026, 13:00, sem mudança de sentido) e **Acréscimos nossos** (coisa que o Fábio não disse: perguntas e recomendações de Eduardo e Claude, marcadas para ele aceitar ou cortar). Onde o Fábio (13:16 e 13:28) e o Gui (13:31) já responderam, está marcado.

## 1. Contexto

A frente de Fundos (Gui) precisa ligar fundos às instituições que os administram, custodiam e gerem, e um fundo aos fundos em que investe. A camada compartilhada (`src/pense_alm/shared/`) hoje:

- tem `EntityType` sem administradora nem custodiante, e a `Entity` sem campo de papel;
- tem `RelationshipType` com `MANAGES`, `ADMINISTERED_BY` e `PROVIDES_SERVICES_TO`, mas sem custódia e sem "investe em"; só `ISSUES` está em uso (#11);
- guarda um CNPJ em uma só entidade, com um só `entity_type` (`canonical_key` única no banco inteiro);
- casa por CNPJ sem olhar o tipo da entidade e não atualiza o tipo de entidade existente (ADR-007);
- guarda `entity_type`, `identifier_type` e `relationship_type` como texto sem `CHECK`.

**Medição (banco de teste de Fundos, cadastro de 27/10/2026 e informes de 09/2026; só contagens, nenhum CNPJ):** 99 administradoras, 49 custodiantes, 707 gestoras com CNPJ. Dos 49 custodiantes, 41 também administram; 46 das 99 administradoras também gerem; 16 CNPJs têm os três papéis; dos 766 CNPJs com algum dos três papéis, 73 (9,5%) têm dois ou três. Limites: banco de teste, escopo FIDC e FIAGRO, e o cruzamento com emissores de debêntures (zero) não vale, porque o único backup com emissores tem 3 deles.

## 2. Decisões propostas

### D1. O papel fica na relação, não no tipo da entidade

**Inclinação do Fábio.** O papel (administradora, custodiante) fica na relação. A instituição que presta serviço a fundo usa o tipo neutro `FINANCIAL_INSTITUTION`. A custódia ganha tipo de relação próprio (por exemplo `CUSTODIED_BY`). Ele confirma com o Gui.

**Por quê (evidência).** Um CNPJ é uma entidade com um tipo; os números acima mostram que tipo por papel não representa os dados.

**Acréscimos nossos.**
- Nome do novo `RelationshipType`: `CUSTODIED_BY` é o exemplo do Fábio; nome confirmado pelo Gui (13:31).
- `PROVIDES_SERVICES_TO` deixa de ser usado para administração e custódia em Fundos (cada serviço tem relação própria). Sugestão: não usar a relação genérica para fundos até haver outro serviço a registrar.
- Auditor e controlador (36 e 29 CNPJs na medição) não entram neste ADR; ficam fora até o Gui dizer se a camada precisa deles.

### D2. O tipo de uma entidade existente nunca é atualizado

**Inclinação do Fábio.** Nunca atualizar o tipo de entidade já existente. Prestadores de serviço de fundo usam o tipo neutro.

**Acréscimos nossos (respondido pelo Fábio e pelo Gui).**
- **Conflito com a gestora (sem a proposta de tipo abaixo).** O Fábio quer `MANAGES` com a gestora como origem, "como hoje", e o pacote do Gui cria a gestora como `ASSET_MANAGER`. Mas 46 das 99 administradoras também são gestoras, e 18 gestoras também são custodiantes. Para esses CNPJs, o tipo que fica na entidade depende de qual importação rodou primeiro (`ASSET_MANAGER` se a gestora entrou antes; `FINANCIAL_INSTITUTION` se entrou antes como administradora). A mesma coisa vale para um CNPJ que já exista como `COMPANY` pelo adaptador de debêntures.
- **Decidido pelo Fábio (13:16):** aceita a dependência da ordem, com as duas regras abaixo; ordem fixa dentro do adaptador não vale o custo. Regras: (a) o `entity_type` de um prestador é informativo e nenhum leitor pode deduzir papel dele (o papel vem só das relações); (b) o adaptador de fundos, ao achar o CNPJ já cadastrado, reutiliza a entidade e não altera o tipo. 
- **Tipo que o adaptador de fundos dá quando ele mesmo cria a entidade (proposta do Fábio, 13:16):** `FINANCIAL_INSTITUTION` para os três papéis (gestora, administradora e custodiante), não `ASSET_MANAGER` para a gestora. Com isso a dependência da ordem se reduz ao caso do adaptador de debêntures (que cria como `COMPANY`). **Muda dois pontos do pacote do Gui (FU7.2, item 1):** a gestora deixa de ser criada como `ASSET_MANAGER`, e a lista de relações (hoje `MANAGES`, `ADMINISTERED_BY`, `PROVIDES_SERVICES_TO` e "investe em") passa a trazer `CUSTODIED_BY` no lugar de `PROVIDES_SERVICES_TO` (D1). **Gui confirmou em 12/11/2026, 13:31** (a FU7.2 não foi começada, então a troca não desfaz nada); o pacote foi ajustado. `MANAGES` continua com a gestora como origem.
- **Revisão ou casamento direto.** Hoje o CNPJ já existente em outro tipo é casado direto, sem revisão. O prompt da FU7.2 do pacote do Gui dizia o contrário ("vai para revisão"); foi corrigido em 12/11/2026. Se o Fábio quiser revisão nesse caso, é mudança de comportamento do #11 e fica fora deste ADR (decisão futura).
- **Gatilho de medição:** quando o cadastro real de emissores de debêntures existir, refazer a contagem de CNPJs que são ao mesmo tempo emissor e prestador/fundo e informar o Fábio (pedido dele, 12/11/2026). Hoje o resultado é zero, mas sem valor como evidência.

### D3. Direção das relações

**Inclinação do Fábio.**
- `ADMINISTERED_BY` e `CUSTODIED_BY`: origem é o fundo, destino é a prestadora.
- `MANAGES`: origem é a gestora, destino é o fundo (como hoje).

**Acréscimos nossos.**
- Registrar no ADR a convenção em uma frase: cada relação se lê "origem verbo destino"; na forma passiva (`..._BY`), a origem é quem sofre a ação (o fundo, que é administrado ou custodiado). Vale também para `CONTROLLED_BY`, que já existe no enum. O ADR-002 já diz "A controla B" e que a direção faz parte da identidade da relação, então a convenção se apoia nele. Hoje as convenções convivem sem texto que as diga (só `CONTROLS` tem exemplo).
- Sem relação inversa automática (regra da camada): quem quiser "fundos administrados por X" consulta pelo destino.
- **"Investe em"** (Fábio, 13:16): `INVESTS_IN`, origem o fundo detentor, destino o fundo investido, de acordo; **Gui confirmou o nome em 13:31.** Como a FU6.1 ainda não está na `main`, a relação só é gravada depois dela. Valor e data da posição **não** entram na relação: ficam em `holdings` no módulo de Fundos (F-06). Posição confidencial (só consolidada) não tem investido conhecido e não gera relação.
- **D9 (Gui):** quando a relação derivada da posição deixa de ser ativa. O Gui decide quando chegar na FU6.1 e a decisão é registrada aqui.

### D4. Uma linha por par; reabrir quando a prestadora voltar; sem histórico por ora

**Inclinação do Fábio.** Uma linha por par (origem, tipo, destino); reabre quando a administradora volta; história fora por enquanto.

**Acréscimos nossos.**
- O que se perde, dito para não surpreender: quando um fundo muda de administradora de A para B e depois volta para A, há uma linha só com A, reaberta; o período em que B administrou aparece só na linha de B, e o intervalo em que A esteve fora não fica registrado na linha de A. Quem precisar de série histórica de administradora lê o módulo de Fundos, não a camada.
- Regra de reabertura (de acordo, Fábio 13:16): limpar o fim da vigência (`valid_to`) e mover o início (`valid_from`) para a data da fonte que mostra a volta; status volta a ativo.
- **Identidade da linha (condição para a reabertura ser upsert).** O repositório faz `ON CONFLICT` no `relationship_id`; outro id com a mesma chave canônica `origem:tipo:destino` levanta `DuplicateRelationshipError`. Por isso o adaptador de fundos deve derivar o `relationship_id` da chave canônica (`uuid5`, como o adaptador de debêntures do #11 faz). Com o id derivado, reabrir é regravar o mesmo id; com id aleatório, o erro aparece.
- **Fechamento.** Quando a prestadora deixa de aparecer na fonte, a relação recebe `valid_to` e status inativo. A data é a de referência da fonte (a do cadastro em que ela deixou de aparecer), e não a da mudança real, que o cadastro não informa. Isso vale para `ADMINISTERED_BY`, `CUSTODIED_BY` e `MANAGES`.
- **Condição para fechar (de acordo, Fábio 13:28).** O fechamento só ocorre quando a leitura foi completa. **Definição:** leitura completa é o que o próprio adaptador consegue afirmar: a execução terminou com sucesso em `collection_runs` e o arquivo do cadastro foi lido até o fim, sem erro de leitura. A camada não define critério novo; como verificar isso é detalhe do adaptador (FU7.2, Gui). Sem isso, um cadastro baixado pela metade inativaria relações em massa, o que contraria o princípio "nada estimado". Em execução parcial ou com falha, o adaptador não fecha nenhuma relação e reporta. Comparar o conjunto lido com o já gravado é comportamento novo em relação ao #11 e é responsabilidade do adaptador de fundos (FU7.2).
- Se o histórico passar a importar, é mudança de chave única e de todos os adaptadores; registrar como gatilho para novo ADR, não resolver aqui.

## 3. Fora do escopo deste ADR

- **D5 (gestora pessoa física), D6 (classe como entidade), D7 (mapa de situação) e D9 ("investe em" derivado):** decisão tomada à parte do ADR-012. A proposta de trabalho para D5 é não criar entidade e só contar no relatório do adaptador (sem CPF, o único identificador possível seria o nome, que nunca une).
- **D8 (CNPJ alfanumérico):** o Fábio aprovou o ADR-011. A regra da camada é a referência; `fundos.cnpj` do Gui continua mais estrito de propósito.

## 4. Migração

Nenhuma migration de schema: os três enums são texto sem `CHECK`. O que existe é ordem de atualização: o código que conhece `CUSTODIED_BY` e `INVESTS_IN` (nome confirmado pelo Gui) precisa estar na `main` e nas máquinas antes de qualquer banco gravar valores novos, porque um código antigo que leia uma relação de tipo desconhecido pode falhar ao converter o texto no enum (risco já descrito no ADR-007). O adaptador de fundos (FU7.2) só grava depois disso.

## 5. Consequências

- A camada representa os dados de fundos sem criar um tipo por papel e sem alterar entidades existentes.
- O `entity_type` de prestadores de serviço deixa de significar papel; qualquer leitor (inclusive o contrato de leitura do ADR-006) precisa ler papel nas relações.
- Ficam duas relações novas (custódia e "investe em", nome confirmado pelo Gui) e uma convenção de direção por escrito.
- O adaptador de fundos passa a fechar relações que somem da fonte, só em execução completa (D4).
- Histórico de prestadores fica fora da camada até uma decisão nova.

## 6. Perguntas e respostas (Fábio, 13:16 e 13:28; Gui, 13:31)

1. D2: aceita a dependência da ordem, com as duas regras; ordem fixa não vale o custo. **Pergunta nova dele, respondida pelo Gui (13:31):** `FINANCIAL_INSTITUTION` aos três papéis, não `ASSET_MANAGER` à gestora; o argumento é que o tipo de quem é gestora e administradora não pode depender da ordem de importação.
2. D1: `CUSTODIED_BY`; `PROVIDES_SERVICES_TO` não é usado para administração nem custódia em Fundos. Sim.
3. D3: `INVESTS_IN`, detentor na origem. Sim; o Gui confirmou o nome (13:31).
4. D4: regra de reabertura de acordo, com o uuid5 da chave e a regra de fechamento escritas acima. A condição de leitura completa para fechar: de acordo (13:28), com a definição acima. O relatório do `--dry-run` do adaptador deve dizer quantas relações seriam fechadas e quantas reabertas antes de qualquer `--commit` (fica na FU7.2, não neste ADR).
5. Auditor e controlador ficam fora. Sim.

**Próximo passo:** D5, D6, D7 e D9 ficam para decisão à parte. Detalhe de como verificar "leitura completa" (proposta do Gui: comparar as linhas lidas com as do manifesto em `raw_records`, além do status em `collection_runs`; se divergirem, não fecha nada e reporta) e o relatório do `--dry-run` com relações a fechar e a reabrir ficam na FU7.2, não neste ADR.
