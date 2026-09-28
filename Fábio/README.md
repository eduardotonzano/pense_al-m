# Pense Além — Notas do Fábio (T.I. / Integração)

## Propósito deste documento

Este README é o **contrato de integração** do projeto. Cada frente (Eduardo, Enrico, Gui) constrói seu banco de dados de forma independente; este documento registra, com detalhe técnico real (schema, classes, caminhos de arquivo, comandos), o que cada uma expõe hoje e o que já foi de fato integrado ao galpão central — pra que seja possível (inclusive por um agente de IA que nunca viu o projeto) ler isso e saber exatamente o que já existe, o que falta e como continuar, sem precisar reconstruir esse entendimento do zero lendo código espalhado em várias pastas.

**Aviso pra quem for usar isso no futuro (humano ou agente):** este documento é um retrato do repositório em **28/09/2026**. Código muda mais rápido que documentação — antes de agir sobre qualquer caminho de arquivo, nome de classe, schema ou comando citado aqui, confirme contra o código atual (`git log`, abrir o arquivo). Trate este README como mapa de onde procurar e histórico de decisões, não como fonte definitiva do estado presente.

Meu papel no projeto: **T.I., responsável por juntar as 3 frentes de ativos no sistema principal.** Não sou dono de nenhuma fábrica de dados — meu trabalho é a integração (passo 3 do escopo original: "Junção dos códigos").

Mapa visual (diagramas, fluxogramas — pode estar um passo atrás deste README): **https://claude.ai/artifact/TGPGhZVeUKBsPZoZ95yq1C**

