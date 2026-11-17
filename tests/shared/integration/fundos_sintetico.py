"""Banco de Fundos sintetico para os testes da camada (FU7.2).

O banco nasce em tmp_path, com as migrations reais do modulo de Fundos lidas
como texto: o pacote fundos nunca e importado. Assim os CHECK e os gatilhos
reais valem para os dados de teste, e uma mudanca de schema quebra o teste
em vez de passar calada.

Nada aqui e dado real: os CNPJs vem de cnpj_amostras e os nomes sao
marcados como ficticios.
"""

import hashlib
import itertools
import sqlite3
from pathlib import Path


# Unica referencia a pasta do modulo de Fundos (o nome Gui/fundos e
# provisorio).
FUNDOS_MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[3] / "Gui" / "fundos" / "migrations"
)

MIGRATIONS = {
    1: "001_initial_schema.sql",
    2: "002_party_observations.sql",
    3: "003_party_observation_shares.sql",
    4: "004_holdings.sql",
}

COMPETENCIA = "2026-10-27"
INICIO = "2026-10-27T12:00:00.000000+00:00"
NORMAL = "Em Funcionamento Normal"
TIPO_CLASSE_FIDC = "Classes de Cotas de Fundos FIDC"
TIPO_CLASSE_FIAGRO = "Classes de Cotas de Fundos FIAGRO"
MEMBRO_FUNDO = "registro_fundo.csv"
MEMBRO_CLASSE = "registro_classe.csv"
MEMBROS = (MEMBRO_FUNDO, MEMBRO_CLASSE)

_CONTADOR = itertools.count(1)


def _checksum() -> str:
    return hashlib.sha256(
        ("fundos-sintetico:" + str(next(_CONTADOR))).encode("ascii")
    ).hexdigest()


def criar_banco(pasta, versoes=(1, 2, 3), nome="fundos.db") -> Path:
    """Cria o banco com as migrations pedidas, lidas como texto."""

    caminho = Path(pasta) / nome
    conexao = sqlite3.connect(caminho)

    try:
        for versao in versoes:
            sql = (FUNDOS_MIGRATIONS_DIR / MIGRATIONS[versao]).read_text(
                encoding="utf-8-sig"
            )
            conexao.executescript(sql)
    finally:
        conexao.close()

    return caminho


