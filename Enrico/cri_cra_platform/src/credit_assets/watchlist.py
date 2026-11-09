"""Lista de acompanhamento de crédito dos ativos do catálogo: ordena por gravidade os sinais que a plataforma já tem.

Junta, por ativo, o Informe Mensal da CVM (séries em atraso, eventos dos últimos 12 meses), o que as atas decidiram
(regras de texto de ``assembly_outcomes``), o parecer da DF do patrimônio separado e o contágio do devedor. É triagem
para leitura, não alerta: nenhum nível depende de regra contratual aprovada, e cada motivo aponta a fonte.

Níveis (do mais grave para o menos):
1. a ata declarou vencimento antecipado, tratou de recuperação judicial ou extrajudicial, de liquidação do patrimônio
   separado ou de dação em pagamento;
2. série em atraso no Informe mais recente;
3. nos últimos 12 meses: waiver, repactuação, não declaração do vencimento antecipado ou aporte dos titulares nas atas;
   ou DF com ressalva, abstenção ou opinião adversa; ou devedor com outras emissões em atraso (contágio);
4. outros sinais de triagem do mercado (pontuação do ranking maior que zero) ou eventos do Informe nos últimos 12 meses;
5. nenhum sinal.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SEVERE = ("vencimento_antecipado_declarado", "recuperacao_judicial", "liquidacao_patrimonio", "dacao_em_pagamento")
STRESS = ("waiver", "prorrogacao_repactuacao", "vencimento_antecipado_nao_declarado", "aporte_titulares")
LEVEL_NAMES = {1: "evento grave nas atas", 2: "atraso no Informe", 3: "estresse recente", 4: "outros sinais", 5: "sem sinal"}


@dataclass
class AssetSignals:
    late_series: int = 0
    informe_events: list[str] = field(default_factory=list)       # "2026-07 entrou_em_atraso", ...
    ata_decisions: list[tuple[str, str]] = field(default_factory=list)  # (data, evento)
    df_opinion: str = ""
    df_flags: list[str] = field(default_factory=list)
    contagion: bool = False
    ranking_score: int = 0


def _approved(event: str, prefixes: tuple[str, ...]) -> bool:
    """Evento de ata aprovado (ou declarado) de um dos assuntos; rejeitados não contam, salvo a rejeição da não
    declaração do vencimento antecipado, que é grave."""

    if prefixes is SEVERE and event.startswith("nao_declaracao_do_vencimento_antecipado_rejeitada"):
        return True
    if event.endswith("_rejeitado") or event.endswith("_rejeitada"):
        return False
    return any(event.startswith(prefix) for prefix in prefixes)


def classify(signals: AssetSignals, since: str) -> tuple[int, list[str]]:
    """Nível e motivos. ``since`` (AAAA-MM-DD) limita as decisões de ata do nível 3; as do nível 1 valem sempre."""

    reasons: list[str] = []
    severe = [(d, e) for d, e in signals.ata_decisions if _approved(e, SEVERE)]
    if severe:
        date, event = max(severe)
        reasons.append(f"ata de {date}: {event.replace('_', ' ')}")
        return 1, reasons + _rest(signals, since)
    if signals.late_series:
        reasons.append(f"{signals.late_series} série(s) em atraso no Informe")
        return 2, reasons + _rest(signals, since)
    rest = _rest(signals, since)
    stress = [r for r in rest if not r.startswith("Informe") and not r.startswith("ranking")]
    if stress:
        return 3, rest
    if rest:
        return 4, rest
    return 5, []


def _rest(signals: AssetSignals, since: str) -> list[str]:
    reasons = []
    recent = sorted({e for d, e in signals.ata_decisions if d >= since and _approved(e, STRESS)})
    if recent:
        reasons.append("atas em 12 meses: " + ", ".join(e.replace("_", " ") for e in recent))
    if any(flag in ("df_com_ressalva", "df_abstencao_ou_adversa") for flag in signals.df_flags):
        reasons.append(f"DF: {signals.df_opinion}")
    if signals.contagion:
        reasons.append("devedor com outras emissões em atraso")
    if signals.informe_events:
        reasons.append("Informe em 12 meses: " + ", ".join(sorted(set(e.split(" ", 1)[1] for e in signals.informe_events))))
    if signals.ranking_score > 0:
        reasons.append(f"ranking de triagem: {signals.ranking_score} pontos")
    return reasons
