# Diagnóstico da ação oficial de documento

- Documento: `981509` — Informe Mensal de CRA
- Tentativas: **1**

## Resultado

- Tentativa 1: grade carregada=True, linha encontrada=True, página=5, erro=nenhum.
  - `A` Visualizar Documento
  - `A` Download do Documento
  - ação oficial usada: `https://fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id=981509`
  - mecanismo: **event_download**
  - download: HTTP **200**, `text/xml; charset=UTF-8`, formato **XML**, 11209 bytes, SHA-256 `d5ffda24f7f86deb41769babcc8938703b767314eb9cc4fe20bc0917b44a2dd8`
  - content-disposition: `attachment; filename="BRECOACRABX0-IFP31082025V01-000981509.xml"`, redirecionamentos: 0
  - arquivo temporário removido: **True**
  - popup: `edge://downloads-hub/`
  - resposta: `200` `text/html;charset=UTF-8` `https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCertificadosCVM`
  - resposta: `200` `application/javascript; charset=UTF-8` `https://fnet.bmfbovespa.com.br/fnet/resources/js/paginas/publico/gerenciador-documentos-cvm.js`
  - resposta: `200` `application/json; charset=UTF-8` `https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados?d=1&s=0&l=10&o%5B0%5D%5BdataEntrega%5D=desc&idCategoriaDocumento=0&idTipoDocumento=0&idEspecieDocumento=0&paginaCertificados=true&isSession=true&_=1790103711578`
  - resposta: `200` `application/json; charset=UTF-8` `https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados?d=2&s=0&l=10&o%5B0%5D%5BdataEntrega%5D=desc&tipoFundo=6&administrador=1300&idFundo=8795&idCategoriaDocumento=0&idTipoDocumento=0&idEspecieDocumento=0&paginaCertificados=true&isSession=false&_=1790103719423`
  - resposta: `200` `application/json; charset=UTF-8` `https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados?d=3&s=10&l=10&o%5B0%5D%5BdataEntrega%5D=desc&tipoFundo=6&administrador=1300&idFundo=8795&idCategoriaDocumento=0&idTipoDocumento=0&idEspecieDocumento=0&paginaCertificados=true&isSession=false&_=1790103719568`
  - resposta: `200` `application/json; charset=UTF-8` `https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados?d=4&s=20&l=10&o%5B0%5D%5BdataEntrega%5D=desc&tipoFundo=6&administrador=1300&idFundo=8795&idCategoriaDocumento=0&idTipoDocumento=0&idEspecieDocumento=0&paginaCertificados=true&isSession=false&_=1790103719701`
  - resposta: `200` `application/json; charset=UTF-8` `https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados?d=5&s=30&l=10&o%5B0%5D%5BdataEntrega%5D=desc&tipoFundo=6&administrador=1300&idFundo=8795&idCategoriaDocumento=0&idTipoDocumento=0&idEspecieDocumento=0&paginaCertificados=true&isSession=false&_=1790103719820`
  - resposta: `200` `application/json; charset=UTF-8` `https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados?d=6&s=40&l=10&o%5B0%5D%5BdataEntrega%5D=desc&tipoFundo=6&administrador=1300&idFundo=8795&idCategoriaDocumento=0&idTipoDocumento=0&idEspecieDocumento=0&paginaCertificados=true&isSession=false&_=1790103719940`
  - resposta: `200` `text/xml; charset=UTF-8` `https://fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id=981509`

## Recomendação

reproduzir a ação oficial capturada no mesmo BrowserContext e validar a assinatura do arquivo
