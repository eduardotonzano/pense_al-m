"""Linhas do relatorio de revisao do quota_class_map: so contagens e rotulos normalizados.

Nunca traz CNPJ, nome, valor de linha, o rotulo original nem o texto da
nota de revisao (so o tamanho dela). O rotulo normalizado so aparece onde a
revisao precisa dele: sem regra e novo desde a ultima revisao.
"""

from collections import Counter

from fundos.quota_classes.mapping import STATUSES
from fundos.quota_classes.mapping import UNMAPPED_TEXT


def _dash(value):
    return "-" if value is None else str(value)


def _validity(rule):
    if rule.valid_from is None and rule.valid_to is None:
        return "aberta"

    return _dash(rule.valid_from) + " a " + _dash(rule.valid_to)


def format_rules(rules):
    """As regras, com a situacao da revisao, o papel, a data e a vigencia."""

    statuses = Counter(rule.review_status for rule in rules)
    lines = [
        "  Regras: "
        + str(len(rules))
        + " ("
        + ", ".join(status + " " + str(statuses[status]) for status in STATUSES)
        + ")"
    ]

    for rule in rules:
        lines.append(
            "    #" + str(rule.id) + " " + rule.pattern
            + " | casamento " + rule.match_type
            + " | " + rule.level + " / " + rule.subtype
            + " | " + rule.review_status
            + " | revisor " + _dash(rule.reviewer)
            + " | data " + _dash(rule.reviewed_at)
            + " | vigencia " + _validity(rule)
        )

    return lines


def format_review_report(report):
    """O relatorio de revisao inteiro, em linhas."""

    lines = ["Mapa das series de FIDC (quota_class_map; decisao 8 de Fundos):"]
    lines.extend(format_rules(report.rules))
    lines.append(
        "  Ultima revisao: "
        + ("nenhuma revisao registrada" if report.last_review is None else report.last_review)
    )
    patterns = {rule.id: rule.pattern for rule in report.rules}

    if not report.competences:
        lines.append("Competencias com tab_X_2 no banco: nenhuma")

    for item in report.competences:
        lines.append("Competencia " + item.reference_date + ":")
        lines.append(
            "  Series de FIDC com tab_X_2: " + str(item.series)
            + " (rotulos normalizados distintos: " + str(item.label_keys) + ")"
        )
        lines.append("  Por regra (series; rotulos distintos):")

        counted = {rule_id: (series, keys) for rule_id, series, keys in item.by_rule}

        for rule in report.rules:
            series, keys = counted.get(rule.id, (0, 0))
            lines.append(
                "    #" + str(rule.id) + " " + patterns[rule.id] + " (" + rule.review_status + "): "
                + str(series) + "; " + str(keys)
            )

        lines.append(
            "  Sem regra (" + UNMAPPED_TEXT + "): "
            + str(sum(label.series for label in item.unmapped)) + " serie(s), "
            + str(len(item.unmapped)) + " rotulo(s)"
        )

        for label in item.unmapped:
            lines.append(
                "    " + label.label_key + ": " + str(label.series) + " serie(s), "
                + str(label.variants) + " variante(s) original(is), " + label.reason
            )

        lines.append(
            "  Ordem entre subordinadas nao informada (assuntos com 2 ou mais series de "
            "subtipo subordinada ou ausente, com ou sem mezanino): "
            + str(item.subjects_order_not_informed)
        )
        lines.append(
            "  Assuntos com 2 ou mais series nao seniores e nenhum mezanino: "
            + str(item.subjects_without_mezzanine)
        )
        lines.append(
            "  Series com subtipo ausente: " + str(item.absent_subtype_series)
            + " (em " + str(item.absent_subtype_subjects) + " assunto(s))"
        )

    if report.new_labels is None:
        lines.append(
            "Rotulos novos desde a ultima revisao: nenhuma revisao registrada; "
            + str(report.label_keys_total) + " rotulo(s) normalizado(s) de FIDC sem revisao"
        )
    else:
        lines.append(
            "Rotulos novos desde a ultima revisao: " + str(len(report.new_labels))
            + " (de " + str(report.label_keys_total) + " rotulo(s) normalizado(s) de FIDC)"
        )

        for label in report.new_labels:
            rule = "sem regra" if label.rule_id is None else "regra #" + str(label.rule_id)
            lines.append(
                "    " + label.label_key + ": " + str(label.series) + " serie(s), " + rule
            )

    lines.append(
        "FIAGRO (fora desta etapa): " + str(report.fiagro_series)
        + " serie(s) de FIAGRO sem mapa (as subclasses de FIAGRO nao dizem senior ou subordinada)"
    )

    return lines
