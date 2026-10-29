from apoio import FAKE_CPF
from apoio_cadastro import FIAGRO_CLASS
from apoio_cadastro import PF_MANAGER_NAME
from apoio_cadastro import build_zip
from apoio_cadastro import class_row
from apoio_cadastro import fake_cnpj
from apoio_cadastro import fund_row
from apoio_cadastro import pf_manager_row
from fundos.cadastro.reader import read_cadastro_bytes
from fundos.cadastro.report import format_selection_report
from fundos.cadastro.selection import select_fidc_fiagro


CANCELLED = {"Situacao": "Cancelado", "Data_Cancelamento": "2024-05-02"}


def select(fund_rows, class_rows=None):
    cadastro = read_cadastro_bytes(
        build_zip(fund_rows, [] if class_rows is None else class_rows),
        "registro_fundo_classe.zip",
    )
    return select_fidc_fiagro(cadastro)


def registros(selection):
    return [(s.registro_id, s.cnpj) for s in selection.funds]


def out(selection, table, reason):
    return selection.counts[("fora", table, reason)]


def test_non_cancelled_registro_wins():
    selection = select(
        [
            fund_row(ID_Registro_Fundo="1", Data_Inicio_Situacao="2024-05-02", **CANCELLED),
            fund_row(ID_Registro_Fundo="2", Data_Inicio_Situacao="2020-01-02"),
        ]
    )

    assert registros(selection) == [("2", fake_cnpj(1))]
    assert selection.funds[0].cancelled is False


def test_most_recent_situation_date_breaks_the_tie_between_cancelled():
    selection = select(
        [
            fund_row(ID_Registro_Fundo="1", Data_Inicio_Situacao="2023-01-02", **CANCELLED),
            fund_row(ID_Registro_Fundo="2", Data_Inicio_Situacao="2024-05-02", **CANCELLED),
        ]
    )

    assert registros(selection) == [("2", fake_cnpj(1))]
    assert selection.funds[0].cancelled is True
    assert selection.counts[("vigentes", "registro_fundo", "FIDC", "cancelado")] == 1


def test_remaining_tie_is_unresolved_and_left_out():
    selection = select(
        [
            fund_row(ID_Registro_Fundo="1", Data_Inicio_Situacao="2024-05-02", **CANCELLED),
            fund_row(ID_Registro_Fundo="2", Tipo_Fundo="FI", Data_Inicio_Situacao="2024-05-02", **CANCELLED),
        ],
        [class_row()],
    )

    assert selection.funds == ()
    assert selection.classes == ()
    assert out(selection, "registro_fundo", "empate") == 1
    assert out(selection, "registro_classe", "fundo fora da carga") == 1


def test_current_registro_of_another_type_leaves_the_fund_out():
    selection = select(
        [
            fund_row(ID_Registro_Fundo="1", Data_Inicio_Situacao="2024-05-02", **CANCELLED),
            fund_row(ID_Registro_Fundo="2", Tipo_Fundo="FI"),
        ]
    )

    assert selection.funds == ()
    assert selection.counts[("cnpjs_candidatos", "registro_fundo")] == 1
    assert out(selection, "registro_fundo", "vigente de outro tipo") == 1


def test_fidc_class_of_a_fund_out_of_scope_is_left_out():
    # O caso da classe FIDC cancelada de um fundo FIF.
    selection = select(
        [fund_row(Tipo_Fundo="FIF")],
        [class_row(Situacao="Cancelado")],
    )

    assert selection.funds == ()
    assert selection.classes == ()
    assert selection.counts[("cnpjs_candidatos", "registro_fundo")] == 0
    assert out(selection, "registro_classe", "fundo fora da carga") == 1


def test_class_whose_current_registro_is_of_another_type_is_left_out():
    selection = select(
        [fund_row()],
        [
            class_row(ID_Registro_Classe="1", Situacao="Cancelado"),
            class_row(ID_Registro_Classe="2", Tipo_Classe="Classes de Cotas de Fundos FIF"),
        ],
    )

    assert len(selection.funds) == 1
    assert selection.classes == ()
    assert out(selection, "registro_classe", "vigente de outro tipo") == 1


