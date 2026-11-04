# Histórico da conversa com o Claude — submissão Pense Além 2026

Conversa de 04/11/2026 (Fábio Junior + Claude Code, no computador do trabalho). Este arquivo registra tudo o que foi feito e decidido, para continuar em outro computador sem perder contexto. O resumo do que falta está em `PENDENCIAS.md`.

---

## 1. Pedido inicial

Fábio pediu para puxar as atualizações do projeto e estruturar a entrega pedida pela Multiplica:

> Faltam poucos dias para a submissão oficial dos projetos do Pense Além 2026 — IA em Ação. Até sexta-feira, 06/11, às 23h59, as equipes deverão enviar: apresentação em PPT/PDF, vídeo do projeto (se houver), ficha de métricas e descritivo do protótipo. O envio é feito pelo formulário de submissão.

## 2. Atualização do repositório

- O repositório local estava desatualizado (último commit `e8f5970`, de 16/09).
- Foi rodado `git pull origin main` na branch `fabio`, um fast-forward até `360409c`, que trouxe 111 commits novos: o módulo de Fundos do Gui, eventos de debêntures, catálogo de CRI/CRA, a camada compartilhada (galpão), ADRs, `README.md` e `CLAUDE.md` na raiz.
- **Regra combinada:** commits e push só na branch `fabio`, nunca em `main`.

## 3. Levantamento do projeto

**Dor** (validada pelo padrinho Gustavo Vilela, área de Research): o time não consegue acompanhar os ativos como gostaria por falta de uma base de dados sólida e consolidada.

**Solução:** uma plataforma única com base consolidada de ativos, emissores, documentos e preços, mais alertas de variação de preço e de notícias. O plano tem 3 passos: listar os ativos, construir os robôs de cada frente e juntar tudo no galpão.

| Frente | Dono | Fonte | O que coleta | Status em 04/11 |
|---|---|---|---|---|
| Debêntures | Eduardo Tonzano | SND | Emissor, vencimento, indexador, taxa, valor, histórico, eventos | Em operação, 8 de 9 etapas (falta a interface) |
| CRI/CRA | Enrico Suman Marques | Fundos.NET (Playwright) | Termo, informes mensais, fatos relevantes, rating | 2 ativos piloto, 168 documentos |
| Fundos (FIDC/FIAGRO) | Gui | CVM (dados abertos) | Gestora, administradora, custodiante, informes, cedentes | Carga real em banco de teste |
| Galpão (integração) | Fábio Junior (T.I. e integração) | — | Cadastro único por CNPJ | Só emissores de debêntures |
| Renda fixa | Eduardo | A definir | Taxas, marcação a mercado, indicadores dos bancos | Não iniciado |

**Números conferidos nos arquivos do repositório:**
- 417 testes de debêntures (a soma de duas suítes, 312 + 105; ver `CLAUDE.md`) e 285 testes do galpão.
- Debêntures: 3 emissores (Petrobras, Sabesp, Celpe), 3 debêntures, 38 observações (`Fábio/README.md`).
- CRI/CRA: 168 documentos no banco, sendo 126 do Café Brasil e 42 da Almeida Junior (`Enrico/cri_cra_platform/reports/duplicate_assets_diagnostic.md`). Os READMEs mais antigos ainda falam em 124.
- FIAGRO 09/2026: 308 classes, 688 séries, 39.316 observações, 0 conflitos (`docs/fundos-descoberta.md`).
- FIDC 09/2026: 7.452 células, 3.605 cedentes com CNPJ válido, 385 percentuais acima de 100% (`Gui/fundos/README.md`).
- Teste de volume de Fundos: 1,57 milhão de observações por competência; carga completa em 7,3 min; simulação em 15 s. Medido com dados fictícios no volume real.

**Onde está a IA:**
- Em uso: o time desenvolve com o Claude Code como copiloto (a confirmar com o time), e o layout HTML foi feito com o Claude.
- Próxima fase: o agente que lê documentos de CRI/CRA, cita a página e passa por revisão humana (regra S-06 em `docs/regras-de-exibicao-pendentes.md`), e os alertas.
- Não apresentar o agente nem os alertas como prontos.

## 4. Como funcionam os materiais (explicação dada ao Fábio)

