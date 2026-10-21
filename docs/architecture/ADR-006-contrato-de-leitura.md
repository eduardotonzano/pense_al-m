# ADR-006: Contrato de leitura para o site

## Status

Proposta. Depende de decisões em aberto registradas em `docs/decisoes-em-aberto.md` (G-06 em especial).

## Contexto

O site da plataforma vai exibir os produtos (debêntures, CRI/CRA, renda fixa e fundos) sem escrever no banco e sem completar dado que não foi coletado. As regras de exibição pendentes (`docs/regras-de-exibicao-pendentes.md`) pedem:

- G-02: proveniência de cada valor (fonte e data);
- G-03: nível de confiança do dado;
- G-04: conflitos entre fontes visíveis;
- G-07: campos da listagem e da ficha, ordenação e filtros;
- G-08: busca por código, ISIN, emissor e CNPJ.

Hoje não há um ponto único de leitura. O que existe no módulo de debêntures (`Eduardo/debenture-replica`):

- A tabela `observations` guarda cada valor com tipo, unidade, fonte, `observed_at`, `collected_at` e `confidence`. Cada linha tem exatamente um valor preenchido (restrição `CHECK` do schema), então valor nulo não é gravado.
- A view `current_observations` (migration `001_initial_schema.sql`) escolhe uma linha por debênture e campo, ordenando por prioridade da fonte, depois `observed_at`, `collected_at` e `id`. Considera só fontes ativas. É usada por `ObservationRepository.get_current` e `list_current`.
- `DebentureQueryService.current_values` calculava o "valor atual" de outro modo: pegava o `observed_at` mais recente e **ignorava a prioridade da fonte**. Agora lê a view `current_observations`. É essa consulta que alimenta `get_details` e os exports (`exports/debentures.csv`).
- O conflito aparece apenas como contagem por debênture (`count_open_conflicts`, coluna `open_conflicts`). A tabela `data_conflicts` tem `field_name` e as observações `observation_a_id` e `observation_b_id`, mas a contagem descarta essa informação.
- Os campos de identificação (código, ISIN, emissor, CNPJ) ficam em `debentures` e `issuers`. Passaram a ser gravados também em `observations` (D-08), com fonte e data de observação, mas só nas coletas feitas depois dessa mudança: os ativos já coletados continuam sem essas observações até serem recoletados.
- A busca existente cobre código (`find_by_code`), ISIN (`find_by_isin`) e nome do emissor (`search_by_issuer`). Não cobre CNPJ.
- Dos produtos, só as debêntures têm o esqueleto `observations` / `data_conflicts`. O schema do CRI/CRA (`Enrico/cri_cra_platform/src/credit_assets/database/schema.sql`) é diferente.
- A fonte `ANBIMA_API` está cadastrada como inativa; a view a ignora.

Dados reais que o contrato precisa representar sem distorcer: a PETR27 tem dois valores de `valor_nominal` coletados (1465.60931 em 11/09/2026 e 1460.23387 em 14/09/2026, com 5 casas); a CEPEA1 tem `spread` = 100 com unidade `percentual`; a CEPEA1 venceu em 15/10/2026 e consta `active`; todos os ativos têm 0 conflitos abertos.

## Decisão

Adotar um contrato de leitura somente leitura, por produto, com duas consultas:

1. **Listagem:** `listar_<produto>(filtros, ordenacao, pagina, campos)` devolve um resumo de cada ativo.
2. **Ficha:** `obter_ficha_<produto>(identificador, tipo)` devolve todos os campos do ativo.

Uma terceira consulta, `buscar(termo)`, atende a busca global (G-08).

A primeira implementação cobre debêntures. Os demais produtos adotam o mesmo envelope de valor quando tiverem observações com proveniência. Este ADR não implementa nada.

### Envelope de valor

Todo campo que o contrato devolve segue a mesma estrutura:

| Atributo | Conteúdo |
|---|---|
| `estado` | `presente` ou `ausente`. Nunca `null` silencioso |
| `valor` | valor tal como coletado, sem arredondar. Só existe se `estado = presente` |
| `tipo` | `text`, `numeric`, `date` ou `boolean` |
| `unidade` | unidade da observação, quando houver |
| `fonte` | código, nome, tipo e prioridade da fonte |
| `data_observacao` | `observed_at` da observação |
| `confianca` | `reported`, `verified`, `manual`, `conflicting` ou `suspect` (G-03) |
| `conflito_aberto` | indicador, quantidade e as observações em disputa (G-04) |
| `motivo_ausencia` | só se `estado = ausente` |

Exemplo (campo presente):

    valor_nominal:
      estado: presente
      valor: 1460.23387
      tipo: numeric
      unidade: BRL
      fonte: { codigo: SND, prioridade: 100 }
      data_observacao: 2026-09-14T10:54:55+00:00
      confianca: reported
      conflito_aberto: { aberto: false, quantidade: 0, observacoes: [] }

Exemplo (campo ausente):

    rating:
      estado: ausente
      motivo_ausencia: nunca_coletado

### Regras do envelope

