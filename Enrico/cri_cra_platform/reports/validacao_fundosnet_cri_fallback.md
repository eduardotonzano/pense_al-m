# Validação técnica do Fundos.NET: CRI e fallback

## O que foi testado

Os testes foram executados com Playwright usando Microsoft Edge headless. O fluxo reutilizou a página pública de documentos e os endpoints observados na Tarefa A. Chromium ficou configurado como fallback de navegador, mas o Edge foi utilizado.

No Teste 1 foram usados `buscarAdministrador` para Opea, `listarFundos` com o ISIN `BRRBRACRIP13` e `pesquisarGerenciadorDocumentosDados` com o `idFundo` retornado.

No Teste 2 foi escolhido o caso **Virgo CRA JBS**. Foram testados termos progressivos sem enviar ISIN. Nenhum candidato foi escolhido quando a resposta foi ambígua.

## Teste 1 — CRI por ISIN

Resultado: **aprovado**.

- `tipoFundo=5` corresponde a CRI; a página também mostrou `tipoFundo=6` para CRA.
- `buscarAdministrador` localizou `OPEA SECURITIZADORA S.A.` com `administrador_id=1338`.
- `listarFundos` com `term=BRRBRACRIP13`, `idTipoFundo=5` e `idAdm=1338` retornou exatamente um certificado:
  `idFundo=13003`, `OPEA CRI Emissão:301 Série:1 ALMEIDA JUNIOR SHOPP 08/2024 BRRBRACRIP13`.
- A busca documental com `idFundo=13003` retornou HTTP 200, 42 documentos e uma única descrição de operação em todos os registros.
- A amostra está registrada no JSON.

O código CETIP `24G2100031` foi usado somente como dado de conferência e não como filtro. Ele não aparece na descrição retornada para o ISIN consultado; a identificação operacional confiável neste teste foi o próprio ISIN e o `idFundo`.

## Teste 2 — fallback sem ISIN

Resultado: **reprovado / não validado**.

O tipo CRA foi confirmado como `tipoFundo=6`, mas `buscarAdministrador` não retornou Virgo para `Virgo`, `Virgo Securitizadora` ou `VIRGO COMPANHIA`. Sem `administrador_id`, a busca por `JBS` ficou ampla e retornou 13 certificados de várias securitizadoras e emissões. A busca por `SEARA` retornou 5 candidatos e a combinação `JBS 190` retornou zero.

Esse comportamento não permite confirmar o caso Virgo de forma inequívoca. Nenhum `idFundo` foi escolhido e o endpoint documental não foi chamado para o fallback.

## Regras recomendadas para a Tarefa C

1. Usar ISIN como filtro primário quando disponível.
2. Descobrir o `tipoFundo` pela opção do site; para CRI, usar `5`, e para CRA, `6`.
3. Localizar a securitizadora com `buscarAdministrador` e exigir uma correspondência única antes de chamar `listarFundos`.
4. Usar o `idFundo` retornado para buscar documentos.
5. Validar que todas as descrições documentais correspondem ao certificado escolhido.
6. Manter o fallback emissão+série desabilitado como regra aprovada até que administrador, securitizadora, emissão e série produzam exatamente um certificado.

## Hipóteses rejeitadas e limitações

- Não foi aceito que uma busca ampla por devedor/operação identifique Virgo: os resultados foram múltiplos ou vazios.
- Não foi usado o CETIP como filtro principal.
- Não foram alterados banco, schema, `FundosNetCollector` ou `main`.
- Não houve CAPTCHA ou bloqueio durante as chamadas realizadas; o site retornou HTTP 200.
- Não foram salvos cookies, tokens, CAPTCHA, cabeçalhos sensíveis ou capturas brutas.
