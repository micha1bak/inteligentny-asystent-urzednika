"""Testy deterministycznego wyszukiwania przepisów z folderu „Dokumenty i podstawy prawne” (bez modelu AI)."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from inteligentny_asystent_urzednika.app import app, pobierz_ustawienia
from inteligentny_asystent_urzednika.config import wczytaj_ustawienia
from inteligentny_asystent_urzednika.przepisy import parsuj_odwolania, szukaj_przepisow, wczytaj_indeks_przepisow

U = wczytaj_ustawienia()
INDEKS = wczytaj_indeks_przepisow(U.katalog_dokumentow)


def test_indeks_zawiera_glowne_akty():
    akty = {d.akt for d in INDEKS.dokumenty}
    assert {"UDIP", "KPA", "ZARZADZENIE_535_2024"} <= akty


def test_parser_odwolan_rozne_formaty():
    o1 = parsuj_odwolania("Art. 13 ust. 1 UDIP")
    assert len(o1) == 1 and o1[0].akt == "UDIP" and o1[0].numer == "13" and o1[0].podnumery == ("1",)

    o2 = parsuj_odwolania("Art. 5 ust. 1, 2, 2a, 2b, 3 i 4 UDIP")
    assert len(o2) == 1 and o2[0].podnumery == ("1", "2", "2a", "2b", "3", "4")

    o3 = parsuj_odwolania("Art. 6 ust. 1 pkt 4 lit. d UDIP")
    assert len(o3) == 1 and o3[0].podnumery == ("1",) and o3[0].punkty == ("4",) and o3[0].litery == ("d",)

    o4 = parsuj_odwolania("Art. 57 § 1 i § 4 KPA")
    assert len(o4) == 1 and o4[0].akt == "KPA" and o4[0].podrodzaj == "par" and o4[0].podnumery == ("1", "4")

    o5 = parsuj_odwolania("§ 11 ust. 8-9 Zarządzenia Nr 535/2024")
    assert len(o5) == 1 and o5[0].akt == "ZARZADZENIE_535_2024" and o5[0].rodzaj == "par" and o5[0].podnumery == ("8", "9")

    o6 = parsuj_odwolania("Art. 4 ust. 3 UDIP; § 11 ust. 3 Zarządzenia Nr 535/2024")
    assert len(o6) == 2
    assert o6[0].akt == "UDIP" and o6[0].numer == "4"
    assert o6[1].akt == "ZARZADZENIE_535_2024" and o6[1].numer == "11"

    o7 = parsuj_odwolania("Art. 16 ust. 1 i ust. 2 pkt 2 UDIP")
    assert len(o7) == 2
    assert o7[0].podnumery == ("1",)
    assert o7[1].podnumery == ("2",) and o7[1].punkty == ("2",)


@pytest.mark.parametrize(
    ("zapytanie", "akt", "fragment_tresci"),
    [
        ("Art. 13 ust. 1 UDIP", "UDIP", "14 dni"),
        ("Art. 13 ust. 2 UDIP", "UDIP", "2 miesiące"),
        ("Art. 5 ust. 2 zd. 2 UDIP", "UDIP", "prywatność osoby fizycznej"),
        ("Art. 6 ust. 1 pkt 5 UDIP", "UDIP", "majątku publicznym"),
        ("Art. 6 ust. 1 pkt 4 lit. d UDIP", "UDIP", "stanie państwa"),
        ("Art. 57 § 4 KPA", "KPA", "wolny od pracy"),
        ("Art. 64 § 2 KPA", "KPA", "siedem dni"),
        ("§ 8 ust. 1 Zarządzenia Nr 535/2024", "ZARZADZENIE_535_2024", "opublikowana w BIP"),
        ("§ 9 ust. 1 Zarządzenia Nr 535/2024", "ZARZADZENIE_535_2024", "AIP koordynuje"),
        ("§ 11 ust. 3 Zarządzenia Nr 535/2024", "ZARZADZENIE_535_2024", "nie jest w posiadaniu"),
    ],
)
def test_wyszukiwanie_konkretnych_ustepow(zapytanie, akt, fragment_tresci):
    wynik = szukaj_przepisow(INDEKS, zapytanie)
    assert wynik.wyniki, f"Brak wyników dla: {zapytanie}"
    pierwszy = wynik.wyniki[0]
    assert pierwszy.akt == akt
    assert pierwszy.dopasowanie == "dokladne"
    assert fragment_tresci.lower() in pierwszy.tresc.lower()


def test_zarzadzenie_pdf_podaje_numery_stron():
    wynik = szukaj_przepisow(INDEKS, "§ 11 ust. 8-9 Zarządzenia Nr 535/2024")
    assert len(wynik.wyniki) == 2
    assert wynik.wyniki[0].strona == 3
    assert "anonimizacji" in wynik.wyniki[0].tresc.lower()
    assert wynik.wyniki[1].strona == 4
    assert "decyzji administracyjnej" in wynik.wyniki[1].tresc.lower()


def test_wyszukiwanie_frazowe_bez_cytowania():
    wynik = szukaj_przepisow(INDEKS, "informacji przetworzonej")
    assert wynik.wyniki
    assert any("przetworzonej" in w.tresc.lower() for w in wynik.wyniki)

    wynik_pesel = szukaj_przepisow(INDEKS, "PESEL")
    assert wynik_pesel.wyniki
    assert any("anonimizacji" in w.plik.lower() for w in wynik_pesel.wyniki)


def test_endpointy_dzialaja_bez_klucza_llm():
    app.dependency_overrides[pobierz_ustawienia] = lambda: replace(U, groq_api_key=None)
    try:
        klient = TestClient(app)
        dok = klient.get("/api/przepisy/dokumenty")
        assert dok.status_code == 200
        akty = {d["akt"] for d in dok.json()}
        assert {"UDIP", "KPA", "ZARZADZENIE_535_2024"} <= akty

        sz = klient.get("/api/przepisy/szukaj", params={"q": "Art. 13 ust. 1 UDIP"})
        assert sz.status_code == 200
        dane = sz.json()
        assert dane["wyniki"] and "14 dni" in dane["wyniki"][0]["tresc"]
    finally:
        app.dependency_overrides.clear()


def test_dynamiczne_wykrywanie_nowego_pliku_w_katalogu(tmp_path):
    plik1 = tmp_path / "Ustawa_testowa.txt"
    plik1.write_text("Art. 1. 1. Pierwszy przepis testowy.\n2. Drugi ustęp testowy.\n", encoding="utf-8")

    ind1 = wczytaj_indeks_przepisow(tmp_path)
    w1 = szukaj_przepisow(ind1, "Art. 1 ust. 2")
    assert w1.wyniki and "Drugi ustęp testowy" in w1.wyniki[0].tresc

    plik2 = tmp_path / "Nowa_ustawa.txt"
    plik2.write_text("Art. 99. 1. Świeżo dodany artykuł.\n", encoding="utf-8")

    ind2 = wczytaj_indeks_przepisow(tmp_path)
    w2 = szukaj_przepisow(ind2, "Art. 99 ust. 1")
    assert w2.wyniki and "Świeżo dodany artykuł" in w2.wyniki[0].tresc


def test_wszystkie_przepisy_z_etapow_oceny_znajduja_fragmenty():
    import json

    ocena = json.loads(U.plik_oceny.read_text(encoding="utf-8"))
    for etap in ocena["algorytm_oceny_krokowej"]:
        for podstawa in etap.get("podstawa_prawna", []):
            if podstawa in {"BIP_UMB_Info", "Katalog_Anonimizacji"}:
                continue
            wynik = szukaj_przepisow(INDEKS, podstawa)
            assert wynik.wyniki, f"Nie znaleziono fragmentu dla podstawy z {etap['etap_id']}: {podstawa}"

