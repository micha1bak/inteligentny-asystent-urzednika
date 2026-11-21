"""Deterministyczne wyszukiwanie przepisów (artykułów, ustępów, paragrafów) w folderze „Dokumenty i podstawy prawne”.

Moduł działa całkowicie lokalnie i bez użycia żadnego modelu AI/LLM:
- czyta pliki .txt, .pdf (pdfplumber) i .docx (zipfile + XML) z katalogu dokumentów,
- dzieli ustawy i zarządzenia na artykuły / paragrafy / ustępy z zachowaniem numeru strony (dla PDF),
- parsuje odwołania prawne wyrażeniami regularnymi (np. „Art. 13 ust. 2 UDIP”, „Art. 64 § 2 KPA”,
  „§ 11 ust. 8-9 Zarządzenia Nr 535/2024”),
- wspiera też wyszukiwanie pełnotekstowe (dokładne dopasowanie + TF-IDF z `podobienstwo.py`).
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

import pdfplumber
from pydantic import BaseModel

from .podobienstwo import najpodobniejsze

OBSLUGIWANE_ROZSZERZENIA = {".txt", ".pdf", ".docx"}

# Nazwy skrócone używane przy formatowaniu etykiet odwołań.
ETYKIETA_AKTU: dict[str, str] = {
    "UDIP": "UDIP",
    "KPA": "KPA",
    "ZARZADZENIE_535_2024": "Zarządzenia Nr 535/2024",
}

NAZWA_AKTU: dict[str, str] = {
    "UDIP": "Ustawa o dostępie do informacji publicznej (UDIP)",
    "KPA": "Kodeks postępowania administracyjnego (KPA)",
    "ZARZADZENIE_535_2024": "Zarządzenie Nr 535/2024 Prezydenta Miasta Bydgoszczy",
}


class FragmentPrzepisu(BaseModel):
    etykieta: str
    akt: str
    plik: str
    strona: int | None = None
    tresc: str
    pelny_artykul: str | None = None
    dopasowanie: Literal["dokladne", "artykul", "tekstowe"]


class DokumentPrawnyInfo(BaseModel):
    plik: str
    akt: str
    nazwa: str
    liczba_jednostek: int


class WynikWyszukiwaniaPrzepisow(BaseModel):
    zapytanie: str
    wyniki: list[FragmentPrzepisu]
    dostepne_pliki: list[str]


@dataclass(frozen=True)
class Podjednostka:
    rodzaj: Literal["ust", "par"]
    numer: str
    tresc: str
    strona: int | None


@dataclass(frozen=True)
class Jednostka:
    akt: str
    plik: str
    rodzaj: Literal["art", "par", "akapit"]
    numer: str
    etykieta: str
    tresc: str
    strona: int | None
    podjednostki: dict[tuple[str, str], Podjednostka] = field(default_factory=dict)


@dataclass(frozen=True)
class DokumentPrawny:
    plik: str
    akt: str
    nazwa: str
    jednostki: list[Jednostka]
    wg_klucza: dict[tuple[str, str], Jednostka]


@dataclass(frozen=True)
class Odwolanie:
    akt: str | None
    rodzaj: Literal["art", "par"]
    numer: str
    podrodzaj: Literal["ust", "par"] | None = None
    podnumery: tuple[str, ...] = ()
    punkty: tuple[str, ...] = ()
    litery: tuple[str, ...] = ()


@dataclass(frozen=True)
class IndeksPrzepisow:
    katalog: Path
    dokumenty: list[DokumentPrawny]

    @property
    def nazwy_plikow(self) -> list[str]:
        return [d.plik for d in self.dokumenty]

    def informacje_o_dokumentach(self) -> list[DokumentPrawnyInfo]:
        return [
            DokumentPrawnyInfo(
                plik=d.plik,
                akt=d.akt,
                nazwa=d.nazwa,
                liczba_jednostek=len(d.jednostki),
            )
            for d in self.dokumenty
        ]


# ------------------------------------------------------------------ odczyt plików

def _odczytaj_docx(sciezka: Path) -> tuple[str, list[tuple[int, int, int]]]:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(sciezka) as zf:
        root = ElementTree.fromstring(zf.read("word/document.xml"))
    akapity = [
        "".join(t.text or "" for t in p.findall(".//w:t", ns)).strip()
        for p in root.findall(".//w:p", ns)
    ]
    tekst = "\n".join(a for a in akapity if a)
    return tekst, []


def _odczytaj_pdf(sciezka: Path) -> tuple[str, list[tuple[int, int, int]]]:
    czesci: list[str] = []
    strony: list[tuple[int, int, int]] = []
    pozycja = 0
    with pdfplumber.open(sciezka) as pdf:
        for nr, strona in enumerate(pdf.pages, 1):
            t = (strona.extract_text() or "").strip()
            if not t:
                continue
            if czesci:
                pozycja += 1  # znak nowej linii między stronami
            start = pozycja
            czesci.append(t)
            pozycja += len(t)
            strony.append((start, pozycja, nr))
    return "\n".join(czesci), strony


def _odczytaj_plik(sciezka: Path) -> tuple[str, list[tuple[int, int, int]]]:
    ext = sciezka.suffix.lower()
    if ext == ".txt":
        return sciezka.read_text(encoding="utf-8", errors="replace"), []
    if ext == ".pdf":
        return _odczytaj_pdf(sciezka)
    if ext == ".docx":
        return _odczytaj_docx(sciezka)
    return "", []


def _strona_dla_pozycji(pozycja: int, strony: list[tuple[int, int, int]]) -> int | None:
    for start, koniec, nr in strony:
        if start <= pozycja <= koniec:
            return nr
    return strony[-1][2] if strony else None


# ------------------------------------------------------------------ klasyfikacja i podział na jednostki

_RE_ART_NAGLOWEK = re.compile(r"(?m)^[ \t]*Art\.\s*(\d+[a-z]?)\.[ \t]*")
_RE_PAR_GLOWNY = re.compile(
    r"(?m)^[ \t]*(?:(?P<znak>[§$])\s*(?P<nr>\d+[a-z]?)\.|(?P<ocr89>8)(?P<nr89>9)\.(?=\s*1\.))[ \t]*"
)
_RE_DZIAL_ROZDZIAL = re.compile(r"(?m)^[ \t]*(?:DZIAŁ|Rozdział|Oddział)\b")
_RE_UZASADNIENIE = re.compile(r"(?m)^[ \t]*UZASADNIENIE\b")
_RE_PAR_WEW = re.compile(r"(?:(?<=^)|(?<=\n))[ \t]*§\s*(\d+[a-z]?)\.[ \t]*")
_RE_UST_WEW = re.compile(r"(?:(?<=^)|(?<=\n))[ \t]*(\d+[a-z]?)\.[ \t]+")


def _identyfikuj_akt(nazwa_pliku: str, tekst: str) -> tuple[str, str]:
    stem = Path(nazwa_pliku).stem
    stem_low = stem.lower()
    naglowek = tekst[:800].lower()
    ma_artykuly = bool(_RE_ART_NAGLOWEK.search(tekst))
    ma_paragrafy = bool(_RE_PAR_GLOWNY.search(tekst))

    if "zarządzenie" in stem_low or "zarzadzenie" in stem_low or "535" in stem_low:
        return "ZARZADZENIE_535_2024", NAZWA_AKTU["ZARZADZENIE_535_2024"]
    if ma_paragrafy and not ma_artykuly and re.search(r"zarz[aą]dzenie\s+nr\s+53[56]", naglowek):
        return "ZARZADZENIE_535_2024", NAZWA_AKTU["ZARZADZENIE_535_2024"]

    if ma_artykuly:
        if "udip" in stem_low or "o dostępie do informacji publicznej" in naglowek:
            return "UDIP", NAZWA_AKTU["UDIP"]
        if "kpa" in stem_low or "kodeks postępowania administracyjnego" in naglowek:
            return "KPA", NAZWA_AKTU["KPA"]

    kod = re.sub(r"[^A-Z0-9]+", "_", stem.upper()).strip("_") or "DOKUMENT"
    return kod, stem


def _utnij_naglowek_nastepnego_rozdzialu(tekst: str) -> str:
    """Usuwa z końca artykułu/paragrafu nagłówek kolejnego Rozdziału/Działu albo sekcję UZASADNIENIE."""
    m_uzas = _RE_UZASADNIENIE.search(tekst)
    if m_uzas:
        tekst = tekst[: m_uzas.start()]

    # Szukamy nagłówka Rozdział/DZIAŁ/Oddział blisko końca fragmentu (nie na początku)
    for m in _RE_DZIAL_ROZDZIAL.finditer(tekst):
        if m.start() > 0:
            ogon = tekst[m.start() :].strip()
            linie_ogona = [l for l in ogon.splitlines() if l.strip()]
            if len(linie_ogona) <= 6:
                tekst = tekst[: m.start()]
                break
    return tekst.strip()


def _oczysc_ocr_paragrafu(tekst: str) -> str:
    """Poprawia znane artefakty OCR znaku paragrafu na początku linii ($ -> §, 89.1. -> § 9. 1.)."""
    tekst = re.sub(r"(?m)^[ \t]*\$\s*(\d+[a-z]?)\.", r"§ \1.", tekst)
    tekst = re.sub(r"(?m)^[ \t]*89\.1\.", "§ 9. 1.", tekst)
    return tekst.strip()


def _podziel_podjednostki(
    cialo_po_naglowku: str,
    offset_ciala: int,
    strony: list[tuple[int, int, int]],
) -> dict[tuple[str, str], Podjednostka]:
    """Dzieli treść artykułu lub paragrafu na podjednostki (§ w KPA lub ust. w UDIP/Zarządzeniu)."""
    wynik: dict[tuple[str, str], Podjednostka] = {}
    if not cialo_po_naglowku.strip():
        return wynik

    # 1. Paragrafy wewnątrz artykułu (np. KPA: Art. 57. § 1. ... \n§ 2. ...)
    dopasowania_par = list(_RE_PAR_WEW.finditer(cialo_po_naglowku))
    if dopasowania_par and dopasowania_par[0].start() <= 3:
        for i, m in enumerate(dopasowania_par):
            nr = m.group(1).lower()
            koniec = dopasowania_par[i + 1].start() if i + 1 < len(dopasowania_par) else len(cialo_po_naglowku)
            fragment = cialo_po_naglowku[m.start() : koniec].strip()
            wynik[("par", nr)] = Podjednostka(
                rodzaj="par",
                numer=nr,
                tresc=fragment,
                strona=_strona_dla_pozycji(offset_ciala + m.start(), strony),
            )
        return wynik

    # 2. Ustępy numerowane (np. UDIP / Zarządzenie: 1. ... \n2. ... \n2a. ...)
    dopasowania_ust = list(_RE_UST_WEW.finditer(cialo_po_naglowku))
    if dopasowania_ust and dopasowania_ust[0].start() <= 3 and dopasowania_ust[0].group(1) == "1":
        # Filtrujemy przypadkowe numery w przypisach (np. lata czy duże liczby poza ciągiem ustępów)
        prawidlowe: list[re.Match[str]] = []
        ostatnia_liczba = 0
        for m in dopasowania_ust:
            nr = m.group(1).lower()
            liczba = int(re.match(r"\d+", nr).group(0))  # type: ignore[union-attr]
            if not prawidlowe:
                prawidlowe.append(m)
                ostatnia_liczba = liczba
            elif ostatnia_liczba <= liczba <= ostatnia_liczba + 2:
                prawidlowe.append(m)
                ostatnia_liczba = liczba
        for i, m in enumerate(prawidlowe):
            nr = m.group(1).lower()
            koniec = prawidlowe[i + 1].start() if i + 1 < len(prawidlowe) else len(cialo_po_naglowku)
            fragment = cialo_po_naglowku[m.start() : koniec].strip()
            wynik[("ust", nr)] = Podjednostka(
                rodzaj="ust",
                numer=nr,
                tresc=fragment,
                strona=_strona_dla_pozycji(offset_ciala + m.start(), strony),
            )
    return wynik


def _indeksuj_dokument(sciezka: Path) -> DokumentPrawny | None:
    tekst, strony = _odczytaj_plik(sciezka)
    if not tekst.strip():
        return None

    akt, nazwa = _identyfikuj_akt(sciezka.name, tekst)
    etykieta_aktu = ETYKIETA_AKTU.get(akt, sciezka.stem)
    jednostki: list[Jednostka] = []
    wg_klucza: dict[tuple[str, str], Jednostka] = {}

    dopasowania_art = list(_RE_ART_NAGLOWEK.finditer(tekst))
    if dopasowania_art:
        for i, m in enumerate(dopasowania_art):
            nr = m.group(1).lower()
            koniec = dopasowania_art[i + 1].start() if i + 1 < len(dopasowania_art) else len(tekst)
            surowy = _utnij_naglowek_nastepnego_rozdzialu(tekst[m.start() : koniec])
            cialo = surowy[m.end() - m.start() :]
            pod = _podziel_podjednostki(cialo, m.end(), strony)
            j = Jednostka(
                akt=akt,
                plik=sciezka.name,
                rodzaj="art",
                numer=nr,
                etykieta=f"Art. {nr} {etykieta_aktu}",
                tresc=surowy,
                strona=_strona_dla_pozycji(m.start(), strony),
                podjednostki=pod,
            )
            jednostki.append(j)
            wg_klucza[("art", nr)] = j
        return DokumentPrawny(sciezka.name, akt, nazwa, jednostki, wg_klucza)

    dopasowania_par = list(_RE_PAR_GLOWNY.finditer(tekst))
    if dopasowania_par:
        for i, m in enumerate(dopasowania_par):
            nr = (m.group("nr") or m.group("nr89") or "").lower()
            koniec = dopasowania_par[i + 1].start() if i + 1 < len(dopasowania_par) else len(tekst)
            surowy_nieocz = _utnij_naglowek_nastepnego_rozdzialu(tekst[m.start() : koniec])
            # Dla ostatniego paragrafu usuwamy ewentualne śmieci OCR po podpisie (krótkie losowe linie)
            if i == len(dopasowania_par) - 1:
                linie = surowy_nieocz.splitlines()
                dobre: list[str] = []
                for linia in linie:
                    if re.fullmatch(r"[\W\d_a-zA-Z]{1,12}", linia.strip()) and not re.search(
                        r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]|dnia|życie|podpisania|roku", linia
                    ):
                        if dobre:
                            break
                    dobre.append(linia)
                surowy_nieocz = "\n".join(dobre).strip()

            surowy = _oczysc_ocr_paragrafu(surowy_nieocz)
            # Ciało po "§ N. "
            m_nagl = re.match(r"^§\s*\d+[a-z]?\.\s*", surowy)
            dl_nagl = m_nagl.end() if m_nagl else 0
            cialo = surowy[dl_nagl:]
            pod = _podziel_podjednostki(cialo, m.start() + dl_nagl, strony)
            j = Jednostka(
                akt=akt,
                plik=sciezka.name,
                rodzaj="par",
                numer=nr,
                etykieta=f"§ {nr} {etykieta_aktu}",
                tresc=surowy,
                strona=_strona_dla_pozycji(m.start(), strony),
                podjednostki=pod,
            )
            jednostki.append(j)
            wg_klucza[("par", nr)] = j
        return DokumentPrawny(sciezka.name, akt, nazwa, jednostki, wg_klucza)

    # Dokument bez struktury Art./§ (np. katalog anonimizacji, instrukcje, linki)
    akapity = [a.strip() for a in re.split(r"\n\s*\n", tekst) if a.strip()]
    for idx, akapit in enumerate(akapity, 1):
        j = Jednostka(
            akt=akt,
            plik=sciezka.name,
            rodzaj="akapit",
            numer=str(idx),
            etykieta=f"{sciezka.stem} (poz. {idx})",
            tresc=akapit,
            strona=_strona_dla_pozycji(0, strony),
        )
        jednostki.append(j)
    return DokumentPrawny(sciezka.name, akt, nazwa, jednostki, wg_klucza)


# Cache indeksu kluczowany ścieżką katalogu i stanem plików (mtime + rozmiar)
_CACHE_INDEKSU: dict[Path, tuple[tuple[tuple[str, int, int], ...], IndeksPrzepisow]] = {}


def _sygnatura_katalogu(katalog: Path) -> tuple[tuple[str, int, int], ...]:
    if not katalog.is_dir():
        return ()
    wpisy = []
    for p in sorted(katalog.iterdir()):
        if p.is_file() and p.suffix.lower() in OBSLUGIWANE_ROZSZERZENIA:
            st = p.stat()
            wpisy.append((p.name, st.st_mtime_ns, st.st_size))
    return tuple(wpisy)


def wczytaj_indeks_przepisow(katalog: Path) -> IndeksPrzepisow:
    katalog = katalog.resolve()
    syg = _sygnatura_katalogu(katalog)
    zapis = _CACHE_INDEKSU.get(katalog)
    if zapis and zapis[0] == syg:
        return zapis[1]

    dokumenty: list[DokumentPrawny] = []
    if katalog.is_dir():
        for nazwa, _, _ in syg:
            dok = _indeksuj_dokument(katalog / nazwa)
            if dok and dok.jednostki:
                dokumenty.append(dok)

    # Stabilna kolejność: najpierw główne akty (UDIP, KPA, Zarządzenie), potem pozostałe pliki
    priorytet = {"UDIP": 0, "KPA": 1, "ZARZADZENIE_535_2024": 2}
    dokumenty.sort(key=lambda d: (priorytet.get(d.akt, 10), d.plik.lower()))

    indeks = IndeksPrzepisow(katalog=katalog, dokumenty=dokumenty)
    _CACHE_INDEKSU[katalog] = (syg, indeks)
    return indeks


# ------------------------------------------------------------------ parser odwołań prawnych

def _wykryj_akt_w_zapytaniu(tekst: str) -> str | None:
    t = tekst.lower()
    if re.search(r"\budip\b|dost[eę]p\w*\s+do\s+informacji\s+publicznej", t):
        return "UDIP"
    if re.search(r"\bkpa\b|\bk\.p\.a\.|kodeks\w*\s+post[eę]powania\s+administracyjnego", t):
        return "KPA"
    if re.search(r"zarz[aą]dzeni\w*|535\s*/\s*2024|535-2024", t):
        return "ZARZADZENIE_535_2024"
    return None


def _rozwin_liste_numerow(fragment: str) -> list[str]:
    """Zamienia np. '1, 2, 2a, 2b, 3 i 4' albo '8-9' na ['1','2','2a','2b','3','4'] / ['8','9']."""
    wyniki: list[str] = []
    # Zakresy liczbowe: 8-9 lub 8–9
    for token in re.split(r"\s*(?:,|(?:\bi\b|\boraz\b))\s*", fragment.strip(), flags=re.I):
        token = token.strip()
        if not token:
            continue
        m_zakres = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", token)
        if m_zakres:
            a, b = int(m_zakres.group(1)), int(m_zakres.group(2))
            if a <= b and b - a <= 15:
                wyniki.extend(str(n) for n in range(a, b + 1))
                continue
        m_nr = re.match(r"(\d+[a-z]?)", token, re.I)
        if m_nr:
            wyniki.append(m_nr.group(1).lower())
    # Deduplikacja z zachowaniem kolejności
    return list(dict.fromkeys(wyniki))


def _rozwin_liste_liter(fragment: str) -> list[str]:
    wyniki: list[str] = []
    for token in re.split(r"\s*(?:,|(?:\bi\b|\boraz\b))\s*", fragment.strip(), flags=re.I):
        token = token.strip()
        m_zakres = re.fullmatch(r"([a-z])\s*[-–]\s*([a-z])", token, re.I)
        if m_zakres:
            a, b = ord(m_zakres.group(1).lower()), ord(m_zakres.group(2).lower())
            if a <= b and b - a <= 12:
                wyniki.extend(chr(c) for c in range(a, b + 1))
                continue
        m_lit = re.match(r"([a-z])\b", token, re.I)
        if m_lit:
            wyniki.append(m_lit.group(1).lower())
    return list(dict.fromkeys(wyniki))


_RE_KOTWICA = re.compile(r"(?i)\b(?:art\.?\s*(\d+[a-z]?))|(?:§\s*(\d+[a-z]?))")
_RE_LISTA_NUMEROW = r"\d+[a-z]?(?:\s*(?:[-–]\s*\d+[a-z]?|(?:,\s*|\s+(?:i|oraz)\s+)(?:(?:ust\.?|§|pkt\.?)\s*)?\d+[a-z]?))*"
_RE_LISTA_LITER = r"[a-z](?:\s*(?:[-–]\s*[a-z]|(?:,\s*|\s+(?:i|oraz)\s+)[a-z]))*"


def _parsuj_segment_artykulu(akt: str | None, rodzaj: Literal["art", "par"], numer: str, ogon: str) -> list[Odwolanie]:
    """Parsuje specyfikatory po numerze artykułu/paragrafu (ust., §, pkt, lit.)."""
    # Usuwamy wzmiankę o akcie z końca ogona, żeby nie myliła parsera (np. '535/2024')
    ogon_czysty = re.split(r"(?i)\b(?:udip|kpa|k\.p\.a\.|zarz[aą]dzeni|ustaw[ay]|kodeks)", ogon, maxsplit=1)[0]
    ogon_czysty = re.sub(r"\([^)]*\)", " ", ogon_czysty)
    ogon_czysty = re.sub(r"(?i)\bzd\.?\s*\d+", " ", ogon_czysty)

    # Specjalny przypadek: „ust. 1 i ust. 2 pkt 2” – rozbijamy na osobne pododwołania po drugim „ust.”
    podczesci_ust = re.split(r"(?i)(?:\bi\b|\boraz\b|,)\s*(?=ust\.?\s*\d)", ogon_czysty)
    if len(podczesci_ust) > 1 and re.search(r"(?i)\bust\.?\s*\d", podczesci_ust[0]):
        wynik: list[Odwolanie] = []
        for czesc in podczesci_ust:
            wynik.extend(_parsuj_segment_artykulu(akt, rodzaj, numer, czesc))
        return wynik

    podrodzaj: Literal["ust", "par"] | None = None
    podnumery: list[str] = []
    punkty: list[str] = []
    litery: list[str] = []

    m_ust = re.search(rf"(?i)\bust\.?\s*({_RE_LISTA_NUMEROW})", ogon_czysty)
    if m_ust:
        podrodzaj = "ust"
        podnumery = _rozwin_liste_numerow(re.sub(r"(?i)\bust\.?\s*", "", m_ust.group(1)))
    elif rodzaj == "art":
        m_par = re.search(rf"(?i)§\s*({_RE_LISTA_NUMEROW})", ogon_czysty)
        if m_par:
            podrodzaj = "par"
            podnumery = _rozwin_liste_numerow(re.sub(r"§\s*", "", m_par.group(1)))

    m_pkt = re.search(rf"(?i)\bpkt\.?\s*({_RE_LISTA_NUMEROW})", ogon_czysty)
    if m_pkt:
        punkty = _rozwin_liste_numerow(re.sub(r"(?i)\bpkt\.?\s*", "", m_pkt.group(1)))

    m_lit = re.search(rf"(?i)\blit\.?\s*({_RE_LISTA_LITER})", ogon_czysty)
    if m_lit:
        litery = _rozwin_liste_liter(m_lit.group(1))

    return [
        Odwolanie(
            akt=akt,
            rodzaj=rodzaj,
            numer=numer.lower(),
            podrodzaj=podrodzaj,
            podnumery=tuple(podnumery),
            punkty=tuple(punkty),
            litery=tuple(litery),
        )
    ]


def parsuj_odwolania(zapytanie: str, domyslny_akt: str | None = None) -> list[Odwolanie]:
    """Wydobywa ustrukturyzowane odwołania z tekstu (np. „Art. 6 ust. 1 pkt 5 UDIP; § 11 ust. 3 Zarządzenia Nr 535/2024”)."""
    wyniki: list[Odwolanie] = []
    # Średnik oddziela różne akty w jednym wpisie (np. „Art. 4 ust. 3 UDIP; § 11 ust. 3 Zarządzenia Nr 535/2024”)
    for klauzula in re.split(r"\s*;\s*", zapytanie.strip()):
        if not klauzula:
            continue
        akt = domyslny_akt or _wykryj_akt_w_zapytaniu(klauzula)
        # Znajdujemy kotwice top-level: każde "art. N" oraz "§ N" które NIE należą do poprzedniego "art."
        wszystkie = list(_RE_KOTWICA.finditer(klauzula))
        kotwice: list[tuple[int, int, Literal["art", "par"], str]] = []
        ma_art = any(m.group(1) is not None for m in wszystkie)
        for m in wszystkie:
            if m.group(1) is not None:
                kotwice.append((m.start(), m.end(), "art", m.group(1)))
            elif m.group(2) is not None and not ma_art:
                kotwice.append((m.start(), m.end(), "par", m.group(2)))

        for i, (_, koniec_nagl, rodzaj, nr) in enumerate(kotwice):
            koniec_seg = kotwice[i + 1][0] if i + 1 < len(kotwice) else len(klauzula)
            ogon = klauzula[koniec_nagl:koniec_seg]
            # Obsługa zakresów artykułów np. "Art. 104-113 KPA" lub "Art. 14 i 15 UDIP"
            m_zakres_art = re.match(r"^\s*[-–]\s*(\d+)\b", ogon)
            if m_zakres_art and nr.isdigit():
                a, b = int(nr), int(m_zakres_art.group(1))
                if a <= b and b - a <= 15:
                    for n in range(a, b + 1):
                        wyniki.append(Odwolanie(akt=akt, rodzaj=rodzaj, numer=str(n)))
                    continue
            wyniki.extend(_parsuj_segment_artykulu(akt, rodzaj, nr, ogon))
    return wyniki


# ------------------------------------------------------------------ zawężanie do pkt / lit. i wyszukiwanie

def _wytnij_punkty_i_litery(tresc: str, punkty: tuple[str, ...], litery: tuple[str, ...]) -> str:
    """Jeśli podano pkt (i opcjonalnie lit.), wycina wprowadzenie do wyliczenia + wskazany punkt/literę."""
    if not punkty:
        return tresc

    re_pkt = re.compile(r"(?m)^[ \t]*(\d+[a-z]?)\)[ \t]+")
    dopasowania = list(re_pkt.finditer(tresc))
    if not dopasowania:
        return tresc

    wprowadzenie = tresc[: dopasowania[0].start()].strip()
    wybrane_pkt: list[str] = []
    for i, m in enumerate(dopasowania):
        nr_pkt = m.group(1).lower()
        if nr_pkt not in punkty:
            continue
        koniec = dopasowania[i + 1].start() if i + 1 < len(dopasowania) else len(tresc)
        tekst_pkt = tresc[m.start() : koniec].strip()
        if litery:
            tekst_pkt = _wytnij_litery(tekst_pkt, litery)
        wybrane_pkt.append(tekst_pkt)

    if not wybrane_pkt:
        return tresc
    return (wprowadzenie + "\n" + "\n".join(wybrane_pkt)).strip() if wprowadzenie else "\n".join(wybrane_pkt)


def _wytnij_litery(tekst_pkt: str, litery: tuple[str, ...]) -> str:
    re_lit = re.compile(r"(?m)^[ \t]*([a-z])\)[ \t]+")
    dopasowania = list(re_lit.finditer(tekst_pkt))
    if not dopasowania:
        return tekst_pkt

    wprowadzenie = tekst_pkt[: dopasowania[0].start()].strip()
    wybrane: list[str] = []
    for i, m in enumerate(dopasowania):
        lit = m.group(1).lower()
        if lit not in litery:
            continue
        koniec = dopasowania[i + 1].start() if i + 1 < len(dopasowania) else len(tekst_pkt)
        wybrane.append(tekst_pkt[m.start() : koniec].strip())
    if not wybrane:
        return tekst_pkt
    return (wprowadzenie + "\n" + "\n".join(wybrane)).strip() if wprowadzenie else "\n".join(wybrane)


def _rozstrzygnij_odwolanie(indeks: IndeksPrzepisow, odw: Odwolanie, filtr_aktu: str | None) -> list[FragmentPrzepisu]:
    docelowy_akt = (filtr_aktu or odw.akt or "").upper() or None
    kandydaci = [
        d for d in indeks.dokumenty
        if (docelowy_akt is None or d.akt.upper() == docelowy_akt)
    ]
    fragmenty: list[FragmentPrzepisu] = []

    for dok in kandydaci:
        jednostka = dok.wg_klucza.get((odw.rodzaj, odw.numer))
        if not jednostka:
            continue
        etykieta_aktu = ETYKIETA_AKTU.get(dok.akt, Path(dok.plik).stem)
        prefiks = f"Art. {jednostka.numer}" if jednostka.rodzaj == "art" else f"§ {jednostka.numer}"

        if odw.podrodzaj and odw.podnumery:
            znaleziono_pod = False
            for podnr in odw.podnumery:
                pod = jednostka.podjednostki.get((odw.podrodzaj, podnr))
                if not pod:
                    continue
                znaleziono_pod = True
                tresc_frag = _wytnij_punkty_i_litery(pod.tresc, odw.punkty, odw.litery)
                opis_pod = f"ust. {podnr}" if odw.podrodzaj == "ust" else f"§ {podnr}"
                opis_pkt = f" pkt {', '.join(odw.punkty)}" if odw.punkty else ""
                opis_lit = f" lit. {', '.join(odw.litery)}" if odw.litery else ""
                fragmenty.append(
                    FragmentPrzepisu(
                        etykieta=f"{prefiks} {opis_pod}{opis_pkt}{opis_lit} {etykieta_aktu}",
                        akt=dok.akt,
                        plik=dok.plik,
                        strona=pod.strona,
                        tresc=tresc_frag,
                        pelny_artykul=jednostka.tresc if tresc_frag != jednostka.tresc else None,
                        dopasowanie="dokladne",
                    )
                )
            if znaleziono_pod:
                continue

        # Brak podnumeru albo artykuł nie dzieli się na ustępy – zwracamy cały artykuł/paragraf (z ewentualnym pkt)
        tresc_frag = _wytnij_punkty_i_litery(jednostka.tresc, odw.punkty, odw.litery)
        opis_pkt = f" pkt {', '.join(odw.punkty)}" if odw.punkty else ""
        opis_lit = f" lit. {', '.join(odw.litery)}" if odw.litery else ""
        fragmenty.append(
            FragmentPrzepisu(
                etykieta=f"{prefiks}{opis_pkt}{opis_lit} {etykieta_aktu}",
                akt=dok.akt,
                plik=dok.plik,
                strona=jednostka.strona,
                tresc=tresc_frag,
                pelny_artykul=jednostka.tresc if tresc_frag != jednostka.tresc else None,
                dopasowanie="dokladne" if not odw.podnumery else "artykul",
            )
        )
    return fragmenty


def _szukaj_tekstowo(indeks: IndeksPrzepisow, zapytanie: str, filtr_aktu: str | None, limit: int) -> list[FragmentPrzepisu]:
    akt_filtr = (filtr_aktu or _wykryj_akt_w_zapytaniu(zapytanie) or "").upper() or None
    dokumenty = [d for d in indeks.dokumenty if akt_filtr is None or d.akt.upper() == akt_filtr]
    if not dokumenty:
        dokumenty = indeks.dokumenty

    # Zbieramy najdrobniejsze przeszukiwalne jednostki (podjednostki jeśli istnieją, w przeciwnym razie całe jednostki)
    elementy: list[tuple[DokumentPrawny, Jednostka, Podjednostka | None]] = []
    teksty: list[str] = []
    for dok in dokumenty:
        for j in dok.jednostki:
            if j.podjednostki:
                for pod in j.podjednostki.values():
                    elementy.append((dok, j, pod))
                    teksty.append(f"{j.etykieta} {pod.tresc}")
            else:
                elementy.append((dok, j, None))
                teksty.append(f"{j.etykieta} {j.tresc}")

    if not elementy:
        return []

    fraza = zapytanie.strip().lower()
    wybrane: list[tuple[DokumentPrawny, Jednostka, Podjednostka | None]] = []
    widziane: set[int] = set()

    # 1. Dokładne wystąpienie frazy (bez uwzględniania wielkości liter)
    if len(fraza) >= 3:
        for idx, t in enumerate(teksty):
            if fraza in t.lower():
                wybrane.append(elementy[idx])
                widziane.add(idx)
                if len(wybrane) >= limit:
                    break

    # 2. Uzupełnienie przez TF-IDF na rdzeniach słów (podobienstwo.py – zero AI)
    if len(wybrane) < limit:
        indeksy = list(range(len(elementy)))
        podobne = najpodobniejsze(zapytanie, indeksy, teksty, limit=limit * 2)
        for idx in podobne:
            if idx not in widziane:
                wybrane.append(elementy[idx])
                widziane.add(idx)
                if len(wybrane) >= limit:
                    break

    wyniki: list[FragmentPrzepisu] = []
    for dok, j, pod in wybrane[:limit]:
        etykieta_aktu = ETYKIETA_AKTU.get(dok.akt, Path(dok.plik).stem)
        if pod is not None:
            prefiks = f"Art. {j.numer}" if j.rodzaj == "art" else f"§ {j.numer}"
            opis_pod = f"ust. {pod.numer}" if pod.rodzaj == "ust" else f"§ {pod.numer}"
            wyniki.append(
                FragmentPrzepisu(
                    etykieta=f"{prefiks} {opis_pod} {etykieta_aktu}",
                    akt=dok.akt,
                    plik=dok.plik,
                    strona=pod.strona,
                    tresc=pod.tresc,
                    pelny_artykul=j.tresc,
                    dopasowanie="tekstowe",
                )
            )
        else:
            wyniki.append(
                FragmentPrzepisu(
                    etykieta=j.etykieta,
                    akt=dok.akt,
                    plik=dok.plik,
                    strona=j.strona,
                    tresc=j.tresc,
                    pelny_artykul=None,
                    dopasowanie="tekstowe",
                )
            )
    return wyniki


def szukaj_przepisow(
    indeks: IndeksPrzepisow,
    zapytanie: str,
    akt: str | None = None,
    limit: int = 8,
) -> WynikWyszukiwaniaPrzepisow:
    """Wyszukuje konkretny przepis (strukturalnie) lub frazę (tekstowo) w lokalnym folderze dokumentów."""
    czyste = zapytanie.strip()
    if not czyste:
        return WynikWyszukiwaniaPrzepisow(zapytanie=zapytanie, wyniki=[], dostepne_pliki=indeks.nazwy_plikow)

    filtr = akt.strip().upper() if akt and akt.strip() else None
    wyniki: list[FragmentPrzepisu] = []
    widziane: set[tuple[str, str]] = set()

    # 1. Ścieżka strukturalna: konkretne odwołania do Art. / § / ust. / pkt / lit.
    for odw in parsuj_odwolania(czyste, domyslny_akt=filtr):
        for frag in _rozstrzygnij_odwolanie(indeks, odw, filtr):
            klucz = (frag.plik, frag.etykieta)
            if klucz not in widziane:
                widziane.add(klucz)
                wyniki.append(frag)

    # 2. Ścieżka pełnotekstowa (gdy brak cytowań lub nic nie dopasowano strukturalnie)
    if not wyniki:
        wyniki = _szukaj_tekstowo(indeks, czyste, filtr, limit=limit)

    return WynikWyszukiwaniaPrzepisow(
        zapytanie=czyste,
        wyniki=wyniki[:limit],
        dostepne_pliki=indeks.nazwy_plikow,
    )