def test_several_managers_become_one_registro_with_the_set():
    selection = select(
        [
            fund_row(),
            fund_row(CPF_CNPJ_Gestor=fake_cnpj(802), Gestor="Segunda Gestora Ficticia"),
        ],
        [class_row()],
    )
    fund = selection.funds[0]
    managers = [(p.cnpj, p.name) for p in fund.parties if p.role == "gestor"]

    assert len(selection.funds) == 1
    assert managers == [
        (fake_cnpj(801), "Gestora Ficticia Ltda"),
        (fake_cnpj(802), "Segunda Gestora Ficticia"),
    ]
    assert [p.role for p in fund.parties].count("administrador") == 1
    assert selection.counts[("registros_com_varias_linhas", "registro_fundo", "FIDC")] == 1
    assert selection.counts[("papeis", "gestor")] == 2
    assert len(selection.classes) == 1


def test_identical_rows_collapse():
    selection = select([fund_row(), fund_row()])

    assert len(selection.funds) == 1
    assert len(selection.funds[0].parties) == 2


def test_inconsistent_registro_is_left_out():
    selection = select(
        [fund_row(), fund_row(Denominacao_Social="Outro Nome Ficticio")]
    )

    assert selection.funds == ()
    assert out(selection, "registro_fundo", "registro inconsistente") == 1


def test_mixed_person_type_is_not_recorded():
    selection = select([fund_row(), pf_manager_row()])
    fund = selection.funds[0]

    assert "Tipo_Pessoa_Gestor" not in fund.values
    assert [p.cnpj for p in fund.parties if p.role == "gestor"] == [fake_cnpj(801)]
    assert selection.counts[("tipo_pessoa_misturado", "FIDC")] == 1


def test_natural_person_manager_keeps_only_the_type():
    selection = select([pf_manager_row()])
    fund = selection.funds[0]

    assert fund.values["Tipo_Pessoa_Gestor"] == "PF"
    assert [p.role for p in fund.parties] == ["administrador"]


def test_invalid_situation_date_out_of_scope_leaves_the_cnpj_unresolved():
    selection = select(
        [
            fund_row(ID_Registro_Fundo="1"),
            fund_row(ID_Registro_Fundo="2", Tipo_Fundo="FI", Data_Inicio_Situacao="02/01/2020"),
        ]
    )

    assert selection.funds == ()
    assert out(selection, "registro_fundo", "data invalida") == 1


def test_invalid_identity_cnpj_in_scope_is_counted():
    wrong = fake_cnpj(1)[:12] + ("00" if fake_cnpj(1)[12:] != "00" else "11")
    selection = select([fund_row(CNPJ_Fundo=wrong)])

    assert selection.funds == ()
    assert out(selection, "registro_fundo", "CNPJ invalido") == 1


def test_divergent_pair_is_loaded_and_counted():
    selection = select([fund_row()], [class_row(Tipo_Classe=FIAGRO_CLASS)])

    assert len(selection.classes) == 1
    assert selection.classes[0].scope == "FIAGRO"
    assert selection.counts[("par_divergente",)] == 1


def test_fiagro_fund_and_class():
    selection = select(
        [fund_row(Tipo_Fundo="FIAGRO")],
        [class_row(Tipo_Classe=FIAGRO_CLASS)],
    )

    assert [s.scope for s in selection.funds + selection.classes] == ["FIAGRO", "FIAGRO"]
    assert selection.classes[0].fund_registro_id == "1"


def test_counts_candidates_by_table_and_type():
    selection = select([fund_row()], [class_row()])
    counts = selection.counts

    assert counts[("observacoes", "registro_fundo", "text")] == 6
    assert counts[("observacoes", "registro_fundo", "date")] == 7
    assert counts[("observacoes", "registro_fundo", "numeric")] == 1
    assert counts[("observacoes", "registro_classe", "boolean")] == 2
    assert counts[("papeis", "auditor")] == 1
    assert counts[("papeis", "controlador")] == 0


def test_selection_report_has_only_aggregates():
    selection = select(
        [fund_row(), pf_manager_row(ID_Registro_Fundo="2", CNPJ_Fundo=fake_cnpj(2))],
        [class_row()],
    )
    text = "\n".join(format_selection_report(selection))

    assert "vigentes que entram: FIDC 2 (cancelados 0); FIAGRO 0 (cancelados 0)" in text
    assert "  funds: 2" in text
    assert "  fund_classes: 1" in text

    for secret in (FAKE_CPF, PF_MANAGER_NAME, fake_cnpj(1), fake_cnpj(2), "Ficticia"):
        assert secret not in text
