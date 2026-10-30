"""O que uma ata de assembleia de CRA/CRI decidiu, por regras de texto (sem IA).

Separa a parte da decisão (depois de "Deliberações", "colocada em votação" ou "deliberaram") do eco da ordem do dia e,
em volta de cada verbo de decisão ("aprovam", "não aprovaram", "rejeitaram"), procura o assunto: declaração ou não
declaração de vencimento antecipado, waiver, prorrogação, liquidação do patrimônio separado, troca de prestador,
resgate ou amortização extraordinária, dação em pagamento. Também marca assembleia não instalada e suspensa.
A comparação é feita sobre o texto sem acentos e sem espaços, o que tolera o OCR que cola palavras.
Triagem: cada evento guarda o trecho; a decisão só vale depois de lida.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def compact(text: str) -> tuple[str, list[int]]:
    """Texto minúsculo, sem acentos e sem espaços, e a posição de cada caractere no texto original."""

    out, positions = [], []
    for index, char in enumerate(text):
        if char.isspace():
            continue
        for piece in unicodedata.normalize("NFKD", char):
            if not unicodedata.combining(piece):
                out.append(piece.lower())
                positions.append(index)
    return "".join(out), positions


DECISION_START = re.compile(r"delibera(?:coes|cao)(?:\w{0,3})?:|colocad[ao]s?em(?:discussaoe)?votacao|deliberaram|"
                            r"(?:foram|foi)tomadasasseguintesdeliberacoes")
NOT_INSTALLED = re.compile(r"nao(?:houve|foiverificad[ao]|atingiu|seatingiu|foiatingido)[^.]{0,60}quorum(?:minimo)?(?:de|para)instalacao|"
                           r"nao(?:foi)?instalada|termodenaoinstalacao|deixoudeserinstalada|naoinstalacao")
SUSPENDED = re.compile(r"suspens(?:ao|os?|as?)(?:dos|da)?(?:trabalhos|votacao)|suspendera?(?:m)?(?:os|a)?(?:trabalhos|votacao)|"
                       r"foisuspensa|ficasuspensa|reaberturadostrabalhos|reaberturamarcada|seraretomada|"
                       r"suspensaodapresente(?:assembleia|deliberacao|da)|novasuspensao|deveraserreaberta|serareaberta|"
                       r"(?:pela|por)suspen(?:sao|der)|suspenderaapreciacao|suspendendoapresenteassembleia")
EDITAL = re.compile(r"editalde(?:primeira|segunda|1a|2a)?convocacao|ficamconvocad|convoca(?:m)?ossenhores|pelopresenteedital")
ATA_TITLE = re.compile(r"atad[ae]s?(?:\w{0,30})?assembleia|termodenaoinstalacao")
# sem espaços não há fronteira de palavra: formas da mais longa para a mais curta; "aprovar" e "aprovação" ficam de fora
# (ecoam a ordem do dia), salvo em "deliberaram ... aprovar"
DELIBERATED_FOR = r"(?:deliberaram|deliberou|decidiram|decidiu|resolveram|resolveu)[^.:;]{0,250}?(?:pel[ao]s?|por)(?!unanimidade|maioria|cento)"
APPROVED = re.compile(r"(?:foi|foram|restou|restaram)aprovad|aprovaram|aprovadas|aprovados|aprovada|aprovado|aprovam|aprovou|"
                      r"autorizaram|autorizou|ratificaram|ratificou|"
                      r"aprova(?![rc])|(?<=[:;)])aprovar|(?:deliberaram|decidiram|resolveram)[^.]{0,60}?aprovar|" + DELIBERATED_FOR)
STRONG_APPROVAL = re.compile(r"(?:foi|foram|restou|restaram)aprovad|aprovaram|aprovam|aprovar|aprovou|autorizaram|autorizou|ratificaram|"
                             r"ratificou|(?:deliberaram|decidiram|resolveram)[^.]*aprovar|" + DELIBERATED_FOR)
# todos os titulares presentes se abstiveram: a matéria não é votada (nas DFs sem ressalva, contam como aprovadas pela norma)
ABSTAINED = re.compile(r"manifest\w{0,6}(?:pela)?abstencao|seabster(?:em)?(?:de|do)?(?:direitode)?votar|abstiveram-?se(?:de|do)?(?:direitode)?vot|"
                       r"abstencaoaodireitodevoto|abstencaodevotosobreatotalidade")
CLOSING = re.compile(r"\d{0,2}\.?disposicoesfinais|\d{0,2}\.?encerramento:|nadamaishavendoatratar")
# aprovação em bloco: o assunto vem da ordem do dia
ALL_ITEMS = re.compile(r"todasasmaterias|ositens\(?[ivx]+\)?a\(?[ivx]+\)?daordemdodia|asmateriasconstantes(?:da|na)ordemdodia|"
                       r"integralidadedaordemdodia|integralidadedasmaterias|todosositens|aordemdodia(?:integralmente|naintegra)|"
                       r"aprovacaointegral|integraldositens|naintegradositens|itensdescritosnaordemdodia")
NO_QUORUM = re.compile(r"aus[e]nciadequorum(?:minimo)?(?:para|de)(?:a)?deliberacao|ausenciadoquorum(?:minimo)?(?:para|de)(?:a)?deliberacao|"
                       r"naohouvequorum(?:minimo)?(?:para|de)(?:a)?deliberacao|naofoiatingidooquorum(?:minimo)?(?:para|de)(?:a)?deliberacao|"
                       r"quoruminsuficienteparadeliberacao")
CONDITIONAL = re.compile(r"(?:caso|se|umavez|desdeque|hipotesede|emcasode|sejam?|seja)$")
TALLY = re.compile(r"nenhum")  # "nenhum dos Titulares ... rejeitaram" é placar, não rejeição
TALLY_TAIL = re.compile(r"^,?(?:nenhum\w*?(?:seabstiveram|rejeitaram|votaramcontra|seabsteve|rejeitou)e?){1,3}")
INSTALL_CONDITIONAL = re.compile(r"(?:caso|hipotese|emcaso|se)\w{0,12}$")
INSTALL_HISTORY = re.compile(r"^\w{0,6}(?:em)?(?:1a|1ª|primeira)convocacao")
NEGATED = re.compile(r"(?:nao|reprova|rejeit)\w{0,12}$")
REJECTED = re.compile(r"naoaprova|naoforamaprovad|naofoiaprovad|reprova(?:m|ram|da|do|das|dos)|rejeita(?:m|ram|da|do|das|dos)|"
                      r"naohouvequorum(?:de|para)(?:aprovacao|deliberacao)|naoatingi\w{0,8}quorum(?:de|para)(?:aprovacao|deliberacao)")

VA_NEGATIVE = re.compile(r"nao(?:a)?(?:declaracao|decretacao|declarar|decretar)(?:d[eo]s?)?(?:efeitos)?(?:d[eo]s?)?(?:evento(?:s)?de)?"
                         r"vencimentoantecipado")
VA_POSITIVE = re.compile(r"(?:declaracao|decretacao|declarar|decretar)(?:d[eo]s?)?(?:efeitos)?(?:d[eo]s?)?(?:evento(?:s)?de)?vencimentoantecipado")
TOPICS = {
    "waiver": re.compile(r"waiver|anuenciapravia|anuenciaprevia|perdaotemporario|renunciaadireitos|renunciadedireitos"),
    # "prorrogação da vigência" de contrato de prestador não é repactuação da dívida
    "prorrogacao_repactuacao": re.compile(r"prorroga(?:cao|r)(?!d[ao]vigencia|d[ao]prazodevigencia|d[ao]contrato)|repactua|novocronograma|"
                                          r"alteracaodo(?:s)?cronograma|carencia|posterga[cd]|alteracaod[ao]s?(?:datas?de)?vencimento"),
    "liquidacao_patrimonio": re.compile(r"liquidacaodopatrimonioseparado"),
    "troca_prestador": re.compile(r"(?:substituicao|destituicao)d[oa](?:agentefiduciario|securitizadora|emissora|custodiante|servicer)"),
    "resgate_amortizacao": re.compile(r"resgateantecipado|amortizacaoextraordinaria|ofertaderesgate"),
    "dacao_em_pagamento": re.compile(r"dacaoempagamento"),
    "garantias": re.compile(r"(?:substituicao|reforco|liberacao|complementacao)d[ae]s?garantia"),
    "dfs": re.compile(r"demonstracoesfinanceiras|demonstracoescontabeis"),
    "aporte_titulares": re.compile(r"aportederecursos|aporte(?:,)?pelostitulares|aportedostitulares|aportepelosinvestidores|"
                                   r"aportedosinvestidores|realizacaodeaporte|aportedevalores"),
    "assessor_legal": re.compile(r"contratacaod[eoa]s?(?:\w{0,12})?(?:assessor|assessoria|escritorio|advogad)|assessorlegal|"
                                 r"assessoriajuridica|honorariosadvocaticios"),
    "recuperacao_judicial": re.compile(r"recuperacaojudicial|recuperacaoextrajudicial|planoderecuperacao|habilitacaod[eo]s?credito|"
                                       r"individualizacaod[eo]s?(?:seu)?(?:direito|credito)|pedidodefalencia|falenciad"),
    "uso_fundo_reserva": re.compile(r"(?:utiliza\w{0,4}|uso|recomposicao|liberacao)(?:d[eoa]s?)?(?:recursosd[oa])?(?:fundo(?:s)?dereserva|fundodedespesas)"),
}
WINDOW = 260
# "atos necessários para a implementação das matérias constantes da ordem do dia" é autorização padrão, não aprovação em bloco
BOILERPLATE_ALL = re.compile(r"(?:implementacao|efetivacao|execucao|formalizacao|cumprimento)(?:e\w{0,14})?d[ao]?s?$")


@dataclass(frozen=True)
class Decision:
    event: str      # ex.: "waiver_aprovado", "vencimento_antecipado_declarado"
    excerpt: str


@dataclass(frozen=True)
class Outcome:
    kind: str       # "ata" | "edital_ou_outro"
    status: str     # "nao_instalada" | "suspensa" | "abstencao" | "aprovada" | "rejeitada" | "mista" | "sem_decisao_identificada"
    decisions: tuple[Decision, ...]


def _decision_part(text: str) -> int | None:
    """Onde começa a parte da decisão (depois da ordem do dia); None quando não há (edital)."""

    agenda = re.search(r"ordemdodia:", text) or re.search(r"ordemdodia", text)
    start = agenda.end() if agenda else int(len(text) * 0.2)
    found = DECISION_START.search(text, start)
    return found.start() if found else None


def _event(topic: str, approved: bool) -> str:
    return f"{topic}_{'aprovado' if approved else 'rejeitado'}"


def _not_installed(flat: str) -> re.Match | None:
    """Marca de assembleia não instalada, fora de texto condicional ("em caso de não instalação") e de histórico
    ("não foi instalada em 1ª convocação")."""

    for found in NOT_INSTALLED.finditer(flat):
        if found.group(0).startswith("termode"):
            return found
        if INSTALL_CONDITIONAL.search(flat[max(0, found.start() - 25):found.start()]):
            continue
        if INSTALL_HISTORY.search(flat[found.end():found.end() + 30]):
            continue
        return found
    return None


def _negated(part: str, start: int) -> bool:
    return "nao" in part[max(0, start - 25):start]


def _topics(text: str, approved: bool, head: int | None = None) -> list[str]:
    """Eventos de um trecho: vencimento antecipado (declarado ou não) no trecho todo e os demais assuntos nos primeiros
    ``head`` caracteres, sem os negados."""

    events = []
    negative, positive = VA_NEGATIVE.search(text), VA_POSITIVE.search(text)
    if negative and (not positive or negative.start() <= positive.start()):
        events.append("vencimento_antecipado_nao_declarado" if approved else "nao_declaracao_do_vencimento_antecipado_rejeitada")
    elif positive and not _negated(text, positive.start()):
        events.append("vencimento_antecipado_declarado" if approved else "vencimento_antecipado_nao_declarado")
    start = text[:head] if head else text
    for topic, pattern in TOPICS.items():
        found = pattern.search(start)
        if found and not _negated(start, found.start()):
            events.append(_event(topic, approved))
    return events


def decide(text: str) -> Outcome:
    flat, positions = compact(text)

    def excerpt(start: int, end: int) -> str:
        a, b = positions[max(0, start)], positions[min(len(positions) - 1, end)]
        return " ".join(text[a:b + 1].split())

    not_installed = _not_installed(flat)
    head = flat[:1500]
    if EDITAL.search(head) and not ATA_TITLE.search(head[:700]):
        return Outcome("edital_ou_outro", "sem_decisao_identificada", ())
    begin = _decision_part(flat)
    if begin is None:
        if not_installed:
            return Outcome("ata", "nao_instalada", (Decision("nao_instalada", excerpt(not_installed.start() - 120, not_installed.end() + 80)),))
        return Outcome("edital_ou_outro", "sem_decisao_identificada", ())
    # as disposições finais e o encerramento são texto padrão ("matéria aqui aprovada"): ficam fora
    closing = CLOSING.search(flat, begin + 40)
    part = flat[begin:closing.start() if closing else len(flat)]
    agenda_match = re.search(r"ordemdodia:", flat) or re.search(r"ordemdodia", flat)
    agenda = flat[agenda_match.end():begin] if agenda_match and agenda_match.end() < begin else ""
    decisions: list[Decision] = []
    verdicts: set[bool] = set()
    seen: set[str] = set()
    generic_approval: int | None = None
    # placar ("nenhum dos Titulares ... rejeitaram") não é decisão nem fronteira: o objeto vem logo depois dele
    verbs = [v for v in re.finditer(REJECTED.pattern + "|" + APPROVED.pattern, part)
             if not (REJECTED.fullmatch(v.group(0)) and TALLY.search(part[max(0, v.start() - 90):v.start()]))]
    for index, verb in enumerate(verbs):
        before = part[max(0, verb.start() - 90):verb.start()]
        rejected = bool(REJECTED.fullmatch(verb.group(0))) or bool(NEGATED.search(before[-14:]))
        if rejected and TALLY.search(before):
            continue
        if rejected and "%" in before[-70:]:
            # placar de minoria ("... aprovaram ..., 0,57% rejeitaram"): a frase já tem a aprovação da maioria
            sentence = part[max(0, verb.start() - 600):verb.start()]
            if APPROVED.search(sentence[sentence.rfind(".") + 1:]):
                continue
        if not rejected and CONDITIONAL.search(before[-12:]):
            continue
        approved = not rejected
        # cada verbo é dono do texto até o próximo verbo de decisão (no máximo WINDOW caracteres)
        following = next((v.start() for v in verbs[index + 1:] if v.start() >= verb.end() + 20), len(part))
        window = part[verb.end(): min(verb.end() + WINDOW, following)]
        tally = TALLY_TAIL.search(window)
        if tally:
            window = window[tally.end():] + part[verb.end() + len(window): min(verb.end() + len(window) + tally.end(), following)]
        if SUSPENDED.search(window[:80]):
            continue  # "aprovaram a suspensão da assembleia" é suspensão, tratada abaixo
        block = ALL_ITEMS.search(window[:250])
        if block and BOILERPLATE_ALL.search(window[max(0, block.start() - 30):block.start()]):
            block = None
        if approved and block and agenda:
            own = _topics(window[:block.start()], True)
            events = own + [e + "_em_bloco" for e in _topics(agenda, True) if e not in own] or ["ordem_do_dia_aprovada_em_bloco"]
        else:
            events = _topics(window, approved, head=WINDOW // 2 + 60)
        if not events:
            if approved and generic_approval is None and STRONG_APPROVAL.fullmatch(verb.group(0)):
                generic_approval = begin + verb.start()
            continue
        verdicts.add(approved)
        absolute = begin + verb.start()
        for event in events:
            if event in seen:
                continue
            seen.add(event)
            reach = 380 if tally else 220  # no placar, o objeto da decisão vem depois de "nenhum ... rejeitaram"
            decisions.append(Decision(event, excerpt(absolute - 60, absolute + len(verb.group(0)) + reach)))
    if not_installed and not decisions:
        return Outcome("ata", "nao_instalada", (Decision("nao_instalada", excerpt(not_installed.start() - 120, not_installed.end() + 80)),))
    no_quorum = NO_QUORUM.search(part)
    if no_quorum and not decisions:
        return Outcome("ata", "sem_quorum_para_deliberar",
                       (Decision("sem_quorum_para_deliberar", excerpt(begin + no_quorum.start() - 80, begin + no_quorum.end() + 120)),))
    suspended = SUSPENDED.search(part)
    abstained = ABSTAINED.search(part)
    if abstained and not decisions and not suspended:
        return Outcome("ata", "abstencao", (Decision("titulares_se_abstiveram", excerpt(begin + abstained.start() - 120, begin + abstained.end() + 200)),))
    if suspended:
        decisions.append(Decision("assembleia_suspensa", excerpt(begin + suspended.start() - 100, begin + suspended.end() + 120)))
    elif generic_approval is not None and not decisions:
        verdicts.add(True)
        decisions.append(Decision("outras_materias_aprovadas", excerpt(generic_approval - 60, generic_approval + 260)))
    if not decisions:
        return Outcome("ata", "sem_decisao_identificada", ())
    if suspended and not verdicts:
        status = "suspensa"
    elif verdicts == {True}:
        status = "aprovada"
    elif verdicts == {False}:
        status = "rejeitada"
    else:
        status = "mista"
    return Outcome("ata", status, tuple(decisions))
