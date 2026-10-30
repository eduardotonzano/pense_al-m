from __future__ import annotations

import re

from credit_assets.contract_sheet import excerpt_at, field_excerpts, is_definition, is_toc_page

PATTERNS = [re.compile(r"Data de Vencimento", re.IGNORECASE)]
TOC = "\n".join(f"{i}. Cláusula {i} ........ {i * 3}" for i in range(1, 7)) + "\nData de Vencimento ........ 20"
DEFINITION_PAGE = "1.1 Definições\n“Data de Vencimento”: 15 de outubro de 2030.\nOutra linha"
CLAUSE_PAGE = ("3.4 A Data de Vencimento dos CRA será 15 de outubro de 2030,\n"
               "ressalvadas as hipóteses de resgate.\nNa Data de Vencimento serão pagos o saldo e a remuneração.")


def test_is_definition_needs_quotes_and_colon_or_meaning():
    line = "“Data de Vencimento”: 15 de outubro de 2030."
    m = PATTERNS[0].search(line)
    assert is_definition(line, m.start(), m.end())
    line = '"Data de Vencimento Final" significa a data de 15/10/2030'
    m = PATTERNS[0].search(line)
    assert is_definition(line, m.start(), m.end())
    line = "A Data de Vencimento dos CRA será 15 de outubro de 2030"
    m = PATTERNS[0].search(line)
    assert not is_definition(line, m.start(), m.end())
    quoted = re.compile(r"[“\"]Devedora?[”\"]")
    line = "“Devedora”: a Café Brasil Ltda."
    m = quoted.search(line)
    assert is_definition(line, m.start(), m.end())


def test_toc_page_and_excerpt_cleanup():
    assert is_toc_page(TOC) and not is_toc_page(CLAUSE_PAGE)
    assert excerpt_at("a\n   b    c  \n\nd", 1, before=1, after=1) == "a b c"
    assert excerpt_at("x" * 1000, 0, limit=50).endswith("…") and len(excerpt_at("x" * 1000, 0, limit=50)) == 50


def test_field_excerpts_picks_definition_from_latest_document_and_densest_clause_outside_toc():
    documents = [
        ("100", [(1, TOC, False), (2, DEFINITION_PAGE, False), (9, CLAUSE_PAGE, False)]),
        ("200", [(1, DEFINITION_PAGE.replace("2030", "2031"), True), (5, "sem o campo", False)]),
    ]
    result = field_excerpts(documents, PATTERNS)
    definition, clause = result.excerpts
    assert (definition.kind, definition.document, definition.page, definition.ocr) == ("definicao", "200", 1, True)
    assert "2031" in definition.text and definition.line == 2 and definition.pages == (1, 1)
    assert (clause.kind, clause.document, clause.page, clause.line, clause.pages) == ("clausula", "100", 9, 1, (9, 9))
    assert result.other_pages == (("100", 1), ("100", 2)) and result.total_pages == 4


def test_clause_extends_to_neighbour_pages_and_annexes_are_listed_apart():
    from credit_assets.contract_sheet import annex_start
    body = [(n, "Vencimento Antecipado" * (3 if n == 12 else 1), False) for n in (10, 11, 12, 13, 20)]
    annex = [(30, "ANEXO III\nCronograma", False)] + [(31, "Vencimento Antecipado " * 9, False)]
    pages = [(1, "capa", False)] + body + annex
    assert annex_start(pages) == 30
    result = field_excerpts([("7", pages)], [re.compile("Vencimento Antecipado")])
    (clause,) = result.excerpts
    assert clause.page == 12 and clause.pages == (10, 13)  # a página do anexo tem mais menções, mas o corpo vem primeiro
    assert result.other_pages == (("7", 20),) and result.annex_pages == (("7", 31),)


def test_field_only_in_annex_uses_annex():
    pages = [(1, "capa", False), (5, "ANEXO I\nCronograma de Pagamentos", False)]
    (clause,) = field_excerpts([("7", pages)], [re.compile("Cronograma de Pagamentos")]).excerpts
    assert clause.page == 5


def test_field_without_hits_returns_empty():
    result = field_excerpts([("1", [(1, "nada aqui", False)])], PATTERNS)
    assert result.excerpts == () and result.total_pages == 0


