"""Testy bazy SQLite i endpointów /api/wnioski."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from inteligentny_asystent_urzednika.app import app, pobierz_ustawienia
from inteligentny_asystent_urzednika.config import wczytaj_ustawienia

U = wczytaj_ustawienia()

PRZYKLAD = {
    "data_wplywu": "2026-11-20",
    "temat": "Koszt remontu ul. Gdańskiej w 2026 r.",
    "wnioskodawca": "Jan Nowicki",
    "kontakt": "jan.nowicki@example.com",
    "inicjaly": "ak",
    "tresc": "Wnoszę o udostępnienie informacji o koszcie remontu ul. Gdańskiej w 2026 r.",
    "nazwa_pliku": "wniosek_1.pdf",
}


@pytest.fixture
def api_bazy(tmp_path):
    plik_bazy = tmp_path / "test_wnioski.db"
    ustawienia = replace(U, plik_bazy=plik_bazy)
    app.dependency_overrides[pobierz_ustawienia] = lambda: ustawienia
    yield TestClient(app), plik_bazy
    app.dependency_overrides.clear()


def test_pusta_baza_i_crud(api_bazy):
    klient, plik_bazy = api_bazy
    assert klient.get("/api/wnioski").json() == []
    assert plik_bazy.exists()

    odp = klient.post("/api/wnioski", json=PRZYKLAD)
    assert odp.status_code == 201, odp.text
    w = odp.json()
    assert w["numer"] == "BKS.IV.1431.1.2026"
    assert w["inicjaly"] == "AK"
    assert w["status"] == "brak_dzialan"

    pobrany = klient.get(f"/api/wnioski/{w['id']}").json()
    assert pobrany["temat"] == PRZYKLAD["temat"]
    assert pobrany["nazwa_pliku"] == "wniosek_1.pdf"

    zmiana = {
        **PRZYKLAD,
        "numer": w["numer"],
        "temat": "Zaktualizowany temat",
        "status": "kwerenda",
        "dni_kwerendy": 14,
    }
    odp_put = klient.put(f"/api/wnioski/{w['id']}", json=zmiana)
    assert odp_put.status_code == 200
    z = odp_put.json()
    assert z["temat"] == "Zaktualizowany temat"
    assert z["status"] == "kwerenda"
    assert z["dni_kwerendy"] == 14

    assert klient.delete(f"/api/wnioski/{w['id']}").status_code == 204
    assert klient.get(f"/api/wnioski/{w['id']}").status_code == 404


def test_dodawanie_wsadowe_nadaje_kolejne_numery(api_bazy):
    klient, _ = api_bazy
    wsad = {
        "wnioski": [
            {**PRZYKLAD, "temat": "Wniosek pierwszy", "nazwa_pliku": "a.pdf"},
            {**PRZYKLAD, "temat": "Wniosek drugi", "nazwa_pliku": "b.docx"},
            {**PRZYKLAD, "temat": "Wniosek trzeci", "nazwa_pliku": "c.png"},
        ]
    }
    odp = klient.post("/api/wnioski/wsadowo", json=wsad)
    assert odp.status_code == 201
    dodane = odp.json()
    assert [w["numer"] for w in dodane] == [
        "BKS.IV.1431.1.2026",
        "BKS.IV.1431.2.2026",
        "BKS.IV.1431.3.2026",
    ]
    assert len(klient.get("/api/wnioski").json()) == 3


def test_duplikat_numeru_zwraca_409(api_bazy):
    klient, _ = api_bazy
    w = klient.post("/api/wnioski", json={**PRZYKLAD, "numer": "BKS.IV.1431.99.2026"}).json()
    assert w["numer"] == "BKS.IV.1431.99.2026"
    odp = klient.post("/api/wnioski", json={**PRZYKLAD, "numer": "BKS.IV.1431.99.2026"})
    assert odp.status_code == 409


def test_zastap_wszystkie_i_zdrowie(api_bazy):
    klient, _ = api_bazy
    klient.post("/api/wnioski", json=PRZYKLAD)
    odp = klient.post(
        "/api/wnioski/zastap",
        json={
            "wnioski": [
                {**PRZYKLAD, "numer": "BKS.IV.1431.10.2026", "temat": "Nowy 1"},
                {**PRZYKLAD, "numer": "BKS.IV.1431.11.2026", "temat": "Nowy 2"},
            ]
        },
    )
    assert odp.status_code == 200
    assert len(klient.get("/api/wnioski").json()) == 2
    assert klient.get("/api/zdrowie").json()["wnioskow_w_bazie"] == 2
