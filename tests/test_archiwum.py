"""Archiwum spraw: CRUD (/api/archiwum), historia zmian, anonimizacja i propozycja wpisu z dokumentów."""

import json
import shutil
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from inteligentny_asystent_urzednika import archiwum as modul_archiwum
from inteligentny_asystent_urzednika.anonimizacja import wykryj, zanonimizuj
from inteligentny_asystent_urzednika.app import app, pobierz_klienta, pobierz_ustawienia
from inteligentny_asystent_urzednika.config import wczytaj_ustawienia
from inteligentny_asystent_urzednika.wiedza import wczytaj_wiedze

U = wczytaj_ustawienia()
WIEDZA = wczytaj_wiedze(U.plik_oceny, U.plik_werdyktow, U.plik_wzorow)

NOWA_SPRAWA = {
    "sygnatura": "BKS.IV.1431.700.2026",
    "data_odpowiedzi": "2026-11-25",
    "komorka_merytoryczna": "Wydział Zieleni i Gospodarki Komunalnej",
    "wniosek_o_co": "Liczba psów i kotów przyjętych przez schronisko w 2026 r. oraz koszt opieki nad zwierzętami.",
    "jaka_odpowiedz": "Udostępniono liczbę zwierząt przyjętych do schroniska i koszt opieki w 2026 r.",
    "werdykt": "MOZNA_UDOSTEPNIC",
    "forma_zalatwienia": "Pismo udostępniające informację",
    "etap_i_podstawa": "Art. 1 ust. 1, art. 6 ust. 1 pkt 5 UDIP",
}


class FalszywyKlient:
    def __init__(self, odpowiedz: str):
        self.odpowiedz = odpowiedz
        self.wiadomosci: list | None = None

    async def czat_json(self, wiadomosci):
        self.wiadomosci = wiadomosci
        return self.odpowiedz


@pytest.fixture
def api(tmp_path):
    """API z kopią archiwum w katalogu tymczasowym – testy nie zmieniają pliku w repozytorium."""
    plik = tmp_path / "werdykty.json"
    shutil.copy(U.plik_werdyktow, plik)
    ustawienia = replace(U, plik_werdyktow=plik)
    app.dependency_overrides[pobierz_ustawienia] = lambda: ustawienia
    yield TestClient(app), plik, ustawienia
    app.dependency_overrides.clear()


def _zapis(sprawa: dict, autor: str = "AK") -> dict:
    return {"sprawa": sprawa, "autor": autor}


def _wiedza(u, plik):
    return wczytaj_wiedze(u.plik_oceny, plik, u.plik_wzorow)


def test_lista(api):
    klient, _, _ = api
    dane = klient.get("/api/archiwum").json()
    assert len(dane["sprawy"]) == len(WIEDZA.sygnatury)
    assert "MOZNA_UDOSTEPNIC" in dane["werdykty"] and dane["jednostki"]


def test_obecne_archiwum_przechodzi_walidacje():
    for s in modul_archiwum.lista(U.plik_werdyktow):
        modul_archiwum.sprawdz(s, WIEDZA.slownik_werdyktow)


def test_dodana_sprawa_od_razu_trafia_do_podobnych(api):
    klient, plik, u = api
    odp = klient.post("/api/archiwum", json=_zapis(NOWA_SPRAWA))
    assert odp.status_code == 201
    wpis = odp.json()["historia"][0]
    assert wpis["zmiana"] == "dodano" and wpis["kto"] == "AK"

    zapisane = json.loads(plik.read_text(encoding="utf-8"))
    assert zapisane["metadane"]["liczba_spraw"] == len(zapisane["sprawy"])
    podobne = _wiedza(u, plik).podobne_sprawy("ile psów i kotów przyjęło schronisko", 1)  # bez restartu backendu
    assert podobne[0]["sygnatura"] == NOWA_SPRAWA["sygnatura"]
    assert "historia" not in podobne[0]  # pola techniczne nie trafiają do modelu


def test_duplikat_sygnatury(api):
    klient, _, _ = api
    istniejaca = next(iter(WIEDZA.sygnatury))
    odp = klient.post("/api/archiwum", json=_zapis({**NOWA_SPRAWA, "sygnatura": istniejaca}))
    assert odp.status_code == 409 and "już w archiwum" in odp.json()["detail"]


