"""CNPJ do devedor de cada ativo do catálogo, pelo Informe Mensal da CVM (só leitura; nada é gravado no banco).

    python scripts/build_cnpj_devedor_cvm.py

O catálogo (data/cri_cra.db) quase nunca traz o CNPJ do devedor; o Informe Mensal traz, na tabela de cedentes e
devedores (data/cvm_open.db). O ativo é ligado ao certificado da CVM pelo código CETIP ou pelo ISIN da série
(*_classe) e usa a última competência e a última versão informadas. CPF não sai no relatório (só a contagem);
identificador inválido idem. Saída: reports/cnpj_devedor_cvm.{csv,md}, uma linha por ativo e CNPJ, com a fonte
(arquivo da CVM e SHA-256). Candidato para a camada compartilhada preencher o cadastro com proveniência (regras 1 e 2):
este script não une nem grava entidade nenhuma.
"""
from __future__ import annotations

import csv
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.debtor_exposure import classify_identifier, format_cnpj

FIELDS = ["codigo_cetip", "isin", "tipo", "devedor_catalogo", "certificado_cvm", "competencia", "versao", "cnpj_devedor",
          "identificador", "percentual", "devedores_no_informe", "fonte", "sha256"]
CERTIFICATES = """
    SELECT c.Codigo_Identificacao_Certificado AS cert, upper(trim(c.Codigo_CETIP)) AS cetip, upper(trim(c.Codigo_ISIN)) AS isin,
           max(c.Data_Referencia) AS ref
    FROM {kind}_classe c JOIN source_files f ON f.file_id = c._file_id
    WHERE f.is_current = 1
    GROUP BY 1, 2, 3
"""
DEBTORS = """
    SELECT * FROM (
        SELECT t.Codigo_Identificacao_Certificado AS cert, t.Data_Referencia AS ref, t.Versao AS versao, t.CNPJ AS cnpj,
               t.Percentual AS pct, f.url AS url, f.sha256 AS sha,
               DENSE_RANK() OVER (PARTITION BY t.Codigo_Identificacao_Certificado
                                  ORDER BY substr(t.Data_Referencia, 1, 7) DESC, CAST(t.Versao AS INTEGER) DESC,
                                           t._file_id DESC) AS r
        FROM {kind}_cedente_devedor t JOIN source_files f ON f.file_id = t._file_id
        WHERE f.is_current = 1 AND t.Tipo = 'Devedor')
    WHERE r = 1
"""


def main() -> int:
    catalog = sqlite3.connect(f"file:{ROOT / 'data' / 'cri_cra.db'}?mode=ro", uri=True)
    assets = catalog.execute("SELECT codigo_cetip, upper(coalesce(isin, '')), tipo_ativo, coalesce(devedor, ''), "
                             "coalesce(cnpj_devedor, '') FROM assets WHERE codigo_cetip IS NOT NULL").fetchall()
    catalog.close()

    cvm = sqlite3.connect(f"file:{ROOT / 'data' / 'cvm_open.db'}?mode=ro", uri=True)
    by_code: dict[str, set[tuple[str, str]]] = defaultdict(set)  # CETIP ou ISIN -> {(kind, certificado)}
    debtors: dict[tuple[str, str], list[tuple]] = defaultdict(list)
    for kind in ("cra", "cri"):
        for cert, cetip, isin, _ in cvm.execute(CERTIFICATES.format(kind=kind)):
            for code in (cetip, isin):
                if code and code not in ("-", "0"):
                    by_code[code].add((kind, cert))
        for cert, ref, version, cnpj, pct, url, sha, _ in cvm.execute(DEBTORS.format(kind=kind)):
            debtors[(kind, cert)].append((ref, version, cnpj, pct, url, sha))
    cvm.close()

    rows, outcome, private = [], Counter(), Counter()
    for cetip, isin, kind, debtor, known in assets:
        certificates = by_code.get(cetip.upper(), set()) | by_code.get(isin, set())
        if not certificates:
            outcome["sem certificado na CVM"] += 1
            continue
        if len(certificates) > 1:
            outcome["mais de um certificado (não escolhido)"] += 1
            continue
        key = next(iter(certificates))
        found = debtors.get(key, [])
        if not found:
            outcome["certificado sem devedor informado"] += 1
            continue
        valid = []
        for ref, version, raw, pct, url, sha in found:
            kind_id, digits = classify_identifier(raw)
            if digits:
                valid.append((ref, version, digits, kind_id, pct, url, sha))
            else:
                private[kind_id] += 1
        cnpjs = {v[2] for v in valid}
        outcome["um CNPJ" if len(cnpjs) == 1 else "vários CNPJs (pulverizado)" if cnpjs else "só CPF, inválido ou não informado"] += 1
        for ref, version, digits, kind_id, pct, url, sha in valid:
            rows.append({"codigo_cetip": cetip, "isin": isin, "tipo": kind, "devedor_catalogo": debtor,
                         "certificado_cvm": f"{key[0]}:{key[1]}", "competencia": ref[:7], "versao": version,
                         "cnpj_devedor": format_cnpj(digits), "identificador": kind_id, "percentual": pct or "",
                         "devedores_no_informe": len(found), "fonte": url, "sha256": sha})
    rows.sort(key=lambda r: (r["codigo_cetip"], r["cnpj_devedor"]))
    with (ROOT / "reports" / "cnpj_devedor_cvm.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    already = sum(1 for a in assets if a[4])
    lines = ["# CNPJ do devedor pelo Informe Mensal da CVM", "",
             "Liga cada ativo do catálogo ao certificado do Informe Mensal (CETIP ou ISIN da série) e lê os devedores da última "
             "competência e versão informadas. Só leitura: nada foi gravado no cadastro. CPF e identificador inválido não "
             "saem no relatório, só na contagem. O dado é o que a securitizadora informou à CVM (erros vêm junto).", "",
             f"Ativos no catálogo: **{len(assets)}**; com CNPJ do devedor no cadastro: **{already}**; "
             f"linhas no CSV: **{len(rows)}** ({len({r['codigo_cetip'] for r in rows})} ativos).", "",
             "| Resultado por ativo | Ativos |", "|---|---|", *[f"| {k} | {v} |" for k, v in outcome.most_common()], "",
             "| Identificadores fora do relatório | Linhas |", "|---|---|", *[f"| {k} | {v} |" for k, v in private.most_common()], "",
             "Ativo com um CNPJ é candidato direto para a camada compartilhada preencher o devedor (com a fonte). Ativo "
             "pulverizado (carteira com muitos devedores) não tem \"o\" devedor: o cadastro deve ficar vazio ou indicar a "
             "carteira. Ativo ligado a mais de um certificado não foi escolhido (conflito de identificador bloqueia)."]
    (ROOT / "reports" / "cnpj_devedor_cvm.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print({"ativos": len(assets), **outcome, "linhas": len(rows)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