class BancoFundos:
    """Insere linhas validas no banco sintetico, uma conexao por chamada."""

    def __init__(self, caminho) -> None:
        self.caminho = Path(caminho)
        self._fontes = {}
        self._zips = {}
        self._membros = {}

    def _executar(self, sql, parametros=()):
        conexao = sqlite3.connect(self.caminho)

        try:
            conexao.execute("PRAGMA foreign_keys = ON")

            with conexao:
                cursor = conexao.execute(sql, parametros)

            return cursor.lastrowid
        finally:
            conexao.close()

    def _um(self, sql, parametros=()):
        conexao = sqlite3.connect(self.caminho)

        try:
            return conexao.execute(sql, parametros).fetchone()[0]
        finally:
            conexao.close()

    def coleta(
        self,
        *,
        status="success",
        inicio=INICIO,
        fonte="CVM_DADOS_ABERTOS",
        membros=MEMBROS,
        pendentes=(),
        sem_linhas=(),
    ) -> int:
        """Coleta com o ZIP e os membros do cadastro no manifesto."""

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
            " VALUES (?, ?, 'registro_fundo_classe.zip', 100, ?, ?, 'processed')",
            (fonte_id, coleta_id, _checksum(), inicio),
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
                    membro,
                    _checksum(),
                    None if membro in sem_linhas else 10,
                    inicio,
                    "pending" if membro in pendentes else "processed",
                ),
            )

        return coleta_id

    def _manifesto(self, coleta_id, campo) -> int:
        membro = MEMBRO_FUNDO if campo.startswith("registro_fundo.") else MEMBRO_CLASSE
        return self._membros[coleta_id].get(membro, self._zips[coleta_id])

    def _inicio(self, coleta_id) -> str:
        return self._um(
            "SELECT started_at FROM collection_runs WHERE id = ?",
            (coleta_id,),
        )

    def fundo(self, cnpj) -> int:
        return self._executar("INSERT INTO funds (cnpj) VALUES (?)", (cnpj,))

    def classe(self, cnpj, fundo_id) -> int:
        return self._executar(
            "INSERT INTO fund_classes (fund_id, cnpj) VALUES (?, ?)",
            (fundo_id, cnpj),
        )

    def observacao(
        self,
        coleta_id,
        campo,
        valor,
        *,
        fundo=None,
        classe=None,
        competencia=COMPETENCIA,
    ) -> int:
        return self._executar(
            "INSERT INTO observations (fund_id, fund_class_id, source_id,"
            " collection_run_id, raw_record_id, field_name, value_type, value_text,"
            " reference_date, collected_at, checksum)"
            " VALUES (?, ?, ?, ?, ?, ?, 'text', ?, ?, ?, ?)",
            (
                fundo,
                classe,
                self._fontes[coleta_id],
                coleta_id,
                self._manifesto(coleta_id, campo),
                campo,
                valor,
                competencia,
                self._inicio(coleta_id),
                _checksum(),
            ),
        )

    def papel(
        self,
        coleta_id,
        papel,
        campo,
        cnpj,
        *,
        fundo=None,
        classe=None,
        campo_nome=None,
        nome=None,
        competencia=COMPETENCIA,
    ) -> int:
        return self._executar(
            "INSERT INTO party_observations (fund_id, fund_class_id, role,"
            " field_name, party_cnpj, name_field_name, party_name, source_id,"
            " collection_run_id, raw_record_id, reference_date, collected_at,"
            " checksum) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                fundo,
                classe,
                papel,
                campo,
                cnpj,
                campo_nome,
                nome,
                self._fontes[coleta_id],
                coleta_id,
                self._manifesto(coleta_id, campo),
                competencia,
                self._inicio(coleta_id),
                _checksum(),
            ),
        )

    def fundo_do_cadastro(
        self,
        coleta_id,
        cnpj,
        *,
        nome="FUNDO FICTÍCIO",
        situacao=NORMAL,
        tipo="FIDC",
        tipo_pessoa="PJ",
        competencia=COMPETENCIA,
        fundo_id=None,
    ) -> int:
        """Fundo com as observacoes do cadastro; None deixa o campo de fora."""

        if fundo_id is None:
            fundo_id = self.fundo(cnpj)

        for campo, valor in (
            ("registro_fundo.Denominacao_Social", nome),
            ("registro_fundo.Situacao", situacao),
            ("registro_fundo.Tipo_Fundo", tipo),
            ("registro_fundo.Tipo_Pessoa_Gestor", tipo_pessoa),
        ):
            if valor is not None:
                self.observacao(
                    coleta_id,
                    campo,
                    valor,
                    fundo=fundo_id,
                    competencia=competencia,
                )

        return fundo_id

    def classe_do_cadastro(
        self,
        coleta_id,
        cnpj,
        fundo_id,
        *,
        nome="CLASSE FICTÍCIA",
        situacao=NORMAL,
        tipo=TIPO_CLASSE_FIDC,
        competencia=COMPETENCIA,
        classe_id=None,
    ) -> int:
        """Classe com as observacoes do cadastro; None deixa o campo de fora."""

        if classe_id is None:
            classe_id = self.classe(cnpj, fundo_id)

        for campo, valor in (
            ("registro_classe.Denominacao_Social", nome),
            ("registro_classe.Situacao", situacao),
            ("registro_classe.Tipo_Classe", tipo),
        ):
            if valor is not None:
                self.observacao(
                    coleta_id,
                    campo,
                    valor,
                    classe=classe_id,
                    competencia=competencia,
                )

        return classe_id

    def administrador(
        self,
        coleta_id,
        fundo_id,
        cnpj,
        nome="PRESTADORA FICTÍCIA",
        competencia=COMPETENCIA,
    ) -> int:
        return self.papel(
            coleta_id,
            "administrador",
            "registro_fundo.CNPJ_Administrador",
            cnpj,
            fundo=fundo_id,
            campo_nome="registro_fundo.Administrador",
            nome=nome,
            competencia=competencia,
        )

    def gestor(
        self,
        coleta_id,
        fundo_id,
        cnpj,
        nome="PRESTADORA FICTÍCIA",
        competencia=COMPETENCIA,
    ) -> int:
        return self.papel(
            coleta_id,
            "gestor",
            "registro_fundo.CPF_CNPJ_Gestor",
            cnpj,
            fundo=fundo_id,
            campo_nome="registro_fundo.Gestor",
            nome=nome,
            competencia=competencia,
        )

    def custodiante(
        self,
        coleta_id,
        classe_id,
        cnpj,
        nome="PRESTADORA FICTÍCIA",
        competencia=COMPETENCIA,
    ) -> int:
        return self.papel(
            coleta_id,
            "custodiante",
            "registro_classe.CNPJ_Custodiante",
            cnpj,
            classe=classe_id,
            campo_nome="registro_classe.Custodiante",
            nome=nome,
            competencia=competencia,
        )
