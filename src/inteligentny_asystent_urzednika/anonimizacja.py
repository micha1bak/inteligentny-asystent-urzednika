"""Wykrywanie i maskowanie danych osobowych o jednoznacznym formacie (e-mail, telefon, PESEL, numer konta).

Imion i nazwisk nie da się pewnie wykryć regułami – zajmuje się nimi model przy propozycji wpisu,
a ostatecznie urzędnik, który zatwierdza wpis.
"""

from __future__ import annotations

import re

ZNACZNIK = "[zanonimizowano]"

# Kolejność ma znaczenie: dłuższe ciągi cyfr (konto, PESEL) przed telefonem.
WZORCE: list[tuple[str, re.Pattern[str]]] = [
    ("adres e-mail", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("numer konta", re.compile(r"(?<![\w/-])(?:PL\s?)?\d{2}(?:[ ]?\d{4}){6}(?!\d|[.,]\d)")),
    ("PESEL", re.compile(r"(?<![\w/-])(?<!\d[.,])\d{11}(?!\d|[.,]\d)")),
    (
        "numer telefonu",
        re.compile(
            r"(?<![\w/+-])(?<!\d[.,])(?:\+48[ -]?)?(?:"
            r"\d{3}[ -]\d{3}[ -]\d{3}"  # 600 100 200
            r"|\d{9}"  # 600100200
            r"|\(\d{2}\)[ ]?\d{2,3}[ -]?\d{2}[ -]?\d{2,3}"  # (52) 58 58 365
            r")(?!\d|[.,]\d)"
        ),
    ),
]


def wykryj(tekst: str) -> list[tuple[str, str]]:
    """Zwraca listę (rodzaj, znaleziony fragment) bez powtórzeń."""
    znalezione: list[tuple[str, str]] = []
    zajete = tekst
    for rodzaj, wzorzec in WZORCE:
        for m in wzorzec.finditer(zajete):
            if (rodzaj, m.group()) not in znalezione:
                znalezione.append((rodzaj, m.group()))
        zajete = wzorzec.sub(lambda m: " " * len(m.group()), zajete)
    return znalezione


def zanonimizuj(tekst: str) -> str:
    for _, wzorzec in WZORCE:
        tekst = wzorzec.sub(ZNACZNIK, tekst)
    return tekst


# ---------------------------------------------------------------- sugestie anonimizacji dla urzędnika
# Szerszy (ale mniej pewny) zestaw reguł niż `WZORCE`: służy do PODPOWIEDZI w piśmie / dokumencie – urzędnik
# każdą sugestię akceptuje (czarny prostokąt) albo odrzuca. Działa w pełni lokalnie, bez modelu AI.

from dataclasses import asdict, dataclass  # noqa: E402

# Najczęstsze polskie imiona (mianownik); odmiany tworzone są niżej.
IMIONA = """Adam Adrian Agata Agnieszka Aleksander Aleksandra Alicja Amelia Andrzej Aneta Angelika Anna Antoni Antonina
Arkadiusz Artur Barbara Bartłomiej Bartosz Beata Bogdan Bogumiła Bogusław Bożena Cezary Czesław Damian Daniel Daniela
Danuta Dariusz Dawid Dominik Dominika Dorota Edward Edyta Elżbieta Emil Emilia Eryk Ewa Ewelina Filip Franciszek
Gabriel Gabriela Grażyna Grzegorz Halina Hanna Helena Henryk Hubert Ignacy Igor Irena Iwona Izabela Jacek Jadwiga Jakub
Jan Janina Janusz Jarosław Jerzy Joanna Jolanta Józef Julia Julian Justyna Kacper Kamil Kamila Karina Karol Karolina
Katarzyna Kazimierz Kinga Klaudia Konrad Kornelia Krystian Krystyna Krzysztof Lech Lena Leszek Lidia Łucja Łukasz
Maciej Magdalena Maja Malwina Małgorzata Marcin Marek Maria Marian Marianna Mariola Mariusz Marta Marzena Mateusz Michał
Michalina Mieczysław Mikołaj Milena Mirosław Monika Natalia Nikola Norbert Oliwia Oskar Patrycja Patryk Paula Paulina
Paweł Piotr Przemysław Rafał Renata Robert Roman Rozalia Ryszard Sabina Sandra Sebastian Stanisław Stefan Sylwia Szymon
Tadeusz Teresa Tomasz Urszula Wanda Weronika Wiesław Wiktor Wiktoria Wioletta Witold Władysław Włodzimierz Wojciech
Zbigniew Zdzisław Zenon Zofia Zuzanna Zygmunt""".split()


def _odmiany(imie: str) -> list[str]:
    if imie.endswith("a"):  # Anna -> Anny, Annie, Annę, Anną
        rdzen = imie[:-1]
        return [imie] + [rdzen + k for k in ("y", "i", "ie", "ę", "ą", "o")]
    # Jan -> Jana, Janowi, Janem, Janie; Paweł -> Pawła (uproszczenie: dopuszczamy oba warianty)
    rdzenie = {imie}
    if len(imie) > 3 and imie[-2] == "e":  # Paweł -> Pawł-, Marek -> Mark-
        rdzenie.add(imie[:-2] + imie[-1])
    return [r + k for r in rdzenie for k in ("", "a", "owi", "em", "ie", "u")]


_DUZA = r"[A-ZĄĆĘŁŃÓŚŹŻ]"
_MALA = r"[a-ząćęłńóśźż]"
_NAZWISKO = rf"{_DUZA}{_MALA}+(?:-{_DUZA}{_MALA}+)?"
_IMIE = "|".join(sorted({o for i in IMIONA for o in _odmiany(i)}, key=len, reverse=True))

WZORCE_SUGESTII: list[tuple[str, re.Pattern[str]]] = [
    *WZORCE,
    ("NIP", re.compile(r"(?<!\d)(?:NIP[:\s]*)?\d{3}-\d{3}-\d{2}-\d{2}(?!\d)|(?<!\d)\d{3}-\d{2}-\d{2}-\d{3}(?!\d)|NIP[:\s]*\d{10}\b")),
    ("numer dowodu osobistego", re.compile(r"\b[A-Z]{3}\s?\d{6}\b")),
    (
        "adres",
        re.compile(
            rf"\b(?:ul\.|al\.|os\.|pl\.|ulica|aleja|osiedle)\s*(?:{_DUZA}[\w.\-]*\s+){{0,3}}?\d+[a-zA-Z]?(?:\s?/\s?\d+[a-zA-Z]?)?"
            r"(?:\s*(?:m\.|lok\.)\s*\d+)?"
        ),
    ),
    ("kod pocztowy i miejscowość", re.compile(rf"(?<!\d)\d{{2}}-\d{{3}}(?!\d)(?:\s+{_DUZA}{_MALA}+(?:[- ]{_DUZA}{_MALA}+)?)?")),
    ("imię i nazwisko", re.compile(rf"\b(?:{_IMIE})\s+{_NAZWISKO}\b")),
    # „Pan Nowak”, „Pani Anna Nowak” – ukrywane samo imię/nazwisko (grupa 1), bez zwrotu grzecznościowego
    ("imię i nazwisko", re.compile(rf"\b(?:Pan|Pani|Pana|Panią|Panu)\s+({_NAZWISKO}(?:\s+{_NAZWISKO})?)\b")),
]

# Dane kontaktowe samego urzędu nie są danymi osobowymi do ukrycia.
JAWNE_URZEDU = (
    "bks@um.bydgoszcz.pl", "bip@um.bydgoszcz.pl", "(52) 58 58 365", "(52) 58 58 623", "ul. Jezuicka 1",
    "85-102 Bydgoszcz",
)


@dataclass(frozen=True)
class Fragment:
    rodzaj: str
    tekst: str
    start: int
    koniec: int

    def jako_slownik(self) -> dict:
        return asdict(self)


def sugestie(tekst: str, dodatkowe: list[str] | None = None) -> list[Fragment]:
    """Fragmenty proponowane do anonimizacji (bez nakładania się), w kolejności występowania.

    `dodatkowe` – frazy wskazane z zewnątrz (np. wnioskodawca, dane wskazane przez model) – wyszukiwane dosłownie.
    """
    kandydaci: list[Fragment] = []
    for fraza in dodatkowe or []:
        fraza = fraza.strip()
        if len(fraza) < 3:
            continue
        for m in re.finditer(re.escape(fraza), tekst):
            kandydaci.append(Fragment("wskazane", m.group(), m.start(), m.end()))
    for rodzaj, wzorzec in WZORCE_SUGESTII:
        for m in wzorzec.finditer(tekst):
            caly, poczatek = (m.group(1), m.start(1)) if m.re.groups else (m.group(), m.start())
            frag = caly.strip(" ,;")
            if not frag or any(frag in j or j in frag for j in JAWNE_URZEDU):
                continue
            start = poczatek + caly.find(frag)
            kandydaci.append(Fragment(rodzaj, frag, start, start + len(frag)))
    # najpierw dłuższe, potem bez nakładania się
    wynik: list[Fragment] = []
    for f in sorted(kandydaci, key=lambda f: (-(f.koniec - f.start), f.start)):
        if all(f.koniec <= w.start or f.start >= w.koniec for w in wynik):
            wynik.append(f)
    return sorted(wynik, key=lambda f: f.start)


def zanonimizuj_szeroko(tekst: str, dodatkowe: list[str] | None = None) -> str:
    """Zastępuje znacznikiem wszystkie sugestie anonimizacji (także imiona i nazwiska, adresy) – np. przed zapisem
    fragmentu wniosku w archiwum, gdzie nikt nie zatwierdza sugestii pojedynczo."""
    for f in reversed(sugestie(tekst, dodatkowe)):
        tekst = tekst[: f.start] + ZNACZNIK + tekst[f.koniec :]
    return tekst


def zastosuj(tekst: str, frazy: list[str], znak: str = "█") -> str:
    """Zastępuje każde wystąpienie zatwierdzonej frazy ciągiem `znak` tej samej długości (czarny prostokąt)."""
    for fraza in sorted({f for f in frazy if f.strip()}, key=len, reverse=True):
        tekst = tekst.replace(fraza, znak * len(fraza))
    return tekst


# ---------------------------------------------------------------- maskowanie przed wysłaniem do modelu AI
# Dane niepotrzebne do oceny wniosku i napisania odpowiedzi nie są wysyłane do modelu (zasada minimalizacji danych).
# Imię, nazwisko i e-mail zostają – model potrzebuje ich do adresata i zwrotu grzecznościowego.
_DO_MASKOWANIA_DLA_AI = ("PESEL", "numer konta", "numer telefonu", "numer dowodu osobistego", "NIP")


def maskuj_dla_ai(tekst: str) -> str:
    wzorce = [(r, w) for r, w in WZORCE_SUGESTII if r in _DO_MASKOWANIA_DLA_AI]
    for rodzaj, wzorzec in wzorce:
        tekst = wzorzec.sub(lambda m, r=rodzaj: m.group() if any(j in m.group() for j in JAWNE_URZEDU) else f"[{r}]", tekst)
    return tekst
