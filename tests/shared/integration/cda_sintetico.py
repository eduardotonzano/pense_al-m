"""Coletas e posicoes do CDA no banco de Fundos sintetico (FU7.2, PR C).

Estende o BancoFundos do B2 sem mexer nele: as linhas passam pelos CHECK e
pelos gatilhos reais da migration 004. Nada aqui e dado real: os CNPJs vem
de cnpj_amostras e o nome do investido e marcado como ficticio.
"""

from .fundos_sintetico import BancoFundos, _checksum


PERIODO = "202610"
COMPETENCIA_CDA = "2026-10-31"
INICIO_CDA = "2026-11-28T12:00:00.000000+00:00"
MEMBROS_CDA = ("cda_fie", "cda_fie_CONFID")


class BancoCda(BancoFundos):
    """BancoFundos com coleta de CDA, posicao identificada e confidencial."""

    def coleta_cda(
        self,
        *,
        periodo=PERIODO,
        status="success",
        inicio=INICIO_CDA,
        fonte="CVM_DADOS_ABERTOS",
        membros=MEMBROS_CDA,
        pendentes=(),
        sem_linhas=(),
    ) -> int:
        """Coleta com o ZIP cda_fi_AAAAMM.zip e os membros lidos no manifesto."""

        fonte_id = self._um("SELECT id FROM sources WHERE code = ?", (fonte,))
        fim = None if status == "running" else inicio
        coleta_id = self._executar(
            "INSERT INTO collection_runs (source_id, started_at, finished_at, status)"
            " VALUES (?, ?, ?, ?)",
            (fonte_id, inicio, fim, status),
        )
        zip_id = self._executar(
            "INSERT INTO raw_records (source_id, collection_run_id, file_name,"
            " size_bytes, sha256, collected_at, processing_status)"
            " VALUES (?, ?, ?, 100, ?, ?, 'processed')",
            (fonte_id, coleta_id, "cda_fi_" + periodo + ".zip", _checksum(), inicio),
        )
        self._fontes[coleta_id] = fonte_id
        self._zips[coleta_id] = zip_id
        self._membros[coleta_id] = {}

        for membro in membros:
            self._membros[coleta_id][membro] = self._executar(
                "INSERT INTO raw_records (source_id, collection_run_id,"
                " parent_raw_record_id, file_name, size_bytes, sha256, line_count,"
                " collected_at, processing_status)"
                " VALUES (?, ?, ?, ?, 10, ?, ?, ?, ?)",
                (
                    fonte_id,
                    coleta_id,
                    zip_id,
                    membro + "_" + periodo + ".csv",
                    _checksum(),
                    None if membro in sem_linhas else 10,
                    inicio,
                    "pending" if membro in pendentes else "processed",
                ),
            )

        return coleta_id

    def posicao(
        self,
        coleta_id,
        investido,
        *,
        fundo_id=None,
        classe_id=None,
        competencia=COMPETENCIA_CDA,
        ordem=1,
    ) -> int:
        """Posicao identificada em cotas, com nome e valor ficticios."""

        return self._executar(
            "INSERT INTO holdings (fund_id, fund_class_id, investee_field_name,"
            " investee_cnpj, name_field_name, investee_name, value_field_name,"
            " market_value, source_id, collection_run_id, raw_record_id,"
            " reference_date, line_order, collected_at, checksum)"
            " VALUES (?, ?, 'cda_fie.CPF_CNPJ_EMISSOR', ?, 'cda_fie.EMISSOR',"
            " 'FUNDO INVESTIDO FICTICIO', 'cda_fie.VL_MERC_POS_FINAL', '1000.00',"
            " ?, ?, ?, ?, ?, ?, ?)",
            (
                fundo_id,
                classe_id,
                investido,
                self._fontes[coleta_id],
                coleta_id,
                self._membros[coleta_id].get("cda_fie", self._zips[coleta_id]),
                competencia,
                ordem,
                self._inicio(coleta_id),
                _checksum(),
            ),
        )

    def confidencial(
        self,
        coleta_id,
        *,
        fundo_id=None,
        classe_id=None,
        competencia=COMPETENCIA_CDA,
        ate="2026-12-31",
    ) -> int:
        """Consolidado confidencial de cotas, sem investido."""

        return self._executar(
            "INSERT INTO confidential_holdings (fund_id, fund_class_id,"
            " value_field_name, market_value, confidential_until_field_name,"
            " confidential_until, source_id, collection_run_id, raw_record_id,"
            " reference_date, collected_at, checksum)"
            " VALUES (?, ?, 'cda_fie_CONFID.VL_MERC_POS_FINAL', '500.00',"
            " 'cda_fie_CONFID.DT_CONFID_APLIC', ?, ?, ?, ?, ?, ?, ?)",
            (
                fundo_id,
                classe_id,
                ate,
                self._fontes[coleta_id],
                coleta_id,
                self._membros[coleta_id].get("cda_fie_CONFID", self._zips[coleta_id]),
                competencia,
                self._inicio(coleta_id),
                _checksum(),
            ),
        )
