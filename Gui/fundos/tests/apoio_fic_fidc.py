"""Banco sintetico para os testes de FIC-FIDC (FU6.1, partes 3 e 4).

Tudo e ficticio: os CNPJs vem de apoio.make_test_cnpj e os valores foram
inventados para cada teste. Os nomes de campo sao os reais da CVM
(tabela.coluna), porque e isso que a classificacao le.
"""

from apoio_indicadores import SyntheticInforme

from fundos.cadastro import columns as cadastro_spec
from fundos.fic_fidc.classification import DENOMINATOR
from fundos.fic_fidc.classification import NUMERATOR
from fundos.indicators.values import CLASS_SUBJECT


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