def test_nieznany_werdykt(api):
    klient, _, _ = api
    odp = klient.post("/api/archiwum", json=_zapis({**NOWA_SPRAWA, "werdykt": "MOZE_KIEDYS"}))
    assert odp.status_code == 422 and "Nieznany werdykt" in odp.json()["detail"]


def test_blokada_danych_osobowych(api):
    klient, plik, _ = api
    przed = plik.read_text(encoding="utf-8")
    sprawa = {**NOWA_SPRAWA, "jaka_odpowiedz": "Odpowiedź wysłano na adres jan.testowy@example.com, tel. 600 100 200."}
    odp = klient.post("/api/archiwum", json=_zapis(sprawa))
    assert odp.status_code == 422
    assert "adres e-mail" in odp.json()["detail"] and "numer telefonu" in odp.json()["detail"]
    assert plik.read_text(encoding="utf-8") == przed


def test_edycja_historia_i_nieaktualnosc(api):
    klient, plik, u = api
    klient.post("/api/archiwum", json=_zapis(NOWA_SPRAWA))
    syg = NOWA_SPRAWA["sygnatura"]

    zmieniona = {**NOWA_SPRAWA, "werdykt": "MOZNA_Z_ANONIMIZACJA"}
    odp = klient.put(f"/api/archiwum/{syg}", json=_zapis(zmieniona, "MW"))
    assert odp.status_code == 200
    wpis = odp.json()["historia"][-1]
    assert wpis["kto"] == "MW" and wpis["zmiana"] == "edytowano"
    assert wpis["pola"] == {"werdykt": {"przed": "MOZNA_UDOSTEPNIC", "po": "MOZNA_Z_ANONIMIZACJA"}}

    odp = klient.put(f"/api/archiwum/{syg}", json=_zapis({**zmieniona, "nieaktualna": True}))
    assert odp.json()["nieaktualna"] and odp.json()["historia"][-1]["zmiana"] == "oznaczono jako nieaktualną"
    wiedza = _wiedza(u, plik)
    assert syg not in wiedza.sygnatury  # model nie używa nieaktualnej sprawy
    assert syg not in wiedza.kontekst_pelny()

    odp = klient.put(f"/api/archiwum/{syg}", json=_zapis(zmieniona))
    assert odp.json()["historia"][-1]["zmiana"] == "przywrócono jako aktualną"
    assert syg in _wiedza(u, plik).sygnatury


def test_zapis_bez_zmian_nie_dopisuje_historii(api):
    klient, _, _ = api
    klient.post("/api/archiwum", json=_zapis(NOWA_SPRAWA))
    odp = klient.put(f"/api/archiwum/{NOWA_SPRAWA['sygnatura']}", json=_zapis(NOWA_SPRAWA))
    assert len(odp.json()["historia"]) == 1


def test_nie_mozna_zmienic_sygnatury(api):
    klient, _, _ = api
    syg = next(iter(WIEDZA.sygnatury))
    assert klient.put(f"/api/archiwum/{syg}", json=_zapis(NOWA_SPRAWA)).status_code == 422


def test_usuwanie(api):
    klient, _, _ = api
    klient.post("/api/archiwum", json=_zapis(NOWA_SPRAWA))
    assert klient.delete(f"/api/archiwum/{NOWA_SPRAWA['sygnatura']}").status_code == 204
    assert klient.delete(f"/api/archiwum/{NOWA_SPRAWA['sygnatura']}").status_code == 404


