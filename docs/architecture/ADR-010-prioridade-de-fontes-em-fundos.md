# ADR-010: Prioridade de fontes em Fundos

## Status

Proposta, de 28/10/2026. Vale só para o módulo de Fundos (`Gui/fundos`). Nada aqui foi implementado: as mudanças de código, de teste e de migration estão no ponto g como tarefas futuras propostas.

Pontos que exigem confirmação explícita do Gui: b) (a prioridade passa a valer só dentro da mesma competência, o que muda o comportamento da view e inverte um teste existente) e g) (migration 003 que muda a prioridade semeada da CVM_DADOS_ABERTOS de 200 para 450).

## Contexto

### A regra

As "Regras de dados" do `CLAUDE.md` dizem:

- **Regra 3:** hierarquia de fontes BACEN > CVM > ANBIMA > plataformas especializadas > sites institucionais. A fonte de menor prioridade complementa a oficial, nunca a sobrescreve automaticamente.
- **Regra 4:** preservar o valor original de cada fonte antes de reconciliar.
- **Regra 6:** o CNPJ é o identificador forte. Match só por nome vai para revisão e nunca une automaticamente.

### O que existe em Fundos

Na migration `Gui/fundos/migrations/001_initial_schema.sql`:

- `sources.priority` é um inteiro maior ou igual a 0, com padrão 0. Só duas fontes são semeadas: `CVM_DADOS_ABERTOS` (`open_data`, prioridade 200, ativa) e `MANUAL` (`manual`, 1000, ativa). A ANBIMA e o Fundos.NET não são semeados; o comentário da migration diz que entram depois deste ADR.
- A view `current_observations` escolhe uma linha por assunto (fundo, classe ou série) e por `field_name`, só entre fontes ativas, na ordem `priority DESC, reference_date DESC, collected_at DESC, id DESC`. O comentário da view diz que a escala é provisória até este ADR.
- `field_name` é a `tabela.coluna` da CVM, sem renomear. Como a view particiona por assunto e `field_name`, duas fontes só disputam o valor atual quando gravam o mesmo `field_name`.
- `observations` é imutável: os triggers recusam UPDATE e DELETE. A confiança gravada (`reported`, `verified`, `manual`, `conflicting` ou `suspect`) é a do momento da gravação e não muda depois.
- Toda observação exige uma coleta (`collection_run_id`) e um manifesto de arquivo (`raw_record_id`: nome, tamanho e SHA-256).
- `audit_log` tem `actor` obrigatório e `reason` opcional.
- `source_type` aceita `internal`, que nenhuma fonte usa.

No código e nos testes:

- `Gui/fundos/tests/test_current_observations_view.py` fixa a ordem da view em dois testes:
  - `test_higher_priority_source_wins_over_newer_reference_date`: uma observação MANUAL de 2026-06-30 vence uma da CVM de 2026-09-30;
  - `test_same_reference_date_most_recent_collection_wins_and_both_rows_stay`: na mesma fonte e na mesma competência, vence a coleta mais recente, e as duas linhas ficam.
- `ObservationRepository.record` (`Gui/fundos/src/fundos/repositories/observation_repository.py`) abre conflito em `data_conflicts` para todo par de valores diferentes (tipo, valor ou unidade) com o mesmo assunto, campo e competência. Vale tanto para a reapresentação na mesma fonte quanto para a divergência entre fontes, e não depende da prioridade nem de a fonte estar ativa.
- `data_conflicts` guarda o campo, a competência, as duas observações, `status` (`open`, `resolved` ou `ignored`), `resolution_note` e `resolved_at`. Não tem coluna para quem resolveu. O `ConflictRepository` só consulta; resolver ou ignorar com registro em `audit_log` é etapa futura (docstring da classe).
- Fontes e prioridades só mudam por migration (`SourceRepository`).
- O fixture de teste `connection` (`Gui/fundos/tests/conftest.py`) cria o banco só com a migration 001.

