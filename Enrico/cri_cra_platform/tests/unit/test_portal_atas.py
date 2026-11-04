from credit_assets.portal_atas import (document_kind, eco_documents, grave_events, in_window, opea_family, opea_published,
                                       opea_selected)


def test_kind_by_title_with_category_as_tiebreaker():
    # títulos reais dos portais (Opea, Riza, Eco, Vert)
    assert document_kind("Ata da Assembleia - Reunião de 28/10/2026", "Assembleia") == "ata"
    assert document_kind("Edital de Convocaçao - Reunião de 19/10/2026", "Assembleia") == "edital"
    assert document_kind("Proposta para a Assembleia - Reunião de 19/10/2026", "Assembleia") == "proposta"
    assert document_kind("Termo de não instalação AGT sem lista", "Termo de não instalação AGT sem lista") == "ata"
    assert document_kind("Sumário de ATA de Assembleia", "ATA de Assembleia") == "ata"
    assert document_kind(" Ajuizamento do pedido de  Recuperação Judicial ", "Fato Relevante") == "fato_relevante"
    assert document_kind("Inadimplência de PMT", "Fato Relevante") == "fato_relevante"
    assert document_kind("Comunicado ao Mercado", "Comunicado ao Mercado") == "comunicado"
    assert document_kind("Termo_de_Não_Instalação_296ª_Segunda_convocação_15042025[1].pdf") == "ata"
    assert document_kind("Edital de Convocação (AGT xx.xx.2025) - 2025.02.17 PTGN v1 (009).pdf") == "edital"
    # título sem palavra-chave: a aba/categoria do portal decide
    assert document_kind("CRI.301.CIA.1 20261028-Assinado", "Atas de Assembléias") == "ata"
    assert document_kind("Apresentação aos investidores", "Assembléias") == "assembleia"


def test_excluded_titles_are_not_rescued_by_category():
    assert document_kind("Informe Mensal CVM - 08/2026", "Assembleia") == ""
    assert document_kind("Relatório Mensal Gestão Fiduciária - 09/2026") == ""
    assert document_kind("Anúncio de início", "Comunicados ao Mercado") == ""
    assert document_kind("DFs Patrimônio Separado", "DFs Patrimônio Separado") == ""
    assert document_kind("Relatório de Monitoramento Rating", "Rating") == ""
    assert document_kind("Termo de Securitização - 1 Adit", "TS") == ""
    assert document_kind("Material de Apoio", "Material de Apoio") == ""
    assert document_kind("Protocolo CVM ATA de Assembleia sem lista ", "Protocolo CVM ATA de Assembleia sem lista ") == ""
    assert document_kind("Comunicado de encerramento da oferta", "Comunicado ao Mercado") == ""
    # ata que aprova DFs continua sendo ata
    assert document_kind("Ata da Assembleia - Termo de Não Instalação - Aprovação Automática DF") == "ata"


def test_eco_documents_keep_tab_and_fix_doubled_link():
    page = """
    <span class="documents__link" data-tab="1" active>Atas de Assembl&eacute;ias</span>
    <span class="documents__link" data-tab="2" >Comunicados ao Mercado</span>
    <div class="documents__current" data-group="1" active>
      <div class="documents__item"><p class="documents__text"> 296ª EMISSÃO-ATAS DE ASSEMBLEIAS-22052026 </p>
      <a href="https://ecoagro.agr.br/public/storage/Arquivo/1779501322296ª EMISSÃO-ATA.pdf" target="_blank">Baixar</a></div>
      <div class="documents__item"><p class="documents__text"> Termo 07042026 </p>
      <a href="https://ecoagro.agr.br/public/storage/http://ecoagro.agr.br/public/storage/Arquivo/1775590200Termo.pdf">Baixar</a></div>
    </div>
    <div class="documents__current" data-group="2" >
      <div class="documents__item"><p class="documents__text"> Anúncio de início </p>
      <a href="https://ecoagro.agr.br/public/storage/Arquivo/1701476372INICIO.pdf">Baixar</a></div>
    </div>"""
    docs = eco_documents(page)
    assert [(d.category, d.title, d.uploaded) for d in docs] == [
        ("Atas de Assembléias", "296ª EMISSÃO-ATAS DE ASSEMBLEIAS-22052026", 1779501322),
        ("Atas de Assembléias", "Termo 07042026", 1775590200),
        ("Comunicados ao Mercado", "Anúncio de início", 1701476372)]
    assert docs[1].url == "https://ecoagro.agr.br/public/storage/Arquivo/1775590200Termo.pdf"
    assert docs[1].file_name == "Termo.pdf"
    assert docs[0].published == "2026-05-22"  # 22h de 22/05 em Brasília (23/05 em UTC)
    assert [document_kind(f"{d.title} | {d.file_name}", d.category) for d in docs] == ["ata", "ata", ""]


