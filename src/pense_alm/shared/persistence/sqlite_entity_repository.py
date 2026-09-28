"""Repositorio SQLite de entidades."""

from sqlite3 import Connection, IntegrityError, Row
from uuid import UUID

from pense_alm.shared.entities import (
    DataProvenance,
    DuplicateEntityError,
    Entity,
    EntityIdentifier,
    EntityType,
    IdentifierType,
    RepositoryValidationError,
    normalize_identifier,
)

from .connection import SQLiteConnectionManager
from .migration_runner import MigrationRunner
from .serialization import (
    entity_from_rows,
    entity_to_record,
    identifier_from_row,
    identifier_to_record,
    provenance_from_row,
    provenance_to_record,
)


class SQLiteEntityRepository:
    """Repositorio persistente de entidades em SQLite."""

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

    def save(self, entity: Entity) -> Entity:
        """Salva ou atualiza uma entidade completa."""

        if not isinstance(entity, Entity):
            raise RepositoryValidationError(
                "entity deve ser uma instancia de Entity."
            )

        try:
            with self._connection_manager.transaction() as connection:
                self._save_provenance(
                    connection,
                    entity.provenance,
                )

                for identifier in entity.identifiers:
                    self._save_provenance(
                        connection,
                        identifier.provenance,
                    )

                entity_record = entity_to_record(entity)

                connection.execute(
                    """
                    INSERT INTO entities (
                        entity_id,
                        legal_name,
                        trade_name,
                        entity_type,
                        status,
                        country_code,
                        sector,
                        subsector,
                        website,
                        provenance_id,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :entity_id,
                        :legal_name,
                        :trade_name,
                        :entity_type,
                        :status,
                        :country_code,
                        :sector,
                        :subsector,
                        :website,
                        :provenance_id,
                        :created_at,
                        :updated_at
                    )
                    ON CONFLICT(entity_id)
                    DO UPDATE SET
                        legal_name = excluded.legal_name,
                        trade_name = excluded.trade_name,
                        entity_type = excluded.entity_type,
                        status = excluded.status,
                        country_code = excluded.country_code,
                        sector = excluded.sector,
                        subsector = excluded.subsector,
                        website = excluded.website,
                        provenance_id = excluded.provenance_id,
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at
                    """,
                    entity_record,
                )

                connection.execute(
                    """
                    DELETE FROM entity_identifiers
                    WHERE entity_id = ?
                    """,
                    (str(entity.entity_id),),
                )

                for identifier in entity.identifiers:
                    connection.execute(
                        """
                        INSERT INTO entity_identifiers (
                            entity_id,
                            identifier_type,
                            value,
                            canonical_key,
                            provenance_id,
                            is_primary
                        )
                        VALUES (
                            :entity_id,
                            :identifier_type,
                            :value,
                            :canonical_key,
                            :provenance_id,
                            :is_primary
                        )
                        """,
                        identifier_to_record(
                            entity.entity_id,
                            identifier,
                        ),
                    )

        except IntegrityError as error:
            raise DuplicateEntityError(
                "Nao foi possivel salvar a entidade. "
                "Um identificador pode pertencer "
                "a outra entidade."
            ) from error

        return entity

    def get_by_id(
        self,
        entity_id: UUID,
    ) -> Entity | None:
        """Localiza uma entidade pelo UUID."""

        if not isinstance(entity_id, UUID):
            raise RepositoryValidationError(
                "entity_id deve ser UUID."
            )

        with self._connection_manager.read_connection() as connection:
            entity_row = connection.execute(
                """
                SELECT *
                FROM entities
                WHERE entity_id = ?
                """,
                (str(entity_id),),
            ).fetchone()

            if entity_row is None:
                return None

            return self._load_entity(
                connection,
                entity_row,
            )

    def get_by_identifier(
        self,
        identifier_type: IdentifierType,
        value: str,
    ) -> Entity | None:
        """Localiza uma entidade por identificador."""

        if not isinstance(identifier_type, IdentifierType):
            raise RepositoryValidationError(
                "identifier_type invalido."
            )

        normalized = normalize_identifier(
            identifier_type,
            value,
        )

        canonical_key = (
            f"{identifier_type.value}:{normalized}"
        )

        with self._connection_manager.read_connection() as connection:
            entity_row = connection.execute(
                """
                SELECT entity.*
                FROM entities AS entity
                INNER JOIN entity_identifiers AS identifier
                    ON identifier.entity_id = entity.entity_id
                WHERE identifier.canonical_key = ?
                """,
                (canonical_key,),
            ).fetchone()

            if entity_row is None:
                return None

            return self._load_entity(
                connection,
                entity_row,
            )

    def list_all(
        self,
        entity_type: EntityType | None = None,
    ) -> tuple[Entity, ...]:
        """Lista entidades em ordem deterministica."""

        if (
            entity_type is not None
            and not isinstance(entity_type, EntityType)
        ):
            raise RepositoryValidationError(
                "entity_type invalido."
            )

        parameters: tuple[str, ...] = ()

        query = """
            SELECT *
            FROM entities
        """

        if entity_type is not None:
            query += """
                WHERE entity_type = ?
            """

            parameters = (entity_type.value,)

        query += """
            ORDER BY
                legal_name COLLATE NOCASE,
                entity_id
        """

        with self._connection_manager.read_connection() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

            return tuple(
                self._load_entity(connection, row)
                for row in rows
            )

    def exists(self, entity_id: UUID) -> bool:
        """Indica se uma entidade existe."""

        if not isinstance(entity_id, UUID):
            raise RepositoryValidationError(
                "entity_id deve ser UUID."
            )

        with self._connection_manager.read_connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM entities
                WHERE entity_id = ?
                """,
                (str(entity_id),),
            ).fetchone()

        return row is not None

    def count(
        self,
        entity_type: EntityType | None = None,
    ) -> int:
        """Conta entidades, opcionalmente por tipo."""

        if (
            entity_type is not None
            and not isinstance(entity_type, EntityType)
        ):
            raise RepositoryValidationError(
                "entity_type invalido."
            )

        parameters: tuple[str, ...] = ()

        query = """
            SELECT COUNT(*) AS total
            FROM entities
        """

        if entity_type is not None:
            query += """
                WHERE entity_type = ?
            """

            parameters = (entity_type.value,)

        with self._connection_manager.read_connection() as connection:
            row = connection.execute(
                query,
                parameters,
            ).fetchone()

        return int(row["total"])

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

    def _load_entity(
        self,
        connection: Connection,
        entity_row: Row,
    ) -> Entity:
        entity_provenance = self._load_provenance(
            connection,
            entity_row["provenance_id"],
        )

        identifier_rows = connection.execute(
            """
            SELECT *
            FROM entity_identifiers
            WHERE entity_id = ?
            ORDER BY
                identifier_type,
                value
            """,
            (entity_row["entity_id"],),
        ).fetchall()

        identifiers: list[EntityIdentifier] = []

        for identifier_row in identifier_rows:
            identifier_provenance = self._load_provenance(
                connection,
                identifier_row["provenance_id"],
            )

            identifiers.append(
                identifier_from_row(
                    identifier_row,
                    identifier_provenance,
                )
            )

        return entity_from_rows(
            entity_row,
            entity_provenance,
            tuple(identifiers),
        )

