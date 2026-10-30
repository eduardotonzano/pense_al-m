"""Papeis (gestor, administrador, custodiante, controlador, auditor, cedente) por CNPJ.

Uma linha por papel, com a mesma proveniencia de observations (migration
002). So CNPJ: a guarda de dados pessoais roda antes de qualquer SQL, no
campo do identificador e no campo do nome. Chave: assunto + papel + campo +
CNPJ + competencia; o valor e o nome e, no cedente, o percentual. Valor
diferente para a mesma chave gera linha nova e conflito aberto em
party_conflicts; nada e sobrescrito.

O percentual do cedente fica em party_observation_shares (migration 003),
1:1 com a linha do papel. Em banco sem a 003 (o cadastro so exige 001 e
002), os papeis sem percentual funcionam como antes.

Limitacao: uma parte que some numa reapresentacao da mesma competencia nao
gera conflito, porque as linhas se somam.
"""

import hashlib
import json
from dataclasses import dataclass

from fundos.cnpj import is_valid_cnpj
from fundos.database import normalize_iso_date
from fundos.database import normalize_timestamp
from fundos.personal_data import PersonalDataError
from fundos.personal_data import check_observation
from fundos.personal_data import column_of
from fundos.personal_data import is_identification_column
from fundos.repositories.observation_repository import FIELD_NAME
from fundos.repositories.observation_repository import canonical_decimal


ROLES = (
    "gestor",
    "administrador",
    "custodiante",
    "controlador",
    "auditor",
    "cedente",
)

CEDENTE = "cedente"
SHARES_TABLE = "party_observation_shares"

SUBJECTS = (
    ("fund_id", "funds"),
    ("fund_class_id", "fund_classes"),
)


@dataclass(frozen=True)
class PartyObservationRecord:
    """Um papel gravado, com toda a proveniencia (e o percentual, se houver)."""

    id: int
    fund_id: int | None
    fund_class_id: int | None
    role: str
    field_name: str
    party_cnpj: str
    name_field_name: str | None
    party_name: str | None
    source_id: int
    collection_run_id: int
    raw_record_id: int
    reference_date: str
    collected_at: str
    checksum: str
    share_field_name: str | None = None
    share_value: str | None = None


@dataclass(frozen=True)
class PartyConflictRecord:
    """Dois valores (nome ou percentual) para o mesmo papel, CNPJ e competencia."""

    id: int
    field_name: str
    reference_date: str
    party_observation_a_id: int
    party_observation_b_id: int
    status: str
    resolution_note: str | None
    resolved_at: str | None
    created_at: str


@dataclass(frozen=True)
class PartyRecordResult:
    """Resultado de record(): o papel, se foi criado e os conflitos novos."""

    party: PartyObservationRecord
    created: bool
    conflicts: tuple[PartyConflictRecord, ...]


