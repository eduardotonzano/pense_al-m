"""Gera o rascunho do mapeamento do Informe Mensal de CRI por analogia com o mapeamento CRA aprovado.

Cada caminho do CRI herda a decisão do mesmo caminho (ou do caminho análogo) no CRA,
com a justificativa citando a origem. O resultado sai com approval.status = pending.
"""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
u = json.load(open("reports/almeida_junior_xml_union.json", encoding="utf-8"))["paths"]
cra_doc = json.load(open("config/xml_mappings/informe_mensal_cra.json", encoding="utf-8"))
cra = cra_doc["paths"]
NIL = "/@{http://www.w3.org/2001/XMLSchema-instance}nil"
subs = [("PercentualCreditosOutrasGarantias", "PercentualDireitosCreditoriosOutrasGarantias"),
        ("CincoMaioresCedentes", "MaiorCedente"), ("DezMaioresCedentes", "MaiorCedente"), ("VinteMaioresCedentes", "MaiorCedente"),
        ("/InformeMensalCRI", "/InformeMensalCRA"), ("/InfoCreditos", "/InfoDireitosCreditoriosAgro"),
        ("/Ativo/CreditosTotais/CreditosAVencerComParcelasAtrasadas", "/Ativo/DireitosCreditorios/DirCredAVencerComParcelasAtraso"),
        ("/Ativo/CreditosTotais/CreditosAVencerSemParcelasAtrasadas", "/Ativo/DireitosCreditorios/DirCredAVencerSemParcelasAtraso"),
        ("/Ativo/CreditosTotais/CreditosVencidosNaoPagos", "/Ativo/DireitosCreditorios/DirCredVencidosNaoPagos"),
        ("/Ativo/CreditosTotais", "/Ativo/DireitosCreditorios"),
        ("OutrasInfoCreditosAReceber", "OutrasInfoDireitosCreditoriosAReceber"),
        ("VlrTotalCreditosRelacaoVlrTotalEmissao", "VlrTotalDirCredRelacaoVlrTotalEmissao"),
        ("PercentualCreditosCedentesTerceiros", "PercentualDireitosCreditoriosCedentesTerceiros"),
        ("PercentualCreditos", "PercentualDirCred"),
        ("RecebimentosCreditos", "RecebimentosDireitosCreditorios"), ("AquisicaoNovosCreditos", "AquisicaoNovosDireitosCreditorios"),
        ("ProvisaoRecuperacaoCreditos", "ProvisaoRecuperacaoDireitosCreditorios"),
        ("/DadosGerais/OutrasCaracteristicasEmissao", "/DadosGerais/OutrasCaracteristicas/OutrasCaracteristicasEmissao"),
        ("/DadosGerais/RetencaoRisco/", "/DadosGerais/OutrasCaracteristicas/"),
        ("/DadosGerais/RetencaoRisco", "/DadosGerais/OutrasCaracteristicas"),
        ("/Commodities", "/CommoditiesAgricolas"),
        ("PercentualCreditosOutrasGarantias", "PercentualDireitosCreditoriosOutrasGarantias")]
def analog(path, swap_cedente=False):
    for a, b in subs + ([("Cedentes", "Devedores")] if swap_cedente else []):
        path = path.replace(a, b)
    return path
MONEY = {"status": "mapped", "data_type": "decimal", "currency": "BRL", "scale": "1", "scale_rule": "monetary_scale_suspect"}
paths, origin = {}, {}
for p in u:
    x = p["xml_path"]
    direct = x.replace("/InformeMensalCRI", "/InformeMensalCRA", 1)
    for cand, how in ((direct, "mesmo caminho"), (analog(x), "caminho análogo"), (analog(x, True), "caminho análogo (cedente->devedor)")):
        if cand in cra:
            d = dict(cra[cand])
            if d["status"] != "pending_decision":
                d["justification"] = f"{how} no mapeamento CRA 0.1.1 ({cand}): {cra[cand]['justification']}"
            d["cra_analog"] = cand
            paths[x] = d; origin[x] = how; break
    else:
        if x.endswith(NIL):
            paths[x] = {"status": "ignored", "justification": "Atributo xsi:nil; registrado como flag xsi_nil no valor (decisão 2026-10-26)."}
            origin[x] = "regra xsi_nil"
        elif "/VlrCreditosNaturezaEcon" in x:
            if p["node_kind"] == "container":
                paths[x] = {"status": "ignored", "justification": "Contêiner estrutural sem valor próprio."}
            else:
                paths[x] = dict(MONEY, justification="Específico do CRI (valor dos créditos por natureza econômica); valor monetário em reais, mesma regra dos demais monetários do CRA 0.1.1.")
            origin[x] = "novo (CRI)"
        else:
            paths[x] = {"status": "pending_decision", "justification": None, "question": "Sem análogo no CRA; decidir tipo e uso."}
            origin[x] = "sem análogo"
rules = json.loads(json.dumps(cra_doc["rules"]).replace("/InformeMensalCRA", "/InformeMensalCRI"))
draft = {
    "mapping_version": "0.1.0-draft",
    "layout_version": None,
    "layout_validation_status": "structural_only",
    "root": "InformeMensalCRI",
    "derived_from": "config/xml_mappings/informe_mensal_cra.json 0.1.1",
    "approval": {"status": "pending", "note": "Rascunho por analogia com o mapeamento CRA aprovado; requer aprovação humana antes da extração."},
    "rules": rules,
    "paths": dict(sorted(paths.items())),
}
from collections import Counter
print(Counter(origin.values())); print(Counter(v["status"] for v in paths.values()))
for k, v in paths.items():
    if v["status"] == "pending_decision": print("PENDENTE", k, v.get("cra_analog", ""))
for k in ("/InformeMensalCRI/DetalhesSeries/totalVlrCertificados", "/InformeMensalCRI/DadosGerais/Series/Serie/VlrTotalIntegralizado", "/InformeMensalCRI/Passivo/ReducaoVlrEmissao"):
    print(k, k in paths)
json.dump(draft, open("config/xml_mappings/informe_mensal_cri.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
