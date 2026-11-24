"""Banco sintetico para os testes dos indicadores (FU11.1).

Tudo e ficticio: os CNPJs vem de apoio.make_test_cnpj e os valores foram
inventados para cada teste. Os nomes de campo sao os reais da CVM
(tabela.coluna), porque e isso que os indicadores leem.
"""

from apoio import T0
from apoio import insert_observation
from apoio import insert_raw
from apoio import insert_run
from apoio import make_test_cnpj
from apoio import source_id

from fundos.indicators.values import CLASS_SUBJECT
from fundos.indicators.values import FUND_SUBJECT
from fundos.indicators.values import Subject
from fundos.repositories.party_observation_repository import PartyObservationRepository


_KINDS = {CLASS_SUBJECT: "class", FUND_SUBJECT: "fund"}
_SUBJECT_ARGUMENT = {CLASS_SUBJECT: "fund_class_id", FUND_SUBJECT: "fund_id"}


class SyntheticInforme:
    """Fontes, coletas, manifestos e assuntos ficticios, e atalho de gravacao."""

    def __init__(self, connection):
        self.connection = connection
        self.source = {
            "cvm": source_id(connection, "CVM_DADOS_ABERTOS"),
            "manual": source_id(connection, "MANUAL"),
        }
        self.run = {
            name: insert_run(connection, source)
            for name, source in self.source.items()
        }
        self.raw = {
            name: insert_raw(connection, self.source[name], self.run[name], name)
            for name in self.source
        }

    def fund_and_class(self, n=1):
        """Fundo e classe com o mesmo CNPJ ficticio; devolve (fundo, classe)."""

        cnpj = make_test_cnpj(n)
        fund_id = self.connection.execute(
            "INSERT INTO funds (cnpj) VALUES (?)", (cnpj,)
        ).lastrowid
        class_id = self.connection.execute(
            "INSERT INTO fund_classes (fund_id, cnpj) VALUES (?, ?)",
            (fund_id, cnpj),
        ).lastrowid

        return Subject(FUND_SUBJECT, fund_id, cnpj), Subject(
            CLASS_SUBJECT, class_id, cnpj
        )

    def new_raw(self, label, collected_at, source="cvm"):
        """Outro manifesto da mesma fonte (por exemplo, uma reapresentacao)."""

        return insert_raw(
            self.connection, self.source[source], self.run[source], label, collected_at
        )

    def put(
        self,
        subject,
        values,
        reference_date="2026-09-30",
        source="cvm",
        collected_at=T0,
        raw=None,
        value_type="numeric",
    ):
        """Grava {campo: valor} do assunto; devolve {campo: id da observacao}."""

        return {
            field_name: insert_observation(
                self.connection,
                subject=(_KINDS[subject.kind], subject.id),
                source=self.source[source],
                run=self.run[source],
                raw=raw or self.raw[source],
                field_name=field_name,
                value=value,
                value_type=value_type,
                reference_date=reference_date,
                collected_at=collected_at,
            )
            for field_name, value in values.items()
        }

    def put_cedente(
        self,
        subject,
        block,
        position,
        cnpj,
        share=None,
        reference_date="2026-09-30",
        source="cvm",
        collected_at=T0,
        raw=None,
    ):
        """Grava um cedente ficticio pelo repositorio real (papel cedente).

        block e "a" (TAB_I2A12) ou "b" (TAB_I2B12); share None grava o
        cedente sem percentual. Devolve o PartyRecordResult.
        """

        group = {"a": "TAB_I2A12", "b": "TAB_I2B12"}[block]
        share_field = "tab_I." + group + "_PR_CEDENTE_" + str(position)

        return PartyObservationRepository(self.connection).record(
            **{_SUBJECT_ARGUMENT[subject.kind]: subject.id},
            role="cedente",
            field_name="tab_I." + group + "_CPF_CNPJ_CEDENTE_" + str(position),
            party_cnpj=cnpj,
            share_field_name=None if share is None else share_field,
            share_value=share,
            source_id=self.source[source],
            collection_run_id=self.run[source],
            raw_record_id=raw or self.raw[source],
            reference_date=reference_date,
            collected_at=collected_at,
        )

    def put_administrator(self, subject, cnpj, reference_date="2026-09-30"):
        """Grava uma administradora ficticia (outro papel, para teste de filtro)."""

        return PartyObservationRepository(self.connection).record(
            **{_SUBJECT_ARGUMENT[subject.kind]: subject.id},
            role="administrador",
            field_name="tab_I.CNPJ_ADMIN",
            party_cnpj=cnpj,
            name_field_name="tab_I.ADMIN",
            party_name="Administradora Ficticia",
            source_id=self.source["cvm"],
            collection_run_id=self.run["cvm"],
            raw_record_id=self.raw["cvm"],
            reference_date=reference_date,
            collected_at=T0,
        )

    def open_conflict(self, field_name, reference_date, first_id, second_id):
        """Conflito aberto entre duas observacoes do mesmo campo e competencia."""

        first, second = sorted((first_id, second_id))
        self.connection.execute(
            "INSERT INTO data_conflicts"
            " (field_name, reference_date, observation_a_id, observation_b_id)"
            " VALUES (?, ?, ?, ?)",
            (field_name, reference_date, first, second),
        )
