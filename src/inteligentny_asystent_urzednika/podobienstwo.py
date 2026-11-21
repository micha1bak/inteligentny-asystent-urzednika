"""Proste wyszukiwanie podobnych tekstów (TF-IDF na rdzeniach słów) – bez modeli i sieci.

Rdzeń = pierwsze 6 liter słowa; dla polskiego dobrze zbija odmiany (remontu/remont, zwierząt/zwierzętami).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")

_STOP = set(
    """oraz które który która jakie jaki jaka przez proszę prosimy wnoszę wnosi informacji informację informacja
    udostępnienie udostępnienia dotyczy dotyczące roku latach miasta miasto bydgoszczy bydgoszcz urzędu urząd ustawy
    publicznej publiczną dostępie podstawie szanowni państwo poważaniem odpowiedź odpowiedzi będzie także również jeśli
    tylko można dnia wraz adres adresu mail przesłać przesłanie podziałem formie elektronicznej dzień dobry wniosek
    wniosku wniosków zakresie sprawie danych dane podanie zestawienie""".split()
)
_EMAIL_URL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|https?://\S+")
_SLOWO = re.compile(r"[^\W\d_]{4,}")


def rdzenie(tekst: str) -> list[str]:
    tekst = _EMAIL_URL.sub(" ", tekst.lower())
    return [s[:6] for s in _SLOWO.findall(tekst) if s not in _STOP]


def najpodobniejsze(zapytanie: str, elementy: Sequence[T], teksty: Sequence[str], limit: int) -> list[T]:
    """Zwraca do `limit` elementów najbardziej podobnych do zapytania (z dodatnim podobieństwem)."""
    dokumenty = [Counter(rdzenie(t)) for t in teksty]
    df = Counter(r for d in dokumenty for r in d)
    n = len(dokumenty) + 1

    def wektor(c: Counter) -> dict[str, float]:
        return {r: (1 + math.log(v)) * (math.log(n / (df.get(r, 0) + 1)) + 1) for r, v in c.items()}

    q = wektor(Counter(rdzenie(zapytanie)))
    q_norma = math.sqrt(sum(x * x for x in q.values()))
    if not q_norma:
        return []
    wyniki = []
    for el, d in zip(elementy, dokumenty):
        v = wektor(d)
        norma = math.sqrt(sum(x * x for x in v.values()))
        if norma:
            wynik = sum(x * v.get(r, 0.0) for r, x in q.items()) / (q_norma * norma)
            if wynik > 0:
                wyniki.append((wynik, el))
    wyniki.sort(key=lambda w: w[0], reverse=True)
    return [el for _, el in wyniki[:limit]]