class PartyObservationRepository:
    """Grava e le os papeis de fundos e classes."""

    def __init__(self, connection):
        self.connection = connection
        self.has_shares = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (SHARES_TABLE,),
        ).fetchone() is not None

        if self.has_shares:
            self.select = (
                "SELECT p.*, s.share_field_name, s.share_value"
                " FROM party_observations p LEFT JOIN "
                + SHARES_TABLE
                + " s ON s.party_observation_id = p.id"
            )
        else:
            self.select = (
                "SELECT p.*, NULL AS share_field_name, NULL AS share_value"
                " FROM party_observations p"
            )

    @staticmethod
    def row_to_record(row):
        return PartyObservationRecord(
            **{
                field: row[field]
                for field in PartyObservationRecord.__dataclass_fields__
            }
        )

    @staticmethod
    def conflict_to_record(row):
        return PartyConflictRecord(
            **{
                field: row[field]
                for field in PartyConflictRecord.__dataclass_fields__
            }
        )

    @staticmethod
    def subject(fund_id=None, fund_class_id=None):
        """Devolve (coluna, tabela, id) do unico assunto informado."""

        given = [
            (column, table, value)
            for (column, table), value in zip(SUBJECTS, (fund_id, fund_class_id))
            if value is not None
        ]

        if len(given) != 1:
            raise ValueError("Informe exatamente um assunto: fundo ou classe.")

        return given[0]

    @staticmethod
    def checksum(subject_column, subject_id, source_id, role, field_name,
                 party_cnpj, name_field_name, party_name, reference_date,
                 share_field_name=None, share_value=None):
        """SHA-256 da chave e do valor.

        O percentual so entra quando existe: o checksum dos papeis sem
        percentual e o mesmo de antes da migration 003.
        """

        data = {
            "subject": subject_column,
            "subject_id": int(subject_id),
            "source_id": int(source_id),
            "role": role,
            "field_name": field_name,
            "party_cnpj": party_cnpj,
            "name_field_name": name_field_name,
            "party_name": party_name,
            "reference_date": reference_date,
        }

        if share_value is not None:
            data["share_field_name"] = share_field_name
            data["share_value"] = share_value

        serialized = json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get_by_id(self, party_observation_id):
        """Busca um papel pelo ID."""

        row = self.connection.execute(
            self.select + " WHERE p.id = ?",
            (party_observation_id,),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def _check_share(self, role, share_field_name, share_value):
        """Confere o percentual do cedente; devolve o decimal canonico ou None."""

        if (share_field_name is None) != (share_value is None):
            raise ValueError(
                "O percentual e o campo do percentual vem juntos ou nao vem."
            )

        if share_value is None:
            return None

        if role != CEDENTE:
            raise ValueError("Percentual so existe no papel cedente.")

        if not self.has_shares:
            raise ValueError(
                "O percentual do cedente exige a migration 003 "
                "(party_observation_shares)."
            )

        if not isinstance(share_field_name, str) or FIELD_NAME.fullmatch(share_field_name) is None:
            raise ValueError(
                "O campo do percentual deve ser tabela.coluna da CVM."
            )

        if is_identification_column(column_of(share_field_name)):
            raise PersonalDataError(
                "O campo do percentual nao pode ser de identificacao: "
                + share_field_name
                + ". Nada foi gravado."
            )

        try:
            value = canonical_decimal(share_value)
        except ValueError as error:
            raise ValueError(
                "Percentual fora do formato decimal: " + share_field_name + "."
            ) from error

        check_observation(share_field_name, "numeric", value)
        return value

    def record(
        self,
        *,
        fund_id=None,
        fund_class_id=None,
        role,
        field_name,
        party_cnpj,
        name_field_name=None,
        party_name=None,
        share_field_name=None,
        share_value=None,
        source_id,
        collection_run_id,
        raw_record_id,
        reference_date,
        collected_at=None,
    ):
        """Grava o papel; devolve PartyRecordResult.

        Mesmo assunto, fonte, papel, campo, CNPJ, nome, percentual e
        competencia: devolve a linha existente (idempotente). Nome ou
        percentual diferente para o mesmo assunto, papel, campo, CNPJ e
        competencia: linha nova e conflito. O cedente nao tem nome; o
        percentual so existe no cedente.
        """

        if role not in ROLES:
            raise ValueError("Papel invalido.")

        if not isinstance(field_name, str) or FIELD_NAME.fullmatch(field_name) is None:
            raise ValueError(
                "O campo do identificador deve ser tabela.coluna da CVM."
            )

        # Guarda de dados pessoais antes de qualquer SQL: o identificador so
        # aceita CNPJ valido e normalizado.
        check_observation(field_name, "text", party_cnpj)

        if not is_valid_cnpj(party_cnpj):
            raise PersonalDataError(
                "Papel so aceita CNPJ valido e normalizado: "
                + field_name
                + ". Nada foi gravado."
            )

        if (name_field_name is None) != (party_name is None):
            raise ValueError(
                "O nome do papel e o campo do nome vem juntos ou nao vem."
            )

        if role == CEDENTE and party_name is not None:
            raise ValueError("O cedente nao tem nome gravado.")

        if party_name is not None:
            if FIELD_NAME.fullmatch(name_field_name) is None:
                raise ValueError(
                    "O campo do nome deve ser tabela.coluna da CVM."
                )

            check_observation(name_field_name, "text", party_name)

            if not isinstance(party_name, str) or not party_name.strip():
                raise ValueError("Nome ausente nao e gravado.")

        share = self._check_share(role, share_field_name, share_value)
        normalized_reference = normalize_iso_date(reference_date, "A competencia")
        subject_column, subject_table, subject_id = self.subject(
            fund_id,
            fund_class_id,
        )

        if self.connection.execute(
            "SELECT id FROM " + subject_table + " WHERE id = ?",
            (subject_id,),
        ).fetchone() is None:
            raise ValueError("O assunto informado nao existe.")

        run = self.connection.execute(
            "SELECT source_id FROM collection_runs WHERE id = ?",
            (collection_run_id,),
        ).fetchone()

        if run is None:
            raise ValueError("A coleta informada nao existe.")

        if int(run["source_id"]) != int(source_id):
            raise ValueError("A coleta informada e de outra fonte.")

        raw = self.connection.execute(
            "SELECT source_id, collected_at FROM raw_records WHERE id = ?",
            (raw_record_id,),
        ).fetchone()

        if raw is None:
            raise ValueError("O manifesto informado nao existe.")

        if int(raw["source_id"]) != int(source_id):
            raise ValueError("O manifesto informado e de outra fonte.")

        normalized_collected_at = (
            str(raw["collected_at"])
            if collected_at is None
            else normalize_timestamp(collected_at, "A data de coleta")
        )
        checksum = self.checksum(
            subject_column,
            subject_id,
            source_id,
            role,
            field_name,
            party_cnpj,
            name_field_name,
            party_name,
            normalized_reference,
            share_field_name,
            share,
        )
        existing = self.connection.execute(
            self.select + " WHERE p.checksum = ?",
            (checksum,),
        ).fetchone()

        if existing is not None:
            return PartyRecordResult(self.row_to_record(existing), False, ())

        self.connection.execute("SAVEPOINT fundos_party_record")

        try:
            cursor = self.connection.execute(
                "INSERT INTO party_observations ("
                + subject_column
                + ", role, field_name, party_cnpj, name_field_name,"
                " party_name, source_id, collection_run_id, raw_record_id,"
                " reference_date, collected_at, checksum"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    subject_id,
                    role,
                    field_name,
                    party_cnpj,
                    name_field_name,
                    party_name,
                    source_id,
                    collection_run_id,
                    raw_record_id,
                    normalized_reference,
                    normalized_collected_at,
                    checksum,
                ),
            )

            if share is not None:
                # Logo depois do INSERT do papel e antes de qualquer outro
                # (party_conflicts inclusive): o trigger
                # trg_party_observation_shares_with_parent so aceita o
                # percentual da ultima linha inserida nesta conexao.
                self.connection.execute(
                    "INSERT INTO "
                    + SHARES_TABLE
                    + " (party_observation_id, share_field_name, share_value)"
                    " VALUES (?, ?, ?)",
                    (cursor.lastrowid, share_field_name, share),
                )

            party = self.get_by_id(cursor.lastrowid)
            conflicts = self._open_conflicts(party, subject_column)
            self.connection.execute("RELEASE SAVEPOINT fundos_party_record")
        except BaseException:
            self.connection.execute("ROLLBACK TO SAVEPOINT fundos_party_record")
            self.connection.execute("RELEASE SAVEPOINT fundos_party_record")
            raise

        return PartyRecordResult(party, True, conflicts)

    def _open_conflicts(self, party, subject_column):
        """Abre conflito contra cada valor diferente ja gravado para a chave."""

        others = self.connection.execute(
            self.select
            + " WHERE p."
            + subject_column
            + " = ? AND p.role = ? AND p.field_name = ? AND p.party_cnpj = ?"
            " AND p.reference_date = ? AND p.id <> ?",
            (
                getattr(party, subject_column),
                party.role,
                party.field_name,
                party.party_cnpj,
                party.reference_date,
                party.id,
            ),
        ).fetchall()

        created = []
        value = (
            party.name_field_name,
            party.party_name,
            party.share_field_name,
            party.share_value,
        )

        for other in others:
            if (
                other["name_field_name"],
                other["party_name"],
                other["share_field_name"],
                other["share_value"],
            ) == value:
                continue

            first, second = sorted((int(other["id"]), party.id))
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO party_conflicts (
                    field_name, reference_date,
                    party_observation_a_id, party_observation_b_id
                ) VALUES (?, ?, ?, ?)
                """,
                (party.field_name, party.reference_date, first, second),
            )

            if cursor.rowcount == 1:
                created.append(
                    self.conflict_to_record(
                        self.connection.execute(
                            "SELECT * FROM party_conflicts WHERE id = ?",
                            (cursor.lastrowid,),
                        ).fetchone()
                    )
                )

        return tuple(created)

    def list_by_subject(self, *, fund_id=None, fund_class_id=None, role=None):
        """Papeis do assunto (competencia mais recente antes)."""

        column, _, subject_id = self.subject(fund_id, fund_class_id)
        clause = "p." + column + " = ?"
        parameters = [subject_id]

        if role is not None:
            clause += " AND p.role = ?"
            parameters.append(role)

        rows = self.connection.execute(
            self.select
            + " WHERE "
            + clause
            + " ORDER BY p.reference_date DESC, p.role, p.party_cnpj, p.id",
            tuple(parameters),
        ).fetchall()

        return [self.row_to_record(row) for row in rows]

    def list_open_conflicts(self):
        """Conflitos de papel abertos."""

        rows = self.connection.execute(
            "SELECT * FROM party_conflicts WHERE status = 'open' ORDER BY id"
        ).fetchall()

        return [self.conflict_to_record(row) for row in rows]