def test_opea_selection_uses_inclusion_date_and_needs_attachment():
    events = [
        {"id": 1, "titulo": "Ata da Assembleia - Reunião de 28/10/2026", "tipoEventoDiarioBordo": "Assembleia",
         "dataOcorrencia": "2026-10-28", "dataInclusao": "2026-10-28T18:12:36", "diarioBordoAnexoList": [{"idDiarioBordo": "1"}]},
        # assembleia antiga incluída no portal depois do corte entra; a recente sem anexo não
        {"id": 2, "titulo": "Ata da Assembleia - Reunião de 12/12/2025", "dataOcorrencia": "2025-12-12",
         "dataInclusao": "2026-08-15T10:00:00", "diarioBordoAnexoList": [{"idDiarioBordo": "2"}]},
        {"id": 3, "titulo": "Edital de Convocaçao - Reunião de 04/11/2026", "dataOcorrencia": "2026-10-20",
         "diarioBordoAnexoList": []},
        {"id": 4, "titulo": "Relatório Mensal Gestão Fiduciária - 09/2026", "dataOcorrencia": "2026-09-30",
         "diarioBordoAnexoList": [{"idDiarioBordo": "4"}]},
        {"id": 5, "titulo": "Edital de Convocaçao - Reunião de 10/07/2026", "dataOcorrencia": "2026-06-20",
         "diarioBordoAnexoList": [{"idDiarioBordo": "5"}]},
    ]
    assert [(kind, e["id"]) for kind, e in opea_selected(events, "2026-08-01")] == [("ata", 1), ("ata", 2)]
    assert opea_published(events[4]) == "2026-06-20"
    assert opea_family("CRI.301.CIA.1") == "CRI.301.CIA" and opea_family("CRA.38.ABC") == "CRA.38.ABC"
    assert in_window("2026-08-01", "2026-08-01") and not in_window("", "2026-08-01")


def test_grave_events_prefer_the_decision_over_the_text():
    graves, origin = grave_events(["waiver_aprovado_em_bloco", "vencimento_antecipado_nao_declarado", "dfs_aprovado"],
                                  [("waiver", "...")])
    assert (graves, origin) == (["vencimento antecipado não declarado", "waiver (aprovado)"], "decisão")
    # ata que só aprovou as DFs: vencimento antecipado no texto é cláusula padrão
    assert grave_events(["dfs_aprovado"], [("vencimento_antecipado", "evento de inadimplemento")]) == ([], "")
    # não instalada ou edital: vale o que o texto discute; recuperação judicial vem do trecho de inadimplência
    assert grave_events(["nao_instalada"], [("prorrogacao_repactuacao", "prorrogação"),
                                            ("inadimplencia_devedor", "ajuizou pedido de recuperação judicial")]) == (
        ["recuperação judicial", "repactuação/prorrogação"], "texto")
    assert grave_events([], [("inadimplencia_devedor", "atraso no pagamento da parcela")]) == ([], "")