| Material | Pergunta que responde | Formato |
|---|---|---|
| Apresentação | "Qual é a história?" | Visual: problema → solução → resultado |
| Vídeo | "Funciona mesmo?" | Demonstração rodando |
| Ficha de métricas | "Quanto isso vale?" | Números: como é hoje × como fica com a solução |
| Descritivo | "O que foi construído e como?" | Texto |

- **Ficha de métricas:** como não veio modelo, foi seguido o padrão de programas de inovação. Cada indicador traz a linha de base (como é hoje), o resultado ou meta e a forma de medição. A banca valoriza mais um número pequeno e medido do que um grande e estimado. Por isso tudo está marcado como [MEDIDO] ou [ESTIMATIVA].
- **Estimativas atuais, ainda sem medição:** 30–60 min para montar a visão de um ativo (meta: menos de 5 min); 10–15 h por semana de coleta manual (meta: 2–3 h); 2–4 h para ler os documentos de um CRI/CRA (meta: cerca de 30 min com o agente e revisão humana).
- **Descritivo:** é texto. O protótipo em si aparece no vídeo e no PPT. Sugestão: incluir no PPT um print do layout HTML e um print de uma consulta real (PETR27).

## 5. O formulário de submissão (estrutura real)

1. Número da equipe (texto) — **falta descobrir**
2. Nome do padrinho ou madrinha — Gustavo Vilela
3. Anexo do PPT/PDF da apresentação (1 arquivo)
4. Anexo do vídeo, se houver (1 arquivo)
5. Anexo da ficha de métricas (1 arquivo) — mandar o PDF
6. "Descreva detalhadamente como o protótipo foi elaborado" — **texto livre**, não anexo. O texto está pronto em `campo6_como_o_prototipo_foi_elaborado.txt` (2.720 caracteres; o limite do Forms fica em torno de 4.000).

Por causa do campo 6, o Word do descritivo não é anexado e passa a servir de base para o PPT.

## 6. Organograma do time (`organograma-pense-alem (1).pptx`)

Slides de outubro/2026 (retrato de 20/10), com 9 slides: capa, problema e solução, fluxo fontes → robôs → bancos → galpão → equipe, de onde vem cada informação, um robô por ativo, quem faz o quê, mapa do sistema, onde estamos e protótipo com equipe.

O que acrescentou aos documentos: a área (Research), o Eduardo como dono de renda fixa, o Fábio como "T.I. e integração", o que cada robô coleta e os próximos passos (ligar as frentes ao galpão, conectar CVM e ANBIMA às debêntures, definir a interface com a equipe e construir os alertas).

**Protótipo de interface:** https://claude.ai/artifact/Fv7GYVBGr2Ny5tg2nEHKKG. É um layout em HTML com busca, menu por classe (Renda Fixa, Debêntures, Securitizados, Fundos, Emissores), ativos em carteira com maiores altas e quedas, e as fontes (SND e Fundos.NET ativas; CVM e ANBIMA planejadas). Usa **dados ilustrativos**, não está ligado aos bancos e não tem IA. **Está privado: liberar o acesso antes de mandar para a banca.**

**A corrigir no slide 5:** Fundos aparece como "Ainda sem dado real", o que está desatualizado.

## 7. Mensagens prontas para enviar

### Para o time de Research (perguntas 1 a 7 alimentam a ficha; 8 e 9 servem ao PPT e ao descritivo)

> Oi, pessoal! Estamos fechando a submissão do Pense Além (entrega sexta, 06/11) e precisamos de números reais da rotina de vocês. Respostas aproximadas já ajudam:
>
> 1. Quantas pessoas do Research acompanham os ativos de crédito?
> 2. Quantos ativos vocês acompanham hoje, mais ou menos, por tipo (debêntures, CRI/CRA, FIDC/FIAGRO, renda fixa)?
> 3. Quanto tempo leva hoje para montar a visão completa de um ativo (cadastro, preço, eventos, documentos)? Se puderem cronometrar 2 ou 3 casos reais, melhor.
> 4. Quantas horas por semana, somando o time, vão em coleta e conferência manual de dados?
> 5. Quais fontes vocês consultam hoje (SND, Fundos.NET, CVM, ANBIMA, B3, Bloomberg, planilhas, e-mails de agente fiduciário)?
> 6. Quanto tempo leva ler os documentos de um CRI/CRA novo (termo de securitização) e o relatório mensal de um que já está em carteira?
> 7. Já aconteceu de perceberem tarde um evento importante (quebra de covenant, assembleia, atraso de pagamento, rebaixamento)? Lembram de algum caso?
> 8. Ao abrir a ficha de um ativo, quais são as 3 informações que vocês querem ver primeiro?
> 9. Quais alertas seriam úteis (por exemplo, PU variou mais de X%, saiu documento novo, mudou o rating)?
>
> Obrigado!

