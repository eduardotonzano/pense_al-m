"""Comparacao do informe de FIAGRO com o que ja esta no banco (reapresentacao).

Quando a competencia ja tem ZIP carregado, cada celula, papel, classe e
serie do ZIP novo e comparada com o ultimo valor carregado desta fonte na
competencia: entre as linhas da chave, a de collected_at e id maiores, que
e a que a view mostra enquanto nao houver outra fonte. E o mecanismo da
reapresentacao do FIDC (informe_fidc/compare.py), com o que o FIAGRO tem de
diferente: 2 arquivos (classe e subclasse), o assunto e so a classe, a
serie e so pelo rotulo normalizado (o arquivo nao traz ID da CVM), os
papeis sao o administrador e o gestor, sem percentual, e o banco so precisa
das migrations 001 e 002 (nada aqui le party_observation_shares).

O estado do banco e lido arquivo por arquivo, pelos manifestos dos membros
dos ZIPs ja carregados da competencia. A celula igual de um ZIP posterior
continua presa ao manifesto do ZIP que a gravou primeiro; por isso a uniao
dos membros de todos os ZIPs da competencia tem todas as linhas.

Retidas: linhas que o ZIP traz, mas que a carga nao grava por regra propria
(withhold), como as subclasses de uma classe com mais de uma linha no
arquivo ou a classe inteira com Versao menor que a carregada. O que o banco
tem delas nao e comparado: as celulas, as series e os papeis sao contados
como retidos, com o motivo, e nunca como sumidos nem como possivel troca de
rotulo.

Versao e Data_Entrega sao celulas comuns. Alem da situacao de cada celula,
a classe e contada quando a Versao sobe, quando a Versao e a mesma com
alguma celula alterada e quando a Data_Entrega anda para tras com a Versao
igual ou maior. Nada disso ordena a carga.

So le o banco; so contagens saem daqui: nenhum CNPJ, nome ou valor.
"""

from collections import Counter
from decimal import Decimal

from fundos.informe_fiagro import columns as spec
from fundos.informe_fidc.compare import CHANGED
from fundos.informe_fidc.compare import EQUAL
from fundos.informe_fidc.compare import NEW
from fundos.informe_fidc.compare import NEW_SERIES_SUBJECT
from fundos.informe_fidc.compare import PARTY_GONE
from fundos.informe_fidc.compare import PARTY_NAME
from fundos.informe_fidc.compare import PARTY_NEW
from fundos.informe_fidc.compare import PARTY_SWAPPED
from fundos.informe_fidc.compare import RETURNS
from fundos.informe_fidc.compare import SERIES_SUBJECT
from fundos.informe_fidc.compare import VANISHED_EMPTY
from fundos.informe_fidc.compare import VANISHED_ROW
from fundos.informe_fidc.compare import LatestValues
from fundos.repositories.observation_repository import ObservationRepository


CLASS_SUBJECT = "fund_class_id"

# Papel retido: a classe dele nao foi comparada (regra propria da carga).
WITHHELD = "retidos"
PARTY_STATUSES = (EQUAL, RETURNS, PARTY_NAME, PARTY_SWAPPED, PARTY_NEW, PARTY_GONE, WITHHELD)

# Situacao da Versao e da Data_Entrega da classe contra a carregada.
VERSION_HIGHER = "versao_maior"
SAME_VERSION_CHANGED = "mesma_versao_alterada"
DELIVERY_EARLIER = "data_entrega_anterior"
VERSION_STATUSES = (VERSION_HIGHER, SAME_VERSION_CHANGED, DELIVERY_EARLIER)

VERSION_FIELD = spec.field_name(spec.CLASS_TABLE, spec.VERSION_COLUMN)

# Posicao do valor gravado em cada tipo, na consulta de observations.
_VALUE_INDEX = {"text": 3, "numeric": 4, "date": 5, "boolean": 6}


def _placeholders(values):
    return ", ".join("?" * len(values))


def member_ids(connection, period, zip_ids):
    """{arquivo: ids dos manifestos do membro} nos ZIPs ja carregados."""

    tables = {spec.member_name(table, period): table for table in spec.TABLES}
    members = {table: [] for table in spec.TABLES}

    if not zip_ids:
        return members

    rows = connection.execute(
        "SELECT id, file_name FROM raw_records WHERE parent_raw_record_id IN ("
        + _placeholders(zip_ids)
        + ") ORDER BY id",
        tuple(zip_ids),
    )

    for raw_id, file_name in rows:
        if file_name in tables:
            members[tables[file_name]].append(int(raw_id))

    return members


