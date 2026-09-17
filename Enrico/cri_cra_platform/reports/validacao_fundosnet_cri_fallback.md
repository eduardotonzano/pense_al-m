# Validação técnica do Fundos.NET: CRI e fallback

## O que foi testado

Os testes foram executados com Playwright usando Microsoft Edge headless. O fluxo reutilizou a página pública de documentos e os endpoints observados na Tarefa A. Chromium ficou configurado como fallback de navegador, mas o Edge foi utilizado.

No Teste 1 foram usados `buscarAdministrador` para Opea, `listarFundos` com o ISIN `BRRBRACRIP13` e `pesquisarGerenciadorDocumentosDados` com o `idFundo` retornado.

No Teste 2 foi escolhido o caso **Virgo CRA JBS**. Foram testados termos progressivos sem enviar ISIN, e nenhum candidato foi escolhido automaticamente sem validação do administrador, emissão, série e descrição.

## Teste 1 — CRI por ISIN

Resultado: **aprovado**.

- `tipoFundo=5` corresponde a CRI; a página também mostrou `tipoFundo=6` para CRA.
- `buscarAdministrador` localizou `OPEA SECURITIZADORA S.A.` com `administrador_id=1338`.
- `listarFundos` com `term=BRRBRACRIP13`, `idTipoFundo=5` e `idAdm=1338` retornou exatamente um certificado:
  `idFundo=13003`, `OPEA CRI Emissão:301 Série:1 ALMEIDA JUNIOR SHOPP 08/2024 BRRBRACRIP13`.
- A busca documental com `idFundo=13003` retornou HTTP 200, 42 documentos e uma única descrição de operação em todos os registros.
- A amostra está registrada no JSON.

O código CETIP `24G2100031` foi usado somente como dado de conferência e não como filtro. Ele não aparece na descrição retornada para o ISIN consultado; a identificação operacional confiável neste teste foi o próprio ISIN e o `idFundo`.

## Teste 2 — fallback sem ISIN (retomado)

Resultado: **aprovado para o caso testado**.

A antiga Virgo foi localizada no cadastro atual como `RIZA SECURITIZADORA S.A.`:

- `buscarAdministrador("Riza")` retornou Riza e Riza II; a escolha não foi feita por aproximação.
- `buscarAdministrador("Riza Securitizadora")` retornou somente `id=1320`.
- `buscarAdministrador("Riza Securitizadora S.A.")` confirmou novamente somente `id=1320`.
- O caso usado foi **Virgo CRA JBS**, com `tipoFundo=6`, emissão 122 e série principal 1.
- `listarFundos` com `idAdm=1320` e `term=122` retornou exatamente um certificado: `idFundo=8573`.
- `listarFundos` com `idAdm=1320` e `term=JBS IV` também retornou exatamente esse certificado.
- `listarFundos` com `term=CORP JBS IV` retornou exatamente esse certificado.
- Os termos literais `122 1` e `JBS IV 122 1` retornaram zero; o endpoint não trata essa composição como busca textual válida.
- O certificado retornado foi `ISEC CRA Emissão:122 Série(s):1 (+2) CORP JBS IV 09/2022 BRIMWLCRA523`.

`pesquisarGerenciadorDocumentosDados` com `idFundo=8573` retornou HTTP 200 e 105 documentos. Os 105 registros tinham uma única descrição de operação, exatamente a do certificado, portanto os documentos foram confirmados como exclusivos da operação esperada.

O fallback foi considerado aprovado porque a combinação do administrador atual da antiga Virgo (`1320`), tipo CRA (`6`), emissão/operação e validação da descrição retornou exatamente um certificado correto. A aprovação é específica deste caso. A operação é multissérie (`Série(s):1 (+2)`), então não se deve interpretar o retorno como uma série única isolada.

## Regras recomendadas para a Tarefa C

1. Usar ISIN como filtro primário quando disponível.
2. Descobrir o `tipoFundo` pela opção do site; para CRI, usar `5`, e para CRA, `6`.
3. Localizar a securitizadora com `buscarAdministrador` e exigir uma correspondência única antes de chamar `listarFundos`.
4. Usar o `idFundo` retornado para buscar documentos.
5. Validar que todas as descrições documentais correspondem ao certificado escolhido.
6. O fallback pode ser habilitado para casos equivalentes quando o administrador for identificado sem ambiguidade e a combinação de tipo, emissão/operação e série confirmada no texto do certificado produzir exatamente um certificado.
7. Como o endpoint rejeitou `122 1` e `JBS IV 122 1`, a implementação deve fazer tentativas progressivas e validar o texto retornado, nunca assumir que um termo composto vazio significa ausência da operação.

## Hipóteses rejeitadas e limitações

- Não foi aceito usar somente o nome do devedor sem filtrar o administrador; a busca controlada por `idAdm=1320` foi necessária.
- A identidade `ISEC` exibida no certificado não foi tratada como contradição: a associação com a antiga Virgo/Riza foi feita pelo filtro `idAdm=1320`.
- Não foi usado o CETIP como filtro principal.
- Não foram alterados banco, schema, `FundosNetCollector` ou `main`.
- Não houve CAPTCHA ou bloqueio durante as chamadas realizadas; o site retornou HTTP 200.
- Não foram salvos cookies, tokens, CAPTCHA, cabeçalhos sensíveis ou capturas brutas.
