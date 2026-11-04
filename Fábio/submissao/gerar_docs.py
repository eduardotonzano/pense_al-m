import sys
from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

AZUL = RGBColor(0x1F, 0x3A, 0x5F)
CINZA = RGBColor(0x55, 0x55, 0x55)
LARANJA = RGBColor(0xB3, 0x5C, 0x00)
VERDE = RGBColor(0x1E, 0x6B, 0x3A)


def novo_doc():
    d = Document()
    s = d.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.left_margin = s.right_margin = Cm(2.2)
    s.top_margin = s.bottom_margin = Cm(1.6)
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10)
    st.paragraph_format.space_after = Pt(3)
    for nome, tam in (("Heading 1", 14), ("Heading 2", 12)):
        h = d.styles[nome]
        h.font.name = "Calibri"
        h.font.size = Pt(tam)
        h.font.bold = True
        h.font.color.rgb = AZUL
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(4)
        h.paragraph_format.keep_with_next = True
    return d


def capa(d, titulo, sub):
    p = d.add_paragraph()
    r = p.add_run(titulo)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(20), AZUL
    p = d.add_paragraph()
    r = p.add_run(sub)
    r.font.size, r.font.color.rgb = Pt(11), CINZA
    borda_inferior(p)


def borda_inferior(p):
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "8"), ("w:space", "4"), ("w:color", "1F3A5F")):
        b.set(qn(k), v)
    bdr.append(b)
    pPr.append(bdr)


def sombrear(cell, cor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), cor)
    tcPr.append(shd)


def texto_rico(par, texto, tam=None):
    # marcações: [MEDIDO] em verde, [ESTIMATIVA] em laranja, **negrito**
    partes = []
    for token in ("[MEDIDO]", "[ESTIMATIVA]"):
        texto = texto.replace(token, f"\x00{token}\x00")
    for bloco in texto.split("\x00"):
        if bloco in ("[MEDIDO]", "[ESTIMATIVA]"):
            r = par.add_run(bloco)
            r.bold = True
            r.font.color.rgb = VERDE if bloco == "[MEDIDO]" else LARANJA
            if tam:
                r.font.size = tam
            continue
        for i, pedaco in enumerate(bloco.split("**")):
            if not pedaco:
                continue
            r = par.add_run(pedaco)
            r.bold = i % 2 == 1
            if tam:
                r.font.size = tam
    return par


def p(d, texto):
    return texto_rico(d.add_paragraph(), texto)


def bullets(d, itens, estilo="List Bullet"):
    for it in itens:
        texto_rico(d.add_paragraph(style=estilo), it)


def tabela(d, cab, linhas, larguras):
    t = d.add_table(rows=1, cols=len(cab))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, c in enumerate(cab):
        cell = t.rows[0].cells[i]
        cell.text = ""
        r = cell.paragraphs[0].add_run(c)
        r.bold, r.font.size, r.font.color.rgb = True, Pt(9.5), RGBColor(0xFF, 0xFF, 0xFF)
        sombrear(cell, "1F3A5F")
    for n, linha in enumerate(linhas):
        cells = t.add_row().cells
        for i, v in enumerate(linha):
            cells[i].text = ""
            texto_rico(cells[i].paragraphs[0], v, Pt(9.5))
            if n % 2 == 1:
                sombrear(cells[i], "EEF2F7")
    for row in t.rows:
        for i, w in enumerate(larguras):
            row.cells[i].width = Cm(w)
    espaco(d)
    return t


def espaco(d):
    e = d.add_paragraph()
    e.paragraph_format.space_after = Pt(0)
    e.paragraph_format.line_spacing = Pt(4)


def caixa(d, texto, cor="FFF4E5"):
    t = d.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    c = t.rows[0].cells[0]
    c.width = Cm(16.6)
    c.text = ""
    texto_rico(c.paragraphs[0], texto, Pt(9.5))
    sombrear(c, cor)
    espaco(d)


EQUIPE = [
    ["Eduardo de Almeida Guardia Tonzano", "Debêntures e bonds"],
    ["Enrico Suman Marques", "Securitizados (CRI/CRA)"],
    ["Gui", "Fundos (FIDC e FIAGRO)"],
    ["Fábio Junior", "Integração (camada compartilhada)"],
    ["Gustavo Vilela", "Padrinho do projeto"],
]

# ---------------------------------------------------------------- FICHA
d = novo_doc()
capa(d, "Ficha de Métricas",
     "Plataforma de Acompanhamento de Ativos  |  Pense Além 2026 — IA em Ação  |  Multiplica Capital  |  Novembro de 2026")

caixa(d, "**Legenda.** [MEDIDO] = número extraído do protótipo ou da documentação do repositório. "
         "[ESTIMATIVA] = hipótese da equipe, ainda não cronometrada — validar antes do envio. "
         "Trechos entre colchetes, como [preencher], precisam ser completados pela equipe.")