### O que existe nas debêntures

Em `Eduardo/debenture-replica/migrations/001_initial_schema.sql`, as sementes são `SND` 100, `CVM` 200, `ANBIMA_API` 300 (inativa) e `MANUAL` 1000. A view ordena `priority DESC, observed_at DESC, collected_at DESC, id DESC`. Se a `ANBIMA_API` for ativada, ela passa à frente da CVM, contra a regra 3. O problema já está registrado em `docs/divergencias-claude-md.md` (item 9) e em `docs/fundos-descoberta.md` (seção 5, item 2).

### O que existe na camada compartilhada

`src/pense_alm/shared/entities/provenance.py` usa a convenção inversa: número menor vence (BACEN 1, CVM 2, ANBIMA 3, SPECIALIZED 4, INSTITUTIONAL 5, MANUAL 6), e a fonte manual fica em último lugar. Nos dois módulos SQL, número maior vence e a MANUAL ("entrada manual validada") fica em primeiro. São três escalas para a mesma regra.

### O que não foi conferido

A ANBIMA e o Fundos.NET não foram amostrados como fonte de dado de fundos. Do Fundos.NET só se conhece a grade de documentos (`docs/fundos-descoberta.md`, seção 11): a linha não traz CNPJ, e o formato dos documentos de fundos (PDF ou XML) não foi conferido. Por isso os exemplos deste ADR são sintéticos, com fundo fictício e valores sem significado, e estão marcados como exemplo ilustrativo.

### Vocabulário

Os termos seguem o ADR-006 sempre que possível:

- **Fonte:** uma linha de `sources`.
- **Camada:** um degrau da regra 3 (BACEN, CVM, ANBIMA, plataformas especializadas, sites institucionais). A entrada manual fica fora da regra.
- **Prioridade:** `sources.priority`. Número maior vence.
- **Competência:** `observations.reference_date`, a data a que o dado se refere, como a fonte a informa.
- **Chave:** assunto (fundo, classe ou série) + `field_name` + competência.
- **Conflito:** uma linha de `data_conflicts`, com duas observações da mesma chave e valores diferentes.
- **Confiança:** `observations.confidence`, com os valores do ADR-006 (G-03).
- **Valor atual:** a linha que `current_observations` escolhe.

## Decisão

### a) Escala por camada

A regra 3 vira faixas de 100 em `sources.priority`. A convenção atual do módulo continua: número maior vence.

| Camada | Faixa | Fonte | Prioridade | Situação |
|---|---|---|---|---|
| Entrada manual validada (fora da regra 3; ver d) | 1000 | `MANUAL` | 1000 | semeada; não muda |
| Reservada | 600 a 999 | nenhuma | | sem uso |
| BACEN | 500 a 599 | nenhuma prevista em Fundos | 550, se vier | reservada |
| CVM | 400 a 499 | `CVM_DADOS_ABERTOS` | 450 (hoje 200) | semeada; muda na migration 003 (ver g) |
| CVM | 400 a 499 | Fundos.NET, documento estruturado | 440 | futura, não semeada (ver e) |
| CVM | 400 a 499 | Fundos.NET, extração de texto livre | 430 | futura, só se houver extrator (ver e) |
| ANBIMA | 300 a 399 | ANBIMA | 350 | futura, nasce inativa (ver e) |
| Plataformas especializadas | 200 a 299 | nenhuma | 250, se vier | reservada |
| Sites institucionais | 100 a 199 | nenhuma | 150, se vier | reservada |
| Sem camada | 0 a 99 | nenhuma | | proibida (0 é o padrão da coluna) |

O código de cada fonte futura é escolhido na migration que a semear.

Regras dos valores:

