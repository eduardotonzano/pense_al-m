"""Comparacao do informe de FIDC com o que ja esta no banco (reapresentacao).

Quando a competencia ja tem ZIP carregado, cada celula, papel, assunto e
serie do ZIP novo e comparado com o ultimo valor carregado desta fonte na
competencia: entre as linhas da chave, a de collected_at e id maiores, que
e a que a view mostra enquanto nao houver outra fonte. So le o banco; a
carga usa a classificacao para pular a celula igual e regravar a que volta.

O estado do banco e lido tabela por tabela, pelos manifestos dos membros
dos ZIPs ja carregados da competencia (indices por raw_record_id): o custo
nao cresce com o numero de competencias no banco, e so uma tabela fica em
memoria por vez. A celula igual de um ZIP posterior continua presa ao
manifesto do ZIP que a gravou primeiro; por isso a uniao dos membros de
todos os ZIPs da competencia tem todas as linhas.

So contagens saem daqui: nenhum CNPJ, nome ou valor vai para relatorio.
"""

from collections import Counter

from fundos.informe_fidc import columns as spec
from fundos.repositories.observation_repository import ObservationRepository
from fundos.repositories.observation_repository import canonical_decimal


EQUAL = "iguais"
CHANGED = "alteradas"
NEW = "novas"
RETURNS = "voltam"
CELL_STATUSES = (EQUAL, CHANGED, NEW, RETURNS)

VANISHED_EMPTY = "vazias"
VANISHED_ROW = "sem_linha"
VANISHED_REASONS = (VANISHED_EMPTY, VANISHED_ROW)

PARTY_NAME = "nome_alterado"
PARTY_SHARE = "percentual_alterado"
PARTY_SWAPPED = "cnpj_trocado"
PARTY_NEW = "entrou"
PARTY_GONE = "saiu"
PARTY_STATUSES = (EQUAL, RETURNS, PARTY_NAME, PARTY_SHARE, PARTY_SWAPPED, PARTY_NEW, PARTY_GONE)

SERIES_SUBJECT = "quota_series_id"
# Serie que ainda nao existe no banco (dry-run): cada uma com chave propria.
NEW_SERIES_SUBJECT = "serie_nova"
SUBCLASS_TABLE = "tab_X_1"

# Posicao do valor gravado em cada tipo, na consulta de observations.
_VALUE_INDEX = {"text": 4, "numeric": 5, "date": 6, "boolean": 7}


def _placeholders(values):
    return ", ".join("?" * len(values))


def member_ids(connection, informe, zip_ids):
    """{tabela: ids dos manifestos do membro} nos ZIPs ja carregados."""

    tables = {spec.member_name(table, informe.zip.period): table for table in spec.TABLES}
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


class _Values:
    """Ultimo valor de cada chave e os valores anteriores diferentes dele.

    pending guarda as chaves do banco que o ZIP novo ainda nao trouxe; no
    fim, sao as que sumiram.
    """

    def __init__(self):
        self.latest = {}
        self.older = {}
        self.pending = set()

    def load(self, key, value):
        """Linha do banco, na ordem de collected_at e id."""

        previous = self.latest.get(key)

        if previous is not None and previous != value:
            self.older.setdefault(key, set()).add(previous)

        self.latest[key] = value

    def loaded(self):
        for key, values in self.older.items():
            values.discard(self.latest[key])

        self.pending = set(self.latest)

    def compare(self, key, value):
        """(situacao, valor atual ou None); o valor novo passa a ser o atual."""

        self.pending.discard(key)
        current = self.latest.get(key)

        if current is None:
            status = NEW
        elif current == value:
            return EQUAL, current
        elif value in self.older.get(key, ()):
            status = RETURNS
        else:
            status = CHANGED

        if current is not None:
            older = self.older.setdefault(key, set())
            older.add(current)
            older.discard(value)

        self.latest[key] = value
        return status, current


