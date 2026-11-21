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