def test_propozycja_wpisu_anonimizuje_i_weryfikuje(api):
    klient, _, _ = api
    odpowiedz_modelu = json.dumps(
        {
            "sygnatura": "BKS.IV.1431.1.2026",
            "data_odpowiedzi": "25.11.2026",
            "komorka_merytoryczna": "Wydział Nieistniejący",
            "wniosek_o_co": "Wnioskodawca (jan@example.com) pytał o liczbę zwierząt w schronisku.",
            "jaka_odpowiedz": "Udostępniono liczbę zwierząt przyjętych w 2026 r.",
            "werdykt": "MOZE_KIEDYS",
            "forma_zalatwienia": "Pismo udostępniające informację",
            "etap_i_podstawa": "Art. 10 ust. 1 UDIP",
        }
    )
    falszywy = FalszywyKlient(odpowiedz_modelu)
    app.dependency_overrides[pobierz_klienta] = lambda: falszywy
    wniosek = "Wnoszę o udostępnienie informacji, ile psów i kotów przyjęło schronisko w 2026 r."
    odp = klient.post(
        "/api/archiwum/propozycja",
        json={"wniosek": wniosek, "odpowiedz": "Bydgoszcz, 25.11.2026 r. Udostępniamy informację …", "sygnatura": "BKS.IV.1431.700.2026"},
    )
    assert odp.status_code == 200
    dane = odp.json()
    sprawa = dane["sprawa"]
    assert sprawa["sygnatura"] == "BKS.IV.1431.700.2026"  # sygnatura od urzędnika ma pierwszeństwo
    assert sprawa["werdykt"] == "" and sprawa["data_odpowiedzi"] == ""
    assert "jan@example.com" not in sprawa["wniosek_o_co"] and "[zanonimizowano]" in sprawa["wniosek_o_co"]
    ostrzezenia = " ".join(dane["ostrzezenia"])
    assert "nieznany werdykt" in ostrzezenia and "Wydział Nieistniejący" in ostrzezenia and "adres e-mail" in ostrzezenia
    tresc = falszywy.wiadomosci[1]["content"]  # model dostaje oba dokumenty i słownik werdyktów
    assert wniosek in tresc and "MOZNA_Z_ANONIMIZACJA" in tresc


def test_wykrywanie_danych_osobowych():
    tekst = (
        "jan.k@wp.pl, tel. 600 100 200, +48 601-200-300, (52) 58 58 365, PESEL 90010112345, "
        "konto PL61 1090 1014 0000 0712 1981 2874"
    )
    rodzaje = [r for r, _ in wykryj(tekst)]
    assert rodzaje.count("numer telefonu") == 3
    assert {"adres e-mail", "PESEL", "numer konta"} <= set(rodzaje)
    assert not wykryj("Dz.U. 2026 poz. 1234, 02.01.2020 r., kwota 123 456 789,50 zł, art. 6 ust. 1 pkt 5")
    assert "600 100 200" not in zanonimizuj(tekst)


def test_wydzialy_symbole_i_nazwy(api):
    klient, plik, _ = api
    sprawa = {**NOWA_SPRAWA, "wydzialy": ["wgk", "Wydział Gospodarki Odpadami", "WGK"], "podmiot_poza_umb": ""}
    odp = klient.post("/api/archiwum", json=_zapis(sprawa))
    assert odp.status_code == 201, odp.text
    assert odp.json()["wydzialy"] == ["WGK", "WGO"]  # nazwa -> symbol, bez powtórzeń
    zapisana = next(s for s in json.loads(plik.read_text(encoding="utf-8"))["sprawy"] if s["sygnatura"] == sprawa["sygnatura"])
    assert zapisana["wydzialy"] == ["WGK", "WGO"]


def test_nieznany_wydzial_odrzucony(api):
    klient, _, _ = api
    odp = klient.post("/api/archiwum", json=_zapis({**NOWA_SPRAWA, "wydzialy": ["Wydział Marzeń"]}))
    assert odp.status_code == 422 and "Wydział Marzeń" in odp.json()["detail"]


def test_wpis_bez_pola_wydzialy_nie_daje_pustej_zmiany_w_historii(api):
    klient, plik, _ = api
    dane = json.loads(plik.read_text(encoding="utf-8"))
    dane["sprawy"].append({k: v for k, v in NOWA_SPRAWA.items()})  # starszy format: bez wydzialy i podmiot_poza_umb
    plik.write_text(json.dumps(dane, ensure_ascii=False), encoding="utf-8")
    odp = klient.put(f"/api/archiwum/{NOWA_SPRAWA['sygnatura']}", json=_zapis(NOWA_SPRAWA))
    assert odp.status_code == 200 and odp.json()["historia"] == []


def test_archiwum_w_repozytorium_ma_wydzialy():
    for s in modul_archiwum.lista(U.plik_werdyktow):
        assert all(modul_archiwum.symbol_jednostki(w) for w in s.wydzialy)
        assert s.wydzialy or s.podmiot_poza_umb or "brak" in s.komorka_merytoryczna.lower()