1. **Ausente é ausente.** O contrato nunca devolve `null`, texto vazio, zero ou valor estimado no lugar de um dado que não existe. O campo ausente aparece na resposta, com `estado = ausente`.
2. **Como se sabe o que está ausente.** A view não tem linha para o que nunca foi coletado. A camada de leitura mantém um catálogo de campos esperados por produto (para debêntures, os campos hoje coletados: `agente_fiduciario`, `classe`, `data_emissao`, `data_vencimento`, `garantia`, `incentivada`, `indexador`, `quantidade_em_mercado`, `quantidade_emitida`, `resgate_antecipado`, `valor_nominal`, `valor_nominal_emissao`, `spread`, mais os que as decisões D-01, D-04 e D-07 vierem a incluir) e marca como `ausente` o que não tem observação.
3. **Motivos de ausência** (apenas os que os dados permitem afirmar): `nunca_coletado` (nenhuma observação) e `fonte_inativa` (só existem observações de fonte inativa). Outros motivos só entram se houver dado que os sustente.
4. **Valor atual** é o da view `current_observations`. O histórico completo continua acessível pela tabela `observations` e não é descartado. `DebentureQueryService.current_values` usa essa view, que é a única definição, para que listagem, ficha e exports mostrem o mesmo valor.
5. **Conflito aberto** vem de `data_conflicts` com `status = 'open'`, por `debenture_id` e `field_name`. Quando há conflito aberto, o valor atual continua sendo entregue, marcado, junto com as duas observações em disputa (valor, fonte, data), para permitir os dois formatos de exibição discutidos em G-04. O contrato não resolve o conflito nem esconde um dos lados.
6. **Proveniência dos identificadores.** Código, ISIN, emissor (razão social) e CNPJ têm fonte e data de observação (a `observed_at` da coleta, não a data do cadastro) quando coletados depois da D-08. Para os ativos ainda não recoletados, o contrato os entrega com `fonte` e `data_observacao` como `ausente` (motivo `nunca_coletado`). Não se usa a data de criação da linha como se fosse data de observação.
7. **Data de observação** é o `observed_at` da nossa coleta. Quando a fonte informar data própria do dado (`valid_from`, `valid_until`), o contrato a entrega em campo separado, sem misturar as duas.

### Listagem e ficha (G-07)

O contrato define o que está disponível. O que o site exibe, a ordem e os filtros padrão continuam sendo decisão de G-07.

- **Resumo na listagem (disponível hoje):** código, ISIN, emissor, CNPJ, status, vencimento, indexador, valor nominal e incentivada, cada campo no envelope acima.
- **Filtros possíveis hoje:** status, indexador, faixa de vencimento, incentivada, resgate antecipado e emissor.
- **Ordenação:** a consulta existente ordena por código; manter como padrão até G-07.
- **Ficha:** todos os campos do catálogo do produto, presentes ou ausentes, mais o histórico de cada campo sob demanda (D-02).
- **Status do ativo (G-06):** o contrato sempre devolve `status` e aceita o filtro `incluir_inativos`. O valor padrão desse filtro depende da decisão G-06.

### Busca (G-08)

`buscar(termo)` devolve os ativos encontrados e, para cada um, `encontrado_em` (`codigo`, `isin`, `emissor` ou `cnpj`).

- A busca por CNPJ não existe hoje e é um acréscimo da implementação.
- Ativos com mais de um identificador (já ocorreu com o ISIN do Café Brasil no CRI/CRA) ficam para o índice da camada compartilhada (Fase 3). O contrato já devolve uma lista de identificadores por ativo, para não precisar mudar depois.

### Somente leitura, de forma verificável

- A conexão é aberta em modo somente leitura (`mode=ro`) com `PRAGMA query_only`, o mesmo padrão do `LegacyDebentureIssuerReader` (ADR-005).
- Só existem consultas `SELECT`.
- O contrato não expõe `raw_records.payload`, `audit_log` nem dados internos da casa.
- Cada consulta tem teste que confirma que nenhuma tabela é alterada.

## Alternativas consideradas

1. **O site lê as tabelas diretamente.** Descartada: acopla o site ao schema de cada módulo, repete a lógica de "valor atual" e permite valor nulo silencioso.
2. **Views `v_site_*` como único contrato.** Podem ser a implementação das consultas, mas uma view não representa o estado `ausente` de campo sem linha, e cada produto teria um formato.
3. **Serviço de leitura em Python com envelope único (esta proposta).** Concentra a regra de valor atual, ausência e conflito em um lugar, reaproveita `DebentureQueryService` e independe do banco de cada frente.

## Consequências positivas

- Todo valor chega ao site com fonte, data, confiança e estado de conflito.
- Ausência é explícita e diferenciada de valor vazio.
- Uma única definição de "valor atual" para listagem, ficha e exports.
- O mesmo envelope serve a debêntures, CRI/CRA, renda fixa e fundos.

## Riscos e limitações

- A view atual não expõe `raw_record_id`, `valid_from` e `valid_until`; incluí-los exige migration, que segue o fluxo de mudança de schema do `CLAUDE.md`.
- Com fonte única (SND), a prioridade nunca é exercida; a diferença entre as duas definições de "valor atual" só aparecerá com a segunda fonte (CVM, ANBIMA ou MANUAL).
- O catálogo de campos esperados precisa de manutenção a cada campo novo.
- CRI/CRA não tem `observations` nem `data_conflicts`; o contrato só vale para o produto quando ele tiver proveniência por valor.
- Dado desatualizado (G-05) não está coberto aqui.

## Fora do escopo

- Implementação das consultas, das views e das migrations.
- Layout e escolhas de exibição: G-01, G-05, G-09 a G-13.
- Decisões de negócio abertas (D-04, G-06, R-01, R-08), registradas em `docs/decisoes-em-aberto.md`.
