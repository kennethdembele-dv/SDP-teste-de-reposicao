"""Funcoes de formatacao do relatorio em Word (python-docx)."""
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

AZUL = RGBColor(0x17, 0x3B, 0x6C)
FONTE = "Calibri"


def configurar_estilos(doc):
    normal = doc.styles["Normal"]
    normal.font.name = FONTE
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONTE)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.1
    for nome, tamanho, antes in (("Heading 1", 14, 12), ("Heading 2", 11.5, 8)):
        e = doc.styles[nome]
        e.font.name = FONTE
        e.font.size = Pt(tamanho)
        e.font.bold = True
        e.font.color.rgb = AZUL
        rfonts = e.element.rPr.rFonts
        for atributo in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rfonts.set(qn(atributo), FONTE)
        for atributo in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rfonts.get(qn(atributo)) is not None:
                del rfonts.attrib[qn(atributo)]
        e.paragraph_format.space_before = Pt(antes)
        e.paragraph_format.space_after = Pt(4)
        e.paragraph_format.keep_with_next = True
    for nome in ("TOC 1", "TOC 2"):
        e = doc.styles.add_style(nome, 1) if nome not in [x.name for x in doc.styles] else doc.styles[nome]
        e.font.name = FONTE
        e.font.size = Pt(10)
        e.paragraph_format.space_after = Pt(1)
        e.paragraph_format.space_before = Pt(0)
        if nome == "TOC 2":
            e.paragraph_format.left_indent = Cm(0.5)
    for nome in ("List Bullet", "List Number"):
        doc.styles[nome].font.name = FONTE
        doc.styles[nome].font.size = Pt(10.5)
        doc.styles[nome].paragraph_format.space_after = Pt(2)


MARCAS = re.compile(r"(\*\*.+?\*\*|`.+?`)")


def escrever(paragrafo, texto, tamanho=None):
    """Texto com **negrito** e `codigo`."""
    for parte in MARCAS.split(texto):
        if not parte:
            continue
        if parte.startswith("**"):
            r = paragrafo.add_run(parte[2:-2])
            r.bold = True
        elif parte.startswith("`"):
            r = paragrafo.add_run(parte[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(9.2 if tamanho is None else tamanho - 0.8)
        else:
            r = paragrafo.add_run(parte)
        if tamanho and not parte.startswith("`"):
            r.font.size = Pt(tamanho)
    return paragrafo


def par(doc, texto, alinhar=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = escrever(doc.add_paragraph(), texto)
    p.alignment = alinhar
    return p


def topicos(doc, itens, numerados=False):
    for i in itens:
        p = escrever(doc.add_paragraph(style="List Number" if numerados else "List Bullet"), i)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def sombrear(celula, cor):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), cor)
    celula._tc.get_or_add_tcPr().append(shd)


def nao_partir_linha(linha):
    trpr = linha._tr.get_or_add_trPr()
    c = OxmlElement("w:cantSplit")
    trpr.append(c)


def tabela(doc, cabecalho, linhas, larguras):
    t = doc.add_table(rows=1, cols=len(cabecalho))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(cabecalho):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        sombrear(c, "173B6C")
    repetir = OxmlElement("w:tblHeader")
    t.rows[0]._tr.get_or_add_trPr().append(repetir)
    for linha in linhas:
        cells = t.add_row().cells
        for i, v in enumerate(linha):
            cells[i].text = ""
            p = escrever(cells[i].paragraphs[0], v, tamanho=9.5)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
    for linha in t.rows:
        nao_partir_linha(linha)
        for i, c in enumerate(linha.cells):
            c.width = Cm(larguras[i])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def codigo(doc, texto, tamanho=8.3):
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    c = t.rows[0].cells[0]
    sombrear(c, "F3F5F8")
    c.width = Cm(16.6)
    c.text = ""
    primeira = True
    for linha in texto.rstrip().split("\n"):
        p = c.paragraphs[0] if primeira else c.add_paragraph()
        primeira = False
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        r = p.add_run(linha if linha else " ")
        r.font.name = "Consolas"
        r.font.size = Pt(tamanho)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def figura(doc, png, legenda, largura=16.6):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(png, width=Cm(largura))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = c.add_run(legenda)
    r.italic = True
    r.font.size = Pt(9)


def campo(paragrafo, instrucao, texto=""):
    """Campo do Word (indice, numero de pagina). O Word calcula-o ao exportar."""
    for tipo, valor in (("begin", None), ("instr", instrucao), ("separate", None), ("texto", texto), ("end", None)):
        r = paragrafo.add_run()
        if tipo == "instr":
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = valor
            r._r.append(el)
        elif tipo == "texto":
            r.text = valor
        else:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tipo)
            r._r.append(el)


def contorno_primeira_pagina(seccao):
    borda = OxmlElement("w:pgBorders")
    borda.set(qn("w:display"), "firstPage")
    borda.set(qn("w:offsetFrom"), "page")
    for lado in ("top", "left", "bottom", "right"):
        el = OxmlElement("w:" + lado)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "6")
        el.set(qn("w:space"), "24")
        el.set(qn("w:color"), "404040")
        borda.append(el)
    seccao._sectPr.append(borda)


def caixa(paragrafo):
    ppr = paragrafo._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    for lado in ("top", "left", "bottom", "right"):
        el = OxmlElement("w:" + lado)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "8")
        el.set(qn("w:space"), "6")
        el.set(qn("w:color"), "404040")
        bdr.append(el)
    ppr.append(bdr)

# ---------------------------------------------------------------- capa


