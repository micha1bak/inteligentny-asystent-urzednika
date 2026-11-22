"""Testy logowania urzędnika (baza SQLite: unikalny id_u + powiązane inicjały Os. + hasło oraz sesje)."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from inteligentny_asystent_urzednika.app import app, pobierz_ustawienia
from inteligentny_asystent_urzednika.baza_urzednikow import (
    BladLogowania,
    LogowanieWejscie,
    RejestracjaWejscie,
    lista_urzednikow,
    sprawdz_sesje,
    wyloguj,
    zaloguj,
    zarejestruj,
)
from inteligentny_asystent_urzednika.config import wczytaj_ustawienia


def test_baza_zasiewa_domyslnych_urzednikow_i_weryfikuje_haslo(tmp_path):
    db = tmp_path / "urzednicy.db"
    assert lista_urzednikow(db) == [
        {"id_u": "UMB-001", "inicjaly": "AK"},
        {"id_u": "UMB-002", "inicjaly": "MW"},
        {"id_u": "UMB-003", "inicjaly": "PB"},
    ]

    sesja = zaloguj(db, LogowanieWejscie(id_u="umb-001", haslo="haslo123"))
    assert sesja.id_u == "UMB-001" and sesja.inicjaly == "AK" and sesja.token
    assert sprawdz_sesje(db, sesja.token) == ("UMB-001", "AK")

    with pytest.raises(BladLogowania) as err:
        zaloguj(db, LogowanieWejscie(id_u="UMB-001", haslo="zle_haslo"))
    assert err.value.status == 401

    wyloguj(db, sesja.token)
    assert sprawdz_sesje(db, sesja.token) is None


def test_rejestracja_nowego_urzednika_i_duplikat(tmp_path):
    db = tmp_path / "urzednicy.db"
    sesja = zarejestruj(db, RejestracjaWejscie(id_u="umb-004", inicjaly="jk", haslo="tajne123"))
    assert sesja.id_u == "UMB-004" and sesja.inicjaly == "JK"
    assert {"id_u": "UMB-004", "inicjaly": "JK"} in lista_urzednikow(db)

    with pytest.raises(BladLogowania) as err:
        zarejestruj(db, RejestracjaWejscie(id_u="UMB-004", inicjaly="JK", haslo="inne123"))
    assert err.value.status == 409

    with pytest.raises(BladLogowania) as err_fmt:
        zarejestruj(db, RejestracjaWejscie(id_u="zly id!", inicjaly="JK", haslo="inne123"))
    assert err_fmt.value.status == 422


def test_endpointy_logowania_sesji_i_wylogowania(tmp_path):
    u = replace(wczytaj_ustawienia(), plik_bazy_urzednikow=tmp_path / "urzednicy.db")
    app.dependency_overrides[pobierz_ustawienia] = lambda: u
    try:
        klient = TestClient(app)
        assert klient.get("/api/sesja").json() == {"zalogowany": False, "id_u": None, "inicjaly": None}

        zle = klient.post("/api/logowanie", json={"id_u": "UMB-001", "haslo": "bledne"})
        assert zle.status_code == 401

        ok = klient.post("/api/logowanie", json={"id_u": "umb-002", "haslo": "haslo123"})
        assert ok.status_code == 200
        dane = ok.json()
        assert dane["id_u"] == "UMB-002" and dane["inicjaly"] == "MW" and dane["token"]

        assert klient.get("/api/sesja").json() == {"zalogowany": True, "id_u": "UMB-002", "inicjaly": "MW"}
        assert klient.get("/api/sesja", headers={"Authorization": f"Bearer {dane['token']}"}).json() == {
            "zalogowany": True,
            "id_u": "UMB-002",
            "inicjaly": "MW",
        }

        assert klient.post("/api/wyloguj").status_code == 204
        assert klient.get("/api/sesja").json() == {"zalogowany": False, "id_u": None, "inicjaly": None}

        nowy = klient.post("/api/urzednicy", json={"id_u": "umb-009", "inicjaly": "zn", "haslo": "nowehaslo"})
        assert nowy.status_code == 201 and nowy.json()["id_u"] == "UMB-009" and nowy.json()["inicjaly"] == "ZN"
        assert klient.get("/api/sesja").json() == {"zalogowany": True, "id_u": "UMB-009", "inicjaly": "ZN"}
    finally:
        app.dependency_overrides.clear()
