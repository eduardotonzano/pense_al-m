# ADR-011: CNPJ alfanumérico na camada compartilhada

## Status

Proposta, até o Fábio aprovar no pull request. A decisão de aceitar o CNPJ alfanumérico é do Fábio, dono da camada compartilhada, de 05/11/2026.

## Contexto

- A IN RFB 2.229/2024 criou o CNPJ alfanumérico, e a Receita começou a emitir em 31/07/2026. Os dois formatos convivem, e os CNPJs numéricos existentes não mudam.
- Até aqui a camada só aceitava dígitos. O `normalize_cnpj` apagava tudo que não fosse dígito, e o `DebentureIssuerRecord` (`integration/records.py`) tinha uma segunda cópia da regra. Nenhum dos dois validava o dígito verificador.
- O CNPJ é o identificador forte (regra 6 do `CLAUDE.md`): nunca se casa por nome. A entidade com CNPJ alfanumérico que não entra na camada é justamente a que quebra esse casamento.

## Decisão

1. **A regra canônica mora na camada compartilhada**, em `normalize_cnpj` (`src/pense_alm/shared/entities/identifiers.py`):
   - remove só ponto, barra e hífen (em qualquer posição) e põe em maiúsculas;
   - exige 14 caracteres ASCII: os 12 primeiros em [0-9A-Z] e os 2 últimos numéricos;
   - recusa sequência de caracteres iguais;
   - valida os 2 dígitos verificadores pelo cálculo da IN: cada caractere vale `ord(c) - 48`; pesos `(5,4,3,2,9,8,7,6,5,4,3,2)` para o primeiro e `(6,5,4,3,2,9,8,7,6,5,4,3,2)` para o segundo, que inclui o primeiro; resto menor que 2 vira 0, senão 11 menos o resto. Para CNPJ só numérico, o resultado é o do cálculo clássico;
   - nunca completa zeros à esquerda (11 dígitos pode ser CPF);
   - levanta `IdentifierValidationError`, e a mensagem nunca repete o valor recebido.
2. **Uma regra só na camada.** O `records.py` chama `normalize_cnpj` em vez de ter a sua cópia.
3. **O Fundos mantém o utilitário próprio** (`Gui/fundos/src/fundos/cnpj.py`), porque não depende da camada (`dependencies = []` no `pyproject.toml` dele). Nenhum dos dois importa o outro. Formato e cálculo do DV são os mesmos. A única diferença é a máscara: a camada remove ponto, barra e hífen em qualquer posição e aceita a máscara parcial (`12.ABC.34501DE-35`); o Fundos só aceita o CNPJ sem máscara ou com a máscara completa.
4. **A paridade é garantida pelos mesmos vetores de teste.** Os testes da camada (`tests/shared/cnpj_amostras.py`) usam as mesmas raízes fictícias dos testes do Fundos (`9999999n9999` e `ZZZZZZZnZZZZ`) e o exemplo da Receita `12.ABC.345/01DE-35`, com DV 35. O DV dos testes é calculado de forma independente do código de produção.
5. **Unificar os dois utilitários** é decisão futura do Fábio e do Gui.

## Consequências

- **Fixtures trocadas.** Os CNPJs dos testes da camada tinham dígito verificador inválido e foram trocados por CNPJs fictícios válidos.
- **Busca com CNPJ inválido.** `get_by_identifier` normaliza o valor procurado. Com DV inválido, passa a levantar `IdentifierValidationError` em vez de devolver `None` (com tamanho errado, já era assim).
- **Dados já gravados.** O `SQLiteEntityRepository` revalida o identificador ao carregar. Uma entidade gravada antes desta regra com DV inválido deixaria de carregar. Não é preciso migration (`entity_identifiers.value` é `TEXT` sem CHECK), mas um banco existente precisa ser conferido antes de ser reutilizado.
- **Correção do import em lote,** consequência direta da validação do DV. O `DebentureIssuerRecord` era montado dentro de `LegacyDebentureIssuerReader.iter_records`, fora do `try` do `DebentureIssuerBatchImportService`, então um CNPJ recusado abortava o lote inteiro.
  - Agora o lote lê as linhas com `iter_rows` e monta o registro com `to_record` dentro do `try`. O CNPJ inválido vira `BatchImportError` daquele `legacy_id`, o relatório o conta e os demais registros seguem. O dry-run se comporta igual.
  - `iter_records` mantém a assinatura e o comportamento.
- **Debêntures adotaram a regra**, em dois pull requests à parte:
  - feito (PR #36): o CHECK de `issuers.cnpj` (`length(cnpj)=14 AND cnpj NOT GLOB '*[^0-9]*'`, em `Eduardo/debenture-replica/migrations/001_initial_schema.sql`) foi aberto pela migration `003_issuers_cnpj_alfanumerico.sql`: 12 caracteres em [0-9A-Z] e 2 dígitos. O DV não é conferido no banco;
  - feito (pull request do código): `IssuerRepository.normalize_cnpj`, em `Eduardo/debenture-replica/src/debenture_search/repositories/issuer_repository.py`, valida formato e DV e levanta `ValueError`;
  - feito (pull request do código): `SndParser.normalize_cnpj`, em `Eduardo/debenture-replica/src/debenture_search/parsers/snd_parser.py`, devolvia "sem CNPJ" (`None`) quando não havia 14 dígitos. Agora devolve o CNPJ no formato 12 + 2 sem conferir o DV; com DV inválido, o repositório recusa e aquele documento falha no lote, sem parar os outros;
  - como o Fundos, as debêntures têm utilitário próprio (`Eduardo/debenture-replica/src/debenture_search/cnpj.py`), porque o pacote não depende da camada. A regra e os vetores de teste são os mesmos;
  - a migration 003 precisa estar aplicada no banco antes do código.
- **CRI/CRA precisa adotar a regra** quando integrar com a camada.

## Fora do escopo

- Mudanças em `Eduardo/`, `Enrico/` e `Gui/` (exceto o README de Fundos, que deixa de apontar a camada como bloqueio).
- Unificar a camada com o `fundos.cnpj`.
- Conferir bancos existentes.
