"""Generator przypadków testowych (end-to-end) dla Inteligentnego asystenta urzędnika.

Każdy przypadek to osobny folder z kompletem plików jednej sprawy:
  1_wniosek.docx                                   – wniosek wnioskodawcy (treść NIEzanonimizowana, dane fikcyjne)
  2_oczekiwany_wydzial.json                        – oczekiwany wybór jednostki UMB albo brak wydziału
  3_oczekiwana_wiadomosc_do_wydzialu.txt           – prośba do wydziału, dokładnie tak, jak składa ją aplikacja
  3b_oczekiwana_wiadomosc_do_wydzialu_zanonimizowana.txt – ta sama prośba po ukryciu danych wnioskodawcy
  4_odpowiedz_wydzialu.docx                        – projekt odpowiedzi / dane przesłane przez wydział
  5_oczekiwana_odpowiedz_do_wnioskodawcy.txt/.docx – oczekiwane pismo BKS do wnioskodawcy
  README.md                                        – opis scenariusza i kryteria oceny

Teksty z punktów 3 i 5 są składane funkcjami aplikacji (wydzialy.zloz_wiadomosc, wzor.pismo.zloz_pismo),
więc odpowiadają szablonom kodu 1:1. Część zależna od modelu AI (wybór wzoru i wartości pól) jest wzorcem
oczekiwanym – w ocenie porównuje się sens, a nie każde słowo.

Uruchomienie (z katalogu głównego repozytorium):
    uv run python "Przypadki testowe/_generator.py"

Wszystkie osoby, adresy, numery telefonów, e-maile, firmy i liczby są zmyślone.
"""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from inteligentny_asystent_urzednika.anonimizacja import zastosuj
from inteligentny_asystent_urzednika.konwersja.ocr_llm import tekst_docx
from inteligentny_asystent_urzednika.wydzialy import jednostka_po_nazwie, zloz_wiadomosc
from inteligentny_asystent_urzednika.wzor.eksport import pismo_do_docx
from inteligentny_asystent_urzednika.wzor.pismo import DanePisma, data_slownie, zloz_pismo, zloz_pismo_z_tekstu

