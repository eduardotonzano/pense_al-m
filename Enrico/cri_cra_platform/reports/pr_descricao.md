## CRI/CRA: pipeline dos pilotos e base para o mercado inteiro

Branch `enricosuman27-e1-auditoria-informes` → `main`. Escopo restrito a `Enrico/cri_cra_platform/`
(os demais arquivos do diff vieram dos merges da `main`).

### O que entra

**Mercado inteiro no Fundos.NET (04/11/2026)**
- Catálogo de documentos do Fundos.NET para todas as emissões vivas: 2.959 ativos e 206 mil documentos catalogados; 2.887 das
  2.905 emissões da lista do mercado estão no catálogo (99,4%). Busca pelo ISIN/CETIP mesmo quando o nome da securitizadora no
  Fundos.NET é outro (`idAdm=0`), certificado listado só pelo código CETIP, e trava de identidade (mesmo CETIP/ISIN com outro CNPJ
  ou emissão bloqueia em vez de sobrescrever).
- Download dos 663 ativos com sinal de triagem (Termo, aditamentos, fatos relevantes; atas e comunicados desde 2025): 12.605
  documentos. Nos demais, o PDF é apagado depois de extraído o texto (só com hash conferido e todas as páginas com texto; lista em
  `data/arquivos_removidos.csv`).

**Covenants apurados nos relatórios mensais das securitizadoras**
- Opea (API pública): relatório mensal de gestão de 1.926 emissões, 23 mil itens com exigido × apurado × situação × data;
  2.297 itens "não atendido" em 864 emissões. Leitor conferido em 42 relatórios reais.
- Vert (VERT Data), Leverage (portal de emissões), Canal (páginas públicas) e Bari (portal de emissões): 153, 106, 176 e 91 relatórios; a Leverage conferida em
  20 relatórios (79 itens iguais ao PDF) e a Vert em 14 (39 valores iguais ao PDF; data da apuração dos índices nem sempre lida). A Canal publica com meses de atraso (competência de cada item no relatório).
- Eco (páginas públicas): relatório de gestão de 164 emissões e de acompanhamento de 34 (garantias × saldo devedor por classe,
  recebíveis vencidos, aderência ao Termo); marca saldo idêntico entre emissões diferentes (provável cópia de modelo).
- Riza: situação "Default" do portal × Informe da CVM (73 operações em Default, 40 "Adimplente" na CVM).
- `build_covenants_mensais.py`: base única no formato do módulo Covenants (um item por linha, com fonte, documento e SHA-256):
  2.768 CETIPs com valor apurado, 34% do saldo da lista do mercado (Riza e Eco, que somam 46% do saldo, não publicam covenant apurado);
  `build_alertas_por_ativo.py`: sinais por ativo de todas as fontes. Garantias e covenants exigidos no Termo
  (`build_guarantees_covenants.py`, 14 tipos de garantia e 6 covenants com limite).
- Atas, editais e comunicados dos portais (Opea, Eco, Vert, Riza) desde 01/08/2026: 2.107 documentos, 281 por OCR; assunto e decisão por
  regras de texto. Ata de reunião futura é minuta e não conta como decisão; "sustação dos efeitos" não é declaração de vencimento
  antecipado. Triagem para leitura, conferida por amostra de 6 atas.
- `build_cnpj_devedor_cvm.py`: CNPJ do devedor de cada ativo pelo Informe da CVM (1.298 ativos com um único CNPJ; só leitura,
  candidato para a camada compartilhada; CPF não sai). Proposta das regras de exibição S-01..S-11 em
  `reports/proposta_regras_exibicao_securitizados.md`.
- `run_monthly_market.py --portais` coleta os portais; sem a opção a rotina só relê os relatórios já gerados.

**Mercado inteiro (dados abertos da CVM)**
- `ingest_cvm_open_data.py`: Informe Mensal de todos os CRA e CRI (2019 a 2026) num banco separado `data/cvm_open.db`, com valor
  original preservado, SHA-256 por arquivo, recarga idempotente e todas as versões guardadas. Universo: 1.209 emissões de CRA e 3.813 de CRI.
- `run_market_checks.py` e `build_market_universe.py`: triagem do mercado (atraso, vencimento passado com saldo, informe defasado,
  vencimento fora do mês-base, ISIN repetido ou inválido) e ranking de emissões; une a mesma emissão publicada com dois códigos
  (só por ISIN com formato válido: o placeholder "00000" juntava emissões diferentes).
- `validate_cvm_vs_xml.py`: a base da CVM bate com a nossa extração do XML em 96,4% dos valores dos pilotos; a diferença é a rentabilidade
  do CRI, que a CVM publica arredondada.
- Eventos de crédito mês a mês, exposição por devedor (CNPJ validado; não informado, CPF e CNPJ inválido contados à parte) com contágio,
  placar por securitizadora, sinal de séries da mesma classe em atraso e adimplentes, e sinais das DFs dos patrimônios separados
  (ressalva, abstenção, piora, prazo) a partir do índice DFIN da CVM.
