import unicodedata
from dataclasses import dataclass

from fundos.repositories import IdentityConflictError


@dataclass(frozen=True)
class QuotaSeriesRecord:
    """Serie de cotas de uma classe (ou do fundo, sem classe no cadastro)."""

    id: int
    fund_class_id: int | None
    fund_id: int | None
    series_label_key: str | None
    cvm_subclass_id: str | None
    created_at: str


class QuotaSeriesRepository:
    """Series pelo rotulo normalizado e/ou pelo ID_Subclasse da CVM.

    O rotulo original nao fica aqui: cada forma original e gravada como
    observacao (por exemplo tab_X_2.TAB_X_CLASSE_SERIE), com proveniencia.
    Uma chave ausente pode ser preenchida; uma chave existente nunca e trocada.
    """

    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def normalize_series_label(label):
        """Sem acento, minusculo, sem '|' e com espacos colapsados."""

        if not isinstance(label, str):
            raise ValueError("O rotulo da serie deve ser texto.")

        decomposed = unicodedata.normalize("NFKD", label)
        without_marks = "".join(
            char for char in decomposed if not unicodedata.combining(char)
        )
        key = " ".join(without_marks.casefold().replace("|", " ").split())

        if not key:
            raise ValueError("O rotulo da serie nao pode ficar vazio.")

        return key

    @staticmethod
    def row_to_record(row):
        return QuotaSeriesRecord(
            id=int(row["id"]),
            fund_class_id=row["fund_class_id"],
            fund_id=row["fund_id"],
            series_label_key=row["series_label_key"],
            cvm_subclass_id=row["cvm_subclass_id"],
            created_at=str(row["created_at"]),
        )

    def get_by_id(self, series_id):
        """Busca uma serie pelo ID."""

        row = self.connection.execute(
            "SELECT * FROM quota_series WHERE id = ?",
            (series_id,),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def get_or_create(
        self,
        *,
        fund_class_id=None,
        fund_id=None,
        label=None,
        cvm_subclass_id=None,
    ):
        """Devolve (serie, criada). Exatamente um pai e ao menos uma chave."""

        if (fund_class_id is None) == (fund_id is None):
            raise ValueError(
                "Informe exatamente um pai: a classe ou o fundo."
            )

        if label is None and cvm_subclass_id is None:
            raise ValueError(
                "Informe o rotulo da serie ou o ID de subclasse da CVM."
            )

        if fund_class_id is not None:
            parent_column, parent_id, parent_table = (
                "fund_class_id",
                fund_class_id,
                "fund_classes",
            )
        else:
            parent_column, parent_id, parent_table = "fund_id", fund_id, "funds"

        parent = self.connection.execute(
            "SELECT id FROM " + parent_table + " WHERE id = ?",
            (parent_id,),
        ).fetchone()

        if parent is None:
            raise ValueError("O fundo ou a classe informada nao existe.")

        key = None if label is None else self.normalize_series_label(label)
        subclass = None

        if cvm_subclass_id is not None:
            subclass = str(cvm_subclass_id).strip()

            if not subclass:
                raise ValueError("O ID de subclasse nao pode ficar vazio.")

        by_label = None
        by_subclass = None

        if key is not None:
            row = self.connection.execute(
                "SELECT * FROM quota_series WHERE "
                + parent_column
                + " = ? AND series_label_key = ?",
                (parent_id, key),
            ).fetchone()
            by_label = None if row is None else self.row_to_record(row)

        if subclass is not None:
            row = self.connection.execute(
                "SELECT * FROM quota_series WHERE cvm_subclass_id = ?",
                (subclass,),
            ).fetchone()
            by_subclass = None if row is None else self.row_to_record(row)

        if (
            by_label is not None
            and by_subclass is not None
            and by_label.id != by_subclass.id
        ):
            raise IdentityConflictError(
                "O rotulo e o ID de subclasse apontam para series diferentes."
            )

        existing = by_label or by_subclass

        if existing is None:
            cursor = self.connection.execute(
                "INSERT INTO quota_series ("
                + parent_column
                + ", series_label_key, cvm_subclass_id) VALUES (?, ?, ?)",
                (parent_id, key, subclass),
            )
            return self.get_by_id(cursor.lastrowid), True

        if getattr(existing, parent_column) != int(parent_id):
            raise IdentityConflictError(
                "A serie ja pertence a outro fundo ou classe."
            )

        for column, value in (
            ("series_label_key", key),
            ("cvm_subclass_id", subclass),
        ):
            stored = getattr(existing, column)

            if value is None or stored == value:
                continue

            if stored is not None:
                raise IdentityConflictError(
                    "A serie ja tem outra chave; uma chave existente "
                    "nunca e trocada."
                )

            self.connection.execute(
                "UPDATE quota_series SET " + column + " = ? WHERE id = ?",
                (value, existing.id),
            )

        return self.get_by_id(existing.id), False
