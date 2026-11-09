import hashlib
import io
import zipfile
from collections import Counter

import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio_cadastro import csv_bytes
from apoio_cadastro import fake_cnpj
from apoio_cadastro import fake_cnpj_with_leading_zero
from apoio_cadastro import masked
from apoio_cadastro import write_zip
from apoio_informe_fiagro import ADMIN_CNPJ
from apoio_informe_fiagro import ADMIN_NAME
from apoio_informe_fiagro import COMPETENCE
from apoio_informe_fiagro import CONTACTS
from apoio_informe_fiagro import DATA_REFERENCIA
from apoio_informe_fiagro import FIRST_SUBCLASS
from apoio_informe_fiagro import FIRST_SUBCLASS_NO_SPACE
from apoio_informe_fiagro import MANAGER_CNPJ
from apoio_informe_fiagro import MANAGER_NAME
from apoio_informe_fiagro import SECOND_SUBCLASS
from apoio_informe_fiagro import ZIP_NAME
from apoio_informe_fiagro import build_informe_zip
from apoio_informe_fiagro import class_row
from apoio_informe_fiagro import fake_isin
from apoio_informe_fiagro import merge
from apoio_informe_fiagro import subclass_row
from apoio_informe_fiagro import subject_name
from apoio_informe_fiagro import subject_rows
from fundos.informe_fiagro import columns
from fundos.informe_fiagro.reader import InformeFormatError
from fundos.informe_fiagro.reader import read_informe_bytes
from fundos.informe_fiagro.reader import read_informe_zip
from fundos.informe_fiagro.report import format_read_report
from fundos.personal_data import FORBIDDEN_COLUMNS
from fundos.repositories.observation_repository import FIELD_NAME


CLASS = columns.CLASS_TABLE
SUBCLASS = columns.SUBCLASS_TABLE


def read(data=None, name=ZIP_NAME, **options):
    return read_informe_bytes(
        build_informe_zip() if data is None else data,
        name,
        **options,
    )


def first(informe, table):
    return next(informe.rows(table))


def with_rows(**files):
    tables = subject_rows()
    tables.update(files)
    return build_informe_zip(tables)


def test_column_list_follows_the_header_of_the_data():
    # 133 e 6 campos no dado de 09/2026 (docs/fundos-descoberta.md, secao 9.2).
    assert columns.TABLES == (CLASS, SUBCLASS)
    assert {table: len(header) for table, header in columns.HEADERS.items()} == {CLASS: 133, SUBCLASS: 6}
    assert columns.HEADERS[CLASS][:5] == ("CNPJ_Classe", "Nome_Classe", "Data_Referencia", "Data_Entrega", "Versao")
    assert columns.HEADERS[CLASS][-1] == "Total_Passivo"
    assert columns.HEADERS[SUBCLASS] == (
        "CNPJ_Classe", "Nome_Classe", "Data_Referencia", "Nome_Subclasse", "Numero_Cotas", "Valor_Patrimonial_Cota",
    )
    # O dicionario trunca este nome; a lista segue o cabecalho do dado.
    assert "Numero_Cotistas_Entidade_Previdencia_Complementar_Exceto_RPPS" in columns.HEADERS[CLASS]

    for header in columns.HEADERS.values():
        assert len(header) == len(set(header))

    assert Counter(columns.KINDS[CLASS].values()) == {
        columns.KEY: 2,
        columns.NAME: 1,
        columns.EXCLUDED: 4,
        columns.PARTY_ID: 2,
        columns.PARTY_NAME: 2,
        "text": 7,
        "date": 2,
        "boolean": 2,
        "numeric": 111,
    }
    observed = [kind for kind in columns.KINDS[CLASS].values() if kind in columns.VALUE_TYPE]
    assert len(observed) == 123
    assert Counter(columns.KINDS[SUBCLASS].values()) == {
        columns.KEY: 2, columns.NAME: 1, columns.SERIES_LABEL: 1, "numeric": 2,
    }