1. A primeira fonte de uma camada fica no meio da faixa (o número terminado em 50). As fontes seguintes da mesma camada ocupam múltiplos de 10, acima ou abaixo. A ordem dentro da camada é decidida na migration que as semeia, com a justificativa num comentário.
2. Duas fontes nunca têm a mesma prioridade. Um empate seria decidido pela data da coleta, que não mede confiabilidade.
3. A `MANUAL` é a única fonte acima de 599.
4. As camadas usam os nomes do `SourceType` da camada compartilhada (`bacen`, `cvm`, `anbima`, `specialized`, `institutional`, `manual`), para que a integração da Fase 3 faça o mapeamento pelo nome, e não pelo número.

**Checagem (tarefa futura 2).** Um teste em `Gui/fundos/tests` aplica todas as migrations, em ordem, num banco temporário. O fixture atual aplica só a 001, então o teste precisa de um banco próprio. Depois, lê `sources` e falha se:

- uma fonte não está no mapa código → camada declarado no teste (fonte nova sem camada);
- a prioridade está fora da faixa da camada;
- a `MANUAL` não vale 1000, ou outra fonte está acima de 599;
- há prioridade repetida ou abaixo de 100;
- uma fonte de camada inferior tem prioridade maior que uma de camada superior;
- alguma fonte tem `source_type = 'internal'` (ver e).

Como as fontes só entram por migration e todas as migrations passam por esse teste, nenhuma fonte nova chega ao banco sem camada. O mapa do teste cita este ADR, e mudar a faixa de uma camada exige mudar o ADR.

### b) Prioridade e competência

A prioridade decide só entre observações da mesma competência. Entre competências diferentes, vale a mais recente.

Na view `current_observations`, muda só a ordem das duas primeiras chaves:

    hoje:     ORDER BY s.priority DESC, o.reference_date DESC, o.collected_at DESC, o.id DESC
    proposta: ORDER BY o.reference_date DESC, s.priority DESC, o.collected_at DESC, o.id DESC

A partição (assunto e `field_name`), o filtro de fontes ativas e as colunas expostas continuam iguais. O teste `test_higher_priority_source_wins_over_newer_reference_date` passa a esperar o contrário. O teste `test_same_reference_date_most_recent_collection_wins_and_both_rows_stay` não muda.

**Exemplo ilustrativo.** Fundo fictício, valores sem significado: a classe do "FIDC Exemplo Alfa (fictício)", campo `tab_IV.TAB_IV_A_VL_PL`.

*Caso 1, já possível hoje (MANUAL e CVM):*

| Observação | Fonte (prioridade hoje) | Competência | Valor |
|---|---|---|---|
| 1 | `MANUAL` (1000) | 2026-06-30 | 90 |
| 2 | `CVM_DADOS_ABERTOS` (200) | 2026-09-30 | 110 |

- **Hoje:** o valor atual é 90, de junho. A correção manual de junho esconde setembro e todas as competências seguintes da CVM, para sempre.
- **Proposta:** o valor atual é 110, de setembro. O 90 continua no histórico como o valor de junho.

*Caso 2, com uma fonte que ainda não existe (o Fundos.NET, hipotético, abaixo dos dados abertos):*

| Observação | Fonte (prioridade proposta) | Competência | Valor |
|---|---|---|---|
| 1 | `CVM_DADOS_ABERTOS` (450) | 2026-08-31 | 100 |
| 2 | Fundos.NET, documento estruturado (440) | 2026-09-30 | 110 |

Setembro já foi entregue no Fundos.NET, mas ainda não está no arquivo semanal dos dados abertos.

- **Ordem atual:** o valor atual é 100, de agosto. A competência mais nova fica escondida até os dados abertos a trazerem, e para sempre se a classe deixar de aparecer neles.
- **Proposta:** o valor atual é 110, de setembro, com a fonte Fundos.NET visível.
- **Quando os dados abertos trouxerem setembro:** se o valor for o mesmo (110), a observação dos dados abertos vence pela prioridade e não há conflito. Se for diferente (111, por exemplo), os dados abertos vencem e um conflito é aberto (ver c).