d.add_heading("1. Identificação", level=1)
tabela(d, ["Campo", "Resposta"], [
    ["Projeto", "Plataforma única de acompanhamento de ativos de crédito"],
    ["Área", "Research"],
    ["Padrinho", "Gustavo Vilela"],
    ["Equipe", "Eduardo Tonzano (debêntures e renda fixa), Enrico Suman Marques (CRI/CRA), Gui (fundos), Fábio Junior (T.I. e integração)"],
    ["Estágio", "Coleta funcionando por frente; integração em andamento; layout da interface em protótipo navegável"],
], [4, 12.6])

d.add_heading("2. A dor em números", level=1)
p(d, "O time não consegue acompanhar os ativos como gostaria porque a informação está espalhada em fontes "
     "oficiais diferentes e em planilhas, sem uma base consolidada nem histórico confiável.")
tabela(d, ["Indicador", "Situação atual", "Tipo"], [
    ["Fontes oficiais consultadas manualmente", "3 (SND, Fundos.NET e Dados Abertos da CVM)", "[MEDIDO]"],
    ["Tempo para montar a visão completa de um ativo", "30 a 60 min", "[ESTIMATIVA]"],
    ["Horas por semana do time em coleta e conferência manual", "10 a 15 h", "[ESTIMATIVA]"],
    ["Leitura inicial dos documentos de um CRI/CRA", "2 a 4 h por ativo", "[ESTIMATIVA]"],
    ["Registro de fonte, data e histórico de cada dado", "Inexistente", "Diagnóstico da equipe"],
], [7.4, 6.2, 3])

d.add_heading("3. Impacto esperado (antes × depois)", level=1)
tabela(d, ["Indicador", "Antes", "Com a plataforma", "Ganho", "Tipo"], [
    ["Tempo para montar a visão de um ativo", "30–60 min", "Menos de 5 min", "~90%", "[ESTIMATIVA]"],
    ["Horas por semana em coleta manual", "10–15 h", "2–3 h", "~80%", "[ESTIMATIVA]"],
    ["Leitura inicial de documentos de CRI/CRA", "2–4 h", "~30 min (resumo do agente + revisão humana)", "~80%", "[ESTIMATIVA]"],
    ["Detecção de evento relevante (preço, evento, novo documento)", "Quando alguém percebe", "Alerta automático no mesmo dia", "—", "[ESTIMATIVA]"],
    ["Dados com fonte e data registradas", "0%", "100%", "—", "Regra do protótipo"],
], [5.2, 2.6, 4.2, 1.6, 3])

d.add_heading("4. Resultados medidos no protótipo", level=1)
tabela(d, ["Frente", "Indicador", "Valor", "Tipo"], [
    ["Debêntures", "Dados reais no banco", "3 emissores (Petrobras, Sabesp, Celpe), 3 debêntures, 38 observações", "[MEDIDO]"],
    ["Debêntures", "Etapas de automação concluídas", "8 de 9 (falta a interface)", "[MEDIDO]"],
    ["CRI/CRA", "Documentos catalogados do Fundos.NET", "168 (126 do Café Brasil + 42 da Almeida Junior)", "[MEDIDO]"],
    ["CRI/CRA", "Integridade do download", "Hash SHA-256 e versão por arquivo", "[MEDIDO]"],
    ["Fundos", "Informe de FIAGRO 09/2026 carregado", "308 classes, 688 séries, 39.316 observações, 0 conflitos", "[MEDIDO]"],
    ["Fundos", "Cedentes do informe de FIDC 09/2026", "3.605 cedentes com CNPJ válido (de 7.452 células)", "[MEDIDO]"],
    ["Fundos", "Teste de volume", "1,57 milhão de observações por mês; carga completa em 7,3 min; simulação em 15 s", "[MEDIDO]"],
    ["Integração", "Testes automatizados da camada compartilhada", "285", "[MEDIDO]"],
    ["Debêntures", "Testes automatizados (linha de base)", "417", "[MEDIDO]"],
], [2.6, 4.6, 6.8, 2.6])

d.add_heading("5. Qualidade e confiabilidade", level=1)
bullets(d, [
    "**Nenhum dado inventado:** valor ausente fica ausente.",
    "**Rastreabilidade:** todo valor guarda fonte e data de coleta; o histórico é preservado e nada é sobrescrito sem registro.",
    "**Conflitos visíveis:** divergências entre fontes são registradas (0 conflitos na carga de FIAGRO 09/2026). [MEDIDO]",
    "**Dados pessoais protegidos:** CPF nunca é gravado; uma verificação automática bloqueia a gravação se aparecer. [MEDIDO]",
    "**Operação segura:** backup e checagem de integridade antes de cada mudança no banco, repetição automática em falhas e monitoramento de saúde (saudável, alerta, crítico).",
    "**A plataforma já encontra problemas na fonte:** 385 percentuais de cedentes acima de 100% no informe oficial de FIDC de 09/2026. [MEDIDO]",
])

