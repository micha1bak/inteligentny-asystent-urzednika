"""Eksport pisma (struktura z wzor/pismo.py) do DOCX i TXT – bez dodatkowych bibliotek.

Anonimizacja: fragmenty ukryte przez urzędnika są w pliku ZASTĘPOWANE znakami █ (a nie tylko zamalowywane),
więc ukrytych danych nie da się odzyskać z pliku (np. zdejmując czarne tło w Wordzie).

Układ DOCX odpowiada pismom BKS: nagłówek urzędu i stopka z adresem na każdej stronie, Times New Roman 12 pt,
treść wyjustowana, zakończenie i podpis od ok. 10 cm, adresat i „Ad n” pogrubione.
"""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

ZNAK = "█"
TWIP = 20  # 1 pt = 20 twipów

# marginesy jak w oryginalnych pismach (pt): treść od x = 71, do x = 540 (A4 = 595,3 × 841,9 pt)
LEWY, PRAWY, GORA, DOL = 71, 55, 98, 100
WCIECIE_PODPISU = 284


def anonimizuj(tekst: str, ukryte: list[str]) -> str:
    for fraza in sorted({f for f in ukryte if f.strip()}, key=len, reverse=True):
        tekst = tekst.replace(fraza, ZNAK * len(fraza))
    return tekst


def ukryte_frazy(pismo: dict) -> list[str]:
    return [u["tekst"] for u in pismo.get("ukrycia") or [] if u.get("stan") == "ukryte" and u.get("tekst")]


def pismo_do_tekstu(pismo: dict) -> str:
    linie = [*pismo.get("naglowek", []), pismo.get("data", ""), pismo.get("znak", ""), *pismo.get("adresat", []),
             *pismo.get("tytul", []), *(b.get("tekst", "") for b in pismo.get("tresc", [])),
             pismo.get("zakonczenie", ""), *pismo.get("podpis", [])]
    if pismo.get("stopka"):
        linie += ["", *pismo["stopka"]]
    return anonimizuj("\n".join(linie), ukryte_frazy(pismo)) + "\n"


# ---------------------------------------------------------------- DOCX (Office Open XML)
def _run(tekst: str, *, pogrubienie=False, rozmiar=12, czcionka="Times New Roman", kolor: str | None = None) -> str:
    wl = [f'<w:rFonts w:ascii="{czcionka}" w:hAnsi="{czcionka}" w:cs="{czcionka}"/>']
    if pogrubienie:
        wl.append("<w:b/>")
    if kolor:
        wl.append(f'<w:color w:val="{kolor}"/>')
    wl.append(f'<w:sz w:val="{rozmiar * 2}"/><w:szCs w:val="{rozmiar * 2}"/>')
    czesci = []
    for i, linia in enumerate(tekst.split("\n")):
        if i:
            czesci.append("<w:br/>")
        czesci.append(f'<w:t xml:space="preserve">{escape(linia)}</w:t>')
    return f"<w:r><w:rPr>{''.join(wl)}</w:rPr>{''.join(czesci)}</w:r>"


def _akapit(runy: str, *, wyrownanie="left", wciecie=0, odstep_przed=0, interlinia=None) -> str:
    wl = [f'<w:jc w:val="{wyrownanie}"/>']
    sp = f'<w:spacing w:before="{odstep_przed * TWIP}" w:after="0"'
    if interlinia:
        sp += f' w:line="{int(interlinia * TWIP)}" w:lineRule="exact"'
    wl.insert(0, sp + "/>")
    if wciecie:
        wl.append(f'<w:ind w:left="{wciecie * TWIP}"/>')
    return f"<w:p><w:pPr>{''.join(wl)}</w:pPr>{runy}</w:p>"