class Comparison:
    """Estado da competencia no banco e as contagens da comparacao."""

    def __init__(self, connection, informe, zip_ids):
        self.connection = connection
        self.members = member_ids(connection, informe.zip.period, zip_ids)
        self.counts = Counter()
        self.counts[("reapresentacao", "zips")] = len(zip_ids)
        # Retrato das series de classe antes da carga: id -> (classe, rotulo).
        self.series = {}
        self.series_by_label = {}

        for row in connection.execute(
            "SELECT id, fund_class_id, series_label_key FROM quota_series WHERE fund_class_id IS NOT NULL"
        ):
            parent = (CLASS_SUBJECT, int(row[1]))
            self.series[int(row[0])] = (parent, row[2])

            if row[2] is not None:
                self.series_by_label[parent + (row[2],)] = int(row[0])

        self.db_classes = set()
        self.zip_classes = set()
        self.db_series = set()
        self.zip_series = set()
        self.vanished_cells = Counter()
        # (arquivo, classe) -> motivo da retencao.
        self.withheld = {}

    def versions(self):
        """{id da classe: Versao atual dela na competencia}, pelos manifestos ja carregados."""

        ids = self.members[spec.CLASS_TABLE]
        found = {}

        if not ids:
            return found

        for class_id, value in self.connection.execute(
            "SELECT fund_class_id, value_numeric FROM observations WHERE raw_record_id IN ("
            + _placeholders(ids)
            + ") AND field_name = ? ORDER BY collected_at, id",
            tuple(ids) + (VERSION_FIELD,),
        ):
            found[int(class_id)] = str(value)

        return found

    def series_id(self, class_id, series_key):
        """Serie ja existente da classe com o mesmo rotulo, ou None."""

        return self.series_by_label.get((CLASS_SUBJECT, class_id, series_key))

    def parent(self, subject):
        """A classe do assunto (a classe da serie, se for serie)."""

        if subject[0] == SERIES_SUBJECT:
            return self.series[subject[1]][0]

        return subject

    def register_db_subject(self, subject):
        parent = self.parent(subject)
        self.db_classes.add(parent)

        if subject[0] == SERIES_SUBJECT and self.series[subject[1]][1] is not None:
            self.db_series.add(parent + (self.series[subject[1]][1],))

    def withhold(self, class_id, reason, tables):
        """A carga retem a classe nestes arquivos: o banco dela nao e comparado."""

        for table in tables:
            self.withheld.setdefault((table, (CLASS_SUBJECT, class_id)), reason)

    def withheld_in(self, table):
        return {parent for (held_table, parent) in self.withheld if held_table == table}

    def table(self, table):
        return TableComparison(self, table)

    def parties(self):
        return PartyComparison(self)

    def finish(self):
        """Contagens de classes e series, depois dos 2 arquivos."""

        counts = self.counts
        held_classes = self.withheld_in(spec.CLASS_TABLE)
        held_series = self.withheld_in(spec.SUBCLASS_TABLE)
        gone = self.db_classes - self.zip_classes - held_classes
        counts[("reapresentacao", "classes", "nos_dois")] = len(self.db_classes & self.zip_classes)
        counts[("reapresentacao", "classes", "novas")] = len(self.zip_classes - self.db_classes)
        counts[("reapresentacao", "classes", "sumiram")] = len(gone)
        counts[("reapresentacao", "classes", "celulas_das_que_sumiram")] = sum(
            self.vanished_cells[parent] for parent in gone
        )
        counts[("reapresentacao", "classes", "retidas")] = len(held_classes & self.db_classes)

        db_series = {key for key in self.db_series if key[:2] not in held_series}
        zip_series = {key for key in self.zip_series if key[:2] not in held_series}
        new_series = zip_series - db_series
        gone_series = db_series - zip_series
        counts[("reapresentacao", "series", "novas")] = len(new_series)
        counts[("reapresentacao", "series", "sumiram")] = len(gone_series)
        counts[("reapresentacao", "series", "possivel_troca_de_rotulo")] = len(
            {key[:2] for key in new_series} & {key[:2] for key in gone_series}
        )
        counts[("reapresentacao", "series", "retidas")] = len(self.db_series) - len(db_series)

        return counts