def test_contact_and_entity_columns_are_excluded():
    excluded = {column for column, kind in columns.KINDS[CLASS].items() if kind == columns.EXCLUDED}

    assert excluded == {"Email_Administrador", "Site", "Servico_Atendimento_Cotista", "Entidade_Administradora"}
    assert excluded == FORBIDDEN_COLUMNS & set(columns.HEADERS[CLASS])
    assert not any(kind == columns.EXCLUDED for kind in columns.KINDS[SUBCLASS].values())

    for role, id_column, name_column in columns.PARTIES:
        assert "cnpj" in id_column.lower()
        assert "cnpj" not in name_column.lower() and "cpf" not in name_column.lower()

    # Nenhuma coluna que vira observacao tem cpf ou cnpj no nome.
    for table, kinds in columns.KINDS.items():
        for column, kind in kinds.items():
            if kind in columns.VALUE_TYPE:
                assert "cpf" not in column.lower() and "cnpj" not in column.lower()


def test_field_and_member_names_do_not_mix_with_fidc():
    assert columns.field_name(CLASS, "Patrimonio_Liquido") == "inf_mensal_fiagro.Patrimonio_Liquido"
    assert columns.field_name(SUBCLASS, "Numero_Cotas") == "inf_mensal_fiagro_subclasse.Numero_Cotas"
    assert columns.member_name(CLASS, "202609") == "inf_mensal_fiagro_202609.csv"
    assert columns.member_name(SUBCLASS, "202609") == "inf_mensal_fiagro_subclasse_202609.csv"

    for table, header in columns.HEADERS.items():
        for column in header:
            assert FIELD_NAME.fullmatch(columns.field_name(table, column))
            assert not columns.field_name(table, column).startswith("tab_")


def test_reads_the_two_members_and_the_competence():
    data = build_informe_zip()
    informe = read(data)

    assert informe.zip.sha256 == hashlib.sha256(data).hexdigest()
    assert informe.zip.period == "202609"
    assert informe.zip.member_dates == ("2026-10-24",)
    assert informe.reference == DATA_REFERENCIA
    assert informe.competence == COMPETENCE
    assert [m.file_name for m in informe.members] == [
        "inf_mensal_fiagro_202609.csv",
        "inf_mensal_fiagro_subclasse_202609.csv",
    ]
    assert [(m.line_count, m.column_count) for m in informe.members] == [(1, 133), (2, 6)]

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in informe.members:
            raw = archive.read(member.file_name)
            assert member.sha256 == hashlib.sha256(raw).hexdigest()
            assert member.size_bytes == len(raw)


def test_class_row_is_normalized_and_keys_are_not_values():
    row = first(read(), CLASS)

    assert row.cnpj == fake_cnpj(1)
    assert row.reference == DATA_REFERENCIA
    assert row.name == subject_name(1)
    assert row.values["Nome_Classe"] == subject_name(1)
    assert row.values["Versao"] == "1"
    assert row.values["Data_Entrega"] == "2026-10-15"
    assert row.values["Classe_Unica"] is False
    assert row.values["Patrimonio_Liquido"] == "1000.5"
    assert row.values["Valor_Ativo"] == "1200"
    assert row.values["Numero_Cotistas"] == "10"
    assert row.values["LCA"] == "0"
    assert row.values["Codigo_ISIN"] == fake_isin(1)
    assert row.values["Encerramento_Exercicio_Social"] == "31/12"
    # Vazio nao vira valor; o resto das 123 colunas vira.
    assert "Classificacao_Autorregulada" not in row.values
    assert len(row.values) == 122

    for column, kind in columns.KINDS[CLASS].items():
        if kind in (columns.KEY, columns.EXCLUDED, columns.PARTY_ID, columns.PARTY_NAME):
            assert column not in row.values

    assert [(p.role, p.field_name, p.cnpj, p.name_field_name, p.name) for p in row.parties] == [
        ("administrador", "inf_mensal_fiagro.CNPJ_Administrador", ADMIN_CNPJ, "inf_mensal_fiagro.Nome_Administrador", ADMIN_NAME),
        ("gestor", "inf_mensal_fiagro.CNPJ_Gestor", MANAGER_CNPJ, "inf_mensal_fiagro.Nome_Gestor", MANAGER_NAME),
    ]


def test_subclass_rows_keep_the_label_and_only_check_the_class_name():
    rows = list(read().rows(SUBCLASS))

    assert [row.series_label for row in rows] == [FIRST_SUBCLASS, SECOND_SUBCLASS]
    assert [row.series_key for row in rows] == ["subclasse 1 (ou classe unica)", "subclasse 2"]
    assert rows[0].name == subject_name(1)
    assert rows[0].values == {
        "Nome_Subclasse": FIRST_SUBCLASS,
        "Numero_Cotas": "100",
        "Valor_Patrimonial_Cota": "10.005",
    }
    assert rows[0].parties == ()