def _dokument(pismo: dict, ukryte: list[str]) -> str:
    a = lambda t: anonimizuj(t, ukryte)  # noqa: E731
    lin = 20.7  # interlinia treści jak w oryginałach
    p = [
        _akapit(_run(a(pismo.get("data", ""))), interlinia=lin),
        _akapit(_run(a(pismo.get("znak", "")), rozmiar=10)),
    ]
    adresat = pismo.get("adresat") or []
    p.append(_akapit(_run(a("\n".join(adresat)), pogrubienie=True), odstep_przed=40, interlinia=lin) if adresat
             else _akapit("", odstep_przed=40))
    if pismo.get("tytul"):
        p.append(_akapit(_run(a("\n".join(pismo["tytul"])), pogrubienie=True), wyrownanie="center", odstep_przed=24, interlinia=lin))
    for i, b in enumerate(pismo.get("tresc", [])):
        typ, tekst = b.get("typ", "akapit"), a(b.get("tekst", ""))
        przed = 40 if i == 0 and not pismo.get("tytul") else (20 if i == 0 else 0)
        if typ == "akapit":
            p.append(_akapit(_run(tekst), wyrownanie="both", odstep_przed=przed, interlinia=lin))
        else:
            p.append(_akapit(_run(tekst, pogrubienie=(typ == "ad")), odstep_przed=przed, interlinia=lin))
    p.append(_akapit(_run(a(pismo.get("zakonczenie", ""))), wciecie=WCIECIE_PODPISU, odstep_przed=29))
    if pismo.get("podpis"):
        p.append(_akapit(_run(a("\n".join(pismo["podpis"]))), wciecie=WCIECIE_PODPISU, odstep_przed=16))
    sekcja = (
        '<w:sectPr><w:headerReference w:type="default" r:id="rIdNaglowek"/>'
        '<w:footerReference w:type="default" r:id="rIdStopka"/>'
        f'<w:pgSz w:w="{int(595.3 * TWIP)}" w:h="{int(841.9 * TWIP)}"/>'
        f'<w:pgMar w:top="{GORA * TWIP}" w:right="{PRAWY * TWIP}" w:bottom="{DOL * TWIP}" w:left="{LEWY * TWIP}" '
        f'w:header="{40 * TWIP}" w:footer="{30 * TWIP}" w:gutter="0"/></w:sectPr>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{''.join(p)}{sekcja}</w:body></w:document>"
    )


def _czesc(znacznik: str, akapity: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:{znacznik} xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">{akapity}</w:{znacznik}>'
    )


def pismo_do_docx(pismo: dict) -> bytes:
    ukryte = ukryte_frazy(pismo)
    naglowek = _czesc("hdr", _akapit(_run("\n".join(pismo.get("naglowek", [])), rozmiar=14, czcionka="Corbel", kolor="323232"),
                                     wciecie=90))
    stopka = _czesc("ftr", _akapit(_run("\n".join(pismo.get("stopka", [])), rozmiar=9, czcionka="Corbel", kolor="323232")))
    pliki = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/header1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
            '<Override PartName="/word/footer1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>'
        ),
        "word/_rels/document.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdNaglowek" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>'
            '<Relationship Id="rIdStopka" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": _dokument(pismo, ukryte),
        "word/header1.xml": naglowek,
        "word/footer1.xml": stopka,
    }
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w", zipfile.ZIP_DEFLATED) as z:
        for nazwa, tresc in pliki.items():
            z.writestr(nazwa, tresc)
    return bufor.getvalue()


def dokument_do_docx(tekst: str, ukryte: list[str]) -> bytes:
    """Dowolny dokument (np. wgrany plik) po anonimizacji jako DOCX: akapit na każdą linię, bez nagłówka BKS."""
    akapity = "".join(_akapit(_run(linia)) for linia in anonimizuj(tekst, ukryte).split("\n"))
    dokument = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{akapity}<w:sectPr><w:pgSz w:w="{int(595.3 * TWIP)}" w:h="{int(841.9 * TWIP)}"/>'
        f'<w:pgMar w:top="{56 * TWIP}" w:right="{56 * TWIP}" w:bottom="{56 * TWIP}" w:left="{71 * TWIP}" '
        'w:header="0" w:footer="0" w:gutter="0"/></w:sectPr></w:body></w:document>'
    )
    pliki = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>'
        ),
        "word/document.xml": dokument,
    }
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w", zipfile.ZIP_DEFLATED) as z:
        for nazwa, tresc in pliki.items():
            z.writestr(nazwa, tresc)
    return bufor.getvalue()