Condições da regra:

1. `reference_date` é a competência informada pela fonte, nunca a data da coleta. Uma competência errada, no futuro, dominaria o valor atual. Por isso a tarefa futura 3 propõe recusar competência posterior à data da coleta.
2. Uma fonte que não é a CVM só grava no `field_name` de uma coluna da CVM quando o dado for a mesma medida, com a mesma competência; por exemplo, o informe mensal entregue em XML no Fundos.NET. Outra medida, mesmo de nome parecido (um PL diário, por exemplo), vai num `field_name` próprio da fonte e não disputa com a CVM: aparece como campo à parte, com a fonte visível. O mapeamento de cada campo fica documentado no adaptador da fonte.
3. **Gatilho de revisão:** este ponto é revisto quando um campo sem competência própria ganhar segunda fonte ou entrada MANUAL. É o caso dos campos do cadastro, que é um retrato diário. A regra por campo (alternativa B3) é a candidata. O cadastro passou a ser carregado (`Gui/fundos/scripts/load_cadastro.py`) só com a fonte `CVM_DADOS_ABERTOS`, então o gatilho não disparou; a data de referência dele está em Pendências.

### c) Conflito

A chave é assunto + `field_name` + competência. Há divergência quando o tipo, o valor ou a unidade são diferentes.

- **O que a view mostra:** a observação escolhida pela regra de b). Na mesma competência, a da fonte de maior prioridade; entre coletas da mesma fonte, a mais recente. A view não lê `data_conflicts`. A camada de leitura (ADR-006, regra 5) entrega o valor atual marcado, junto com as observações em disputa (valor, fonte e competência).
- **O que vai para `data_conflicts`:** um par por divergência, com `status = 'open'`, como o `ObservationRepository` já faz. Isso inclui o caso em que uma das fontes está inativa e a reapresentação na mesma fonte.
- **Quem resolve:** uma pessoa, nunca o código. O responsável é o dono da frente de Fundos (o Gui, decisão 1 de `docs/decisoes-em-aberto.md`) ou quem ele designar.
  - Resolver ou ignorar grava `status`, `resolution_note` e `resolved_at`.
  - Grava também uma linha em `audit_log`, com `actor`, `action`, `entity_type = 'data_conflicts'`, `entity_id`, `before_data`, `after_data` e `reason`.
- Resolver o conflito não muda o valor mostrado. Para mudar o valor, registra-se uma entrada MANUAL (ver d).
- A confiança `conflicting` do ADR-006 é calculada na leitura, a partir do conflito aberto. Ela não é gravada, porque `observations` é imutável.

A fonte menor:

- **Nunca apaga a maior.** As observações são imutáveis; na mesma competência, a view sempre prefere a fonte maior; e nenhum conflito é resolvido automaticamente.
- **Complementa o que falta:** um campo que a fonte maior não publica, ou uma competência que ela ainda não tem. O valor complementar sempre sai com a fonte visível, no envelope do ADR-006.

### d) Entrada manual (MANUAL)

A `MANUAL` (1000) não é camada da regra 3. É a correção validada por uma pessoa, e por isso fica acima de todas as fontes.

**Quando vale.** Só em dois casos, sempre com evidência:

1. corrigir um valor publicado que está comprovadamente errado;
2. registrar um valor lido em documento oficial, quando nenhuma fonte automática o traz.

Nunca serve para estimar, arredondar ou completar dado sem documento. O documento de evidência é registrado como manifesto em `raw_records` (o schema já exige `raw_record_id`), e a observação é gravada com `confidence = 'manual'`.

**O que exige no `audit_log`.** Uma linha por entrada, com:

- `actor`: o responsável, pelo nome;
- `action`: o lançamento manual;
- `entity_type = 'observations'` e `entity_id`: a observação criada;
- `reason`: o motivo, obrigatório. O schema aceita vazio, então a obrigação fica no código (tarefa futura 4);
- `after_data`: o valor, a competência, as observações oficiais que a entrada contraria e o manifesto da evidência.

**Se contrariar a fonte oficial.** Vira conflito aberto, o que o repositório já faz ao gravar. O conflito fica aberto até uma revisão registrada (ver c), de preferência feita por outra pessoa. Enquanto a entrada manual contrariar a fonte oficial na mesma competência, os dois valores e o conflito aberto ficam visíveis na leitura, para que a correção manual nunca esconda a divergência.

**Validade.** O valor manual vale só para a competência em que foi lançado.

- Nessa competência, continua valendo até a revisão. Se a fonte oficial reapresentar um valor diferente do manual, abre-se um conflito novo.
- Nas competências seguintes, a fonte oficial volta a ser o valor atual sozinha, pela regra de b).
- Não há expiração por prazo.

### e) Fontes que entram

**Fundos.NET.** Fica na camada CVM (400 a 499), abaixo dos dados abertos. É o sistema pelo qual o administrador entrega os documentos à CVM; o informe de FIAGRO, por exemplo, é entregue por ele (`docs/fundos-descoberta.md`, seção 2). Os dados abertos são a consolidação que a CVM publica.

- O documento estruturado (XML) e o dado extraído de texto livre (PDF) entram como fontes separadas, com códigos próprios: estruturado com 440, extração com 430.
- O dado extraído de documento **não** tem a mesma confiança do dado estruturado. A diferença aparece em dois lugares:
  - na prioridade: abaixo dos dados abertos e, no caso da extração, abaixo do estruturado;
  - na versão do extrator, em `raw_records.parser_version`.

  O campo `confidence` fica `reported` até uma verificação humana (`verified`). Não se cria nível novo de confiança.
- Precondição: um documento só gera observação depois de ligado à classe pelo CNPJ. A linha da grade não traz CNPJ (seção 11.5), e ligar por nome vai para revisão (regra 6).
- Nada disso foi conferido no dado. O formato dos documentos de fundos e o download fora do navegador continuam em aberto (seção 11.8).

**ANBIMA.** Fica na camada ANBIMA (300 a 399), com prioridade 350, abaixo de toda fonte da CVM. Entra inativa, na migration que a semear, e só depois de uma amostra e da conferência de acesso e de termos de uso. Grava em `field_name` próprio, salvo mapeamento documentado da mesma medida com a mesma competência (ver b). Este ADR não decide se a ANBIMA será usada em Fundos (por exemplo, como segunda fonte da variante do FIAGRO, decisão 7).

**BACEN.** Faixa reservada (500 a 599). Nenhuma fonte prevista em Fundos.

**Plataformas especializadas e sites institucionais.** Faixas reservadas.

**Dado interno da casa.** Fica fora desta escala e fora do banco de Fundos (decisões 2 e 4 de `docs/decisoes-em-aberto.md`): a lista de fundos da casa nunca vira linha de `sources` nem de `observations`. O comparativo casa × mercado é montado só em ambiente interno, com o banco público aberto somente para leitura (`docs/fundos-descoberta.md`, seção 7). O `source_type = 'internal'`, que o schema aceita, não serve para isso. O teste de a) recusa qualquer fonte desse tipo enquanto outro ADR não definir o seu uso.

### f) Escopo

Este ADR vale para o módulo de Fundos (`Gui/fundos`). Não altera as debêntures, o CRI/CRA nem a camada compartilhada. Registra, sem mexer:

- **Debêntures.** A escala está invertida em relação à regra 3: a `ANBIMA_API` (300, inativa) está acima da `CVM` (200). A view também põe a prioridade antes da data (`observed_at`). Antes de ativar a `ANBIMA_API` (opções E e F da D-04), a frente de Debêntures precisa decidir a escala e criar uma migration nova em `Eduardo/debenture-replica/migrations/`. Também cabe a ela decidir em que camada fica o `SND`.
- **Camada compartilhada.** Usa a escala inversa e põe a fonte manual em último lugar. Na integração da Fase 3:
  - as observações de Fundos devem ser mapeadas pelo nome da camada, não pelo número;
  - os dois sentidos de "manual" precisam ser conciliados: em Fundos é a correção validada, na camada compartilhada é a fonte de menor prioridade.

### g) Migrations e tarefas futuras

A recomendação **exige** mudar o que a migration 001 de Fundos semeou e criou:

- a prioridade da `CVM_DADOS_ABERTOS` passa de 200 para 450;
- a view `current_observations` é recriada com a ordem de b).

A `MANUAL` continua em 1000. A migration 001 não é editada.

As duas mudanças vão numa migration 003, numa tarefa futura (a 002 passou a ser a de `party_observations`, do leitor do cadastro), antes da primeira entrada MANUAL real e antes de semear qualquer outra fonte. Ela segue o fluxo de mudança de schema do `CLAUDE.md`: plano aprovado, teste da migration e da idempotência, `--dry-run`, backup e só então `--commit`. Como altera uma linha e uma view que já existem, exige `--allow-existing-changes` no `Gui/fundos/scripts/apply_migration.py`.

Tarefas futuras (**propostas; nenhuma foi feita**):

1. **Migration 003:** prioridade da `CVM_DADOS_ABERTOS` e nova view. Hoje o fixture `connection` aplica só a 001, então a tarefa inclui definir como a suíte passa a usar as migrations seguintes. Depois disso:
   - atualizar os testes que fixam 200 (`test_seeded_sources_by_code`, `test_view_exposes_provenance`);
   - inverter `test_higher_priority_source_wins_over_newer_reference_date`;
   - acrescentar um teste de prioridade dentro da mesma competência.

   Os testes da 001 isolada (`test_migration_001.py`) continuam verificando a 001.
2. **Teste da escala**, como descrito em a).
3. **Recusar competência posterior à data da coleta** (`reference_date` maior que a data de `collected_at`), no repositório ou numa migration.
4. **Lançamento manual:** exigir `confidence = 'manual'`, evidência em `raw_records`, e responsável e motivo no `audit_log`.
5. **Resolver e ignorar conflito** com registro no `audit_log`, como o `ConflictRepository` já prevê.
6. **Semear o Fundos.NET e a ANBIMA**, cada um em migration própria, depois da amostra e da conferência de termos, com a prioridade da sua camada. A ANBIMA nasce inativa.
7. **Debêntures:** decisão e migration da escala, pela frente de Debêntures (fora de Fundos).
8. **Regra por campo (B3)**, só se o gatilho de b) acontecer.

## Alternativas consideradas

As opções recomendadas estão em negrito.

### a) Escala

| Opção | Prós | Contras |
|---|---|---|
| A1. Encaixar cada fonte nova caso a caso (por exemplo, ANBIMA 150) | nenhuma migration agora | não há regra verificável; foi assim que a ANBIMA ficou acima da CVM nas debêntures |
| **A2. Faixas de 100 por camada, com número maior vencendo** | mantém o sentido da coluna, da view e do `SourceRepository.list_all`; deixa folga para fontes novas; é verificável por teste | exige mudar a CVM de 200 para 450 |
| A3. Inverter para "número menor vence", como a camada compartilhada | mesma convenção da `provenance.py` | muda o sentido de uma coluna existente e destoa das debêntures; a MANUAL continuaria em posição oposta à da camada compartilhada; uma inversão incompleta é o próprio erro que se quer evitar |
| A4. Coluna de camada em `sources`, com CHECK de faixa no banco | o banco recusa a fonte fora da faixa | mudança de schema numa tabela referenciada por outras três; pode vir depois, como reforço do teste |