class Comparison:
    """Estado da competencia no banco e as contagens da comparacao."""

    def __init__(self, connection, informe, zip_ids):
        self.connection = connection
        self.shared_subclass_ids = informe.shared_subclass_ids
        self.members = member_ids(connection, informe, zip_ids)
        self.counts = Counter()
        self.counts[("reapresentacao", "zips")] = len(zip_ids)
        # Retrato de quota_series antes da carga: id -> (pai, rotulo, ID).
        self.series = {}
        self.series_by_label = {}

        for row in connection.execute(
            "SELECT id, fund_class_id, fund_id, series_label_key, cvm_subclass_id FROM quota_series"
        ):
            parent = ("fund_class_id", row[1]) if row[1] is not None else ("fund_id", row[2])
            self.series[int(row[0])] = (parent, row[3], row[4])

            if row[3] is not None:
                self.series_by_label[parent + (row[3],)] = int(row[0])

        self.db_subjects = set()
        self.zip_subjects = set()
        self.db_series = set()
        self.zip_series = set()
        self.vanished_cells = Counter()
        self.subclass_changes = {}

    def series_id(self, column, subject_id, series_key):
        """Serie ja existente com o mesmo pai e rotulo, ou None."""

        return self.series_by_label.get((column, subject_id, series_key))

    def parent(self, subject):
        """Classe ou fundo do assunto (o pai, se for serie)."""

        if subject[0] == SERIES_SUBJECT:
            return self.series[subject[1]][0]

        return subject

    def register_db_subject(self, subject):
        parent = self.parent(subject)
        self.db_subjects.add(parent)

        if subject[0] == SERIES_SUBJECT and self.series[subject[1]][1] is not None:
            self.db_series.add(parent + (self.series[subject[1]][1],))

    def table(self, table):
        return TableComparison(self, table)

    def parties(self):
        return PartyComparison(self)

    def finish(self):
        """Contagens de assuntos e series, depois de todas as tabelas."""

        counts = self.counts
        gone = self.db_subjects - self.zip_subjects
        counts[("reapresentacao", "assuntos", "nos_dois")] = len(self.db_subjects & self.zip_subjects)
        counts[("reapresentacao", "assuntos", "novos")] = len(self.zip_subjects - self.db_subjects)
        counts[("reapresentacao", "assuntos", "sumiram")] = len(gone)
        counts[("reapresentacao", "assuntos", "celulas_dos_que_sumiram")] = sum(
            self.vanished_cells[subject] for subject in gone
        )
        new_series = self.zip_series - self.db_series
        gone_series = self.db_series - self.zip_series
        counts[("reapresentacao", "series", "novas")] = len(new_series)
        counts[("reapresentacao", "series", "sumiram")] = len(gone_series)
        counts[("reapresentacao", "series", "possivel_troca_de_rotulo")] = len(
            {key[:2] for key in new_series} & {key[:2] for key in gone_series}
        )

        for change in self.subclass_changes.values():
            counts[("reapresentacao", "id_subclasse", change)] += 1

        return counts


