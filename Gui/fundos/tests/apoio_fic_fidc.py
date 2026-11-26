"""Banco sintetico para os testes de FIC-FIDC (FU6.1, partes 3 e 4).

Tudo e ficticio: os CNPJs vem de apoio.make_test_cnpj (os detentores com a
raiz numerica, os investidos com a alfanumerica) e os valores foram
inventados para cada teste. Os nomes de campo sao os reais da CVM
(tabela.coluna), porque e isso que a classificacao e a conferencia leem.
"""

from apoio import T0
from apoio import make_test_cnpj
from apoio_indicadores import SyntheticInforme

from fundos.cadastro import columns as cadastro_spec
from fundos.cda import columns as cda_spec
from fundos.fic_fidc.classification import DENOMINATOR
from fundos.fic_fidc.classification import NUMERATOR
from fundos.indicators.values import CLASS_SUBJECT
from fundos.indicators.values import FUND_SUBJECT
from fundos.indicators.values import Subject
from fundos.repositories.holding_repository import HoldingRepository


SEP = "2026-09-30"
OCT = "2026-10-31"
CADASTRO_DATE = "2026-10-27"

FIDC = "FIDC"
FIAGRO = "FIAGRO"
CLASS_TYPES = {
    FIDC: "Classes de Cotas de Fundos FIDC",
    FIAGRO: "Classes de Cotas de Fundos FIAGRO",
}

# Outro campo da tab_I, para o assunto que tem informe sem os dois campos.
OTHER_TAB_I_FIELD = "tab_I.TAB_I2_VL_CARTEIRA"

CONFIDENTIAL_UNTIL = "2026-12-31"

_SUBJECT_ARGUMENT = {CLASS_SUBJECT: "fund_class_id", FUND_SUBJECT: "fund_id"}


class SyntheticFicFidc(SyntheticInforme):
    """SyntheticInforme com o tipo no cadastro e o atalho dos dois campos."""

    def put_type(self, subject, text):
        """Grava o tipo do assunto no cadastro (Tipo_Classe ou Tipo_Fundo)."""

        table = (
            cadastro_spec.CLASS_TABLE
            if subject.kind == CLASS_SUBJECT
            else cadastro_spec.FUND_TABLE
        )
        field_name = cadastro_spec.field_name(table, cadastro_spec.TYPE_COLUMN[table])

        return self.put(
            subject,
            {field_name: text},
            reference_date=CADASTRO_DATE,
            value_type="text",
        )

    def typed_class(self, n=1, kind=FIDC, fund_kind=FIDC):
        """Fundo e classe com o mesmo CNPJ ficticio e o tipo no cadastro; devolve a classe."""

        fund, fund_class = self.fund_and_class(n)
        self.put_type(fund_class, CLASS_TYPES[kind])

        if fund_kind is not None:
            self.put_type(fund, fund_kind)

        return fund_class

    def typed_fund(self, n=1, fund_kind=FIDC):
        """So o fundo, com o tipo no cadastro (assunto do informe do tipo Fundo)."""

        fund, _ = self.fund_and_class(n)
        self.put_type(fund, fund_kind)
        return fund

    def put_ratio(self, subject, cotas=None, ativo=None, reference_date=SEP, **options):
        """Grava as cotas de FIDC e o ativo informados (None = sem linha)."""

        values = {NUMERATOR: cotas, DENOMINATOR: ativo}

        return self.put(
            subject,
            {name: value for name, value in values.items() if value is not None},
            reference_date=reference_date,
            **options,
        )

    def investee(self, n, class_kind=FIDC, fund_kind=FIDC, with_class=True):
        """Investido ficticio (raiz alfanumerica) com o tipo no cadastro; devolve o CNPJ.

        class_kind e fund_kind None gravam o assunto sem o tipo; with_class
        False cria so o fundo (investido FIDC so como registro de fundo).
        """

        cnpj = make_test_cnpj(n, alphanumeric=True)
        fund_id = self.connection.execute(
            "INSERT INTO funds (cnpj) VALUES (?)", (cnpj,)
        ).lastrowid

        if fund_kind is not None:
            self.put_type(Subject(FUND_SUBJECT, fund_id, cnpj), fund_kind)

        if with_class:
            class_id = self.connection.execute(
                "INSERT INTO fund_classes (fund_id, cnpj) VALUES (?, ?)", (fund_id, cnpj)
            ).lastrowid

            if class_kind is not None:
                self.put_type(Subject(CLASS_SUBJECT, class_id, cnpj), CLASS_TYPES[class_kind])

        return cnpj

    def holding(
        self,
        holder,
        investee_cnpj,
        value,
        reference_date=SEP,
        line_order=1,
        collected_at=T0,
        raw=None,
    ):
        """Grava uma posicao identificada pelo repositorio real; devolve o resultado."""

        return HoldingRepository(self.connection).record(
            **{_SUBJECT_ARGUMENT[holder.kind]: holder.id},
            investee_field_name=cda_spec.INVESTEE_FIELD,
            investee_cnpj=investee_cnpj,
            value_field_name=cda_spec.VALUE_FIELD,
            market_value=value,
            source_id=self.source["cvm"],
            collection_run_id=self.run["cvm"],
            raw_record_id=raw or self.raw["cvm"],
            reference_date=reference_date,
            line_order=line_order,
            collected_at=collected_at,
        )

    def confidential(self, holder, value, reference_date=SEP, collected_at=T0, raw=None):
        """Grava o consolidado confidencial pelo repositorio real; devolve o resultado."""

        return HoldingRepository(self.connection).record_confidential(
            **{_SUBJECT_ARGUMENT[holder.kind]: holder.id},
            value_field_name=cda_spec.CONFIDENTIAL_VALUE_FIELD,
            market_value=value,
            confidential_until_field_name=cda_spec.CONFIDENTIAL_UNTIL_FIELD,
            confidential_until=CONFIDENTIAL_UNTIL,
            source_id=self.source["cvm"],
            collection_run_id=self.run["cvm"],
            raw_record_id=raw or self.raw["cvm"],
            reference_date=reference_date,
            collected_at=collected_at,
        )