def test_contact_columns_never_leave_the_reader_and_repr_shows_nothing():
    informe = read()

    for table in columns.TABLES:
        for row in informe.rows(table):
            text = repr(row)
            stored = [str(value) for value in row.values.values()]
            stored += [str(p.name) for p in row.parties]

            for value in CONTACTS.values():
                assert value not in stored
                assert value not in text

            for secret in (fake_cnpj(1), ADMIN_CNPJ, MANAGER_CNPJ, ADMIN_NAME, subject_name(1), fake_isin(1), "1000.5"):
                assert secret not in text

            for party in row.parties:
                assert party.cnpj not in repr(party)

    assert fake_cnpj(1) not in repr(informe)


def _member_with_header(table, change):
    header = list(columns.HEADERS[table])

    if change == "faltando":
        header.pop(5)
    elif change == "a mais":
        header.append("Coluna_Nova")
    elif change == "fora de ordem":
        header[3], header[4] = header[4], header[3]
    elif change == "repetida":
        header[-1] = header[-2]

    return {table: csv_bytes(header, [])}


@pytest.mark.parametrize("table", (CLASS, SUBCLASS))
@pytest.mark.parametrize("change", ("faltando", "a mais", "fora de ordem", "repetida"))
def test_header_different_from_the_closed_list_is_refused(table, change):
    with pytest.raises(InformeFormatError, match="Cabecalho de " + table + "_202609.csv diferente"):
        read(build_informe_zip(members=_member_with_header(table, change)))


@pytest.mark.parametrize(
    ("options", "message"),
    (
        ({"drop": (SUBCLASS,)}, "faltam inf_mensal_fiagro_subclasse"),
        ({"extra": {"leia-me.txt": b"x"}}, "1 membro"),
        (
            {"drop": (SUBCLASS,), "extra": {"inf_mensal_fiagro_subclasse_202608.csv": b"x"}},
            "AAAAMM diferente entre os membros",
        ),
    ),
)
def test_members_must_be_exactly_the_two(options, message):
    with pytest.raises(InformeFormatError, match=message):
        read(build_informe_zip(**options))


def test_zip_name_must_match_the_period_when_it_follows_the_pattern():
    data = build_informe_zip()

    with pytest.raises(InformeFormatError, match="nome do ZIP"):
        read(data, name="inf_mensal_fiagro_202608.zip")

    # Fora do padrao, vale o AAAAMM dos membros (como no FIDC).
    assert read(data, name="copia do informe.zip").zip.period == "202609"


@pytest.mark.parametrize(
    ("tables", "message"),
    (
        (subject_rows(**{"Data_Referencia": "2026-09-30"}), "2 valores diferentes"),
        (
            {
                CLASS: [class_row(Data_Referencia="2026-09-30")],
                SUBCLASS: [subclass_row(Data_Referencia="2026-09-30")],
            },
            "nao e o dia 1 do AAAAMM",
        ),
        (
            {
                CLASS: [class_row(Data_Referencia="2026-08-01")],
                SUBCLASS: [subclass_row(Data_Referencia="2026-08-01")],
            },
            "nao e o dia 1 do AAAAMM",
        ),
        (
            {CLASS: [class_row()], SUBCLASS: [subclass_row(Data_Referencia="2026-09-02")]},
            "2 valores diferentes",
        ),
        (merge(subject_rows(1), subject_rows(2, Data_Referencia="2026-10-01")), "2 valores diferentes"),
        ({CLASS: [class_row(Data_Referencia="01/09/2026")], SUBCLASS: []}, "coluna Data_Referencia: valor fora do formato date"),
    ),
)
def test_data_referencia_must_be_one_value_on_day_one(tables, message):
    with pytest.raises(InformeFormatError, match=message):
        read(build_informe_zip(tables))


@pytest.mark.parametrize(
    ("period", "competence"),
    (("202609", "2026-09-30"), ("202602", "2026-02-28"), ("202402", "2024-02-29"), ("202512", "2025-12-31")),
)
def test_competence_is_the_last_day_of_the_month(period, competence):
    reference = period[:4] + "-" + period[4:] + "-01"
    tables = {
        CLASS: [class_row(Data_Referencia=reference)],
        SUBCLASS: [subclass_row(Data_Referencia=reference)],
    }
    informe = read(build_informe_zip(tables, period=period), name="inf_mensal_fiagro_" + period + ".zip")

    assert (informe.reference, informe.competence) == (reference, competence)


