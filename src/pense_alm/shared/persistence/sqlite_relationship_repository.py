"""Repositorio SQLite de relacionamentos."""

from datetime import datetime
from sqlite3 import Connection, IntegrityError, Row
from uuid import UUID

from pense_alm.shared.entities import (
    DataProvenance,
    DuplicateRelationshipError,
    EntityRelationship,
    RelationshipType,
    RepositoryValidationError,
)

from .connection import SQLiteConnectionManager
from .migration_runner import MigrationRunner
from .serialization import (
    provenance_from_row,
    provenance_to_record,
    relationship_from_row,
    relationship_to_record,
)


class SQLiteRelationshipRepository:
    """Repositorio persistente de relacionamentos."""

    def __init__(
        self,
        connection_manager: SQLiteConnectionManager,
    ) -> None:
        if not isinstance(
            connection_manager,
            SQLiteConnectionManager,
        ):
            raise RepositoryValidationError(
                "connection_manager deve ser "
                "SQLiteConnectionManager."
            )

        self._connection_manager = connection_manager

        MigrationRunner(
            connection_manager
        ).apply_all()

    def save(
        self,
        relationship: EntityRelationship,
    ) -> EntityRelationship:
        """Salva ou atualiza um relacionamento."""

        if not isinstance(
            relationship,
            EntityRelationship,
        ):
            raise RepositoryValidationError(
                "relationship deve ser "
                "EntityRelationship."
            )

        try:
            with self._connection_manager.transaction() as connection:
                self._validate_related_entities(
                    connection,
                    relationship,
                )

                self._save_provenance(
                    connection,
                    relationship.provenance,
                )

                record = relationship_to_record(
                    relationship
                )

                connection.execute(
                    """
                    INSERT INTO entity_relationships (
                        relationship_id,
                        source_entity_id,
                        target_entity_id,
                        relationship_type,
                        canonical_key,
                        provenance_id,
                        status,
                        valid_from,
                        valid_to,
                        confidence_score,
                        notes,
                        created_at
                    )
                    VALUES (
                        :relationship_id,
                        :source_entity_id,
                        :target_entity_id,
                        :relationship_type,
                        :canonical_key,
                        :provenance_id,
                        :status,
                        :valid_from,
                        :valid_to,
                        :confidence_score,
                        :notes,
                        :created_at
                    )
                    ON CONFLICT(relationship_id)
                    DO UPDATE SET
                        source_entity_id =
                            excluded.source_entity_id,
                        target_entity_id =
                            excluded.target_entity_id,
                        relationship_type =
                            excluded.relationship_type,
                        canonical_key =
                            excluded.canonical_key,
                        provenance_id =
                            excluded.provenance_id,
                        status =
                            excluded.status,
                        valid_from =
                            excluded.valid_from,
                        valid_to =
                            excluded.valid_to,
                        confidence_score =
                            excluded.confidence_score,
                        notes =
                            excluded.notes,
                        created_at =
                            excluded.created_at
                    """,
                    record,
                )

        except IntegrityError as error:
            raise DuplicateRelationshipError(
                "Nao foi possivel salvar o relacionamento. "
                "A chave canonica pode ja pertencer "
                "a outro relacionamento."
            ) from error

        return relationship

    def get_by_id(
        self,
        relationship_id: UUID,
    ):
        """Localiza um relacionamento pelo UUID."""

        if not isinstance(relationship_id, UUID):
            raise RepositoryValidationError(
                "relationship_id deve ser UUID."
            )

        with self._connection_manager.read_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM entity_relationships
                WHERE relationship_id = ?
                """,
                (str(relationship_id),),
            ).fetchone()

            if row is None:
                return None

            return self._load_relationship(
                connection,
                row,
            )

    def get_by_canonical_key(
        self,
        canonical_key: str,
    ):
        """Localiza um relacionamento pela chave canonica."""

        if not isinstance(canonical_key, str):
            raise RepositoryValidationError(
                "canonical_key deve ser texto."
            )

        normalized_key = canonical_key.strip()

        if not normalized_key:
            raise RepositoryValidationError(
                "canonical_key nao pode ser vazia."
            )

        with self._connection_manager.read_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM entity_relationships
                WHERE canonical_key = ?
                """,
                (normalized_key,),
            ).fetchone()

            if row is None:
                return None

            return self._load_relationship(
                connection,
                row,
            )

    def list_by_source(
        self,
        source_entity_id: UUID,
    ):
        """Lista relações originadas pela entidade."""

        self._validate_entity_id(source_entity_id)

        return self._list_by_query(
            """
            SELECT *
            FROM entity_relationships
            WHERE source_entity_id = ?
            ORDER BY
                relationship_type,
                source_entity_id,
                target_entity_id
            """,
            (str(source_entity_id),),
        )

    def list_by_target(
        self,
        target_entity_id: UUID,
    ):
        """Lista relações destinadas à entidade."""

        self._validate_entity_id(target_entity_id)

        return self._list_by_query(
            """
            SELECT *
            FROM entity_relationships
            WHERE target_entity_id = ?
            ORDER BY
                relationship_type,
                source_entity_id,
                target_entity_id
            """,
            (str(target_entity_id),),
        )

    def list_active_at(
        self,
        reference_datetime: datetime,
        relationship_type: RelationshipType | None = None,
    ):
        """Lista relacionamentos ativos em uma data."""

        if not isinstance(reference_datetime, datetime):
            raise RepositoryValidationError(
                "reference_datetime deve ser datetime."
            )

        if reference_datetime.tzinfo is None:
            raise RepositoryValidationError(
                "reference_datetime deve possuir timezone."
            )

        if (
            relationship_type is not None
            and not isinstance(
                relationship_type,
                RelationshipType,
            )
        ):
            raise RepositoryValidationError(
                "relationship_type invalido."
            )

        parameters = [
            reference_datetime.isoformat(),
            reference_datetime.isoformat(),
        ]

        query = """
            SELECT *
            FROM entity_relationships
            WHERE status = 'active'
              AND (
                    valid_from IS NULL
                    OR valid_from <= ?
              )
              AND (
                    valid_to IS NULL
                    OR valid_to >= ?
              )
        """

        if relationship_type is not None:
            query += """
              AND relationship_type = ?
            """
            parameters.append(
                relationship_type.value
            )

        query += """
            ORDER BY
                relationship_type,
                source_entity_id,
                target_entity_id
        """

        return self._list_by_query(
            query,
            tuple(parameters),
        )

    def count(
        self,
        relationship_type: RelationshipType | None = None,
    ) -> int:
        """Conta relacionamentos, opcionalmente por tipo."""

        if (
            relationship_type is not None
            and not isinstance(
                relationship_type,
                RelationshipType,
            )
        ):
            raise RepositoryValidationError(
                "relationship_type invalido."
            )

        query = """
            SELECT COUNT(*) AS total
            FROM entity_relationships
        """
        parameters = ()

        if relationship_type is not None:
            query += """
            WHERE relationship_type = ?
            """
            parameters = (
                relationship_type.value,
            )

        with self._connection_manager.read_connection() as connection:
            row = connection.execute(
                query,
                parameters,
            ).fetchone()

        return int(row["total"])

    @staticmethod
    def _validate_entity_id(entity_id: UUID) -> None:
        if not isinstance(entity_id, UUID):
            raise RepositoryValidationError(
                "entity_id deve ser UUID."
            )

    @staticmethod
    def _validate_related_entities(
        connection: Connection,
        relationship: EntityRelationship,
    ) -> None:
        rows = connection.execute(
            """
            SELECT entity_id
            FROM entities
            WHERE entity_id IN (?, ?)
            """,
            (
                str(relationship.source_entity_id),
                str(relationship.target_entity_id),
            ),
        ).fetchall()

        found_ids = {
            row["entity_id"]
            for row in rows
        }

        required_ids = {
            str(relationship.source_entity_id),
            str(relationship.target_entity_id),
        }

        if found_ids != required_ids:
            raise RepositoryValidationError(
                "As entidades de origem e destino "
                "devem existir antes do relacionamento."
            )

    @staticmethod
    def _save_provenance(
        connection: Connection,
        provenance: DataProvenance,
    ) -> None:
        record = provenance_to_record(provenance)

        connection.execute(
            """
            INSERT INTO data_provenance (
                provenance_id,
                source_type,
                source_name,
                source_reference,
                collected_at,
                reference_date,
                validation_status,
                confidence_score
            )
            VALUES (
                :provenance_id,
                :source_type,
                :source_name,
                :source_reference,
                :collected_at,
                :reference_date,
                :validation_status,
                :confidence_score
            )
            ON CONFLICT(provenance_id)
            DO NOTHING
            """,
            record,
        )

    @staticmethod
    def _load_provenance(
        connection: Connection,
        provenance_id: str,
    ) -> DataProvenance:
        row = connection.execute(
            """
            SELECT *
            FROM data_provenance
            WHERE provenance_id = ?
            """,
            (provenance_id,),
        ).fetchone()

        if row is None:
            raise RepositoryValidationError(
                "Proveniencia persistida nao encontrada."
            )

        return provenance_from_row(row)

    def _load_relationship(
        self,
        connection: Connection,
        row: Row,
    ) -> EntityRelationship:
        provenance = self._load_provenance(
            connection,
            row["provenance_id"],
        )

        return relationship_from_row(
            row,
            provenance,
        )

    def _list_by_query(
        self,
        query: str,
        parameters,
    ):
        with self._connection_manager.read_connection() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

            return tuple(
                self._load_relationship(
                    connection,
                    row,
                )
                for row in rows
            )
