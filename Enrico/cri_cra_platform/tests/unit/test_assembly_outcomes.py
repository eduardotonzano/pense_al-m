from __future__ import annotations

from credit_assets.assembly_outcomes import compact, decide

HEADER = "ATA DA ASSEMBLEIA ESPECIAL DE TITULARES DOS CRA DA 190ª EMISSÃO\n4. PRESENÇA: Titulares dos CRA representando 73%.\n"
AGENDA = ("5. ORDEM DO DIA: Deliberar sobre: (i) Aprovar a concessão de waiver prévio para o eventual descumprimento dos "
          "índices financeiros; (ii) Aprovar a não declaração do vencimento antecipado do CDCA.\n")
CLOSING = ("7. DISPOSIÇÕES FINAIS: autorização para que sejam celebrados quaisquer instrumentos relacionados à matéria aqui "
           "aprovada. 8. ENCERRAMENTO: nada mais havendo a tratar.")


def ata(decisions: str) -> str:
    return HEADER + AGENDA + "6. DELIBERAÇÕES: " + decisions + "\n" + CLOSING


def events(text: str) -> list[str]:
    return [d.event for d in decide(text).decisions]


def test_compact_keeps_positions_for_excerpts():
    flat, positions = compact("Não  Aprovada")
    assert flat == "naoaprovada" and positions[3] == 5


def test_approved_waiver_and_va_not_declared_ignoring_the_agenda_echo():
    text = ata("Os Titulares dos CRA presentes, representativos de 73,87% dos CRA em Circulação aprovam a concessão do Waiver, "
               "nenhum dos Titulares se abstiveram e nenhum dos Titulares dos CRA presentes rejeitaram. Os Titulares aprovaram a "
               "não declaração do vencimento antecipado do CDCA e, consequentemente, a não realização do resgate antecipado dos CRA.")
    outcome = decide(text)
    assert outcome.kind == "ata" and outcome.status == "aprovada"
    assert events(text) == ["waiver_aprovado", "vencimento_antecipado_nao_declarado"]  # o resgate negado não entra
    assert "aprovam a concessão do Waiver" in outcome.decisions[0].excerpt


def test_rejected_declaration_conditional_and_tally():
    text = ata("Caso aprovado o item (i), a Securitizadora fica autorizada a realizar o resgate antecipado. "
               "Os Titulares não aprovaram a declaração do vencimento antecipado das CPR-F.")
    assert events(text) == ["vencimento_antecipado_nao_declarado"]
    assert decide(text).status == "rejeitada"


def test_declared_acceleration_from_ocr_squashed_text():
    text = ata("OsTitularesdosCRArepresentando80%dosCRAemCirculacaoaprovaramadecretacaodoVencimentoAntecipadodasCPR-F.")
    assert events(text) == ["vencimento_antecipado_declarado"]


def test_not_installed_suspended_no_quorum_and_edital():
    assert decide(HEADER + "TERMO DE NÃO INSTALAÇÃO: considerando que compareceram titulares abaixo do quórum").status == "nao_instalada"
    conditional = ata("Em caso de não instalação da assembleia de reabertura, o termo de adesão será considerado. "
                      "Os Titulares aprovaram a prorrogação da data de vencimento.")
    assert decide(conditional).status == "aprovada" and events(conditional) == ["prorrogacao_repactuacao_aprovado"]
    history = ata("A Assembleia não foi instalada em 1ª convocação. Os Titulares aprovaram a substituição do agente fiduciário.")
    assert events(history) == ["troca_prestador_aprovado"]
    suspended = ata("Os Titulares deliberaram por suspender a votação dos itens da ordem do dia com reabertura marcada para 24/03.")
    assert decide(suspended).status == "suspensa"
    no_quorum = ata("Em vista da ausência do quórum mínimo para deliberação das matérias, a Securitizadora observará os trâmites.")
    assert decide(no_quorum).status == "sem_quorum_para_deliberar"
    edital = "EDITAL DE CONVOCAÇÃO DA ASSEMBLEIA ESPECIAL\n" + AGENDA + "Em caso de não aprovação, ficam os titulares convocados."
    assert decide(edital).kind == "edital_ou_outro"


def test_block_approval_takes_topics_from_the_agenda_and_closing_boilerplate_is_ignored():
    block = ata("Os Titulares, por unanimidade, decidiram por aprovar todas as matérias constantes na Ordem do Dia.")
    assert events(block) == ["vencimento_antecipado_nao_declarado_em_bloco", "waiver_aprovado_em_bloco"]
    nothing = ata("Os Titulares discutiram as matérias e pediram novas informações à Devedora.")
    assert decide(nothing).status == "sem_decisao_identificada"  # "matéria aqui aprovada" das disposições finais não conta


def test_deliberated_for_forms_block_wording_and_boilerplate_authorization():
    integral = ata("Os Titulares de CRA, representando 100% (cem por cento) dos CRA em Circulação, sem voto em contrário ou "
                   "abstenção, deliberaram pela aprovação integral dos itens descritos na Ordem do Dia.")
    assert decide(integral).status == "aprovada"
    assert events(integral) == ["vencimento_antecipado_nao_declarado_em_bloco", "waiver_aprovado_em_bloco"]
    authorization = ata("Os Titulares aprovaram a substituição do agente fiduciário e aprovar a autorização para que a "
                        "Securitizadora pratique todo e qualquer ato necessário para a implementação das matérias constantes da "
                        "Ordem do Dia.")
    assert events(authorization) == ["troca_prestador_aprovado"]  # autorização padrão não é aprovação em bloco
    suspended = ata("Os Titulares dos CRA, representando 30,30% dos CRA em Circulação, deliberaram pela suspensão dos respectivos "
                    "itens, com reabertura programada para 30 de setembro.")
    assert decide(suspended).status == "suspensa"


def test_contribution_legal_advisor_and_judicial_recovery_topics():
    text = ata("Com relação ao item (i), os Titulares aprovaram a realização de aporte de recursos pelos Titulares dos CRA, no "
               "montante de R$ 821.312,81. Com relação ao item (ii), os Titulares aprovaram que os titulares pleiteiem, perante o "
               "juízo da Recuperação Judicial da Devedora, a individualização de seu crédito.")
    assert events(text) == ["aporte_titulares_aprovado", "recuperacao_judicial_aprovado"]


def test_abstention_and_minority_rejection_tally():
    abstention = ata("O Titular dos CRA detentor de 100% dos CRA em Circulação manifestou a abstenção ao direito de voto sobre a "
                     "totalidade das matérias da Ordem do Dia.")
    assert decide(abstention).status == "abstencao"
    minority = ata("Os Titulares representando 60% dos CRA em Circulação aprovaram a ratificação da contratação do escritório X "
                   "Advogados, 3% se abstiveram e 0,57% dos Titulares dos CRA em Circulação presentes rejeitaram a ratificação "
                   "da contratação do escritório X Advogados.")
    assert decide(minority).status == "aprovada" and events(minority) == ["assessor_legal_aprovado"]