def test_competence_in_the_future_is_refused():
    tables = {
        CLASS: [class_row(Data_Referencia="2099-12-01")],
        SUBCLASS: [subclass_row(Data_Referencia="2099-12-01")],
    }

    with pytest.raises(InformeFormatError, match="2099-12-31 .* posterior a hoje"):
        read(build_informe_zip(tables, period="209912"), name="inf_mensal_fiagro_209912.zip")


@pytest.mark.parametrize(("second_version", "different"), (("1", 0), ("2", 1)))
def test_repeated_key_is_marked_and_counted(second_version, different):
    tables = merge(
        subject_rows(1),
        subject_rows(1, labels=(FIRST_SUBCLASS,), Nome_Classe="FIAGRO Exemplo 1B (ficticio)", Versao=second_version),
        subject_rows(2),
    )
    informe = read(build_informe_zip(tables))
    counts = informe.counts

    assert informe.repeated_keys == {fake_cnpj(1)}
    assert informe.class_keys == {fake_cnpj(1), fake_cnpj(2)}
    assert counts[("chaves", "distintas")] == 2
    assert counts[("chaves", "repetidas")] == 1
    assert counts[("chaves", "linhas_repetidas")] == 2
    assert counts[("chaves", "repetidas_com_versao_diferente")] == different
    assert counts[("subclasse", "de_chave_repetida")] == 3
    # O par repetido esta dentro da chave repetida.
    assert counts[("subclasse", "pares_repetidos")] == 1
    assert counts[("subclasse", "linhas_de_pares_repetidos")] == 2
    assert counts[("subclasse", "pares_repetidos_fora_das_chaves_repetidas")] == 0


def test_version_and_delivery_are_counted_with_fixed_labels():
    tables = merge(
        subject_rows(1),
        subject_rows(2, Versao="2", Data_Entrega="2026-10-16"),
        subject_rows(3, Versao=""),
    )
    counts = read(build_informe_zip(tables)).counts

    assert counts[("versao", "igual_a_1")] == 1
    assert counts[("versao", "diferente_de_1")] == 1
    assert counts[("versao", "vazia")] == 1
    assert counts[("data_entrega", "distintas")] == 2


def test_isin_is_counted_and_is_not_a_key():
    tables = merge(
        subject_rows(1, Codigo_ISIN=""),
        subject_rows(2, Codigo_ISIN=fake_isin(7)),
        subject_rows(3, Codigo_ISIN=fake_isin(7)),
        subject_rows(4),
    )
    informe = read(build_informe_zip(tables))
    rows = list(informe.rows(CLASS))

    assert "Codigo_ISIN" not in rows[0].values
    assert rows[1].values["Codigo_ISIN"] == rows[2].values["Codigo_ISIN"] == fake_isin(7)
    assert informe.counts[("isin", "vazio")] == 1
    assert informe.counts[("isin", "preenchido")] == 3
    assert informe.counts[("isin", "distintos")] == 2
    assert informe.counts[("isin", "em_varias_classes")] == 1
    assert informe.repeated_keys == frozenset()


def test_two_spellings_of_the_first_subclass_are_different_keys():
    tables = merge(
        subject_rows(1, labels=(FIRST_SUBCLASS,)),
        subject_rows(2, labels=(FIRST_SUBCLASS_NO_SPACE,)),
        subject_rows(3, labels=(FIRST_SUBCLASS, FIRST_SUBCLASS_NO_SPACE)),
    )
    informe = read(build_informe_zip(tables))
    keys = {(row.cnpj, row.series_key) for row in informe.rows(SUBCLASS)}

    assert keys == {
        (fake_cnpj(1), "subclasse 1 (ou classe unica)"),
        (fake_cnpj(2), "subclasse 1(ou classe unica)"),
        (fake_cnpj(3), "subclasse 1 (ou classe unica)"),
        (fake_cnpj(3), "subclasse 1(ou classe unica)"),
    }
    assert informe.counts[("rotulos", "distintos")] == 2
    assert informe.counts[("rotulos", "normalizados_distintos")] == 2
    assert informe.counts[("subclasse", "pares_repetidos")] == 0


