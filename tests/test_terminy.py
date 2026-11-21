from datetime import date

from inteligentny_asystent_urzednika.terminy import czy_dzien_roboczy, czy_pilny, swieta, termin_odpowiedzi


def test_swieta_ruchome_2026():
    s = swieta(2026)
    assert date(2026, 4, 5) in s   # Wielkanoc
    assert date(2026, 4, 6) in s   # Poniedziałek Wielkanocny
    assert date(2026, 6, 4) in s   # Boże Ciało
    assert date(2026, 12, 24) in s  # Wigilia (od 2025)


def test_termin_14_dni_w_dzien_roboczy():
    # 2 listopada 2026 (pon) + 14 dni = 16 listopada (pon)
    assert termin_odpowiedzi(date(2026, 11, 2)) == date(2026, 11, 16)


def test_termin_przesuwa_sie_z_weekendu():
    # 7 listopada 2026 (sob) + 14 = 21 listopada (sob) -> poniedziałek 23 listopada
    assert termin_odpowiedzi(date(2026, 11, 7)) == date(2026, 11, 23)


def test_termin_przesuwa_sie_ze_swieta():
    # 28 października + 14 = 11 listopada (święto, śr) -> 12 listopada
    assert termin_odpowiedzi(date(2026, 10, 28)) == date(2026, 11, 12)


def test_kwerenda_wydluza_termin():
    assert termin_odpowiedzi(date(2026, 11, 2), dni_kwerendy=14) == date(2026, 11, 30)


def test_pilnosc_w_weekend_i_w_tygodniu():
    sobota, poniedzialek, wtorek = date(2026, 11, 21), date(2026, 11, 23), date(2026, 11, 24)
    assert czy_pilny(poniedzialek, dzis=sobota)
    assert not czy_pilny(wtorek, dzis=sobota)
    assert czy_pilny(wtorek, dzis=poniedzialek)
    assert czy_pilny(date(2026, 11, 20), dzis=poniedzialek)  # po terminie


def test_dzien_roboczy():
    assert czy_dzien_roboczy(date(2026, 11, 20))
    assert not czy_dzien_roboczy(date(2026, 11, 21))
