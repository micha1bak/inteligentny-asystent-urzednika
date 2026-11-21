"""Wskazywanie ścieżki: propozycja wydziałów UMB i wiadomość do wydziału (bez automatycznej wysyłki)."""

import json
from dataclasses import replace

from fastapi.testclient import TestClient

from inteligentny_asystent_urzednika.app import app, pobierz_ustawienia
from inteligentny_asystent_urzednika.config import wczytaj_ustawienia
from inteligentny_asystent_urzednika.wiedza import wczytaj_wiedze
from inteligentny_asystent_urzednika.wydzialy import (
    jednostka_po_nazwie,
    kontekst_wydzialow,
    propozycja_bez_modelu,
    zloz_wiadomosc,
    zweryfikuj,
)

U = wczytaj_ustawienia()
WIEDZA = wczytaj_wiedze(U.plik_oceny, U.plik_werdyktow, U.plik_wzorow)


def test_kontekst_ma_wszystkie_jednostki_z_zakresem():
    k = kontekst_wydzialow(WIEDZA, "Ile uczniów uczy się w szkołach podstawowych?")
    assert "Wydział Edukacji i Sportu" in k and "szkoły, przedszkola" in k and "PODOBNE SPRAWY" in k


def test_weryfikacja_odrzuca_jednostki_spoza_listy():
    p = zweryfikuj(json.dumps({"jednostki": [{"nazwa": "Wydział Edukacji i Sportu", "uzasadnienie": "szkoły"},
                                             {"nazwa": "Wydział Wymyślony"}, {"nazwa": "WE"}],
                               "pytania": ["Liczba uczniów"]}))
    assert [j.symbol for j in p.jednostki] == ["WE"] and any("Wymyślony" in o for o in p.ostrzezenia)


def test_bez_modelu_wskazuje_wydzial_z_podobnej_sprawy():
    p = propozycja_bez_modelu(WIEDZA, "Proszę o aktualną liczbę uczniów w szkołach podstawowych.\n1. Liczba uczniów\n2. Obcokrajowcy")
    assert p.jednostki[0].symbol == "WE" and "307" in p.jednostki[0].uzasadnienie
    assert p.pytania == ["Liczba uczniów", "Obcokrajowcy"] and p.ostrzezenia


def test_wiadomosc_skladana_przez_kod():
    w = zloz_wiadomosc("Wydział Edukacji i Sportu", ["Liczba uczniów."], "BKS.IV.1431.307.2025", "2025-06-24")
    assert "Na co zwrócić uwagę" not in w.tresc
    assert w.termin == "2025-07-01" and w.tresc.startswith("Do: Wydział Edukacji i Sportu")
    assert "1. Liczba uczniów." in w.tresc and "bip@um.bydgoszcz.pl" in w.tresc and "§ 11 ust. 8" in w.tresc
    assert jednostka_po_nazwie("wydział inwestycji miasta")["symbol"] == "WIM"


def test_endpointy_bez_klucza_ai():
    app.dependency_overrides[pobierz_ustawienia] = lambda: replace(U, groq_api_key=None)
    try:
        k = TestClient(app)
        p = k.post("/api/wydzial/propozycja", json={"tresc": "Liczba mieszkańców na podstawie opłat za odpady komunalne."}).json()
        assert p["jednostki"] and p["jednostki"][0]["symbol"] == "WGO"
        w = k.post("/api/wydzial/wiadomosc", json={"jednostka": "WGO", "pytania": ["Liczba mieszkańców"],
                                                   "numer": "BKS.IV.1431.18.2026", "data_wplywu": "2026-01-12"}).json()
        assert w["termin"] == "2026-01-19" and "Wydział Gospodarki Odpadami" in w["tresc"]
        assert k.post("/api/wydzial/wiadomosc", json={"jednostka": "Nieistniejący"}).status_code == 422
        assert len(k.get("/api/jednostki").json()) == 29
    finally:
        app.dependency_overrides.clear()