def test_repeated_subclass_pair_is_marked_after_normalizing():
    tables = subject_rows(1, labels=(FIRST_SUBCLASS, SECOND_SUBCLASS, "Subclasse  2 |"))
    informe = read(build_informe_zip(tables))
    counts = informe.counts

    assert informe.repeated_series == {(fake_cnpj(1), "subclasse 2")}
    assert counts[("subclasse", "pares_repetidos")] == 1
    assert counts[("subclasse", "linhas_de_pares_repetidos")] == 2
    assert counts[("subclasse", "pares_repetidos_fora_das_chaves_repetidas")] == 1
    assert counts[("subclasse", "linhas_de_pares_repetidos_fora_das_chaves_repetidas")] == 2
    assert counts[("rotulos", "distintos")] == 3
    assert counts[("rotulos", "normalizados_distintos")] == 2


def test_subclass_without_class_row_empty_label_and_name_divergence_are_counted():
    data = with_rows(
        **{
            SUBCLASS: [
                subclass_row(1),
                subclass_row(5),
                subclass_row(1, label=" | "),
                subclass_row(1, label=SECOND_SUBCLASS, Nome_Classe="Outro Nome (ficticio)"),
            ]
        }
    )
    counts = read(data).counts

    assert counts[("subclasse", "sem_classe_no_arquivo")] == 1
    assert counts[("subclasse", "nome_classe_divergente")] == 1
    assert counts[("rotulo_vazio", SUBCLASS)] == 1


@pytest.mark.parametrize("role, id_column, name_column", columns.PARTIES)
@pytest.mark.parametrize(
    ("value", "status", "expected"),
    (
        (FAKE_CPF, "cpf", None),
        (FAKE_CPF_MASKED, "cpf", None),
        (masked(fake_cnpj(803)), "cnpj", fake_cnpj(803)),
        (fake_cnpj_with_leading_zero(5)[1:], "cnpj", fake_cnpj_with_leading_zero(5)),
        ("", "vazio", None),
        ("12345", "invalido", None),
    ),
)
def test_party_identifier_only_keeps_a_valid_cnpj(role, id_column, name_column, value, status, expected):
    informe = read(with_rows(**{CLASS: [class_row(**{id_column: value})]}))
    row = first(informe, CLASS)
    kept = {p.role: p for p in row.parties}
    id_field = columns.field_name(CLASS, id_column)

    assert informe.counts[("identificador", id_field, status)] == 1

    if expected is None:
        assert role not in kept
        assert informe.counts[("nome_descartado", columns.field_name(CLASS, name_column))] == 1
        assert FAKE_CPF not in repr(row)
    else:
        assert kept[role].cnpj == expected
        assert kept[role].name is not None


@pytest.mark.parametrize(("value", "status"), ((FAKE_CPF, "cpf"), ("12345", "invalido"), ("", "vazio")))
def test_class_cnpj_that_is_not_a_cnpj_is_counted(value, status):
    tables = {CLASS: [class_row(CNPJ_Classe=value)], SUBCLASS: [subclass_row(CNPJ_Classe=value)]}
    informe = read(build_informe_zip(tables))

    assert first(informe, CLASS).cnpj is None
    assert informe.class_keys == frozenset()
    assert informe.counts[("cnpj_classe", CLASS, status)] == 1
    assert informe.counts[("cnpj_classe", SUBCLASS, status)] == 1


def test_scientific_notation_is_converted_exactly_and_counted():
    data = build_informe_zip(
        {
            CLASS: [class_row(Patrimonio_Liquido="1.5e+3", Valor_Ativo="2E-2")],
            SUBCLASS: [subclass_row(Numero_Cotas="12E2")],
        }
    )
    informe = read(data)
    row = first(informe, CLASS)

    assert row.values["Patrimonio_Liquido"] == "1500"
    assert row.values["Valor_Ativo"] == "0.02"
    assert first(informe, SUBCLASS).values["Numero_Cotas"] == "1200"
    assert informe.counts[("notacao_cientifica", "inf_mensal_fiagro.Patrimonio_Liquido")] == 1
    assert informe.counts[("notacao_cientifica", "inf_mensal_fiagro.Valor_Ativo")] == 1
    assert informe.counts[("notacao_cientifica", "inf_mensal_fiagro_subclasse.Numero_Cotas")] == 1


