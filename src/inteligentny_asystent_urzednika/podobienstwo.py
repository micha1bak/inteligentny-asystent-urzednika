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
    return [el for _, el in z_wynikiem(zapytanie, elementy, teksty, limit)]


def z_wynikiem(zapytanie: str, elementy: Sequence[T], teksty: Sequence[str], limit: int) -> list[tuple[float, T]]:
    """Jak `najpodobniejsze`, ale z miarą podobieństwa 0–1.

    Miara: średnia geometryczna dwóch pokryć liczonych na wagach TF-IDF:
      * jaka część treści dokumentu (np. sprawy z archiwum) występuje we wniosku,
      * jaka część wniosku pokrywa się z dokumentem – liczona tylko po słowach, które występują w przeszukiwanym
        zbiorze. Nazwiska, adresy i zwroty grzecznościowe z wniosku nie trafiają do żadnej sprawy, więc nie
        zaniżają wyniku (zwykły kosinus dawał przez nie nawet tej samej sprawie ok. 30%).
    """
    dokumenty = [Counter(rdzenie(t)) for t in teksty]
    df = Counter(r for d in dokumenty for r in d)
    n = len(dokumenty) + 1

    def wektor(c: Counter) -> dict[str, float]:
        return {r: (1 + math.log(v)) * (math.log(n / (df.get(r, 0) + 1)) + 1) for r, v in c.items()}

    # wniosek ograniczony do słownika przeszukiwanego zbioru
    q = {r: x for r, x in wektor(Counter(rdzenie(zapytanie))).items() if df.get(r)}
    q_kwadrat = sum(x * x for x in q.values())
    if not q_kwadrat:
        return []
    wyniki = []
    for el, d in zip(elementy, dokumenty):
        v = wektor(d)
        d_kwadrat = sum(x * x for x in v.values())
        wspolne = [r for r in v if r in q]
        if not d_kwadrat or not wspolne:
            continue
        pokrycie_dokumentu = sum(v[r] ** 2 for r in wspolne) / d_kwadrat
        pokrycie_wniosku = sum(q[r] ** 2 for r in wspolne) / q_kwadrat
        wyniki.append((math.sqrt(pokrycie_dokumentu * pokrycie_wniosku), el))
    wyniki.sort(key=lambda w: w[0], reverse=True)
    return wyniki[:limit]
