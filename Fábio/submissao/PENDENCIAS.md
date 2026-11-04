# Submissão Pense Além 2026 — onde paramos (04/11/2026)

Prazo: **sexta 06/11/2026, 23h59**, pelo formulário Microsoft Forms.

Histórico completo da conversa (explicações, mensagens prontas para o time, decisões): `HISTORICO_CONVERSA.md`.

## Campos do formulário

| Campo | O que vai | Situação |
|---|---|---|
| 1. Número da equipe | ? | Falta descobrir |
| 2. Padrinho | Gustavo Vilela | Pronto |
| 3. PPT/PDF (1 arquivo) | Apresentação a partir de `organograma-pense-alem (1).pptx` | A fazer |
| 4. Vídeo (opcional) | — | Decidir se vai ter |
| 5. Ficha de métricas (1 arquivo) | `Ficha_de_Metricas_Pense_Alem_2026.pdf` | Pronta; trocar estimativas por números do Research |
| 6. "Descreva detalhadamente como o protótipo foi elaborado" (texto, ~4.000 caracteres no máximo) | `campo6_como_o_prototipo_foi_elaborado.txt` | Pronto; confirmar uso do Claude Code |

## Arquivos desta pasta

- `gerar_docs.py` — gera a ficha e o descritivo em Word (requer `pip install python-docx`). Os números ficam no próprio script.
- `Ficha_de_Metricas_...docx/.pdf` — números marcados como [MEDIDO] ou [ESTIMATIVA].
- `Descritivo_do_Prototipo_...docx/.pdf` — não é anexado; serve de base para o PPT.
- `campo6_...txt` — texto para colar no campo 6.
- `organograma-pense-alem (1).pptx` — slides do time (outubro); base do PPT final.

## Esperando respostas

**Research (alimenta a ficha):** tamanho do time, nº de ativos por tipo, tempo para montar a visão de um ativo, horas/semana em coleta manual, fontes consultadas, tempo de leitura de documentos de CRI/CRA, caso real de evento percebido tarde. As mais importantes: tempo por ativo, horas/semana e leitura de documentos.

**Time do projeto:** nome completo do Gui; confirmação do uso do Claude Code; vai ter vídeo?; demo do agente de IA lendo 1 documento do Café Brasil?; liberar o link do protótipo HTML (https://claude.ai/artifact/Fv7GYVBGr2Ny5tg2nEHKKG) para a banca.

## Correções a fazer no organograma

- Slide 5, Fundos: "Ainda sem dado real" está desatualizado — o FIAGRO 09/2026 já está no banco de teste (308 classes, 39.316 observações).

## Números conferidos no repositório

417 testes (debêntures, 312 + 105) · 285 testes (galpão) · 3 emissores, 3 debêntures, 38 observações · 168 documentos de CRI/CRA (126 Café Brasil + 42 Almeida Junior) · FIAGRO 09/2026: 308 classes, 688 séries, 39.316 observações, 0 conflitos · FIDC 09/2026: 3.605 cedentes com CNPJ válido de 7.452 células, 385 percentuais acima de 100% · teste de volume: 1,57 mi observações, carga em 7,3 min.

## Decisões já tomadas (não rediscutir)

- **Git:** trabalhar e dar push só na branch `fabio`. Nunca dar push para `main`.
- **Formato:** ficha em Word, convertida em PDF para anexar. Sem modelo da Multiplica, a estrutura foi montada do zero.
- **Métricas de impacto:** enquanto o Research não responder, usar estimativas marcadas como [ESTIMATIVA]; números do repositório vão como [MEDIDO]. Não inventar número sem marcar.
- **IA, com honestidade:** hoje a IA está no desenvolvimento (Claude Code, a confirmar com o time) e no layout HTML (feito com o Claude). O agente de leitura de documentos e os alertas são **próxima fase** e não podem ser apresentados como prontos.
- **Produto em destaque:** debêntures é a frente mais madura e serve de exemplo principal (consulta da PETR27).
- **Descritivo:** o formulário pede texto no campo 6 sobre *como* o protótipo foi elaborado (processo), não um anexo.

## Panorama do projeto (em 04/11/2026)

| Frente | Dono | Fonte | Status |
|---|---|---|---|
| Debêntures | Eduardo | SND | Em operação, 8 de 9 etapas; falta a interface |
| CRI/CRA | Enrico | Fundos.NET | Catálogo e download em 2 ativos piloto |
| Fundos (FIDC/FIAGRO) | Gui | CVM | Carga real em banco de teste |
| Galpão (integração) | Fábio | — | Só emissores de debêntures |
| Renda fixa | Eduardo | A definir | Não iniciado |

Dor (padrinho Gustavo Vilela, área de Research): o time não consegue acompanhar os ativos por falta de uma base consolidada.

Para mais contexto técnico, leia `README.md` e `CLAUDE.md` na raiz, `Fábio/README.md` e `Gui/fundos/README.md`.

## Próximo passo

Montar o PPT final (campo 3) a partir do organograma + métricas.
