# ADR-005: Integração gradual de emissores de Debêntures

## Status

Aceita para implementação inicial.

## Contexto

A Shared Entity Layer possui:

- entidades universais;
- identificadores normalizados;
- proveniência;
- matching conservador;
- repositórios em memória;
- persistência SQLite.

Os módulos legados devem ser integrados gradualmente, sem reescrita imediata e sem dependência direta da camada compartilhada sobre suas classes internas.

O primeiro domínio escolhido foi o cadastro de emissores do módulo de Debêntures.

## Decisão

Criar uma camada intermediária de integração contendo:

- DebentureIssuerRecord;
- DebentureIssuerAdapter;
- DebentureIssuerImportService;
- EntityImportResult;
- EntityImportAction.

O módulo legado não será modificado nesta fase.

## Registro intermediário

O DebentureIssuerRecord representa os dados necessários do emissor:

- identificador legado;
- razão social;
- nome comercial;
- CNPJ;
- data de criação;
- data de atualização.

Essa estrutura impede que a Shared Entity Layer dependa diretamente da classe IssuerRecord do módulo de Debêntures.

## Conversão

O DebentureIssuerAdapter converte o registro intermediário em Entity.

O mapeamento utiliza:

- razão social como legal_name;
- nome comercial como trade_name;
- CNPJ como identificador primário;
- tipo COMPANY;
- país BR;
- origem SPECIALIZED;
- referência legada no formato issuer:{legacy_id}.

## Identidade determinística

O UUID da entidade é calculado de maneira determinística a partir do identificador legado.

Importações repetidas do mesmo legacy_id produzem o mesmo entity_id.

## Datas legadas

Timestamps SQLite sem timezone são interpretados como UTC.

Timestamps com timezone são convertidos para UTC.

Datas de atualização anteriores às datas de criação são rejeitadas.

## Matching

O serviço de importação adota comportamento conservador:

- mesmo CNPJ gera correspondência automática;
- mesmo nome sem identificador compartilhado exige revisão;
- conflito de identificador bloqueia a importação;
- ausência de evidência cria uma nova entidade.

## Atualização de dados

Uma correspondência automática não sobrescreve imediatamente a entidade existente.

A atualização automática exigirá regras futuras de precedência e confiança entre fontes.

## CNPJ opcional

Emissores sem CNPJ podem ser convertidos.

Esses registros não são unidos automaticamente apenas pelo nome.

Coincidências por nome são direcionadas para revisão.

## Compatibilidade

O serviço depende do contrato EntityRepository.

A implementação pode utilizar:

- InMemoryEntityRepository;
- SQLiteEntityRepository;
- outra implementação compatível.

## Consequências positivas

- primeira integração real com módulo legado;
- ausência de alteração destrutiva no módulo de Debêntures;
- desacoplamento entre os modelos;
- importações auditáveis;
- matching conservador;
- comportamento idempotente;
- base reutilizável para outros módulos.

## Leitura do banco legado

O banco legado e acessado por caminho explicito.

O LegacyDebentureIssuerReader:

- valida a existencia do arquivo;
- ativa PRAGMA query_only;
- le a tabela issuers;
- pagina os registros por ID;
- preserva uma ordem deterministica;
- converte cada linha em DebentureIssuerRecord;
- nao altera o banco de origem.

## Importacao em lote

O DebentureIssuerBatchImportService conecta:

- LegacyDebentureIssuerReader;
- DebentureIssuerImportService;
- EntityRepository;
- BatchImportReport.

O processamento continua apos erros individuais.

Cada registro e classificado como:

- CREATED;
- MATCHED;
- REVIEW;
- BLOCKED;
- ERROR.

## Modo de simulacao

O modo dry-run copia o estado atual do repositorio para um InMemoryEntityRepository temporario.

A simulacao:

- nao grava entidades no repositorio real;
- considera correspondencias entre registros do proprio lote;
- produz os mesmos contadores operacionais;
- permite validar o processo antes da persistencia.

## Relatorio agregado

O BatchImportReport registra:

- total lido;
- entidades criadas;
- correspondencias;
- registros para revisao;
- registros bloqueados;
- erros;
- indicacao de dry-run.

O relatorio exige que a soma dos resultados seja igual ao total lido.

## Detalhes de erros

Cada erro e representado por BatchImportError, contendo:

- legacy_id;
- tipo da excecao;
- mensagem normalizada.

A quantidade de detalhes deve ser igual ao contador de erros.

## Entrada operacional

A integracao pode ser executada como modulo Python.

Exemplo:

    python -m pense_alm.shared.integration.cli
        --legacy-db "<banco-legado>"
        --target-db "<banco-destino>"
        --batch-size 100
        --dry-run

A CLI exige caminhos explicitos e rejeita:

- banco legado inexistente;
- tamanho de lote menor ou igual a zero;
- uso do mesmo arquivo como origem e destino.

## Codigos de saida

A entrada operacional utiliza:

- 0 para execucao sem pendencias;
- 2 para erros durante o processamento;
- 3 para registros bloqueados;
- 4 para registros que exigem revisao.

Erros de argumentos tambem utilizam o codigo 2 do argparse.

## Validacao operacional

O fluxo foi validado com um backup real contendo tres emissores.

Foram confirmados:

- leitura dos tres registros;
- dry-run com zero entidades persistidas;
- primeira execucao com tres entidades criadas;
- segunda execucao com tres correspondencias;
- ausencia de duplicidades;
- tres CNPJs unicos;
- persistencia apos reabertura do SQLite;
- ausencia de alteracao no banco legado.

A validacao automatizada tambem cobre:

- criacao de entidades;
- correspondencia por CNPJ;
- revisao por nome sem identificador compartilhado;
- bloqueio por conflito de CNPJ;
- erro individual sem interrupcao do lote;
- codigos operacionais 0, 2, 3 e 4.

## Limitacoes atuais

Nesta versao:

- a fila de revisao ainda nao e persistente;
- registros bloqueados nao sao armazenados em fila propria;
- entidades existentes nao sao atualizadas automaticamente;
- nao existem regras de precedencia entre fontes;
- Debentures ainda nao sao integradas como ativos;
- somente emissores sao importados;
- a CLI ainda nao esta registrada como comando instalavel;
- os caminhos dos bancos devem ser informados explicitamente.

## Consequencias positivas adicionais

- execucao operacional controlada;
- validacao antes da gravacao;
- continuidade apos erros individuais;
- erros auditaveis por registro;
- reexecucao idempotente;
- compatibilidade com repositorios em memoria e SQLite;
- protecao contra alteracao do banco legado;
- base reutilizavel para outros modulos.

## Fora do escopo

- alteracoes no modulo legado;
- migracao destrutiva do banco de Debentures;
- integracao de Debentures como ativos;
- CRI e CRA;
- FIDC;
- FIAGRO;
- coletores compartilhados;
- fila persistente de revisao;
- interface e layout.
