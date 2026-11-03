"""Dados ficticios e atalhos de SQL para os testes do modulo de Fundos.

Nada aqui e dado real. Os CNPJs tem DV valido calculado sobre raizes que nao
parecem de empresa (9999999n + 9999 ou ZZZZZZZn + ZZZZ); DV valido nao prova
que o CNPJ nao exista, e sem rede nao ha como conferir na Receita. O formato
de CPF usado (99999999999) tem DV invalido, entao nao e CPF de ninguem.

O calculo do DV aqui e independente do codigo de producao (fundos.cnpj), de
proposito: os testes conferem um contra o outro.
"""

import hashlib


FAKE_CPF = "99999999999"
FAKE_CPF_MASKED = "999.999.999-99"

T0 = "2026-10-27T13:00:00.000000+00:00"
T1 = "2026-10-27T14:00:00.000000+00:00"
T2 = "2026-10-27T15:00:00.000000+00:00"

_WEIGHTS_FIRST = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_WEIGHTS_SECOND = (6,) + _WEIGHTS_FIRST


def _check_digit(values, weights):
    remainder = sum(v * w for v, w in zip(values, weights)) % 11
    return 0 if remainder < 2 else 11 - remainder


def make_test_cnpj(n=1, *, alphanumeric=False):
    """CNPJ ficticio sem mascara, com DV valido."""

    if not 0 <= n <= 9:
        raise ValueError("n vai de 0 a 9.")

    if alphanumeric:
        base = "ZZZZZZZ" + str(n) + "ZZZZ"
    else:
        base = "9999999" + str(n) + "9999"

    values = [ord(char) - 48 for char in base]
    first = _check_digit(values, _WEIGHTS_FIRST)
    second = _check_digit(values + [first], _WEIGHTS_SECOND)

    return base + str(first) + str(second)


def fake_sha256(label):
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def source_id(connection, code):
    return connection.execute(
        "SELECT id FROM sources WHERE code = ?",
        (code,),
    ).fetchone()[0]


def insert_run(connection, source, started_at=T0):
    return connection.execute(
        "INSERT INTO collection_runs (source_id, started_at) VALUES (?, ?)",
        (source, started_at),
    ).lastrowid


def insert_raw(connection, source, run, label="arquivo", collected_at=T0):
    return connection.execute(
        """
        INSERT INTO raw_records (
            source_id, collection_run_id, file_name, size_bytes,
            sha256, collected_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            source,
            run,
            label + "_ficticio.zip",
            100,
            fake_sha256(label),
            collected_at,
        ),
    ).lastrowid


def seed_base(connection):
    """Fontes, uma coleta e um manifesto por fonte, um fundo e uma classe."""

    cvm = source_id(connection, "CVM_DADOS_ABERTOS")
    manual = source_id(connection, "MANUAL")
    cvm_run = insert_run(connection, cvm)
    manual_run = insert_run(connection, manual)
    fund = connection.execute(
        "INSERT INTO funds (cnpj) VALUES (?)",
        (make_test_cnpj(1),),
    ).lastrowid
    fund_class = connection.execute(
        "INSERT INTO fund_classes (fund_id, cnpj) VALUES (?, ?)",
        (fund, make_test_cnpj(1),),
    ).lastrowid

    return {
        "cvm": cvm,
        "manual": manual,
        "cvm_run": cvm_run,
        "manual_run": manual_run,
        "cvm_raw": insert_raw(connection, cvm, cvm_run, "cvm"),
        "manual_raw": insert_raw(connection, manual, manual_run, "manual"),
        "fund": fund,
        "fund_class": fund_class,
    }


_VALUE_COLUMNS = {
    "text": "value_text",
    "numeric": "value_numeric",
    "date": "value_date",
    "boolean": "value_boolean",
}

_SUBJECT_COLUMNS = {
    "fund": "fund_id",
    "class": "fund_class_id",
    "series": "quota_series_id",
}


def insert_observation(
    connection,
    *,
    subject,
    source,
    run,
    raw,
    field_name="tab_IV.TAB_IV_A_VL_PL",
    value="100",
    value_type="numeric",
    reference_date="2026-09-30",
    collected_at=T0,
):
    """Insere uma observacao direto por SQL; subject = (tipo, id)."""

    kind, subject_id = subject
    subject_column = _SUBJECT_COLUMNS[kind]
    value_column = _VALUE_COLUMNS[value_type]
    checksum = fake_sha256(
        repr((kind, subject_id, source, field_name, reference_date, value, collected_at))
    )

    return connection.execute(
        f"""
        INSERT INTO observations (
            {subject_column}, source_id, collection_run_id, raw_record_id,
            field_name, value_type, {value_column}, reference_date,
            collected_at, checksum
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            subject_id,
            source,
            run,
            raw,
            field_name,
            value_type,
            value,
            reference_date,
            collected_at,
            checksum,
        ),
    ).lastrowid