KATALOG = Path(__file__).resolve().parent
WZORY = json.loads((KATALOG.parent / "wzory_pism.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ prosty zapis DOCX (akapity + tabele)
@dataclass
class P:
    """Akapit dokumentu źródłowego."""

    tekst: str
    pogrubienie: bool = False
    wyrownanie: str = "left"  # left | right | center | both


@dataclass
class T:
    """Tabela: pierwszy wiersz to nagłówek."""

    wiersze: list[list[str]]


def _run(tekst: str, pogrubienie: bool = False) -> str:
    rpr = '<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>'
    rpr += "<w:b/>" if pogrubienie else ""
    rpr += '<w:sz w:val="22"/></w:rPr>'
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(tekst)}</w:t></w:r>'


def _p(a: P) -> str:
    return (f'<w:p><w:pPr><w:spacing w:after="80"/><w:jc w:val="{a.wyrownanie}"/></w:pPr>'
            f"{_run(a.tekst, a.pogrubienie) if a.tekst else ''}</w:p>")


def _tabela(t: T) -> str:
    brzegi = "".join(f'<w:{b} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                     for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
    wiersze = []
    for i, w in enumerate(t.wiersze):
        komorki = "".join(f"<w:tc><w:tcPr><w:tcW w:w=\"0\" w:type=\"auto\"/></w:tcPr>{_p(P(k, pogrubienie=i == 0))}</w:tc>"
                          for k in w)
        wiersze.append(f"<w:tr>{komorki}</w:tr>")
    return (f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{brzegi}</w:tblBorders></w:tblPr>'
            f"{''.join(wiersze)}</w:tbl>")


def zapisz_docx(sciezka: Path, elementy: list[P | T]) -> None:
    tresc = "".join(_tabela(e) if isinstance(e, T) else _p(e) for e in elementy)
    dokument = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{tresc}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1418" w:header="708" w:footer="708" w:gutter="0"/>'
        "</w:sectPr></w:body></w:document>"
    )
    pliki = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
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
        for nazwa, t in pliki.items():
            z.writestr(nazwa, t)
    sciezka.write_bytes(bufor.getvalue())


def linie(tekst: str) -> list[P]:
    return [P(l) for l in tekst.strip("\n").split("\n")]


# ------------------------------------------------------------------ model przypadku
@dataclass
class Przypadek:
    folder: str
    numer: str
    data_wplywu: date
    temat: str
    opis: str
    wnioskodawca: str
    forma: str  # pan | pani | państwo
    adresat: list[str]
    wniosek: list[P | T]
    frazy_do_anonimizacji: list[str]
    # wydział
    symbol: str | None
    alternatywy: list[str] = field(default_factory=list)
    niepoprawne: list[str] = field(default_factory=list)
    uzasadnienie: str = ""
    podmiot_poza_umb: str = ""
    powod_braku_wydzialu: str = ""
    # odpowiedź wydziału
    data_odpowiedzi_wydzialu: date | None = None
    odpowiedz_wydzialu: list[P | T] = field(default_factory=list)
    frazy_w_odpowiedzi_wydzialu: list[str] = field(default_factory=list)
    # pismo końcowe
    data_pisma: date | None = None
    werdykt: str = ""
    wzor: str | None = None  # id wzoru z wzory_pism.json; None -> pismo z akapitów
    pola: dict = field(default_factory=dict)
    zalaczniki: list[str] = field(default_factory=list)
    akapity: list[str] = field(default_factory=list)
    tytul: list[str] = field(default_factory=list)
    kryteria: list[str] = field(default_factory=list)


def naglowek_wydzialu(nazwa: str, data: date, znak: str, numer_bks: str) -> list[P]:
    return [
        P("URZĄD MIASTA BYDGOSZCZY", pogrubienie=True),
        P(nazwa),
        P(f"Bydgoszcz, dnia {data_slownie(data)} r.", wyrownanie="right"),
        P(znak),
        P(""),
        P("Biuro Komunikacji Społecznej", pogrubienie=True),
        P("w miejscu", pogrubienie=True),
        P(""),
        P(f"dot. wniosku o udostępnienie informacji publicznej nr {numer_bks} – projekt odpowiedzi", pogrubienie=True),
        P(""),
    ]


def stopka_wydzialu(sporzadzil: str, dyrektor: str, funkcja: str) -> list[P]:
    return [
        P(""),
        P(dyrektor, wyrownanie="right"),
        P(funkcja, wyrownanie="right"),
        P(""),
        P(f"Sporządził(a): {sporzadzil}"),
    ]


# ------------------------------------------------------------------ PRZYPADKI
PRZYPADKI: list[Przypadek] = []

# TC01 ---------------------------------------------------------------- WGO, udostępnienie w treści
PRZYPADKI.append(Przypadek(
    folder="TC01 - WGO - deklaracje odpadowe (udostepnienie w tresci)",
    numer="BKS.IV.1431.701.2026",
    data_wplywu=date(2026, 11, 3),
    temat="Liczba deklaracji odpadowych i zadeklarowanych mieszkańców",
    opis="Typowy, kompletny wniosek o dwie liczby. Wydział podaje dane wprost – odpowiedź w treści pisma.",
    wnioskodawca="Tomasz Wiśniewski",
    forma="pan",
    adresat=["Pan", "Tomasz Wiśniewski", "ul. Kormoranów 12/4", "85-432 Bydgoszcz"],
    wniosek=linie("""
Bydgoszcz, 2 listopada 2026 r.
Tomasz Wiśniewski
ul. Kormoranów 12/4
85-432 Bydgoszcz
tel. 501 234 567
e-mail: t.wisniewski@poczta-przyklad.pl

Prezydent Miasta Bydgoszczy
Urząd Miasta Bydgoszczy
ul. Jezuicka 1, 85-102 Bydgoszcz

WNIOSEK O UDOSTĘPNIENIE INFORMACJI PUBLICZNEJ
Na podstawie art. 2 ust. 1 ustawy z dnia 6 września 2001 r. o dostępie do informacji publicznej zwracam się z prośbą o udostępnienie następujących informacji:
1. liczby deklaracji o wysokości opłaty za gospodarowanie odpadami komunalnymi złożonych dla nieruchomości zamieszkałych na terenie Miasta Bydgoszczy według stanu na dzień 30 września 2026 r.,
2. łącznej liczby mieszkańców wykazanych w tych deklaracjach według tego samego stanu.
Informację proszę przesłać w formie elektronicznej na adres e-mail: t.wisniewski@poczta-przyklad.pl.

Z poważaniem
Tomasz Wiśniewski
"""),
    frazy_do_anonimizacji=["Tomasz Wiśniewski", "ul. Kormoranów 12/4", "85-432 Bydgoszcz", "501 234 567",
                           "t.wisniewski@poczta-przyklad.pl"],
    symbol="WGO",
    alternatywy=[],
    niepoprawne=["WPL"],
    uzasadnienie="Deklaracje o wysokości opłaty za gospodarowanie odpadami komunalnymi i liczba zadeklarowanych "
                 "mieszkańców to dane prowadzone przez Wydział Gospodarki Odpadami (por. sprawa BKS.IV.1431.5.2026).",
    data_odpowiedzi_wydzialu=date(2026, 11, 9),
    odpowiedz_wydzialu=[
        *naglowek_wydzialu("Wydział Gospodarki Odpadami", date(2026, 11, 9), "WGO.1431.48.2026", "BKS.IV.1431.701.2026"),
        P("W odpowiedzi na prośbę Biura Komunikacji Społecznej o przygotowanie projektu odpowiedzi na wniosek "
          "o udostępnienie informacji publicznej, Wydział Gospodarki Odpadami przekazuje następujące dane według "
          "stanu na dzień 30 września 2026 r.:", wyrownanie="both"),
        T([["Lp.", "Wnioskowana informacja", "Wartość (stan na 30.09.2026 r.)"],
           ["1", "Liczba złożonych deklaracji o wysokości opłaty za gospodarowanie odpadami komunalnymi – nieruchomości zamieszkałe", "41 236"],
           ["2", "Łączna liczba mieszkańców wykazanych w deklaracjach", "298 415"]]),
        P(""),
        P("Proponowana treść odpowiedzi: według stanu na dzień 30 września 2026 r. dla nieruchomości zamieszkałych "
          "na terenie Miasta Bydgoszczy złożono 41 236 deklaracji o wysokości opłaty za gospodarowanie odpadami "
          "komunalnymi, w których wykazano łącznie 298 415 mieszkańców.", wyrownanie="both"),
        P("Informacja nie wymaga przetworzenia ani anonimizacji."),
        *stopka_wydzialu("Ewelina Sikora, tel. (52) 58 59 000 wew. 112", "Dyrektor Wydziału Gospodarki Odpadami",
                         "(podpis elektroniczny)"),
    ],
    data_pisma=date(2026, 11, 13),
    werdykt="MOZNA_UDOSTEPNIC",
    wzor="udostepnienie_w_tresci",
    pola={
        "zakres_wniosku": "liczby deklaracji o wysokości opłaty za gospodarowanie odpadami komunalnymi złożonych dla "
                          "nieruchomości zamieszkałych na terenie Miasta Bydgoszczy oraz łącznej liczby mieszkańców "
                          "wykazanych w tych deklaracjach według stanu na dzień 30 września 2026 r.",
        "tresc_informacji": "według stanu na dzień 30 września 2026 r. dla nieruchomości zamieszkałych na terenie Miasta "
                            "Bydgoszczy złożono 41 236 deklaracji o wysokości opłaty za gospodarowanie odpadami "
                            "komunalnymi, w których wykazano łącznie 298 415 mieszkańców",
    },
    kryteria=[
        "Wydział: WGO na 1. miejscu propozycji.",
        "Pismo zawiera obie liczby z odpowiedzi wydziału: 41 236 deklaracji i 298 415 mieszkańców.",
        "Zwrot „Szanowny Panie,”, forma „przez Pana”.",
        "Brak „[[do uzupełnienia]]” w piśmie końcowym.",
    ],
))

# TC02 ---------------------------------------------------------------- WE, zestawienie w załączniku
PRZEDSZKOLA = [
    ["Lp.", "Przedszkole", "Adres", "Liczba oddziałów", "Liczba dzieci (30.09.2026)", "Liczba wolnych miejsc"],
    ["1", "Przedszkole Miejskie nr 3", "ul. Przykładowa 10", "6", "148", "2"],
    ["2", "Przedszkole Miejskie nr 7", "ul. Testowa 4", "5", "121", "4"],
    ["3", "Przedszkole Miejskie nr 12", "ul. Wzorcowa 22", "8", "196", "0"],
    ["4", "Przedszkole Miejskie nr 18", "ul. Próbna 3", "4", "97", "3"],
    ["5", "Przedszkole Miejskie nr 21", "ul. Fikcyjna 15", "7", "170", "5"],
    ["6", "Przedszkole Miejskie nr 26", "ul. Modelowa 8", "5", "125", "0"],
    ["7", "Przedszkole Miejskie nr 33", "ul. Szkicowa 1", "6", "142", "8"],
    ["8", "Przedszkole Miejskie nr 40", "ul. Robocza 19", "3", "72", "3"],
    ["9", "Przedszkole Miejskie nr 47", "ul. Ćwiczebna 6", "9", "220", "5"],
    ["10", "Przedszkole Miejskie nr 52", "ul. Zadaniowa 11", "4", "100", "0"],
    ["", "RAZEM", "", "57", "1391", "30"],
]
PRZYPADKI.append(Przypadek(
    folder="TC02 - WE - przedszkola zestawienie (udostepnienie w zalaczniku)",
    numer="BKS.IV.1431.702.2026",
    data_wplywu=date(2026, 11, 4),
    temat="Zestawienie przedszkoli miejskich – dzieci, oddziały, wolne miejsca",
    opis="Wniosek organizacji (fundacji) o zestawienie tabelaryczne w formie edytowalnej. Wydział przesyła tabelę – "
         "odpowiedź w załączniku.",
    wnioskodawca="Fundacja „Równy Start”",
    forma="państwo",
    adresat=["Fundacja „Równy Start”", "ul. Gdańska 140/2", "85-674 Bydgoszcz"],
    wniosek=linie("""
Od: Anna Kowalczyk <biuro@rownystart-fundacja.example.org>
Temat: Wniosek o informację publiczną – przedszkola

Szanowni Państwo,
w imieniu Fundacji „Równy Start” (KRS 0000999123), na podstawie ustawy z dnia 6 września 2001 r. o dostępie do informacji publicznej, wnoszę o udostępnienie zestawienia wszystkich przedszkoli publicznych prowadzonych przez Miasto Bydgoszcz z podaniem dla każdego przedszkola:
- liczby dzieci uczęszczających według stanu na dzień 30 września 2026 r.,
- liczby oddziałów,
- liczby wolnych miejsc.
Zestawienie proszę przesłać w formie edytowalnej (np. arkusz kalkulacyjny lub tabela w pliku Word) na adres: biuro@rownystart-fundacja.example.org.

Z poważaniem
Anna Kowalczyk
Prezes Zarządu Fundacji „Równy Start”
ul. Gdańska 140/2, 85-674 Bydgoszcz
tel. 698 765 432
"""),
    frazy_do_anonimizacji=["Anna Kowalczyk", "698 765 432"],
    symbol="WE",
    alternatywy=[],
    niepoprawne=["BZS"],
    uzasadnienie="Przedszkola prowadzone przez Miasto, liczba dzieci i oddziałów to sprawy oświaty – Wydział Edukacji "
                 "i Sportu (por. sprawy BKS.IV.1431.1.2025 i 599.2026 o liczbie uczniów).",
    data_odpowiedzi_wydzialu=date(2026, 11, 10),
    odpowiedz_wydzialu=[
        *naglowek_wydzialu("Wydział Edukacji i Sportu", date(2026, 11, 10), "WE.1431.112.2026", "BKS.IV.1431.702.2026"),
        P("W odpowiedzi na prośbę o przygotowanie projektu odpowiedzi Wydział Edukacji i Sportu przekazuje "
          "zestawienie przedszkoli publicznych prowadzonych przez Miasto Bydgoszcz według danych Systemu Informacji "
          "Oświatowej na dzień 30 września 2026 r. Zestawienie przeznaczone jest do przekazania wnioskodawcy jako "
          "załącznik (Informacja_702), w formie edytowalnej.", wyrownanie="both"),
        T(PRZEDSZKOLA),
        P(""),
        P("Uwaga: dane w zestawieniu są fikcyjne – przygotowane na potrzeby testów aplikacji."),
        P("Zestawienie nie zawiera danych osobowych i nie wymaga anonimizacji."),
        *stopka_wydzialu("Karolina Mazur, tel. (52) 58 59 000 wew. 245", "Zastępca Dyrektora Wydziału Edukacji i Sportu",
                         "(podpis elektroniczny)"),
    ],
    data_pisma=date(2026, 11, 16),
    werdykt="MOZNA_UDOSTEPNIC",
    wzor="udostepnienie_w_zalaczniku",
    pola={
        "zakres_wniosku": "zestawienia przedszkoli publicznych prowadzonych przez Miasto Bydgoszcz z podaniem liczby "
                          "dzieci, liczby oddziałów i liczby wolnych miejsc według stanu na dzień 30 września 2026 r.",
    },
    kryteria=[
        "Wydział: WE na 1. miejscu propozycji.",
        "Wybrany wzór: udostępnienie w załączniku; w piśmie linia „Załącznik: Informacja_702”.",
        "Forma „przez Państwa” (wniosek fundacji) – wzór bez zwrotu grzecznościowego.",
        "Adresatem jest Fundacja, a nie osoba prywatna; imię i nazwisko prezes nie musi trafić do pisma.",
        "Interpunkcja: „…30 września 2026 r., na podstawie…” – kropka skrótu „r.” zostaje przed przecinkiem "
        "(obecnie zloz_tresc ją usuwa: „2026 r,”).",
    ],
))

# TC03 ---------------------------------------------------------------- WIM, punkt po punkcie
PRZYPADKI.append(Przypadek(
    folder="TC03 - WIM - inwestycja drogowa (punkt po punkcie)",
    numer="BKS.IV.1431.703.2026",
    data_wplywu=date(2026, 11, 5),
    temat="Budowa ronda Fordońska / Wyszogrodzka – wykonawca, koszty, terminy, kary",
    opis="Dziennikarz zadaje 4 ponumerowane pytania o inwestycję. Odpowiedź punkt po punkcie (Ad 1 … Ad 4).",
    wnioskodawca="Piotr Zając",
    forma="pan",
    adresat=["Pan", "Piotr Zając", "redakcja@kurier-fordonski.example.pl"],
    wniosek=linie("""
Piotr Zając
dziennikarz „Kuriera Fordońskiego”
e-mail: redakcja@kurier-fordonski.example.pl
tel. 512 908 776

Urząd Miasta Bydgoszczy
Biuro Komunikacji Społecznej

Wniosek o udostępnienie informacji publicznej

Działając na podstawie art. 2 ust. 1 oraz art. 10 ust. 1 ustawy z dnia 6 września 2001 r. o dostępie do informacji publicznej, proszę o udzielenie informacji dotyczących inwestycji pn. „Budowa ronda turbinowego u zbiegu ul. Fordońskiej i ul. Wyszogrodzkiej w Bydgoszczy”:
1. Kto jest wykonawcą inwestycji i kiedy zawarto z nim umowę?
2. Jaka jest wartość umowy brutto oraz czy zawierano aneksy zmieniające wynagrodzenie wykonawcy – jeśli tak, to na jakie kwoty?
3. Jaki był pierwotny i jaki jest aktualny termin zakończenia robót?
4. Czy Miasto naliczyło wykonawcy kary umowne – jeśli tak, w jakiej wysokości i z jakiego tytułu?
Odpowiedź proszę przesłać na adres e-mail podany powyżej.

Z wyrazami szacunku
Piotr Zając
"""),
    frazy_do_anonimizacji=["Piotr Zając", "512 908 776", "redakcja@kurier-fordonski.example.pl"],
    symbol="WIM",
    alternatywy=["WZP"],
    niepoprawne=["WAB"],
    uzasadnienie="Inwestycja drogowa realizowana przez Miasto – umowę z wykonawcą, aneksy, terminy i kary umowne "
                 "prowadzi Wydział Inwestycji Miasta (por. sprawa BKS.IV.1431.8.2026). WZP dopuszczalny jako druga "
                 "jednostka (umowa z wykonawcą po przetargu).",
    data_odpowiedzi_wydzialu=date(2026, 11, 12),
    odpowiedz_wydzialu=[
        *naglowek_wydzialu("Wydział Inwestycji Miasta", date(2026, 11, 12), "WIM.1431.77.2026", "BKS.IV.1431.703.2026"),
        P("Wydział Inwestycji Miasta przekazuje odpowiedzi na pytania zawarte we wniosku dotyczącym inwestycji "
          "pn. „Budowa ronda turbinowego u zbiegu ul. Fordońskiej i ul. Wyszogrodzkiej w Bydgoszczy”:", wyrownanie="both"),
        P("Ad 1", pogrubienie=True),
        P("Wykonawcą inwestycji jest Drogbud Infrastruktura Sp. z o.o. z siedzibą w Bydgoszczy. Umowę nr WIM/45/2025 "
          "zawarto w dniu 14 kwietnia 2025 r. po przeprowadzeniu postępowania o udzielenie zamówienia publicznego "
          "w trybie podstawowym.", wyrownanie="both"),
        P("Ad 2", pogrubienie=True),
        P("Wartość umowy brutto wynosiła 18 437 920,00 zł. Aneksem nr 1 z dnia 3 marca 2026 r. wynagrodzenie "
          "zwiększono o 612 400,00 zł brutto w związku z robotami dodatkowymi (przebudowa kolidującej sieci "
          "wodociągowej). Aktualna wartość umowy wynosi 19 050 320,00 zł brutto. Aneks nr 2 z dnia 12 sierpnia "
          "2026 r. nie zmieniał wynagrodzenia.", wyrownanie="both"),
        P("Ad 3", pogrubienie=True),
        P("Pierwotny termin zakończenia robót: 30 września 2026 r. Aneksem nr 2 z dnia 12 sierpnia 2026 r. termin "
          "przesunięto na 15 grudnia 2026 r. z uwagi na nieujawnioną w dokumentacji kolizję z siecią gazową.",
          wyrownanie="both"),
        P("Ad 4", pogrubienie=True),
        P("Miasto nie naliczyło wykonawcy kar umownych. Przesunięcie terminu wynika z okoliczności, za które "
          "wykonawca nie ponosi odpowiedzialności.", wyrownanie="both"),
        P("Dane spółki (osoby prawnej) nie podlegają anonimizacji."),
        *stopka_wydzialu("Łukasz Pawlak, tel. (52) 58 59 000 wew. 318", "Dyrektor Wydziału Inwestycji Miasta",
                         "(podpis elektroniczny)"),
    ],
    data_pisma=date(2026, 11, 17),
    werdykt="MOZNA_UDOSTEPNIC",
    wzor="udostepnienie_punkt_po_punkcie",
    pola={
        "zakres_wniosku": "inwestycji pn. „Budowa ronda turbinowego u zbiegu ul. Fordońskiej i ul. Wyszogrodzkiej "
                          "w Bydgoszczy” – wykonawcy, wartości umowy, terminów realizacji i kar umownych",
        "odpowiedzi": [
            "Wykonawcą inwestycji jest Drogbud Infrastruktura Sp. z o.o. z siedzibą w Bydgoszczy. Umowę nr WIM/45/2025 "
            "zawarto w dniu 14 kwietnia 2025 r. po przeprowadzeniu postępowania o udzielenie zamówienia publicznego "
            "w trybie podstawowym.",
            "Wartość umowy brutto wynosiła 18 437 920,00 zł. Aneksem nr 1 z dnia 3 marca 2026 r. wynagrodzenie "
            "zwiększono o 612 400,00 zł brutto w związku z robotami dodatkowymi (przebudowa kolidującej sieci "
            "wodociągowej). Aktualna wartość umowy wynosi 19 050 320,00 zł brutto. Aneks nr 2 z dnia 12 sierpnia "
            "2026 r. nie zmieniał wynagrodzenia.",
            "Pierwotny termin zakończenia robót przypadał na 30 września 2026 r. Aneksem nr 2 z dnia 12 sierpnia 2026 r. "
            "termin przesunięto na 15 grudnia 2026 r. z uwagi na nieujawnioną w dokumentacji kolizję z siecią gazową.",
            "Miasto nie naliczyło wykonawcy kar umownych. Przesunięcie terminu wynika z okoliczności, za które "
            "wykonawca nie ponosi odpowiedzialności.",
        ],
    },
    kryteria=[
        "Wydział: WIM na 1. miejscu (WZP akceptowalny jako 2.).",
        "Pismo ma 4 punkty Ad 1 – Ad 4 w kolejności pytań.",
        "Kwoty zgodne z odpowiedzią wydziału: 18 437 920,00 zł, 612 400,00 zł, 19 050 320,00 zł.",
        "Nazwa spółki-wykonawcy NIE jest anonimizowana (osoba prawna).",
    ],
))

# TC04 ---------------------------------------------------------------- WSO, brak danych
PRZYPADKI.append(Przypadek(
    folder="TC04 - WSO - CEIDG brak statystyk (brak danych)",
    numer="BKS.IV.1431.704.2026",
    data_wplywu=date(2026, 11, 6),
    temat="Przyczyny zamknięcia działalności gospodarczych w 2025 r.",
    opis="Wniosek trafia do właściwego wydziału, ale urząd nie prowadzi takich danych. Odpowiedź: pismo "
         "informacyjne „urząd nie prowadzi statystyk” (wzór jak BKS.IV.1431.4.2026).",
    wnioskodawca="Joanna Malinowska",
    forma="pani",
    adresat=["Pani", "Joanna Malinowska", "j.malinowska@skrzynka-przyklad.pl"],
    wniosek=linie("""
Dzień dobry,
w trybie dostępu do informacji publicznej proszę o informację, ile osób fizycznych prowadzących działalność gospodarczą z siedzibą w Bydgoszczy zakończyło (wykreśliło z CEIDG) działalność w 2025 r. z powodu wzrostu cen energii.
Odpowiedź proszę przesłać na mój adres e-mail.

Pozdrawiam
Joanna Malinowska
j.malinowska@skrzynka-przyklad.pl
"""),
    frazy_do_anonimizacji=["Joanna Malinowska", "j.malinowska@skrzynka-przyklad.pl"],
    symbol="WSO",
    alternatywy=[],
    niepoprawne=["WPL", "WW"],
    uzasadnienie="Sprawy działalności gospodarczej (CEIDG) prowadzi Wydział Spraw Obywatelskich (por. sprawa "
                 "BKS.IV.1431.4.2026).",
    data_odpowiedzi_wydzialu=date(2026, 11, 10),
    odpowiedz_wydzialu=[
        *naglowek_wydzialu("Wydział Spraw Obywatelskich", date(2026, 11, 10), "WSO.1431.39.2026", "BKS.IV.1431.704.2026"),
        P("Wydział Spraw Obywatelskich informuje, że wnioski o wykreślenie wpisu z Centralnej Ewidencji i Informacji "
          "o Działalności Gospodarczej (CEIDG) nie zawierają informacji o przyczynie zakończenia działalności "
          "gospodarczej – przedsiębiorca nie ma obowiązku jej podawać.", wyrownanie="both"),
        P("W związku z tym Urząd Miasta Bydgoszczy nie prowadzi statystyk przyczyn zakończenia działalności "
          "gospodarczej, które umożliwiłyby udzielenie odpowiedzi na pytanie wnioskodawczyni. Wydział nie dysponuje "
          "również danymi pozwalającymi powiązać wykreślenia z cenami energii.", wyrownanie="both"),
        P("Proponujemy udzielenie odpowiedzi w formie pisma informacyjnego o braku danych."),
        *stopka_wydzialu("Monika Wróbel, tel. (52) 58 59 000 wew. 407", "Dyrektor Wydziału Spraw Obywatelskich",
                         "(podpis elektroniczny)"),
    ],
    data_pisma=date(2026, 11, 17),
    werdykt="NIE_MOZNA_PISMO_INFORMACYJNE",
    wzor="brak_danych",
    pola={
        "zakres_wniosku": "ile osób fizycznych prowadzących działalność gospodarczą z siedzibą w Bydgoszczy zakończyło "
                          "(wykreśliło z CEIDG) działalność w 2025 r. z powodu wzrostu cen energii?",
        "rodzaj_danych": "statystyk przyczyn zakończenia działalności gospodarczej",
    },
    kryteria=[
        "Wydział: WSO na 1. miejscu.",
        "Wzór: brak danych (NIE decyzja odmowna – informacja nie istnieje, więc nie ma czego odmówić).",
        "Zwrot „Szanowna Pani,”, forma „przez Panią”.",
    ],
))

# TC05 ---------------------------------------------------------------- WOA, punkt po punkcie + załącznik
SAMOCHODY = [
    ["Lp.", "Marka", "Model", "Rok produkcji", "Rodzaj napędu"],
    ["1", "Toyota", "Corolla", "2021", "hybrydowy"],
    ["2", "Toyota", "Corolla", "2021", "hybrydowy"],
    ["3", "Toyota", "Camry", "2022", "hybrydowy"],
    ["4", "Škoda", "Octavia", "2019", "benzynowy"],
    ["5", "Škoda", "Octavia", "2019", "benzynowy"],
    ["6", "Škoda", "Superb", "2023", "hybrydowy plug-in"],
    ["7", "Renault", "Zoe", "2020", "elektryczny"],
    ["8", "Renault", "Zoe", "2020", "elektryczny"],
    ["9", "Nissan", "Leaf", "2022", "elektryczny"],
    ["10", "Volkswagen", "Caddy", "2018", "olej napędowy"],
    ["11", "Volkswagen", "Transporter", "2017", "olej napędowy"],
    ["12", "Dacia", "Duster", "2020", "benzynowy"],
    ["13", "Kia", "Niro", "2024", "elektryczny"],
    ["14", "Ford", "Transit Custom", "2019", "olej napędowy"],
]
PRZYPADKI.append(Przypadek(
    folder="TC05 - WOA - samochody sluzbowe (punkt po punkcie z zalacznikiem)",
    numer="BKS.IV.1431.705.2026",
    data_wplywu=date(2026, 11, 9),
    temat="Samochody służbowe Urzędu Miasta – liczba, wykaz, koszt paliwa",
    opis="Wniosek o 4 informacje; wydział podaje liczby w treści i wykaz w tabeli. Odpowiedź punkt po punkcie "
         "z załącznikiem.",
    wnioskodawca="Marek Lewandowski",
    forma="pan",
    adresat=["Pan", "Marek Lewandowski", "ul. Słoneczna 5", "86-031 Osielsko"],
    wniosek=linie("""
Marek Lewandowski
ul. Słoneczna 5
86-031 Osielsko
PESEL 85030412345
m.lewandowski@example.net

Szanowni Państwo,
na podstawie ustawy o dostępie do informacji publicznej proszę o:
1. podanie liczby samochodów służbowych będących w dyspozycji Urzędu Miasta Bydgoszczy według stanu na 31 października 2026 r.,
2. wykaz tych samochodów z podaniem marki, modelu, roku produkcji i rodzaju napędu,
3. podanie łącznego kosztu paliwa i energii elektrycznej do tych samochodów poniesionego w 2025 r.,
4. informację, czy Prezydent Miasta Bydgoszczy korzysta z samochodu służbowego z kierowcą.
Odpowiedź proszę przesłać pocztą na adres podany wyżej.

Marek Lewandowski
"""),
    frazy_do_anonimizacji=["Marek Lewandowski", "ul. Słoneczna 5", "86-031 Osielsko", "85030412345",
                           "m.lewandowski@example.net"],
    symbol="WOA",
    alternatywy=["WK"],
    niepoprawne=["WUK", "WIM"],
    uzasadnienie="Samochody służbowe urzędu są w zakresie Wydziału Organizacyjno-Administracyjnego; Wydział "
                 "Księgowości dopuszczalny jako druga jednostka (koszt paliwa z ewidencji wydatków).",
    data_odpowiedzi_wydzialu=date(2026, 11, 16),
    odpowiedz_wydzialu=[
        *naglowek_wydzialu("Wydział Organizacyjno-Administracyjny", date(2026, 11, 16), "WOA.1431.64.2026",
                           "BKS.IV.1431.705.2026"),
        P("Wydział Organizacyjno-Administracyjny przekazuje odpowiedzi na pytania wnioskodawcy:", wyrownanie="both"),
        P("Ad 1", pogrubienie=True),
        P("Według stanu na dzień 31 października 2026 r. w dyspozycji Urzędu Miasta Bydgoszczy pozostaje 14 samochodów "
          "służbowych.", wyrownanie="both"),
        P("Ad 2", pogrubienie=True),
        P("Wykaz samochodów (do przekazania wnioskodawcy jako załącznik Informacja_705):"),
        T(SAMOCHODY),
        P("Ad 3", pogrubienie=True),
        P("Łączny koszt paliwa i energii elektrycznej do samochodów służbowych w 2025 r. wyniósł 96 482,17 zł brutto "
          "(dane uzgodnione z Wydziałem Księgowości).", wyrownanie="both"),
        P("Ad 4", pogrubienie=True),
        P("Tak. Prezydent Miasta Bydgoszczy korzysta z samochodu służbowego (poz. 3 wykazu) wyłącznie do celów "
          "służbowych; samochód prowadzą kierowcy zatrudnieni w Wydziale Organizacyjno-Administracyjnym.",
          wyrownanie="both"),
        P("Wykaz nie zawiera numerów rejestracyjnych ani danych osobowych kierowców."),
        *stopka_wydzialu("Agnieszka Dudek, tel. (52) 58 59 000 wew. 150",
                         "Dyrektor Wydziału Organizacyjno-Administracyjnego", "(podpis elektroniczny)"),
    ],
    data_pisma=date(2026, 11, 19),
    werdykt="MOZNA_UDOSTEPNIC",
    wzor="udostepnienie_punkt_po_punkcie",
    pola={
        "zakres_wniosku": "samochodów służbowych będących w dyspozycji Urzędu Miasta Bydgoszczy, ich wykazu, kosztu "
                          "paliwa i energii elektrycznej w 2025 r. oraz korzystania z samochodu służbowego przez "
                          "Prezydenta Miasta Bydgoszczy",
        "odpowiedzi": [
            "Według stanu na dzień 31 października 2026 r. w dyspozycji Urzędu Miasta Bydgoszczy pozostaje 14 samochodów "
            "służbowych.",
            "Wykaz samochodów służbowych z podaniem marki, modelu, roku produkcji i rodzaju napędu przekazuję "
            "w załączeniu.",
            "Łączny koszt paliwa i energii elektrycznej do samochodów służbowych poniesiony w 2025 r. wyniósł "
            "96 482,17 zł brutto.",
            "Prezydent Miasta Bydgoszczy korzysta z samochodu służbowego wyłącznie do celów służbowych; samochód "
            "prowadzą kierowcy zatrudnieni w Wydziale Organizacyjno-Administracyjnym Urzędu Miasta Bydgoszczy.",
        ],
    },
    zalaczniki=["Informacja_705 (wykaz samochodów służbowych Urzędu Miasta Bydgoszczy)"],
    kryteria=[
        "Wydział: WOA na 1. miejscu (WK akceptowalny jako 2.).",
        "PESEL wnioskodawcy wykryty jako dane do anonimizacji w prośbie do wydziału i maskowany przed wysłaniem do AI.",
        "Ad 1 – Ad 4; liczba 14 i kwota 96 482,17 zł zgodne z odpowiedzią wydziału.",
        "Wykaz przekazany jako załącznik Informacja_705 (a nie przepisany w treści).",
        "Adresat z adresem pocztowym (odpowiedź pocztą).",
    ],
))

# TC06 ---------------------------------------------------------------- WOŚ, udostępnienie z anonimizacją
PRZYPADKI.append(Przypadek(
    folder="TC06 - WOS - wycinka drzew (udostepnienie z anonimizacja)",
    numer="BKS.IV.1431.706.2026",
    data_wplywu=date(2026, 11, 10),
    temat="Zezwolenie na usunięcie dębów przy ul. Leśnej 14",
    opis="Informację można udostępnić, ale odpowiedź wydziału zawiera dane osoby trzeciej (właściciela działki). "
         "Pismo końcowe musi je pominąć (MOZNA_Z_ANONIMIZACJA).",
    wnioskodawca="Katarzyna Nowak",
    forma="pani",
    adresat=["Pani", "Katarzyna Nowak", "ul. Leśna 9", "85-676 Bydgoszcz"],
    wniosek=linie("""
Katarzyna Nowak
ul. Leśna 9
85-676 Bydgoszcz
tel. 604 111 222

Urząd Miasta Bydgoszczy

Dzień dobry,
w trybie ustawy o dostępie do informacji publicznej proszę o informację, czy Urząd wydał zezwolenie na usunięcie dębów rosnących na nieruchomości przy ul. Leśnej 14 w Bydgoszczy (działka nr 17/3, obręb 0123). Jeżeli tak – proszę o podanie daty i numeru decyzji, liczby drzew objętych zezwoleniem, kto wystąpił o zezwolenie oraz jakie nasadzenia zastępcze nakazano.
Odpowiedź proszę przesłać pocztą.

Z poważaniem
Katarzyna Nowak
"""),
    frazy_do_anonimizacji=["Katarzyna Nowak", "ul. Leśna 9", "85-676 Bydgoszcz", "604 111 222"],
    symbol="WOŚ",
    alternatywy=["WGK"],
    niepoprawne=["WAB", "WMG"],
    uzasadnienie="Zezwolenia na usunięcie drzew z nieruchomości wydaje Prezydent Miasta – sprawy prowadzi Wydział "
                 "Ochrony Środowiska (zakres: wycinka drzew). WGK dopuszczalny jako 2. (zieleń miejska).",
    data_odpowiedzi_wydzialu=date(2026, 11, 16),
    odpowiedz_wydzialu=[
        *naglowek_wydzialu("Wydział Ochrony Środowiska", date(2026, 11, 16), "WOŚ.1431.51.2026", "BKS.IV.1431.706.2026"),
        P("Wydział Ochrony Środowiska informuje, że decyzją nr WOŚ.6131.512.2026 z dnia 12 października 2026 r. "
          "Prezydent Miasta Bydgoszczy zezwolił Panu Jerzemu Kamińskiemu, zam. ul. Leśna 14, 85-676 Bydgoszcz "
          "(właścicielowi nieruchomości, działka nr 17/3, obręb 0123), na usunięcie 2 z 3 wnioskowanych dębów "
          "szypułkowych. W zakresie trzeciego drzewa odmówiono zezwolenia ze względu na jego dobry stan zdrowotny.",
          wyrownanie="both"),
        P("W decyzji nakazano wykonanie nasadzeń zastępczych 6 drzew (lipa drobnolistna, obwód pnia min. 16 cm) "
          "na tej samej nieruchomości w terminie do 30 kwietnia 2027 r.", wyrownanie="both"),
        P("Uwaga: wniosek o zezwolenie złożyła osoba fizyczna – imię, nazwisko i adres wnioskodawcy decyzji "
          "podlegają anonimizacji (art. 5 ust. 2 ustawy o dostępie do informacji publicznej – prywatność osoby "
          "fizycznej). W odpowiedzi można wskazać, że o zezwolenie wystąpił właściciel nieruchomości.",
          wyrownanie="both"),
        *stopka_wydzialu("Tomasz Szulc, tel. (52) 58 59 000 wew. 530", "Dyrektor Wydziału Ochrony Środowiska",
                         "(podpis elektroniczny)"),
    ],
    frazy_w_odpowiedzi_wydzialu=["Jerzemu Kamińskiemu", "ul. Leśna 14, 85-676 Bydgoszcz"],
    data_pisma=date(2026, 11, 20),
    werdykt="MOZNA_Z_ANONIMIZACJA",
    wzor="udostepnienie_w_tresci",
    pola={
        "zakres_wniosku": "zezwolenia na usunięcie dębów rosnących na nieruchomości przy ul. Leśnej 14 w Bydgoszczy "
                          "(działka nr 17/3, obręb 0123)",
        "tresc_informacji": "decyzją nr WOŚ.6131.512.2026 z dnia 12 października 2026 r. Prezydent Miasta Bydgoszczy "
                            "zezwolił właścicielowi nieruchomości, który wystąpił z wnioskiem o wydanie zezwolenia, "
                            "na usunięcie 2 z 3 wnioskowanych dębów szypułkowych, a w zakresie trzeciego drzewa "
                            "odmówił zezwolenia ze względu na jego dobry stan zdrowotny. W decyzji nakazano wykonanie "
                            "nasadzeń zastępczych 6 drzew (lipa drobnolistna, obwód pnia min. 16 cm) na tej samej "
                            "nieruchomości w terminie do 30 kwietnia 2027 r. Dane osobowe właściciela nieruchomości, "
                            "jako osoby fizycznej, nie podlegają udostępnieniu ze względu na ochronę prywatności "
                            "(art. 5 ust. 2 ustawy o dostępie do informacji publicznej)",
    },
    kryteria=[
        "Wydział: WOŚ na 1. miejscu (WGK akceptowalny jako 2.).",
        "W piśmie końcowym NIE ma „Jerzy Kamiński” / „Jerzemu Kamińskiemu” ani jego adresu zamieszkania.",
        "Pismo zawiera numer i datę decyzji, liczbę drzew (2 z 3) i nasadzenia zastępcze (6 lip do 30.04.2027).",
        "Anonimizacja w podglądzie pisma / pliku odpowiedzi wydziału proponuje ukrycie danych osoby trzeciej.",
    ],
))

# TC07 ---------------------------------------------------------------- brak wydziału: dysponent poza UMB
PRZYPADKI.append(Przypadek(
    folder="TC07 - BRAK WYDZIALU - ZDMiKP dysponentem (wskazanie dysponenta)",
    numer="BKS.IV.1431.707.2026",
    data_wplywu=date(2026, 11, 12),
    temat="Punktualność kursów linii autobusowej nr 69",
    opis="Żądane dane posiada miejska jednostka organizacyjna (ZDMiKP), a nie Urząd Miasta. Wniosku nie przekazuje "
         "się do wydziału – BKS od razu informuje wnioskodawcę o właściwym dysponencie (jak BKS.IV.1431.3.2026).",
    wnioskodawca="Krzysztof Jankowski",
    forma="pan",
    adresat=["Pan", "Krzysztof Jankowski", "k.jankowski@poczta-przyklad.pl"],
    wniosek=linie("""
Szanowni Państwo,
proszę o udostępnienie w trybie informacji publicznej danych o tym, ile kursów linii autobusowej nr 69 w październiku 2026 r. zostało zrealizowanych z opóźnieniem większym niż 5 minut oraz ile kursów tej linii w ogóle nie zostało wykonanych, z podziałem na dni robocze i weekendy.
Proszę o odpowiedź mailową.

Krzysztof Jankowski
k.jankowski@poczta-przyklad.pl
tel. 723 456 789
"""),
    frazy_do_anonimizacji=["Krzysztof Jankowski", "k.jankowski@poczta-przyklad.pl", "723 456 789"],
    symbol=None,
    niepoprawne=["WUK", "WIM", "WGK"],
    podmiot_poza_umb="Zarząd Dróg Miejskich i Komunikacji Publicznej w Bydgoszczy",
    powod_braku_wydzialu="Organizacją komunikacji miejskiej i nadzorem nad realizacją kursów zajmuje się ZDMiKP – "
                         "jednostka budżetowa Miasta, samodzielny podmiot zobowiązany do udostępniania informacji "
                         "(art. 4 ust. 3 UDIP). Urząd Miasta nie posiada tych danych.",
    data_pisma=date(2026, 11, 16),
    werdykt="NIE_MOZNA_PISMO_INFORMACYJNE",
    wzor="nieposiadanie_wskazanie_dysponenta",
    pola={
        "zakres_wniosku": "liczby kursów linii autobusowej nr 69 zrealizowanych w październiku 2026 r. z opóźnieniem "
                          "większym niż 5 minut oraz liczby kursów niewykonanych",
        "wlasciwy_podmiot": "Zarządu Dróg Miejskich i Komunikacji Publicznej w Bydgoszczy",
        "dane_kontaktowe": ["Zarząd Dróg Miejskich i Komunikacji Publicznej w Bydgoszczy", "ul. Toruńska 174a",
                            "85-844 Bydgoszcz", "e-mail: zarzad@zdmikp.bydgoszcz.pl"],
    },
    kryteria=[
        "Brak wydziału UMB do wysłania prośby; aplikacja wskazuje podmiot_poza_umb = ZDMiKP.",
        "WUK (transport) NIE jest poprawnym wyborem – uprawnienia komunikacyjne to prawa jazdy i rejestracja pojazdów.",
        "Wzór: UMB nie jest dysponentem informacji – z danymi kontaktowymi ZDMiKP (jak w BKS.IV.1431.3.2026).",
        "Odpowiedź może być wysłana od razu, bez czekania na wydział (krótki czas obsługi).",
    ],
))

# TC08 ---------------------------------------------------------------- brak wydziału: wniosek niejasny
PRZYPADKI.append(Przypadek(
    folder="TC08 - BRAK WYDZIALU - wniosek niejasny (wezwanie do doprecyzowania)",
    numer="BKS.IV.1431.708.2026",
    data_wplywu=date(2026, 11, 13),
    temat="Wniosek o „wszystkie dokumenty w mojej sprawie” – niejasny",
    opis="Z wniosku nie wynika, jakiej sprawy i jakich informacji dotyczy – nie da się wskazać wydziału. "
         "Wniosek wraca do wnioskodawcy z wezwaniem do doprecyzowania (pod rygorem pozostawienia bez rozpoznania), "
         "z pouczeniem o trybie dostępu do akt własnej sprawy (art. 73 KPA).",
    wnioskodawca="Adam Wójcik",
    forma="pan",
    adresat=["Pan", "Adam Wójcik", "ul. Kasztanowa 21/7", "85-605 Bydgoszcz"],
    wniosek=linie("""
Adam Wójcik
ul. Kasztanowa 21/7, 85-605 Bydgoszcz
tel. 669 200 300, adam.wojcik@example.com

Do Urzędu Miasta

Proszę o przesłanie wszystkich dokumentów w mojej sprawie z zeszłego roku oraz o informację, dlaczego urząd do tej pory nic z tym nie zrobił. Sprawę zgłaszałem kilka razy telefonicznie i nikt nie oddzwonił.
Żądam odpowiedzi w terminie.

Adam Wójcik
"""),
    frazy_do_anonimizacji=["Adam Wójcik", "ul. Kasztanowa 21/7, 85-605 Bydgoszcz", "669 200 300",
                           "adam.wojcik@example.com"],
    symbol=None,
    niepoprawne=["BKS", "WOA"],
    powod_braku_wydzialu="Wniosek nie określa sprawy, jej przedmiotu ani komórki, która ją prowadziła – nie da się "
                         "ustalić, kto posiada informacje. Jeżeli chodzi o akta własnej sprawy administracyjnej, "
                         "dostęp następuje w trybie art. 73 KPA, a nie UDIP (art. 1 ust. 2 UDIP).",
    data_pisma=date(2026, 11, 17),
    werdykt="MOZNA_WARUNKOWO",
    wzor=None,
    tytul=["WEZWANIE DO DOPRECYZOWANIA", "ZAKRESU OTRZYMANEGO WNIOSKU"],
    akapity=[
        "w związku z wystosowanym przez Pana wnioskiem z dnia 13 listopada 2026 r. o przesłanie wszystkich dokumentów "
        "w Pana sprawie z ubiegłego roku, uprzejmie informuję, że treść wniosku nie pozwala ustalić, jakiej sprawy "
        "i jakich informacji on dotyczy, a w konsekwencji – która komórka Urzędu Miasta Bydgoszczy posiada "
        "wnioskowane informacje.",
        "W związku z powyższym wnoszę o doprecyzowanie wniosku poprzez wskazanie przedmiotu sprawy (czego dotyczyła), "
        "jej znaku lub numeru (jeżeli jest znany), przybliżonej daty jej wszczęcia lub zgłoszenia oraz komórki "
        "Urzędu Miasta Bydgoszczy, do której sprawa była kierowana, a także rodzaju dokumentów lub informacji, "
        "których udostępnienia Pan oczekuje.",
        "Jednocześnie informuję, że jeżeli wniosek dotyczy akt sprawy administracyjnej, w której jest Pan stroną, "
        "dostęp do nich odbywa się na zasadach art. 73 ustawy z dnia 14 czerwca 1960 r. – Kodeks postępowania "
        "administracyjnego, a nie w trybie ustawy o dostępie do informacji publicznej (art. 1 ust. 2 tej ustawy).",
        "Proszę o przesłanie doprecyzowania w terminie 7 dni od otrzymania niniejszego pisma. Po upływie tego terminu "
        "wniosek zostanie pozostawiony bez rozpoznania, o czym Wnioskodawca zostanie powiadomiony odrębnym pismem.",
    ],
    kryteria=[
        "Brak wydziału – wniosek NIE jest przekazywany do żadnej komórki merytorycznej.",
        "Pismo zatytułowane „WEZWANIE DO DOPRECYZOWANIA ZAKRESU OTRZYMANEGO WNIOSKU”, termin 7 dni, rygor pozostawienia "
        "bez rozpoznania.",
        "Pouczenie o art. 73 KPA / art. 1 ust. 2 UDIP (akta własnej sprawy).",
        "Pismo nie odpowiada na zarzut „urząd nic nie zrobił” (to nie informacja publiczna, tylko ewentualna skarga).",
    ],
))

# TC09 ---------------------------------------------------------------- brak wydziału: nie informacja publiczna
PRZYPADKI.append(Przypadek(
    folder="TC09 - BRAK WYDZIALU - porada prawna i dane sasiada (nie jest informacja publiczna)",
    numer="BKS.IV.1431.709.2026",
    data_wplywu=date(2026, 11, 16),
    temat="Spór sąsiedzki – prośba o poradę i dane sąsiada",
    opis="Wniosek nie dotyczy informacji publicznej (porada prawna w sprawie prywatnej + dane osobowe osoby "
         "prywatnej). Nie pasuje do żadnego wydziału – pismo informacyjne do wnioskodawcy, bez decyzji odmownej.",
    wnioskodawca="Halina Kaczmarek",
    forma="pani",
    adresat=["Pani", "Halina Kaczmarek", "ul. Słowicza 6", "85-436 Bydgoszcz"],
    wniosek=linie("""
Halina Kaczmarek
ul. Słowicza 6
85-436 Bydgoszcz
tel. 501 777 888

Wniosek o informację publiczną

Mój sąsiad, pan Zbigniew Krawczyk zam. ul. Słowicza 8 w Bydgoszczy, postawił w zeszłym miesiącu ogrodzenie, które według mnie wchodzi ok. 20 cm na moją działkę.
Proszę o informację, czy mogę sama rozebrać ten płot i jakie mam prawa w tej sytuacji, a także o podanie numeru PESEL i numeru telefonu pana Krawczyka, abym mogła złożyć pozew do sądu.

Halina Kaczmarek
"""),
    frazy_do_anonimizacji=["Halina Kaczmarek", "ul. Słowicza 6", "85-436 Bydgoszcz", "501 777 888",
                           "Zbigniew Krawczyk", "ul. Słowicza 8", "Krawczyka"],
    symbol=None,
    niepoprawne=["WAB", "WMG", "WSO"],
    powod_braku_wydzialu="Ocena prawna sytuacji w sporze sąsiedzkim (porada prawna) i dane osobowe osoby prywatnej "
                         "(PESEL, telefon) nie są informacją publiczną w rozumieniu art. 1 ust. 1 i art. 6 UDIP – "
                         "nie dotyczą działalności władz publicznych. Wniosku nie przekazuje się do wydziału.",
    data_pisma=date(2026, 11, 18),
    werdykt="NIE_MOZNA_PISMO_INFORMACYJNE",
    wzor=None,
    akapity=[
        "w odpowiedzi na wystosowany przez Panią wniosek z dnia 16 listopada 2026 r., dotyczący ogrodzenia "
        "postawionego przez sąsiada na granicy Pani nieruchomości, uprzejmie informuję, że wniosek nie dotyczy "
        "informacji publicznej w rozumieniu art. 1 ust. 1 i art. 6 ustawy z dnia 6 września 2001 r. o dostępie "
        "do informacji publicznej (t.j. Dz. U. z 2022 r. poz. 902, z 2025 r. poz. 1844). Informacją publiczną jest "
        "informacja o sprawach publicznych, w szczególności o działalności władz publicznych i podmiotów "
        "wykonujących zadania publiczne.",
        "Ocena uprawnień w sporze między właścicielami sąsiednich nieruchomości stanowi poradę prawną w sprawie "
        "prywatnej, a numer PESEL i numer telefonu osoby fizycznej są jej danymi osobowymi, które nie dotyczą "
        "działalności władz publicznych. W związku z tym wniosek nie może zostać rozpatrzony w trybie ustawy "
        "o dostępie do informacji publicznej, a Urząd Miasta Bydgoszczy nie udostępnia w tym trybie żądanych danych.",
        "Jednocześnie informuję, że bezpłatnej porady prawnej udzielają punkty nieodpłatnej pomocy prawnej "
        "działające na podstawie ustawy z dnia 5 sierpnia 2015 r. o nieodpłatnej pomocy prawnej, nieodpłatnym "
        "poradnictwie obywatelskim oraz edukacji prawnej, a ustalenie przebiegu granicy nieruchomości oraz "
        "roszczenia z tym związane mogą być przedmiotem postępowania przed sądem powszechnym.",
    ],
    kryteria=[
        "Brak wydziału – wniosek NIE jest przekazywany do żadnej komórki (ani do WAB/WMG).",
        "Pismo informacyjne (NIE decyzja odmowna): wniosek nie dotyczy informacji publicznej (art. 1 ust. 1, art. 6 UDIP).",
        "Pismo nie zawiera danych sąsiada (Zbigniew Krawczyk, ul. Słowicza 8) ani żadnego numeru PESEL / telefonu.",
        "Anonimizacja wykrywa w treści wniosku dane osoby trzeciej, nie tylko wnioskodawczyni – także odmienione "
        "nazwisko „Krawczyka” (obecnie niewykrywane).",
    ],
))


# ------------------------------------------------------------------ zapis plików
def pismo_koncowe(p: Przypadek):
    nazwa_kom = jednostka_po_nazwie(p.symbol)["nazwa"] if p.symbol else ""
    dane = DanePisma(pola=p.pola, forma=p.forma, adresat=p.adresat, zalaczniki=p.zalaczniki,
                     komorka_merytoryczna=nazwa_kom, znak_sprawy=p.numer, data=p.data_pisma,
                     data_wniosku=p.data_wplywu.isoformat(), wnioskodawca=p.wnioskodawca)
    if p.wzor:
        wzor = next(w for w in WZORY["wzory"] if w["id"] == p.wzor)
        pismo, braki = zloz_pismo(wzor, WZORY, dane)
        assert not braki, f"{p.folder}: brakujące pola {braki}"
    else:
        pismo = zloz_pismo_z_tekstu(p.akapity, WZORY, dane, tytul=p.tytul or None)
    return pismo


def zapisz(p: Przypadek) -> dict:
    kat = KATALOG / p.folder
    if kat.exists():
        shutil.rmtree(kat)
    kat.mkdir(parents=True)

    # 1. wniosek
    zapisz_docx(kat / "1_wniosek.docx", p.wniosek)
    tresc_wniosku = tekst_docx(kat / "1_wniosek.docx")  # dokładnie tak, jak odczyta go aplikacja

    # 2. oczekiwany wydział
    jednostka = jednostka_po_nazwie(p.symbol) if p.symbol else None
    if p.symbol:
        assert jednostka, f"nieznana jednostka {p.symbol}"
    wydzial = {
        "numer_wniosku": p.numer,
        "oczekiwany_wydzial": {"symbol": jednostka["symbol"], "nazwa": jednostka["nazwa"]} if jednostka else None,
        "dopuszczalne_alternatywy": [
            {"symbol": a, "nazwa": jednostka_po_nazwie(a)["nazwa"]} for a in p.alternatywy
        ],
        "niepoprawne_wybory": [{"symbol": n, "nazwa": jednostka_po_nazwie(n)["nazwa"]} for n in p.niepoprawne],
        "podmiot_poza_umb": p.podmiot_poza_umb,
        "przekazac_do_wydzialu": bool(jednostka),
        "uzasadnienie": p.uzasadnienie or p.powod_braku_wydzialu,
    }
    (kat / "2_oczekiwany_wydzial.json").write_text(json.dumps(wydzial, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8")

    # 3. wiadomość do wydziału (backend: zloz_wiadomosc; frontend: Temat + treść + „--- Treść wniosku ---”)
    termin = None
    if jednostka:
        w = zloz_wiadomosc(jednostka["nazwa"], p.numer, p.data_wplywu.isoformat())
        termin = w.termin
        pelna = "\n\n".join([f"Temat: {w.temat}", w.tresc, f"--- Treść wniosku ---\n{tresc_wniosku}"])
        (kat / "3_oczekiwana_wiadomosc_do_wydzialu.txt").write_text(pelna + "\n", encoding="utf-8")
        for fraza in p.frazy_do_anonimizacji:
            assert fraza in pelna, f"{p.folder}: fraza „{fraza}” nie występuje w wiadomości"
        (kat / "3b_oczekiwana_wiadomosc_do_wydzialu_zanonimizowana.txt").write_text(
            zastosuj(pelna, p.frazy_do_anonimizacji) + "\n", encoding="utf-8")
    else:
        (kat / "3_oczekiwana_wiadomosc_do_wydzialu.txt").write_text(
            "BRAK – wniosku nie przekazuje się do żadnego wydziału Urzędu Miasta Bydgoszczy.\n\n"
            f"Powód: {p.powod_braku_wydzialu}\n"
            + (f"\nPodmiot posiadający informacje (poza UMB): {p.podmiot_poza_umb}\n" if p.podmiot_poza_umb else "")
            + "\nOczekiwane zachowanie aplikacji: karta „Zapytanie do wydziału” nie powinna proponować wysłania prośby "
              "do komórki, której zakres tylko słownie pasuje do wniosku; urzędnik przechodzi od razu do pisma "
              "do wnioskodawcy (plik 5).\n",
            encoding="utf-8")

    # 4. odpowiedź wydziału
    if p.odpowiedz_wydzialu:
        zapisz_docx(kat / "4_odpowiedz_wydzialu.docx", p.odpowiedz_wydzialu)

    # 5. pismo końcowe
    pismo = pismo_koncowe(p)
    # Znana usterka zloz_tresc: kropka skrótu „r.” przed przecinkiem wzoru jest usuwana („2026 r,”).
    # Oczekiwany wynik ma poprawną interpunkcję – test ma tę usterkę wykrywać.
    for b in pismo.tresc:
        b.tekst = b.tekst.replace(" r, ", " r., ")
    tekst = pismo.tekst
    (kat / "5_oczekiwana_odpowiedz_do_wnioskodawcy.txt").write_text(tekst + "\n", encoding="utf-8")
    (kat / "5_oczekiwana_odpowiedz_do_wnioskodawcy.docx").write_bytes(pismo_do_docx(pismo.jako_slownik()))
    for zakazana in p.frazy_w_odpowiedzi_wydzialu:
        assert zakazana not in tekst, f"{p.folder}: dane osoby trzeciej w piśmie końcowym: {zakazana}"
    if not p.symbol:
        for fraza in p.frazy_do_anonimizacji:
            if fraza not in p.adresat and fraza not in " ".join(p.adresat):
                assert fraza not in "\n".join(b.tekst for b in pismo.tresc), f"{p.folder}: {fraza} w treści pisma"

    manifest = {
        "id": p.folder.split(" ")[0],
        "folder": p.folder,
        "opis": p.opis,
        "numer": p.numer,
        "data_wplywu": p.data_wplywu.isoformat(),
        "temat": p.temat,
        "wnioskodawca": p.wnioskodawca,
        "forma_zwrotu": p.forma,
        "frazy_do_anonimizacji_we_wniosku": p.frazy_do_anonimizacji,
        "frazy_do_anonimizacji_w_odpowiedzi_wydzialu": p.frazy_w_odpowiedzi_wydzialu,
        "wydzial": wydzial["oczekiwany_wydzial"]["symbol"] if jednostka else None,
        "podmiot_poza_umb": p.podmiot_poza_umb,
        "termin_dla_wydzialu": termin,
        "data_odpowiedzi_wydzialu": p.data_odpowiedzi_wydzialu.isoformat() if p.data_odpowiedzi_wydzialu else None,
        "data_pisma_koncowego": p.data_pisma.isoformat(),
        "werdykt": p.werdykt,
        "wzor_pisma": p.wzor or ("pismo z akapitów (zloz_pismo_z_tekstu)"),
        "pola_wzoru": p.pola,
        "zalaczniki": p.zalaczniki,
        "kryteria_oceny": p.kryteria,
    }
    (kat / "testcase.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # README przypadku
    pliki = ["1_wniosek.docx", "2_oczekiwany_wydzial.json", "3_oczekiwana_wiadomosc_do_wydzialu.txt"]
    if jednostka:
        pliki += ["3b_oczekiwana_wiadomosc_do_wydzialu_zanonimizowana.txt", "4_odpowiedz_wydzialu.docx"]
    pliki += ["5_oczekiwana_odpowiedz_do_wnioskodawcy.txt", "5_oczekiwana_odpowiedz_do_wnioskodawcy.docx",
              "testcase.json"]
    wyd = (f"**{jednostka['nazwa']} ({jednostka['symbol']})**" if jednostka
           else "**brak** – " + (f"dysponent poza UMB: {p.podmiot_poza_umb}" if p.podmiot_poza_umb
                                 else "wniosek odsyłany do wnioskodawcy"))
    readme = [
        f"# {p.folder}",
        "",
        p.opis,
        "",
        f"- Numer sprawy: `{p.numer}`, wpływ: {p.data_wplywu.isoformat()}",
        f"- Wnioskodawca: {p.wnioskodawca} (zwrot: {p.forma})",
        f"- Oczekiwany wydział: {wyd}",
        *( [f"- Dopuszczalne alternatywy: {', '.join(p.alternatywy)}"] if p.alternatywy else []),
        *( [f"- Niepoprawne wybory: {', '.join(p.niepoprawne)}"] if p.niepoprawne else []),
        *( [f"- Termin dla wydziału (z aplikacji: wpływ + 7 dni): {termin}"] if termin else []),
        f"- Werdykt: `{p.werdykt}`, wzór pisma: `{p.wzor or 'pismo z akapitów'}`",
        "",
        "## Pliki",
        "",
        *(f"- `{n}`" for n in pliki),
        "",
        "## Kryteria oceny",
        "",
        *(f"- {k}" for k in p.kryteria),
        "",
    ]
    (kat / "README.md").write_text("\n".join(readme), encoding="utf-8")
    return manifest


def main() -> None:
    manifesty = [zapisz(p) for p in PRZYPADKI]
    wiersze = [
        "# Przypadki testowe – obsługa wniosku od wpływu do odpowiedzi",
        "",
        "Każdy folder to jedna sprawa: wniosek (dane NIEzanonimizowane, fikcyjne) → oczekiwany wydział → "
        "oczekiwana prośba do wydziału → odpowiedź wydziału (DOCX) → oczekiwane pismo do wnioskodawcy.",
        "",
        "Pliki `3_…` i `5_…` są składane funkcjami aplikacji (`wydzialy.zloz_wiadomosc`, `wzor.pismo.zloz_pismo`), "
        "więc szablon (nagłówek, przepisy, podpis, stopka) musi zgadzać się 1:1. Wartości pól wzoru są wzorcem – "
        "model może je sformułować inaczej, ale fakty (liczby, daty, numery, jednostka) muszą być te same.",
        "",
        "Wszystkie osoby, adresy, telefony, e-maile, firmy i liczby są zmyślone. Regeneracja: "
        "`uv run python \"Przypadki testowe/_generator.py\"`.",
        "",
        "| ID | Sprawa | Wydział | Wzór pisma | Werdykt |",
        "|---|---|---|---|---|",
    ]
    for m in manifesty:
        wyd = m["wydzial"] or ("— (" + m["podmiot_poza_umb"] + ")" if m["podmiot_poza_umb"] else "— (odesłanie)")
        wiersze.append(f"| {m['id']} | {m['temat']} | {wyd} | {m['wzor_pisma']} | {m['werdykt']} |")
    (KATALOG / "README.md").write_text("\n".join(wiersze) + "\n", encoding="utf-8")
    print(f"Zapisano {len(manifesty)} przypadków w {KATALOG}")


if __name__ == "__main__":
    main()