@pytest.mark.parametrize(
    ("table", "column", "value", "kind"),
    (
        (CLASS, "Patrimonio_Liquido", "1,5", "numeric"),
        (CLASS, "Versao", "1e400", "numeric"),
        (CLASS, "Data_Entrega", "15/10/2026", "date"),
        (CLASS, "Classe_Unica", "Sim", "boolean"),
        (SUBCLASS, "Valor_Patrimonial_Cota", "abc", "numeric"),
    ),
)
def test_value_out_of_format_aborts_without_showing_it(table, column, value, kind):
    rows = {CLASS: [class_row()], SUBCLASS: [subclass_row()]}
    rows[table] = [(class_row if table == CLASS else subclass_row)(**{column: value})]

    with pytest.raises(InformeFormatError) as error:
        read(build_informe_zip(rows))

    message = str(error.value)
    assert table + "_202609.csv, linha 2, coluna " + column + ": valor fora do formato " + kind in message
    assert value not in message


def test_cp1252_text_is_read_and_other_bytes_are_refused():
    name = "FIAGRO Agroneg\u00f3cio n\u00ba 1 (fict\u00edcio)"
    rule = "ANEXO NORMATIVO II \u2013 aplic\u00e1vel (ficticio)"
    informe = read(with_rows(**{CLASS: [class_row(Nome_Classe=name, Regra_Anexo=rule)]}))
    row = first(informe, CLASS)

    assert row.values["Nome_Classe"] == name
    assert row.values["Regra_Anexo"] == rule

    raw = csv_bytes(columns.HEADERS[CLASS], [class_row()]).replace(b"(ficticio)", b"(fict\x81cio)")

    with pytest.raises(InformeFormatError, match="nao decodifica como cp1252"):
        read(build_informe_zip(members={CLASS: raw}))


def test_free_text_and_names_are_kept_as_they_come():
    row = first(
        read(with_rows(**{CLASS: [class_row(Prazo_Duracao=" 99 ANOS ", Nome_Gestor=" Gestora Ficticia ")]})),
        CLASS,
    )

    assert row.values["Prazo_Duracao"] == " 99 ANOS "
    assert {p.role: p.name for p in row.parties}["gestor"] == " Gestora Ficticia "


def test_line_with_wrong_width_is_refused():
    header = columns.HEADERS[SUBCLASS]
    raw = (";".join(header) + "\r\n" + ";".join(["x"] * (len(header) - 1)) + "\r\n").encode("cp1252")

    with pytest.raises(InformeFormatError, match="linha 2: 5 campo"):
        read(build_informe_zip(members={SUBCLASS: raw}))


def test_member_size_limit_and_progress():
    seen = []
    read(progress=lambda table, lines: seen.append((table, lines)))

    assert seen == [(CLASS, 1), (SUBCLASS, 2)]

    with pytest.raises(InformeFormatError, match="passa do limite"):
        read(max_member_bytes=10)


def test_read_report_has_only_aggregates():
    tables = merge(subject_rows(1), subject_rows(1, labels=(FIRST_SUBCLASS,)), subject_rows(2))
    text = "\n".join(format_read_report(read(build_informe_zip(tables))))

    assert "Competencia: AAAAMM 202609; Data_Referencia 2026-09-01 (dia 1, nos 2 arquivos); gravada como 2026-09-30" in text
    assert "inf_mensal_fiagro: 3 linha(s), 133 coluna(s)" in text
    assert "repetidos 1 (2 linhas; com Versao diferente 0)" in text
    assert "Entidade_Administradora, Email_Administrador, Servico_Atendimento_Cotista, Site" in text

    for secret in (
        fake_cnpj(1), fake_cnpj(2), ADMIN_CNPJ, MANAGER_CNPJ, ADMIN_NAME, MANAGER_NAME,
        subject_name(1), fake_isin(1), FIRST_SUBCLASS, "1000.5", *CONTACTS.values(),
    ):
        assert secret not in text


def test_reads_from_disk_and_refuses_missing_or_bad_files(tmp_path):
    path = write_zip(tmp_path, build_informe_zip(), name=ZIP_NAME)

    assert read_informe_zip(path).competence == COMPETENCE

    with pytest.raises(FileNotFoundError):
        read_informe_zip(tmp_path / "nao_existe.zip")

    bad = write_zip(tmp_path, b"nao e zip", name="ruim.zip")

    with pytest.raises(InformeFormatError, match="nao e um ZIP valido"):
        read_informe_zip(bad)
