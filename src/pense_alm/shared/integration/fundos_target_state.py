"""Estado do destino para as travas da importacao de Fundos (FU7.2).

A maior competencia que o adaptador de Fundos ja gravou no destino e o
MAX(reference_date) de data_provenance com source_type 'cvm' e o
source_name da fonte: "Fundos - CVM Cadastro" para a trava B6 e "Fundos -
CVM CDA" para a trava do CDA (PR C2). As duas fontes nunca se misturam.
Nenhum repositorio expoe essa leitura: a consulta e so de leitura, por
SQLiteConnectionManager.read_connection(), no destino real (commit) ou na
copia (dry-run).

O texto da data e o datetime.isoformat() da serializacao. O adaptador sempre
grava a competencia as 00:00 UTC, entao toda linha desta fonte tem o formato
AAAA-MM-DDT00:00:00+00:00, e o MAX por texto e o MAX por data. Uma linha
fora desse formato, ou sem data, faz a leitura falhar em vez de comparar
errado.

Limite aceito (17/11/2026): uma execucao completa que nao muda nada nao grava
proveniencia, entao a data aplicada e a maior que gravou alguma coisa.
"""

from datetime import datetime

from pense_alm.shared.entities import SourceType
from pense_alm.shared.persistence import SQLiteConnectionManager

from .fundos_adapter import SOURCE_NAME_CADASTRO, SOURCE_NAME_CDA


_Q_APPLIED = (
    "SELECT MAX(reference_date),"
    " COALESCE(SUM(CASE WHEN reference_date IS NULL OR reference_date NOT GLOB"
    " '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T00:00:00+00:00'"
    " THEN 1 ELSE 0 END), 0)"
    " FROM data_provenance WHERE source_type = ? AND source_name = ?"
)


class FundosTargetStateError(Exception):
    """O destino tem proveniencia de Fundos fora do formato (sem dado na mensagem)."""


class FundosTargetState:
    """Le no destino a maior competencia ja aplicada pelo adaptador de Fundos."""

    def __init__(self, connection_manager: SQLiteConnectionManager) -> None:
        if not isinstance(connection_manager, SQLiteConnectionManager):
            raise TypeError("connection_manager deve ser SQLiteConnectionManager.")

        self._connection_manager = connection_manager

    def _latest(self, source_name: str, label: str) -> datetime | None:
        with self._connection_manager.read_connection() as connection:
            latest, unexpected = connection.execute(
                _Q_APPLIED,
                (SourceType.CVM.value, source_name),
            ).fetchone()

        if unexpected:
            raise FundosTargetStateError(
                "Formato de data inesperado na proveniencia " + label + " de "
                "Fundos no destino."
            )

        if latest is None:
            return None

        return datetime.fromisoformat(latest)

    def latest_applied_reference(self) -> datetime | None:
        """A maior competencia do cadastro ja gravada, as 00:00 UTC (B6)."""

        return self._latest(SOURCE_NAME_CADASTRO, "do cadastro")

    def latest_applied_cda_reference(self) -> datetime | None:
        """A maior competencia do CDA ja gravada, as 00:00 UTC (trava do CDA)."""

        return self._latest(SOURCE_NAME_CDA, "do CDA")
