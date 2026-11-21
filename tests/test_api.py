from datetime import date, timedelta

from fastapi.testclient import TestClient

from inteligentny_asystent_urzednika.app import app
from inteligentny_asystent_urzednika.dane_testowe import wczytaj

klient = TestClient(app)


def test_dane_testowe_10_wnioskow_od_najstarszego():
    wczytaj()
    dzis = date.today()
    wnioski = [w for rok in {dzis.year, dzis.year - 1}
               for w in klient.get("/api/wnioski", params={"rok": rok}).json()]
    assert len(wnioski) == 10
    for rok in {w["rok"] for w in wnioski}:
        z_roku = [w for w in wnioski if w["rok"] == rok]
        assert [w["data_wplywu"] for w in z_roku] == sorted(w["data_wplywu"] for w in z_roku)
        assert [w["lp"] for w in z_roku] == list(range(1, len(z_roku) + 1))
    pilne = [w for w in wnioski if w["pilny"]]
    assert len(pilne) >= 3  # termin minął, dziś lub w najbliższy dzień roboczy


def test_wczytanie_jest_idempotentne():
    wczytaj()
    assert "Dodano: 0 wniosków" in wczytaj()


def test_dodanie_i_zmiana_statusu():
    wplyw = date.today() - timedelta(days=3)
    r = klient.post("/api/wnioski", json={"numer": "TEST.1", "temat": "Test", "data_wplywu": wplyw.isoformat()})
    assert r.status_code == 201
    w = r.json()
    assert w["lp"] == 1 and w["status"] == "brak_dzialan"

    r = klient.patch(f"/api/wnioski/{w['id']}", json={"dni_kwerendy": 30})
    assert r.json()["status"] == "kwerenda"
    assert r.json()["termin_odpowiedzi"] > w["termin_odpowiedzi"]

    r = klient.patch(f"/api/wnioski/{w['id']}", json={"status": "odpowiedz_wyslana"})
    assert r.json()["data_odpowiedzi"] == date.today().isoformat()
    assert r.json()["pilny"] is False


def test_wydzialy_i_zaslepki():
    wydzialy = klient.get("/api/wydzialy").json()
    assert {"WIM", "WOA", "BRM", "BKS"} <= {w["symbol"] for w in wydzialy}
    assert klient.get("/api/wnioski/1/wydzialy").status_code == 200
    assert klient.post("/api/wnioski/1/projekt-pisma").json()["tresc"]


def test_nieistniejacy_wniosek():
    assert klient.get("/api/wnioski/999").status_code == 404
