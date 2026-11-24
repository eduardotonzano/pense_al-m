"""Alienacoes do mes para o cedente e partes relacionadas (tab_VII, FU11.2).

Sao ALIENACOES de direitos creditorios realizadas no mes, e nao aquisicoes
nem uma medida geral de parte relacionada. Vem do item VII do modelo do
Suplemento G ("Negocios com Direitos Creditorios Realizados no Mes"), letra
b) Alienacoes, e so dos dois grupos cuja descricao oficial cita parte
relacionada:
- VII.b.1 "Para o Cedente e Partes Relacionadas aos Cedentes";
- VII.b.2 "Para os Prestadores de Servicos e Partes Relacionadas aos
  Prestadores de Servicos".

Cada grupo traz Quantidade, Valor e Valor Contabil, como informados, por
assunto (classe ou fundo) e competencia, com fonte e estado: valor ausente e
sem_dado, nunca zero; zero informado e zero.

Nao confirmado, e por isso nada e calculado: a diferenca entre Valor e Valor
Contabil (o dicionario nao a define). Ficam fora: VII.a (aquisicoes),
VII.b.3 (alienacoes para terceiros), VII.c (substituicoes) e VII.d
(recompras), cuja descricao nao cita parte relacionada. Nada e gravado.
"""

from dataclasses import dataclass

from fundos.indicators.reading import read_competence
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Subject


# (item do modelo, nome oficial, ((rotulo oficial, campo), ...)), sem acento.
GROUPS = (
    (
        "VII.b.1",
        "Alienacoes para o Cedente e Partes Relacionadas aos Cedentes",
        (
            ("Quantidade", "tab_VII.TAB_VII_B1_1_QT_CEDENTE"),
            ("Valor", "tab_VII.TAB_VII_B1_2_VL_CEDENTE"),
            ("Valor Contabil", "tab_VII.TAB_VII_B1_3_VL_CONTAB_CEDENTE"),
        ),
    ),
    (
        "VII.b.2",
        "Alienacoes para os Prestadores de Servicos e Partes Relacionadas aos "
        "Prestadores de Servicos",
        (
            ("Quantidade", "tab_VII.TAB_VII_B2_1_QT_PREST"),
            ("Valor", "tab_VII.TAB_VII_B2_2_VL_PREST"),
            ("Valor Contabil", "tab_VII.TAB_VII_B2_3_VL_CONTAB_PREST"),
        ),
    ),
)


@dataclass(frozen=True)
class SalesGroup:
    """Um grupo de alienacoes do mes (VII.b.1 ou VII.b.2), como informado."""

    item: str
    official_name: str
    values: tuple[tuple[str, FieldValue], ...]

    def value(self, label):
        """O valor de Quantidade, Valor ou Valor Contabil."""

        return next(value for name, value in self.values if name == label)


@dataclass(frozen=True)
class RelatedPartySalesResult:
    """Alienacoes do mes a cedente e a prestadores (e partes relacionadas)."""

    subject: Subject
    reference_date: str
    groups: tuple[SalesGroup, ...]

    def group(self, item):
        """O grupo VII.b.1 ou VII.b.2."""

        return next(group for group in self.groups if group.item == item)


def fields():
    """Os 6 campos lidos, na ordem dos grupos."""

    return tuple(name for _, _, labeled in GROUPS for _, name in labeled)


def alienacoes_partes_relacionadas(connection, reference_date, subjects=None):
    """Alienacoes do mes de VII.b.1 e VII.b.2 por assunto, como informadas."""

    results = []

    for subject, values in read_competence(
        connection, reference_date, fields(), subjects
    ).items():
        results.append(
            RelatedPartySalesResult(
                subject=subject,
                reference_date=values[GROUPS[0][2][0][1]].reference_date,
                groups=tuple(
                    SalesGroup(
                        item,
                        official_name,
                        tuple((label, values[name]) for label, name in labeled),
                    )
                    for item, official_name, labeled in GROUPS
                ),
            )
        )

    return tuple(results)
