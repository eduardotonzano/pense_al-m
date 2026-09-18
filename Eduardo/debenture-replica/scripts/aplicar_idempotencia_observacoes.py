from pathlib import Path
import py_compile
import shutil

PATH = Path("src/debenture_search/repositories/observation_repository.py")
BACKUP = PATH.with_suffix(".py.before_value_idempotency.bak")

METHOD = '''
    def find_equivalent(
        self,
        debenture_id,
        source_id,
        field_name,
        value_type,
        value,
        unit=None,
        valid_from=None,
        valid_until=None,
        confidence="reported",
    ):
        """Busca uma observacao equivalente, ignorando o horario da coleta."""

        value_column = {
            "text": "value_text",
            "numeric": "value_numeric",
            "date": "value_date",
            "boolean": "value_boolean",
        }[value_type]

        if value_type == "numeric":
            stored_value = str(value)
        elif value_type == "boolean":
            stored_value = int(value)
        else:
            stored_value = value

        row = self.db.fetch_one(
            f"""
            SELECT
                id,
                debenture_id,
                source_id,
                raw_record_id,
                field_name,
                value_type,
                value_text,
                value_numeric,
                value_date,
                value_boolean,
                unit,
                observed_at,
                collected_at,
                valid_from,
                valid_until,
                confidence,
                checksum
            FROM observations
            WHERE debenture_id = ?
              AND source_id = ?
              AND field_name = ?
              AND value_type = ?
              AND {value_column} = ?
              AND unit IS ?
              AND valid_from IS ?
              AND valid_until IS ?
              AND confidence = ?
            ORDER BY observed_at DESC, collected_at DESC, id DESC
            LIMIT 1
            """,
            (
                debenture_id,
                source_id,
                field_name,
                value_type,
                stored_value,
                unit,
                valid_from,
                valid_until,
                confidence,
            ),
        )

        if row is None:
            return None

        return self.row_to_record(row)

'''

CREATE_INSERT = '''        existing_value = self.find_equivalent(
            debenture_id=debenture_id,
            source_id=source_id,
            field_name=normalized_field,
            value_type=normalized_type,
            value=normalized_value,
            unit=normalized_unit,
            valid_from=normalized_valid_from,
            valid_until=normalized_valid_until,
            confidence=normalized_confidence,
        )

        if existing_value is not None:
            return existing_value, False

'''

if not PATH.exists():
    raise SystemExit(f"Arquivo nao encontrado: {PATH}")

text = PATH.read_text(encoding="utf-8-sig")

if "def find_equivalent(" in text:
    raise SystemExit("A correcao ja parece ter sido aplicada.")

method_anchor = "    def create(\n"
if method_anchor not in text:
    raise SystemExit("Nao foi possivel localizar def create().")

checksum_anchor = "        checksum = self.generate_checksum(\n"
if checksum_anchor not in text:
    raise SystemExit("Nao foi possivel localizar a geracao do checksum.")

shutil.copy2(PATH, BACKUP)
text = text.replace(method_anchor, METHOD + method_anchor, 1)
text = text.replace(checksum_anchor, CREATE_INSERT + checksum_anchor, 1)
PATH.write_text(text, encoding="utf-8")

try:
    py_compile.compile(str(PATH), doraise=True)
except Exception:
    shutil.copy2(BACKUP, PATH)
    raise

print("Correcao aplicada com sucesso.")
print("Arquivo:", PATH)
print("Backup:", BACKUP)
print("Sintaxe: OK")