def test_value_variants_by_unit():
    from credit_assets.contract_sheet import value_variants
    assert value_variants("2030-12-18", "data") == ["18/12/2030", "18 de dezembro de 2030"]
    assert value_variants("2027-03-01", "data") == ["01/03/2027", "1 de marco de 2027", "01 de marco de 2027", "1o de marco de 2027"]
    assert value_variants("65000000.00", "BRL") == ["65.000.000,00", "r$ 65.000.000"]
    assert value_variants("233142", "CRA") == ["233.142"]
    assert value_variants("0.1480", "fração a.a. (base 252)") == ["14,8%", "14,80%"]
    assert value_variants("1.0800", "fração da Taxa DI") == ["108%", "108,00%", "108,0%"]
    assert value_variants("0.0150", "fração a.a. sobre DI") == ["1,5%", "1,50%"]
    assert value_variants("30", "dias") == [] and value_variants("SIM", "texto") == [] and value_variants("1.20", "razão") == []


# layout real (Termo do CRA02500C1D, p. 11): o termo sai algumas linhas acima do próprio significado
GLOSSARY = "\n".join([
    "                       dezembro de 2035, ressalvadas as hipóteses de Eventos de Liquidação;",
    "“Data de               ",
    "Verificação dos        ",
    "Índices Financeiros”   ",
    "“Despesas”             Tem o significado que lhe é atribuído na Cláusula 7.2.3 deste Termo de",
    "                       Securitização.",
    "“Destinação dos        ",
    "Recursos”              ",
    "“Devedora”             Significa as despesas da Emissão e da Oferta dos CRA, que deverão ser",
    "                       pagas com os recursos do Fundo de Despesas;",
    "“Dia Útil” ou “Dias    Tem o significado que lhe é atribuído na Cláusula Quinta deste Termo de",
    "Úteis”                 Securitização.",
    "                       Significa a ALIBEM ALIMENTOS S.A., sociedade por ações",
    "                       Significa qualquer dia que não seja sábado ou domingo.",
])


def test_two_column_glossary_pairs_terms_and_meanings_by_order():
    from credit_assets.contract_sheet import is_glossary_page, two_column_definition
    assert is_glossary_page(GLOSSARY) and not is_glossary_page(CLAUSE_PAGE)
    lines = GLOSSARY.splitlines()
    index = next(i for i, line in enumerate(lines) if "Devedora" in line)
    text = two_column_definition(GLOSSARY, index, lines[index].index("“"))
    assert text == "“Devedora”: Significa a ALIBEM ALIMENTOS S.A., sociedade por ações"
    index = next(i for i, line in enumerate(lines) if "Destinação" in line)
    assert two_column_definition(GLOSSARY, index, 0).startswith("“Destinação dos Recursos”: Tem o significado")
    assert two_column_definition("“Devedora”: a Café Brasil Ltda.", 0, 0) is None  # uma coluna só


def test_glossary_page_does_not_win_the_clause():
    pattern = [re.compile(r"[“\"]Devedora?[”\"]|\bDevedora\b")]
    body = "8.1 Obrigações da Devedora. A Devedora deverá manter seus registros."
    (definition, clause) = field_excerpts([("1", [(2, GLOSSARY, False), (40, body, False)])], pattern).excerpts
    assert definition.page == 2 and definition.text.startswith("“Devedora”: Significa a ALIBEM")
    assert clause.page == 40


def test_annex_pages_return_to_body_inside_consolidated_termo():
    from credit_assets.contract_sheet import annex_pages
    pages = [(1, "PRIMEIRO ADITAMENTO", False), (18, "ANEXO A\nANEXO II - CARACTERÍSTICAS", False),
             (26, "ANEXO B\nDECLARAÇÃO", False), (28, "ANEXO D\nTERMO DE SECURITIZAÇÃO CONSOLIDADO", False),
             (60, "Cláusula 6", False), (153, "ANEXO I\nAo “Termo de Securitização de Direitos Creditórios”", False),
             (160, "cronograma", False)]
    assert annex_pages(pages) == {18, 26, 153, 160}


def test_consolidated_termo_annex_of_an_amendment_is_body_text():
    from credit_assets.contract_sheet import annex_start
    pages = [(1, "PRIMEIRO ADITAMENTO", False), (5, "x", False),
             (8, "ANEXO A\nTERMO DE SECURITIZAÇÃO CONSOLIDADO", False), (9, "Cláusula 1", False),
             (40, "ANEXO I\nDESCRIÇÃO DOS CRÉDITOS", False)]
    assert annex_start(pages) == 40
    assert annex_start([(1, "x", False), (6, "ANEXO A\nREDAÇÃO ATUALIZADA DO ANEXO I AO TERMO DE SECURITIZAÇÃO", False)]) == 6