d.add_heading("6. Como vamos medir depois da implantação", level=1)
tabela(d, ["KPI", "Como medir", "Meta em 3 meses"], [
    ["Tempo médio para montar a visão de um ativo", "Cronometrar 10 consultas antes e depois", "Redução de 80% [ESTIMATIVA]"],
    ["Uso semanal", "Registro de acesso por usuário", "Todo o time de Research usando toda semana [ESTIMATIVA]"],
    ["Cobertura da carteira", "Ativos da casa cadastrados na base", "100% da carteira [ESTIMATIVA]"],
    ["Qualidade dos alertas", "Alertas marcados como relevantes ÷ total", "70% ou mais [ESTIMATIVA]"],
    ["Qualidade do agente de IA", "Resumos aprovados sem correção ÷ total revisado", "80% ou mais [ESTIMATIVA]"],
], [5.4, 5.8, 5.4])

d.add_heading("7. Premissas das estimativas", level=1)
bullets(d, [
    "As estimativas partem da rotina descrita pela equipe no escopo do projeto; nenhuma foi cronometrada.",
    "Tamanho do time de Research que acompanha os ativos: [preencher] pessoas.",
    "Recomendação: cronometrar 3 consultas reais antes do envio e trocar as estimativas da seção 3 por medições.",
])

d.save(OUT / "Ficha_de_Metricas_Pense_Alem_2026.docx")

# ---------------------------------------------------------------- DESCRITIVO
d = novo_doc()
capa(d, "Descritivo do Protótipo",
     "Plataforma de Acompanhamento de Ativos  |  Pense Além 2026 — IA em Ação  |  Multiplica Capital  |  Novembro de 2026")

d.add_heading("1. Resumo", level=1)
p(d, "Protótipo de uma plataforma que reúne em uma única base os dados oficiais dos ativos de crédito que a "
     "equipe de Research da Multiplica acompanha: debêntures, CRI/CRA e fundos (FIDC e FIAGRO), com renda fixa na "
     "sequência. Robôs de coleta buscam os dados nas fontes oficiais — SND, Fundos.NET e CVM —, guardam cada valor "
     "com fonte, data e histórico e alimentam uma plataforma de consulta, cujo layout já existe em protótipo "
     "navegável. A mesma base prepara os alertas automáticos e um agente de IA que lê os documentos dos ativos.")

d.add_heading("2. O problema", level=1)
p(d, "Dor validada com o padrinho do projeto, Gustavo Vilela: o time não consegue acompanhar os ativos como "
     "gostaria por falta de uma base de dados sólida e consolidada.")
bullets(d, [
    "**Dados espalhados:** cada classe de ativo vive em uma fonte oficial diferente, com formatos diferentes.",
    "**Trabalho manual e repetitivo:** a coleta e a conferência tomam horas do time toda semana.",
    "**Sem histórico nem rastreabilidade:** não se sabe de onde veio cada número nem quando mudou.",
    "**Documentos longos:** termos de securitização, relatórios e atas de CRI/CRA levam horas para ser lidos.",
])

d.add_heading("3. A solução", level=1)
p(d, "O projeto foi dividido em frentes por classe de ativo, cada uma com um dono, e uma camada compartilhada que "
     "reconhece a mesma empresa (pelo CNPJ) em todas as frentes e une as informações.")
tabela(d, ["Frente", "Dono", "O que faz", "Fonte", "Status"], [
    ["Debêntures", "Eduardo", "Emissor, vencimento, indexador, taxa, valor do título, histórico e eventos", "SND", "Em operação (8 de 9 etapas); falta ligar à interface"],
    ["CRI/CRA", "Enrico", "Termo, informes mensais, fatos relevantes e rating, classificados por categoria", "Fundos.NET", "Em andamento: 2 ativos piloto, 168 documentos"],
    ["Fundos", "Gui", "Gestora, administradora, custodiante, situação, informes de FIDC e FIAGRO, cedentes", "CVM", "Em construção: carga real em banco de teste"],
    ["Integração (galpão)", "Fábio", "Cadastro único por CNPJ: uma empresa, um cadastro", "Frentes acima", "Iniciado: emissores de debêntures"],
    ["Renda fixa", "Eduardo", "Taxas, marcação a mercado e indicadores dos bancos", "A definir", "Não iniciado"],
], [2.6, 1.8, 5, 2.6, 4.6])