class TableComparison:
    """As celulas de um arquivo: o banco, lido uma vez, contra o ZIP novo."""

    def __init__(self, comparison, table):
        self.comparison = comparison
        self.table = table
        self.values = LatestValues()
        self.rows = set()
        ids = comparison.members[table]

        if ids:
            for row in comparison.connection.execute(
                "SELECT fund_class_id, quota_series_id, value_type, value_text, value_numeric,"
                " value_date, value_boolean, unit, field_name"
                " FROM observations WHERE raw_record_id IN ("
                + _placeholders(ids)
                + ") ORDER BY collected_at, id",
                tuple(ids),
            ):
                if row[0] is not None:
                    subject = (CLASS_SUBJECT, int(row[0]))
                else:
                    subject = (SERIES_SUBJECT, int(row[1]))

                value = (row[2], row[_VALUE_INDEX[row[2]]], row[7])
                self.values.load(subject + (row[8],), value)

        self.values.loaded()

        for subject in {key[:2] for key in self.values.latest}:
            comparison.register_db_subject(subject)

    def row(self, row, class_id, series_id=None):
        """Classifica as celulas da linha; devolve {coluna: situacao}.

        series_id e a serie da linha (arquivo de subclasse), ou None se ela
        ainda nao existe.
        """

        comparison = self.comparison
        parent = (CLASS_SUBJECT, class_id)
        comparison.zip_classes.add(parent)

        if self.table == spec.SUBCLASS_TABLE:
            comparison.zip_series.add(parent + (row.series_key,))

            if series_id is None:
                subject = (NEW_SERIES_SUBJECT, parent + (row.series_key,))
            else:
                subject = (SERIES_SUBJECT, series_id)
        else:
            subject = parent

        self.rows.add(subject)
        statuses = {}
        previous = {}

        for name, value in row.values.items():
            value_type = spec.VALUE_TYPE[spec.KINDS[self.table][name]]
            stored = ObservationRepository.normalize_value(value_type, value)
            status, current = self.values.compare(
                subject + (spec.field_name(self.table, name),),
                (value_type, stored, None),
            )
            comparison.counts[("reapresentacao", "celulas", self.table, status)] += 1
            statuses[name] = status
            previous[name] = current

        if self.table == spec.CLASS_TABLE:
            self._version(row, statuses, previous)

        return statuses

    def _version(self, row, statuses, previous):
        """Conta a classe pela Versao e pela Data_Entrega contra as carregadas."""

        new = row.values.get(spec.VERSION_COLUMN)
        old = previous.get(spec.VERSION_COLUMN)

        if new is None or old is None:
            return

        new_version = Decimal(new)
        old_version = Decimal(old[1])
        counts = self.comparison.counts

        if new_version > old_version:
            counts[("reapresentacao", "versao", VERSION_HIGHER)] += 1
        elif new_version == old_version and any(s in (CHANGED, RETURNS) for s in statuses.values()):
            counts[("reapresentacao", "versao", SAME_VERSION_CHANGED)] += 1

        delivery = row.values.get(spec.DELIVERY_COLUMN)
        old_delivery = previous.get(spec.DELIVERY_COLUMN)

        if delivery is None or old_delivery is None or new_version < old_version:
            return

        if ObservationRepository.normalize_value("date", delivery) < old_delivery[1]:
            counts[("reapresentacao", "versao", DELIVERY_EARLIER)] += 1

    def finish(self):
        """Conta as celulas do banco que o ZIP novo nao trouxe (ou que a carga reteve)."""

        comparison = self.comparison

        for key in self.values.pending:
            subject = key[:2]
            parent = comparison.parent(subject)
            reason = comparison.withheld.get((self.table, parent))

            if reason is not None:
                comparison.counts[("reapresentacao", "retidas", self.table, reason)] += 1
                continue

            vanished = VANISHED_EMPTY if subject in self.rows else VANISHED_ROW
            comparison.counts[("reapresentacao", "sumiram", self.table, vanished)] += 1
            comparison.vanished_cells[parent] += 1


class PartyComparison:
    """Administrador e gestor da classe, por posicao (papel e campo), sem percentual."""

    def __init__(self, comparison):
        self.comparison = comparison
        self.values = LatestValues()
        ids = comparison.members[spec.CLASS_TABLE]

        if ids:
            for row in comparison.connection.execute(
                "SELECT fund_class_id, role, field_name, party_cnpj, name_field_name, party_name"
                " FROM party_observations WHERE raw_record_id IN ("
                + _placeholders(ids)
                + ") ORDER BY collected_at, id",
                tuple(ids),
            ):
                self.values.load((CLASS_SUBJECT, int(row[0]), row[1], row[2]), tuple(row[3:6]))

        self.values.loaded()

        for key in self.values.latest:
            comparison.db_classes.add(key[:2])

    def party(self, class_id, party):
        """Situacao do papel na posicao (papel e campo do identificador)."""

        value = (party.cnpj, party.name_field_name, party.name)
        status, current = self.values.compare((CLASS_SUBJECT, class_id, party.role, party.field_name), value)

        if status == CHANGED:
            status = PARTY_SWAPPED if current[0] != value[0] else PARTY_NAME
        elif status == NEW:
            status = PARTY_NEW

        self.comparison.counts[("reapresentacao", "papeis", party.role, status)] += 1
        return status

    def finish(self):
        held = self.comparison.withheld_in(spec.CLASS_TABLE)

        for key in self.values.pending:
            status = WITHHELD if key[:2] in held else PARTY_GONE
            self.comparison.counts[("reapresentacao", "papeis", key[2], status)] += 1
