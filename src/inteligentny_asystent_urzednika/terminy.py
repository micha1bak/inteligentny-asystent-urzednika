"""Liczenie terminów odpowiedzi na wnioski UDIP.

- art. 13 ust. 1 UDIP: odpowiedź bez zbędnej zwłoki, nie później niż w terminie 14 dni od dnia złożenia wniosku,
- art. 13 ust. 2 UDIP: termin można przedłużyć (łącznie do 2 miesięcy), powiadamiając wnioskodawcę –
  w aplikacji to "kwerenda" z liczbą dodatkowych dni,
- art. 57 § 4 KPA (stosowany pomocniczo): jeśli koniec terminu wypada w sobotę lub dzień ustawowo wolny,
  termin upływa następnego dnia roboczego.
"""

from datetime import date, timedelta
from functools import cache

TERMIN_PODSTAWOWY_DNI = 14
MAKS_PRZEDLUZENIE_DNI = 61  # ok. 2 miesiące łącznie z terminem podstawowym


def _wielkanoc(rok: int) -> date:
    """Data Wielkanocy (algorytm Meeusa/Jonesa/Butchera)."""
    a = rok % 19
    b, c = divmod(rok, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    miesiac, dzien = divmod(h + l - 7 * m + 114, 31)
    return date(rok, miesiac, dzien + 1)


@cache
def swieta(rok: int) -> frozenset[date]:
    """Dni ustawowo wolne od pracy w Polsce."""
    wielkanoc = _wielkanoc(rok)
    stale = {
        (1, 1), (1, 6), (5, 1), (5, 3), (8, 15), (11, 1), (11, 11), (12, 25), (12, 26),
    }
    if rok >= 2025:
        stale.add((12, 24))  # Wigilia – dzień wolny od 2025 r.
    dni = {date(rok, m, d) for m, d in stale}
    dni |= {
        wielkanoc,
        wielkanoc + timedelta(days=1),   # Poniedziałek Wielkanocny
        wielkanoc + timedelta(days=49),  # Zielone Świątki
        wielkanoc + timedelta(days=60),  # Boże Ciało
    }
    return frozenset(dni)


def czy_dzien_roboczy(dzien: date) -> bool:
    return dzien.weekday() < 5 and dzien not in swieta(dzien.year)


def przesun_na_dzien_roboczy(dzien: date) -> date:
    while not czy_dzien_roboczy(dzien):
        dzien += timedelta(days=1)
    return dzien


def termin_odpowiedzi(data_wplywu: date, dni_kwerendy: int = 0) -> date:
    """Ostateczny termin odpowiedzi z uwzględnieniem kwerendy i dni wolnych."""
    dni = TERMIN_PODSTAWOWY_DNI + max(0, dni_kwerendy)
    return przesun_na_dzien_roboczy(data_wplywu + timedelta(days=dni))


def nastepny_dzien_roboczy(dzien: date) -> date:
    return przesun_na_dzien_roboczy(dzien + timedelta(days=1))


def czy_pilny(termin: date, dzis: date | None = None) -> bool:
    """Termin minął, jest dziś albo w najbliższy dzień roboczy (w piątek i w weekend – poniedziałek)."""
    return termin <= nastepny_dzien_roboczy(dzis or date.today())


def dni_do_terminu(termin: date, dzis: date | None = None) -> int:
    """Liczba dni kalendarzowych do terminu (ujemna = po terminie)."""
    return (termin - (dzis or date.today())).days