### b) Prioridade e competência

| Opção | Prós | Contras |
|---|---|---|
| B1. Manter: prioridade antes da competência | já está testado; a fonte maior nunca é superada | um valor antigo da fonte maior esconde uma competência mais nova (casos 1 e 2); a correção manual de uma competência vira o valor atual para sempre |
| **B2. Prioridade só dentro da mesma competência; entre competências, vale a mais recente** | o valor atual é o da competência mais recente; a fonte menor só complementa o que a maior não tem; continua uma só definição de valor atual, em SQL; a mudança na view é mínima | uma fonte menor pode aparecer como valor atual (sempre com a fonte visível); depende de a competência ser confiável; num campo de retrato com duas fontes de ritmos diferentes, o valor atual pode alternar entre elas |
| B3. Regra por campo, ou por tabela da CVM: série usa B2, cadastro usa B1 | trata série e cadastro de formas diferentes | exige tabela nova de política, um catálogo a manter e junção na view; campo sem política precisa de um padrão; hoje nenhum campo do cadastro tem segunda fonte |

### c) Conflito

| Opção | Prós | Contras |
|---|---|---|
| **C1. Mostrar o valor da fonte maior, marcado, com as observações em disputa; conflito aberto até revisão humana** | é o comportamento atual e a regra 5 do ADR-006; nada fica escondido | a fila de conflitos cresce enquanto não houver a rotina de resolução (tarefa futura 5) |
| C2. Esconder o campo enquanto houver conflito | não mostra valor duvidoso | contraria o ADR-006; um erro da fonte menor apagaria o valor oficial da tela |
| C3. Resolver automaticamente pela prioridade | a fila fica vazia | perde o sinal de que a fonte oficial pode estar errada; contraria o "nunca automaticamente" da regra 3 |
| C4. Abrir conflito só entre camadas diferentes | menos conflitos | o informe de FIDC não tem versão, e a reapresentação dele só aparece como conflito na mesma fonte (`docs/fundos-descoberta.md`, seção 10.7) |

### d) Entrada manual

Quando vale:

| Opção | Prós | Contras |
|---|---|---|
| D1. Para qualquer complemento | flexível | abre a porta para valor estimado |
| **D2. Para correção, ou para valor lido em documento oficial, sempre com evidência** | rastreável; o schema já exige o manifesto | exige registrar a evidência a cada lançamento |
| D3. Só para resolver conflito | mínima | não cobre o valor que nenhuma fonte automática traz (por exemplo, um dado lido no regulamento) |

Validade:

| Opção | Prós | Contras |
|---|---|---|
| E1. Vale para sempre e para todas as competências (comportamento de hoje) | a correção nunca se perde | esconde as competências seguintes da fonte oficial |
| **E2. Vale só na competência em que foi lançada, até a revisão** | corrige um dado, não um campo inteiro; a fonte oficial volta sem ação manual | se a fonte oficial repetir o erro numa competência seguinte, nada avisa |
| E3. Expira quando a fonte oficial publicar de novo na mesma chave | não acumula correções | volta, sem ninguém olhar, ao valor que uma pessoa julgou errado |
| E4. Prazo de validade (`valid_until`) | explícita | exige coluna nova, e o prazo é arbitrário |

### e) Fontes que entram

Fundos.NET:

| Opção | Prós | Contras |
|---|---|---|
| F1. Mesma prioridade da `CVM_DADOS_ABERTOS` | reconhece que é a mesma camada | o empate é decidido pela data da coleta, o que é instável |
| **F2. Camada CVM, abaixo dos dados abertos; estruturado acima de extração, cada um com código próprio** | segue a regra 3; distingue dado estruturado de dado extraído | duas fontes a manter, se houver extrator |
| F3. Camada de plataforma especializada | trata o sistema como intermediário | o documento é a entrega regulatória à CVM |
| F4. Abaixo da ANBIMA | cautela máxima com a extração | põe um documento entregue à CVM abaixo da ANBIMA, contra a regra 3 |