class TableComparison:
    """As celulas de uma tabela: o banco, lido uma vez, contra o ZIP novo."""

    def __init__(self, comparison, table):
        self.comparison = comparison
        self.table = table
        self.values = _Values()
        self.rows = set()
        ids = comparison.members[table]

        if ids:
            fields = {}

            for row in comparison.connection.execute(
                "SELECT fund_id, fund_class_id, quota_series_id, value_type, value_text,"
                " value_numeric, value_date, value_boolean, unit, field_name"
                " FROM observations WHERE raw_record_id IN ("
                + _placeholders(ids)
                + ") ORDER BY collected_at, id",
                tuple(ids),
            ):
                if row[0] is not None:
                    subject = ("fund_id", int(row[0]))
                elif row[1] is not None:
                    subject = ("fund_class_id", int(row[1]))
                else:
                    subject = (SERIES_SUBJECT, int(row[2]))

                field = fields.setdefault(row[9], row[9])
                value = (row[3], row[_VALUE_INDEX[row[3]]], row[8])
                self.values.load(subject + (field,), value)

        self.values.loaded()

        for subject in {key[:2] for key in self.values.latest}:
            comparison.register_db_subject(subject)

    def row(self, row, column, subject_id, series_id=None):
        """Classifica as celulas da linha; devolve {coluna: situacao}.

        column e subject_id sao a classe ou o fundo; series_id e a serie da
        linha (tabelas de serie), ou None se ela ainda nao existe.
        """

        comparison = self.comparison
        parent = (column, subject_id)
        comparison.zip_subjects.add(parent)

        if self.table in spec.SERIES_TABLES:
            comparison.zip_series.add(parent + (row.series_key,))

            if series_id is None:
                subject = (NEW_SERIES_SUBJECT, parent + (row.series_key,))
            else:
                subject = (SERIES_SUBJECT, series_id)

            if self.table == SUBCLASS_TABLE:
                self._subclass(row, series_id)
        else:
            subject = parent

        self.rows.add(subject)
        statuses = {}

        for name, value in row.values.items():
            value_type = spec.VALUE_TYPE[spec.KINDS[self.table][name]]
            stored = ObservationRepository.normalize_value(value_type, value)
            status, _ = self.values.compare(
                subject + (spec.field_name(self.table, name),),
                (value_type, stored, None),
            )
            comparison.counts[("reapresentacao", "celulas", self.table, status)] += 1
            statuses[name] = status

        return statuses

    def _subclass(self, row, series_id):
        """ID_SUBCLASSE que aparece numa serie existente ou que some dela."""

        if series_id not in self.comparison.series:
            return

        stored = self.comparison.series[series_id][2]
        subclass_id = row.subclass_id or None

        if subclass_id in self.comparison.shared_subclass_ids:
            subclass_id = None

        if subclass_id is not None and stored is None:
            self.comparison.subclass_changes[series_id] = "aparece"
        elif subclass_id is None and stored is not None:
            self.comparison.subclass_changes[series_id] = "some"

    def finish(self):
        """Conta as celulas do banco que o ZIP novo nao trouxe."""

        comparison = self.comparison

        for key in self.values.pending:
            subject = key[:2]
            reason = VANISHED_EMPTY if subject in self.rows else VANISHED_ROW
            comparison.counts[("reapresentacao", "sumiram", self.table, reason)] += 1
            comparison.vanished_cells[comparison.parent(subject)] += 1


class PartyComparison:
    """Administradora e cedentes da tab_I, por posicao (papel e campo)."""

    def __init__(self, comparison):
        self.comparison = comparison
        self.values = _Values()
        ids = comparison.members[spec.NAME_TABLE]

        if ids:
            for row in comparison.connection.execute(
                "SELECT p.fund_id, p.fund_class_id, p.role, p.field_name, p.party_cnpj,"
                " p.name_field_name, p.party_name, s.share_field_name, s.share_value"
                " FROM party_observations p LEFT JOIN party_observation_shares s"
                " ON s.party_observation_id = p.id"
                " WHERE p.raw_record_id IN ("
                + _placeholders(ids)
                + ") ORDER BY p.collected_at, p.id",
                tuple(ids),
            ):
                if row[0] is not None:
                    subject = ("fund_id", int(row[0]))
                else:
                    subject = ("fund_class_id", int(row[1]))

                self.values.load(subject + (row[2], row[3]), tuple(row[4:9]))

        self.values.loaded()

        for key in self.values.latest:
            comparison.db_subjects.add(key[:2])

    def party(self, column, subject_id, party):
        """Situacao do papel na posicao (papel e campo do identificador)."""

        share = None if party.share is None else canonical_decimal(party.share)
        value = (party.cnpj, party.name_field_name, party.name, party.share_field_name, share)
        status, current = self.values.compare((column, subject_id, party.role, party.field_name), value)

        if status == CHANGED:
            if current[0] != value[0]:
                status = PARTY_SWAPPED
            elif current[1:3] != value[1:3]:
                status = PARTY_NAME
            else:
                status = PARTY_SHARE
        elif status == NEW:
            status = PARTY_NEW

        self.comparison.counts[("reapresentacao", "papeis", party.role, status)] += 1
        return status

    def finish(self):
        for key in self.values.pending:
            self.comparison.counts[("reapresentacao", "papeis", key[2], PARTY_GONE)] += 1