Repositório: `github.com/eduardotonzano/pense_al-m` · branch principal `main`. A branch `feature/shared-entity-layer` **já foi mesclada** na main (PR #2, 22/09/2026) — o galpão não vive mais isolado numa branch separada, o código está em `src/pense_alm/shared/` na raiz do repositório.

---

## 1. O que é o Pense Além

**Dor:** a equipe não consegue acompanhar os ativos direito porque não existe uma base de dados sólida e consolidada. Validado pelo padrinho do projeto, Gustavo Vilela.

**Solução:** uma plataforma única, de fácil acesso pra toda a equipe, com uma base consolidada e alertas de variações anormais de preço e notícias relevantes.

**Plano original em 3 passos:**
1. Listagem dos ativos — cada pessoa cobrindo uma classe
2. Confecção das APIs
3. **Junção dos códigos** — minha parte, e onde o galpão (Shared Entity Layer) entra

**Quem cobre o quê:**
| Pessoa | Classe de ativo | Maior dor a resolver |
|---|---|---|
| Enrico | Securitizados (CRI/CRA) | Análise de garantia, covenants, histórico de documentos |
| Eduardo | Debêntures/Bonds | Buscar informação por empresa, PU real x PU par |
| (a definir) | Produtos Bancários/Renda Fixa | Taxa + calculadora de marcação a mercado |
| Gui | Fundos (FIAGRO/FIDC) | Casa x mercado |

---

## 2. Status de cada frente (checado em 28/09/2026)

### Eduardo — Debêntures 🟢 madura + já integrada parcialmente ao galpão
- Banco SQLite próprio, com histórico, auditoria e controle de qualidade
- 417 testes automatizados aprovados na versão "congelada" (`debenture-replica/docs/FREEZE.md`)
- Dado real no banco: 3 emissores, 3 debêntures (Petrobras/PETR27, Sabesp/SBSPC9, Celpe/CEPEA1), 38 observações — fonte principal: **SND** (Sistema Nacional de Debêntures)
- **Novidade:** os 3 emissores já foram importados com sucesso pro galpão via a camada de integração (ver seção 5) — validado com dado real, de forma idempotente
- Falta: ligar fontes oficiais adicionais (CVM, ANBIMA), criar a interface visual (pausada de propósito), e integrar a **debênture em si** (o instrumento, não só o emissor) ao galpão

### Enrico — CRI/CRA 🟡 avançando, endpoint real validado
- Consegue acessar o Fundos.NET automaticamente (Playwright, headless validado em 16/09)
- **Novidade (22/09):** encontrou e validou a URL oficial de download de documentos (`fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id=...`) — baixou um XML real com sucesso (HTTP 200, hash SHA-256 conferido)
- **Novidade:** catalogou **124 documentos reais** do ativo piloto (CRA022009VM, "Café Brasil"), com inventário datado de 01/08/2025 a 31/12/2025
- **Achado de qualidade de dado, relevante pro galpão:** o mesmo ISIN aparece associado a dois `asset_id` diferentes no banco dele (`asset_id=1` e `asset_id=6`) — um problema que o matching por identificador do galpão vai ajudar a destravar quando a integração acontecer
- Falta: baixar o lote completo de documentos (hoje é 1 documento validado manualmente, pendente rodar em escala) e persistir tudo isso no banco de produção — ainda **não há dado real persistido no banco principal**, só nos relatórios de diagnóstico

### Gui — Fundos/FIAGRO 🔴 não existe
- Nenhum arquivo, pasta ou commit encontrado no repositório

### Eu (Fábio) 🔴 ainda sem código commitado
- Só existe `debenture_db_base64.txt` nesta pasta — cópia em base64 do banco do Eduardo (retrato de 11/09)

---

## 3. Contrato técnico de cada fonte de dados

> Esta seção é o que um agente de integração precisa ler antes de escrever qualquer adaptador novo.

### 3.1 Eduardo — `debenture-replica` (versão congelada, raiz do repo) / `Eduardo/debenture-replica` (versão de trabalho)

**Banco:** SQLite, caminho padrão `data/debenture.db` (definido em `src/debenture_search/database.py`, constante `DEFAULT_DATABASE_PATH`). Backups versionados em `Eduardo/debenture-replica/data/backups/*.sqlite3` (o mais recente commitado é de 14/09).

**Schema** (`migrations/001_initial_schema.sql`):

| Tabela | Campos principais | Observação |
|---|---|---|
| `issuers` | `id`, `cnpj` (único, 14 dígitos), `legal_name`, `trade_name`, `created_at`, `updated_at` | **Já tem adaptador pro galpão — ver seção 5** |
| `debentures` | `id`, `issuer_id` → FK `issuers`, `asset_code` (único), `isin` (único, 12 chars), `issue_number`, `series`, `status` | Fica no domínio de Eduardo — ainda não vira `Entity` nem nada no galpão |
| `sources` | `id`, `code`, `name`, `source_type`, `priority`, `active` | Hoje: `SND` (prio 100), `CVM` (prio 200), `ANBIMA_API` (prio 300, inativa), `MANUAL` (prio 1000) |
| `collection_runs` | `id`, `source_id`, `started_at`, `finished_at`, `status`, contadores de sucesso/falha | Log de cada execução de coleta |
| `raw_records` | `id`, `source_id`, `payload` (BLOB), `payload_sha256`, `http_status`, `processing_status` | Resposta bruta antes do parsing |
| `observations` | `id`, `debenture_id`, `source_id`, `field_name`, `value_type`, `value_text/numeric/date/boolean`, `observed_at`, `confidence`, `checksum` (único) | Um registro por campo por coleta — histórico completo, nunca sobrescreve |
| `data_conflicts` | `debenture_id`, `field_name`, `observation_a_id`, `observation_b_id`, `status` | Divergência entre fontes, sem apagar nenhuma |
| `audit_log` | `actor`, `action`, `entity_type`, `entity_id`, `before_data`, `after_data`, `reason` | Toda alteração manual |
| `current_observations` (view) | — | Valor consolidado atual por campo, respeitando prioridade de fonte |

**API disponível** (`src/debenture_search/repositories/`):
- `IssuerRepository` — `create()`, `get_or_create()`, `get_by_id()`, `get_by_cnpj()`, `search_by_name()`, `list_all()`, `count()`, `update()`
- `DebentureRepository` — `create()`, `get_or_create()`, `get_by_id()`, `get_by_asset_code()`, `get_by_isin()`, `list_by_issuer()`, `search()`, `update_identification()`, `update_status()`

**Como o galpão lê isso hoje:** não é via `IssuerRepository` diretamente — a integração lê o **arquivo SQLite bruto**, somente leitura (`PRAGMA query_only`), via `LegacyDebentureIssuerReader` (ver seção 5). Não modifica o banco original.

**Debêntures (o instrumento) ainda não têm nenhum caminho de integração** — só o cadastro do emissor foi conectado até agora.

---

### 3.2 Enrico — `Enrico/cri_cra_platform` (mesma base de `coletor_cri_cra`)

**Banco:** SQLite, conexão via `src/credit_assets/database/connection.py` (`connect(database_path)`), schema em `schema.sql` no mesmo diretório.

**Modelos** (`src/credit_assets/models/`):

`Asset` (`asset.py`):
```
codigo_cetip: str
tipo_ativo: str
securitizadora: str
cnpj_securitizadora: str   ← candidato a Entity (tipo SECURITIZER)
emissao: str
serie: str
devedor: str = ""          ← candidato a Entity (tipo COMPANY), se preenchido
cnpj_devedor: str = ""     ← candidato a Entity, se preenchido
isin: str = ""
asset_id: Optional[int] = None
```

`Document` (`document.py`):
```
asset_id: int
source_document_id: str
category: str   # Termo de Securitização, Aditamento, Informe Mensal, Ata/Edital,
                 # Fato Relevante, Relatório Agente Fiduciário, Relatório de Rating,
                 # Anúncio de Encerramento, Outro
document_name: str
source: str
source_url: str
reference_date / publication_date: Optional[str]
file_hash: Optional[str]
download_status: str = "pending"
```

**API disponível** (`src/credit_assets/repositories/`):
- `AssetRepository.upsert(asset: Asset) -> int`
- `DocumentRepository.upsert()`, `upsert_with_status()`, `find_by_source_document()`, `find_by_hash()`, `list_by_asset_id()`, `list_by_cetip()`, `export_csv()`

**Endpoint de download real, validado em 22/09:**
```
https://fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id=<id do documento>
```
Mecanismo: `event_download` via Playwright, reproduzindo a ação oficial de "Download do Documento" na grade do Fundos.NET. Retorna o arquivo (testado com XML, HTTP 200) com `Content-Disposition` trazendo o nome oficial do arquivo.

**Ponto de entrada pra integração, quando houver dado real persistido:** cada `Asset` tem **dois** participantes em potencial (`securitizadora` e `devedor`), cada um com seu próprio CNPJ — a integração vai precisar gerar até 2 registros de `Entity` por ativo (mesmo padrão do adaptador de emissores do Eduardo, só que com 2 candidatos por linha em vez de 1).

**Gap conhecido:** ainda não existe nenhum adaptador Enrico → galpão (só existe pra Eduardo). Além disso, o banco de produção do Enrico ainda não tem os 124 documentos catalogados persistidos — eles estão descritos em relatórios (`reports/cafe_brasil_document_inventory.md`), não no SQLite.

---

### 3.3 Gui — Fundos/FIAGRO

Nada existe ainda. Quando essa frente começar, o padrão esperado (a confirmar com o Gui) é: gestora e fundo entram como `Entity` (tipos `ASSET_MANAGER` e `FUND`/`FIDC`/`FIAGRO`), cotas e histórico do fundo ficam no banco próprio dessa frente — mesmo padrão de Eduardo e Enrico.

---

## 4. O Galpão — Shared Entity Layer, em detalhe técnico

**Localização:** `src/pense_alm/shared/` na raiz do repositório (**mesclado na `main` em 22/09/2026**, PR #2). Documentação própria: `docs/architecture/ADR-001-shared-entity-layer.md`.

### 4.1 Vocabulário controlado (`entities/enums.py`)

```
EntityType:       bank, company, holding, financial_institution, cooperative,
                   asset_manager, fund, fidc, fiagro, securitizer,
                   government, other

EntityStatus:      active, inactive, suspended, under_intervention,
                   in_liquidation, unknown

IdentifierType:    cnpj, bacen_code, cvm_code, anbima_code, lei, internal, other

SourceType:        bacen, cvm, anbima, specialized, institutional, manual
                   (nessa ordem de prioridade — bacen é o mais confiável)

ValidationStatus:  pending, valid, invalid, conflict

MatchStrength:     none, weak, moderate, strong, conflict

MatchDecision:     no_match, review, auto_match, blocked

RelationshipType:  controls, controlled_by, belongs_to_group, manages,
                   administered_by, issues, originates, securitizes,
                   assigns_receivables_to, guarantees, distributes,
                   provides_services_to, succeeds, predecessor_of, other

RelationshipStatus: active, inactive, pending_review, disputed, unknown
```

**Mapeamento usado hoje pra origem → `SourceType`:** SND → `specialized` (é o mapeamento real usado pelo adaptador de emissores — ver seção 5). Sugestão pras próximas fontes: Fundos.NET → `specialized`; CVM → `cvm`; BACEN → `bacen`; ANBIMA → `anbima`; entrada manual → `manual`.

### 4.2 Modelo `Entity` (`entities/models.py`)

```
entity_id: UUID (gerado automaticamente, ou deterministicamente — ver seção 5)
legal_name: str (obrigatório, normalizado)
entity_type: EntityType
provenance: DataProvenance
trade_name: str | None
status: EntityStatus = UNKNOWN
identifiers: tuple[EntityIdentifier, ...]
country_code: str = "BR"
sector / subsector: str | None
website: str | None
created_at / updated_at: datetime
```
Imutável (`frozen=True`) — qualquer alteração gera uma nova instância, nunca edita em lugar.

### 4.3 `EntityIdentifier` (`entities/identifiers.py`)
```
identifier_type: IdentifierType
value: str (normalizado — CNPJ vira 14 dígitos sem formatação)
provenance: DataProvenance
is_primary: bool = False
```

### 4.4 Contrato de persistência (`entities/repository_protocols.py`)

`EntityRepository` (Protocol):
- `save(entity: Entity) -> Entity`
- `get_by_id(entity_id: UUID) -> Entity | None`
- `get_by_identifier(identifier_type: IdentifierType, value: str) -> Entity | None` ← **método-chave pra integração: buscar por CNPJ antes de criar**
- `list_all(entity_type: EntityType | None = None) -> tuple[Entity, ...]`
- `exists(entity_id: UUID) -> bool`
- `count(entity_type: EntityType | None = None) -> int`

`RelationshipRepository` (Protocol):
- `save()`, `get_by_id()`, `get_by_canonical_key()`, `list_by_source()`, `list_by_target()`, `list_active_at(reference_datetime, relationship_type=None)`, `count()`

**Implementação real disponível:** `persistence/sqlite_entity_repository.py` → `SQLiteEntityRepository`, e `persistence/sqlite_relationship_repository.py`. Usadas de verdade pela CLI de importação (seção 5). Testes em `tests/shared/persistence/`.

### 4.5 Matching (`entities/matching.py`)
`EntityMatcher` compara dois registros e retorna uma `MatchDecision`:
- **CNPJ idêntico** → `AUTO_MATCH`
- **CNPJ diferente pro mesmo nome** → `BLOCKED`
- **Só o nome bate, sem CNPJ** → `REVIEW` (exige decisão humana)
- **Sem evidência** → `NO_MATCH`

Regra central do projeto: **uma coincidência de nome nunca é suficiente pra fundir entidades automaticamente.**

### 4.6 Novidade (28/09): contratos de coleta compartilhada (`shared/collection/`)

Trabalho iniciado no mesmo dia, ainda sem consumidores (nenhum adaptador usa isso ainda). São os tipos comuns pra qualquer módulo registrar uma coleta de dado externo:
- `CollectionSource`, `CollectionSourceType` (enum)
- `CollectionRequest`, `CollectedResponse`
- `CollectionRun`, `CollectionRunStatus` (enum)
- `RawCollectionRecord`, `RawRecordStatus` (enum)
- `CollectionError`

Isso é o embrião da etapa 12 do roadmap ("coletores compartilhados" — BACEN, CVM, ANBIMA). Ainda não integrado a nada — vale acompanhar como evolui, porque pode acabar padronizando como o Enrico e o Eduardo registram suas próprias coletas também.

---

## 5. A integração Eduardo → Galpão, já construída (ADR-005)

**Isto não é mais o desenho de referência — já foi implementado, testado e validado com dado real** entre 22 e 25/09/2026. Documentação completa: `docs/architecture/ADR-005-debenture-issuer-integration.md`. Código em `src/pense_alm/shared/integration/`.

### 5.1 Peças da camada intermediária

| Classe/arquivo | Papel |
|---|---|
| `DebentureIssuerRecord` (`records.py`) | Registro neutro do emissor (legacy_id, legal_name, trade_name, cnpj, created_at, updated_at) — impede que o galpão dependa da classe `IssuerRecord` do módulo legado |
| `LegacyDebentureIssuerReader` (`legacy_issuer_reader.py`) | Lê o SQLite do Eduardo em modo **somente leitura** (`PRAGMA query_only`), pagina por ID, nunca altera o banco de origem |
| `DebentureIssuerAdapter` (`debenture_issuer_adapter.py`) | Converte `DebentureIssuerRecord` em `Entity`: `legal_name` → `legal_name`, `trade_name` → `trade_name`, CNPJ → identificador primário, tipo `COMPANY`, país `BR`, origem `SPECIALIZED`, referência legada `issuer:{legacy_id}` |
| `DebentureIssuerImportService` (`debenture_issuer_import_service.py`) | Aplica o `EntityMatcher` e decide `CREATED` / `MATCHED` / `REVIEW` / `BLOCKED` pra um registro |
| `DebentureIssuerBatchImportService` (`debenture_issuer_batch_import_service.py`) | Orquestra a leitura em lote + importação + relatório agregado; suporta `dry_run` |
| `EntityImportResult` / `EntityImportAction` (`import_result.py`) | Resultado auditável de uma importação individual |
| `BatchImportReport` / `BatchImportError` | Relatório agregado do lote — `total_read`, `created`, `matched`, `review`, `blocked`, `errors`, `error_details` |
| `cli.py` | Entrada operacional via linha de comando |

### 5.2 Identidade determinística (resolve o "gap" que a gente discutia antes)

**Não existe uma coluna `entity_id` no banco do Eduardo, e não vai precisar existir.** O `entity_id` no galpão é calculado deterministicamente a partir do `legacy_id` do emissor — ou seja, rodar a importação de novo sempre gera o **mesmo** UUID pro mesmo emissor, sem precisar gravar nada de volta no banco original. É por isso que a segunda execução reconhece os registros como `MATCHED` em vez de criar duplicata.

### 5.3 Como rodar

```powershell
python -m pense_alm.shared.integration.cli `
    --legacy-db "<caminho do banco do Eduardo>" `
    --target-db "<caminho do banco do galpão>" `
    --batch-size 100 `
    --dry-run
```

Tirando `--dry-run`, o comando persiste de verdade. Códigos de saída: `0` sem pendências, `2` erros de processamento, `3` registros bloqueados, `4` registros pendentes de revisão (erros de argumento do `argparse` também usam `2`).

### 5.4 Validação já feita (com o backup real de 3 emissores)

- Leitura dos 3 registros confirmada
- Dry-run: 0 entidades persistidas (simulação correta)
- 1ª execução real: 3 entidades criadas
- 2ª execução (idempotência): 3 correspondências (`MATCHED`), zero duplicidade, 3 CNPJs únicos
- Persistência confirmada após reabrir o SQLite
- Banco legado do Eduardo confirmado como inalterado
- Testes automatizados cobrem: criação, correspondência por CNPJ, revisão por nome sem identificador, bloqueio por conflito de CNPJ, erro individual sem travar o lote inteiro, e os 4 códigos de saída

### 5.5 Limitações atuais (documentadas pelo próprio Eduardo no ADR-005)

- Entidades já existentes **não são atualizadas automaticamente** num `MATCHED` — só a criação é automática; atualização exige regras futuras de precedência entre fontes
- A fila de `REVIEW` **não é persistente** — hoje é só o resultado do relatório, não fica guardada em lugar nenhum pra alguém aprovar depois
- Registros `BLOCKED` também não vão pra fila própria
- **Debêntures (o instrumento) ainda não são integradas** — só o cadastro do emissor
- CRI/CRA, FIDC, FIAGRO: nenhum adaptador ainda
- A CLI não está registrada como comando instalável (roda só via `python -m`)
- Os caminhos dos bancos são sempre explícitos — sem descoberta automática

---

## 6. Checklist de integração (atualizado)

- [x] ~~Confirmar que a branch `feature/shared-entity-layer` foi revisada e mesclada na `main`~~ — feito, 22/09
- [x] ~~Escrever o adaptador Eduardo → galpão~~ — feito e validado com dado real (seção 5)
- [x] ~~Resolver como o banco de origem referencia o galpão~~ — resolvido via UUID determinístico, não precisa de migration no banco legado
- [ ] Persistir os 124 documentos do Enrico no banco de produção (hoje só em relatório de diagnóstico)
- [ ] Escrever o adaptador Enrico → galpão (2 entidades por `Asset`: securitizadora e devedor)
- [ ] Decidir e construir a fila persistente de revisão pros casos `REVIEW` (hoje não existe)
- [ ] Decidir a regra de atualização automática de entidades já `MATCHED` (precedência entre fontes)
- [ ] Integrar a debênture em si (o instrumento) ao galpão, não só o emissor
- [ ] Investigar e corrigir a duplicidade de ISIN no banco do Enrico (asset_id=1 vs asset_id=6) antes de migrar
- [ ] Registrar a CLI de integração como comando instalável
- [ ] Construir a camada de busca federada (fluxograma 2 do mapa visual) — ainda não existe

---

## 7. Perguntas em aberto pra levar ao Eduardo e ao Enrico

- Quem vai definir a regra de precedência entre fontes pra permitir atualização automática de entidades já `MATCHED`?
- Onde a fila de revisão (`REVIEW`) deveria morar — banco, planilha, ferramenta própria?
- Enrico: quando o lote completo de 124 documentos vai ser baixado e persistido no banco principal?
- O que fazer com o ISIN duplicado entre `asset_id=1` e `asset_id=6` — é erro de cadastro ou os dois são legítimos (ex.: ativo reemitido)?
- Quando o adaptador Enrico → galpão deveria começar a ser escrito — já agora com os dados de diagnóstico, ou só depois do banco de produção estar populado?
- Existe alguém definido pra Renda Fixa/Produtos Bancários? Ninguém apareceu no repositório ainda.
- O Gui já tem previsão de começar a frente de Fundos/FIAGRO?
- O `shared/collection` (novo, 28/09) vai virar o padrão pra todo mundo registrar coleta, ou é específico de algum módulo?

---

## 8. Como estou trabalhando nisso

- Ferramenta de implementação permitida no projeto: **GitHub Copilot Chat**
- Uso o Claude (aqui) pra: entender o código existente, tirar dúvida de arquitetura, planejar a integração e gerar material de orientação (como este README e o mapa do galpão) — não pra escrever código de produção diretamente no projeto

---

*Última atualização: 28/09/2026, com base no estado do repositório `pense_al-m` nesse mesmo dia (357 arquivos versionados; commits mais recentes do Eduardo e do Enrico entre 22 e 28/09).*