- `run_monthly_market.py --dry-run|--commit`: a rotina mensal inteira num comando, até o painel `reports/painel_mercado.html`.
  Relatórios na competência de set/2026.
- Leitor de CSV da CVM robusto a aspa sem fechamento (antes perdia registros sem erro); `ingest_cvm_open_data.py --commit --reparse`
  relê os ZIPs já carregados e regrava só as linhas do arquivo que mudaram.
- Acompanhamento de crédito dos 70 ativos do catálogo em 5 níveis de gravidade (`build_credit_watchlist.py`), com a fonte de cada motivo.

**Lote 1 (29 ativos)**
- Catálogo e download de 1.168 documentos pela fila, texto de 1.148 PDFs e OCR dos 53 em imagem.
- Termo × Informe da CVM em escala (extrator determinístico; 16 de 16 nos parâmetros aprovados dos pilotos).
- Fichas por ativo (`reports/fichas/`) e fichas contratuais (`reports/fichas_contratuais/`): o trecho literal de cada um dos 36 campos
  padrão, com página; nos parâmetros aprovados conferíveis, o valor aparece nas páginas mostradas em 84%.
- Atas: assuntos e o que foi decidido (aprovada, não instalada, suspensa, sem quórum; vencimento antecipado declarado ou não, waiver,
  repactuação, troca de prestador, aporte dos titulares, recuperação judicial ou extrajudicial), com o trecho.

**Lote 2 (38 ativos)**
- `config/ativos_lote2.csv`: 28 da triagem e as 10 emissões da Leverage separadas; 2.701 documentos catalogados, 1.176 baixados,
  texto de 1.198 PDFs e OCR de 43.

**Coleta e documentos**
- Fila de download em lotes (migration `003_download_queue.sql`): retomada, limite de taxa, parada automática (403, falhas seguidas,
  taxa de falha, disco), erros temporários × permanentes e grupos de documentos do mesmo ativo por sessão de navegador.
- Coletor: localiza a securitizadora com nomes parecidos (desempate pelo nome exato) e trata "S/A" como "S.A".
- Download por `source_document_id`, texto por página dos PDFs e OCR opcional para PDF em imagem.

**Informes Mensais (pilotos)**
- Extração por mapeamento versionado (CRA `0.1.1`, CRI `cri-0.1.1`), golden sets, versão vigente, comparação entre períodos e
  alertas de qualidade de dado.

**Termos, fatos e alertas contratuais**
- Parâmetros com âncora literal e vigência; fatos com trecho literal conferido; página HTML de revisão.
- Catálogo de 36 campos contratuais padrão, cobertura por ativo, localizador de cláusulas (recall de 89% nos parâmetros aprovados) e
  comparação do mesmo dado entre documentos (Termo, oferta, AF, DFs e Informe), inclusive texto curto.
- Alertas contratuais só com parâmetros e fatos aprovados; regra pendente "cadastro do Informe × Termo".
- Fila de revisão priorizada em 5 níveis.

**Esquema**
- Migrations `002_asset_series.sql` e `003_download_queue.sql`, aplicadas no banco local com backup e verificação.

### Como verificar
```powershell
cd Enrico\cri_cra_platform
$env:PYTHONPATH='..\..\src'; python -m pytest                       # 490 testes
python scripts/apply_migration.py --database data\cri_cra.db --dry-run
python scripts/ingest_cvm_open_data.py --dry-run                     # lista os 16 arquivos da CVM, não grava
python scripts/run_monthly_market.py --dry-run                       # rotina mensal sem gravar no banco
python scripts/collect_vert_reports.py --dry-run                     # portais: contam emissões sem baixar
```

### Riscos e pontos de atenção
- **Tamanho do diff:** a maior parte são relatórios gerados em `reports/`. Nenhum banco, documento baixado ou backup está versionado.
- **Dado da CVM = dado do Informe:** erros de preenchimento vêm junto (ex.: vencimentos do Alibem). A triagem aponta candidatos, não conclusões.
- **Dados interpretados:** valores de tabelas desalinhadas ou OCR têm nota e conferência visual; os incertos estão pendentes e não alimentam alertas.
- **Regras pendentes** (contratuais do Alibem e do CRI, cadastro do Informe × Termo) só rodam com `--preview`.
- **Regras de texto** (Termo × CVM, fichas contratuais, decisões de atas) são triagem com trecho e página; nada vira parâmetro aprovado
  sem revisão humana. Pesos do ranking ainda provisórios.
- **Sites das securitizadoras** são a fonte de menor prioridade: complementam a CVM e nunca a corrigem; nada disso é gravado no banco.
  A situação (atendido/não atendido) é a que a securitizadora informa, sem dedução. Os portais podem mudar de formato sem aviso.

### Fora do escopo
Interface e layout, até o levantamento de requisitos da equipe (ADR-001).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