ANBIMA:

| Opção | Prós | Contras |
|---|---|---|
| G1. Acima da CVM, como nas debêntures | nenhum | contraria a regra 3 |
| **G2. Faixa de 300 a 399, abaixo da CVM, nascendo inativa** | segue a regra 3 | só pode ser ativada depois da amostra e da conferência de termos |

### f) Escopo

| Opção | Prós | Contras |
|---|---|---|
| **H1. Só Fundos, com as debêntures e a camada compartilhada registradas como pendência** | não mexe em frente de outro dono; o problema fica registrado | as três escalas continuam diferentes até as outras frentes decidirem |
| H2. O projeto inteiro | uma escala só | decide por frentes que têm outros donos e mudaria as debêntures e a camada compartilhada |
| H3. Só Fundos, sem registrar as outras | escopo menor | o problema conhecido fica sem dono |

### g) Migrations

| Opção | Prós | Contras |
|---|---|---|
| **I1. Migration 003 própria, antes da primeira entrada MANUAL real e de qualquer fonte nova** | corrige a view antes de o caso 1 acontecer com dado real | uma migration a mais |
| I2. Juntar com a migration que semear a próxima fonte | uma migration a menos | o caso MANUAL × CVM já é possível hoje |
| I3. Editar a migration 001 | nenhum | proibido pelo `CLAUDE.md`: migration aplicada não se edita |

## Consequências

### Positivas

- A ordem da regra 3 passa a estar nos números, com folga para fontes novas. Uma fonte nova sem camada falha no teste antes de chegar ao banco.
- O valor atual passa a ser o da competência mais recente. Uma correção manual não congela mais o campo.
- A fonte menor nunca vence a maior na mesma competência, e toda divergência fica visível até uma pessoa revisá-la.
- O Fundos.NET e a ANBIMA já têm lugar definido antes de serem semeados.
- O dado interno da casa continua fora do banco.

### Negativas e riscos

- Uma fonte menor pode aparecer como valor atual quando tiver competência mais nova. A fonte sempre aparece junto.
- A regra depende de a competência ser confiável. Sem a checagem da tarefa futura 3, uma data errada, no futuro, dominaria o valor atual.
- Se a fonte oficial repetir, numa competência seguinte, um erro já corrigido manualmente, nada avisa.
- A migration 003 muda um valor semeado e inverte um teste existente.
- Enquanto não houver a rotina de resolução (tarefa futura 5), os conflitos só acumulam.
- Continua uma limitação já documentada: se a mesma fonte publicar A, depois B e depois A de novo na mesma competência, a terceira publicação não gera linha, e o valor atual fica B (`test_returning_to_an_old_value_creates_no_row_and_keeps_the_conflict`).

### Pendências

- Debêntures: a escala e a ordem da view (ver f), antes de ativar a `ANBIMA_API`.
- Camada compartilhada: conciliar a escala e o sentido de "manual" na Fase 3.
- ~~A data de referência dos campos do cadastro, a definir no adaptador do cadastro.~~ Definida no leitor do cadastro: é a competência do retrato, informada em `--reference-date` (a data do `Last-Modified` do ZIP na CVM), nunca a data da coleta.
- Onde ficam os valores calculados (a subordinação e o corte do FIC-FIDC), se forem gravados como observação.
- A amostra da ANBIMA e a conferência dos documentos do Fundos.NET.

### Fora do escopo

- Código, testes e migrations (todos propostos em g).
- Escolher se a ANBIMA ou o Fundos.NET serão usados para um campo específico (por exemplo, a variante do FIAGRO, decisão 7).
- A forma de exibir o conflito no site (G-04) e o contrato de leitura (ADR-006).
- As decisões em aberto R-01, D-04, G-06 e R-08.
