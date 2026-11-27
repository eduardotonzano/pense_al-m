"""Series ficticias para os testes do quota_class_map (FU6.2).

Tudo e ficticio: os CNPJs vem de apoio.make_test_cnpj e os rotulos seguem o
molde da secao 10.6 de docs/fundos-descoberta.md (rotulos genericos, como
"Subclasse Senior Serie 1"). As series sao gravadas pelo repositorio real,
com a chave normalizada, e o rotulo original fica como observacao.
"""

from apoio import T0
from apoio import insert_observation
from apoio_indicadores import SyntheticInforme

from fundos.indicators.values import CLASS_SUBJECT
from fundos.repositories.quota_series_repository import QuotaSeriesRepository


SEP = "2026-09-30"
OCT = "2026-10-31"
LABEL_FIELD = "tab_X_2.TAB_X_CLASSE_SERIE"
FIAGRO_LABEL_FIELD = "inf_mensal_fiagro_subclasse.Nome_Subclasse"


class SyntheticSeries(SyntheticInforme):
    """SyntheticInforme com series de FIDC (tab_X_2) e de FIAGRO (subclasse)."""

    def _series_id(self, parent, label):
        argument = "fund_class_id" if parent.kind == CLASS_SUBJECT else "fund_id"
        record, _ = QuotaSeriesRepository(self.connection).get_or_create(
            **{argument: parent.id}, label=label
        )
        return record.id

    def _put(self, series_id, field_name, value, value_type, reference_date, collected_at):
        return insert_observation(
            self.connection,
            subject=("series", series_id),
            source=self.source["cvm"],
            run=self.run["cvm"],
            raw=self.raw["cvm"],
            field_name=field_name,
            value=value,
            value_type=value_type,
            reference_date=reference_date,
            collected_at=collected_at,
        )

    def series(self, parent, label, reference_date=SEP, quantity="10", unit_value="1.5", collected_at=T0):
        """Serie de FIDC na tab_X_2: o rotulo original, a quantidade e o valor da cota."""

        series_id = self._series_id(parent, label)
        self._put(series_id, LABEL_FIELD, label, "text", reference_date, collected_at)
        self._put(series_id, "tab_X_2.TAB_X_QT_COTA", quantity, "numeric", reference_date, collected_at)
        self._put(series_id, "tab_X_2.TAB_X_VL_COTA", unit_value, "numeric", reference_date, collected_at)
        return series_id

    def fiagro_series(self, parent, label, reference_date=SEP):
        """Subclasse de FIAGRO: so o rotulo do arquivo de subclasse, sem campo tab_X."""

        series_id = self._series_id(parent, label)
        self._put(series_id, FIAGRO_LABEL_FIELD, label, "text", reference_date, T0)
        return series_id