As mais importantes são a 3, a 4 e a 6, porque transformam [ESTIMATIVA] em [MEDIDO]. A 7 rende a melhor história para a apresentação.

| Pergunta | Onde entra |
|---|---|
| 1 | Ficha: premissas e cálculo de horas |
| 2 | Ficha: meta de cobertura |
| 3 | Ficha: linha de base do indicador principal |
| 4 | Ficha: linha de base de horas manuais |
| 5 | Ficha: fontes consultadas |
| 6 | Ficha: linha de base do agente de IA |
| 7 | Ficha (risco) e PPT (história) |
| 8 e 9 | Descritivo e PPT (não são métricas) |

### Para o time do projeto

> Pessoal, para fechar a ficha de métricas e o descritivo:
>
> 1. **Gui:** qual é o seu nome completo, para constar na submissão?
> 2. **Todos:** confirmam que usamos o Claude Code no desenvolvimento? O texto sobre IA se apoia nisso.
> 3. **Todos:** vamos mandar vídeo? Se sim, quem grava e qual demo mostramos?
> 4. **Enrico:** dá para fazer até quinta uma demo simples do agente de IA lendo 1 documento do Café Brasil? Isso transforma a IA de "próxima fase" em "protótipo inicial".
> 5. **Gui:** o slide 5 diz que Fundos está "sem dado real", mas o FIAGRO de 09/2026 já está no banco de teste. Posso atualizar?
> 6. **Quem criou o protótipo HTML:** consegue liberar o link para a banca? Hoje ele está privado.
>
> Também precisamos saber qual é o **número da equipe** para o formulário.

## 8. Arquivos gerados (nesta pasta)

| Arquivo | Para quê |
|---|---|
| `Ficha_de_Metricas_Pense_Alem_2026.docx/.pdf` | Campo 5 do formulário (mandar o PDF). 2 páginas |
| `Descritivo_do_Prototipo_Pense_Alem_2026.docx/.pdf` | Base para o PPT. 2 páginas |
| `campo6_como_o_prototipo_foi_elaborado.txt` | Colar no campo 6 |
| `gerar_docs.py` | Regenera a ficha e o descritivo. Os textos e números estão no script |
| `organograma-pense-alem (1).pptx` | Slides do time, base do PPT final |
| `PENDENCIAS.md` | Lista do que falta |

## 9. Notas de ambiente (computador do trabalho)

- Não havia Node nem LibreOffice; o Python 3.13 fica em `%LOCALAPPDATA%\Programs\Python\Python313\python.exe` (o comando `python` aponta para a Microsoft Store).
- O `python-docx` e o `python-pptx` foram instalados num ambiente virtual temporário. Em outra máquina, rode `pip install python-docx python-pptx`.
- Para regenerar: `python gerar_docs.py "Fábio/submissao"`.
- O PDF foi gerado pelo Word, via PowerShell (`Word.Application` → `ExportAsFixedFormat`, formato 17). Também dá para abrir o .docx no Word e usar "Salvar como PDF".

## 10. Próximos passos

1. Mandar as mensagens da seção 7.
2. Montar o PPT final (campo 3) a partir do organograma, com as métricas, os prints do protótipo e a consulta da PETR27.
3. Quando o Research responder, atualizar os números em `gerar_docs.py` e regenerar a ficha.
4. Confirmar o uso do Claude Code e ajustar o campo 6, se precisar.
5. Liberar o link do protótipo, descobrir o número da equipe e enviar tudo até **sexta, 06/11, 23h59**.