d.add_heading("4. Onde está a IA", level=1)
d.add_heading("4.1 IA no desenvolvimento — em uso", level=2)
p(d, "A equipe usa o Claude Code como copiloto de engenharia: ele lê o repositório, propõe um plano antes de "
     "alterar código, escreve testes e mantém a documentação. As regras do projeto (nunca inventar dado, sempre "
     "registrar fonte e data, nunca gravar CPF) ficam em um arquivo lido no início de cada sessão. Assim, um time "
     "pequeno construiu entre setembro e novembro de 2026 quatro módulos com mais de 700 testes automatizados. "
     "O layout navegável da plataforma também foi gerado com o Claude.")
d.add_heading("4.2 Agente de leitura de documentos — próxima fase", level=2)
p(d, "Um agente de IA lê os documentos de CRI/CRA já catalogados e extrai garantias e covenants, sempre citando "
     "a página de origem. Nada entra na ficha do ativo sem revisão humana: cada extração nasce como pendente e só "
     "vira verificada depois que um analista aprova. A base para isso — documentos baixados, versionados e "
     "classificados — já existe.")
d.add_heading("4.3 Alertas automáticos — próxima fase", level=2)
p(d, "Sobre a base consolidada, a plataforma avisa o time sobre variações anormais de preço, novos documentos "
     "publicados e eventos relevantes dos ativos.")

d.add_heading("5. Como funciona", level=1)
bullets(d, [
    "**Coleta:** coletores agendados acessam as fontes oficiais — SND, Fundos.NET (por navegador automatizado) e arquivos da CVM.",
    "**Gravação com proveniência:** cada valor vira uma observação com fonte, data e versão; divergências entre fontes são registradas, nunca sobrescritas.",
    "**Qualidade e monitoramento:** checagem de integridade, repetição automática em falhas, trava contra execução dupla, logs e painel de saúde.",
    "**Integração:** a camada compartilhada liga a mesma empresa entre debêntures, CRI/CRA e fundos.",
    "**Consumo:** hoje, consultas e exportações em CSV e JSON; na próxima fase, interface, alertas e agente de IA.",
], estilo="List Number")
p(d, "**Protótipo da interface:** layout navegável em HTML, com busca de ativos, menu por classe (Renda Fixa, "
     "Debêntures, Securitizados, Fundos, Emissores), ativos em carteira com maiores altas e quedas, e a situação de "
     "cada fonte (SND e Fundos.NET ativas; CVM e ANBIMA planejadas). Usa dados ilustrativos e ainda não está ligado "
     "aos bancos.")
p(d, "**Tecnologia:** Python, SQLite (migração para PostgreSQL prevista), Playwright, pytest, Git e GitHub com revisão por pull request.")

d.add_heading("6. O que já dá para demonstrar", level=1)
bullets(d, [
    "Consulta de uma debênture real (por exemplo, PETR27) com histórico e fonte de cada dado.",
    "Catálogo de 168 documentos de CRI/CRA do Fundos.NET, com download verificado por hash.",
    "Carga do informe de FIAGRO de 09/2026: 308 classes e 39.316 observações, sem conflitos.",
    "Leitura de 3.605 cedentes do informe de FIDC — e detecção de 385 percentuais inconsistentes na fonte oficial.",
    "Suítes de testes automatizados rodando em cada frente.",
])

d.add_heading("7. Limitações atuais", level=1)
bullets(d, [
    "A interface existe só como layout com dados ilustrativos; a consulta real ainda é feita por scripts e exportações.",
    "O agente de leitura de documentos e os alertas estão em planejamento.",
    "A integração cobre só debêntures; CRI/CRA e fundos ainda não chegam ao galpão.",
    "A frente de renda fixa ainda não tem fonte definida nem código.",
    "Os bancos rodam em SQLite local; o PostgreSQL depende de liberação da TI.",
])

d.add_heading("8. Próximos passos", level=1)
bullets(d, [
    "Ligar debêntures, CRI/CRA e fundos ao galpão.",
    "Conectar CVM e ANBIMA às debêntures.",
    "Definir a interface com a equipe de Research e ligá-la aos bancos.",
    "Agente de leitura de documentos de CRI/CRA, com revisão humana.",
    "Alertas automáticos de preço e notícias.",
    "Frente de renda fixa.",
])

d.add_heading("9. Equipe", level=1)
p(d, "**Eduardo de Almeida Guardia Tonzano** — debêntures e renda fixa; **Enrico Suman Marques** — CRI/CRA; "
     "**Gui** — fundos (FIDC e FIAGRO); **Fábio Junior** — T.I. e integração (galpão); **Gustavo Vilela** — padrinho do projeto.")

d.save(OUT / "Descritivo_do_Prototipo_Pense_Alem_2026.docx")
print("ok")
