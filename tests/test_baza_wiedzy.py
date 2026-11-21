"""Aktualizacja bazy wiedzy po wgraniu nowego aktu: porównanie wersji, propozycje modelu, wersjonowanie i wycofanie."""

import json
import shutil
from dataclasses import replace
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from inteligentny_asystent_urzednika import analiza_aktu, baza_wiedzy
from inteligentny_asystent_urzednika.app import app, pobierz_klienta, pobierz_ustawienia
from inteligentny_asystent_urzednika.config import wczytaj_ustawienia
from inteligentny_asystent_urzednika.groq_klient import BladLLM
from inteligentny_asystent_urzednika.przepisy import _indeksuj_dokument

U = wczytaj_ustawienia()
PLIK_UDIP = "UDIP - Ustawa o dostępie do informacji publicznej.txt"


DZIS = date.today()


def udip(nowelizacja: bool = True) -> bytes:
    """Tekst UDIP z repo; z nowelizacją – termin w art. 13 ust. 1 wydłużony z 14 do 21 dni."""
    tekst = (U.katalog_dokumentow / PLIK_UDIP).read_bytes().decode("utf-8")  # bez zamiany końców linii
    if nowelizacja:
        poczatek, koniec = tekst.index("Art. 13."), tekst.index("Art. 14.")
        art13 = tekst[poczatek:koniec]
        assert "14 dni" in art13
        tekst = tekst[:poczatek] + art13.replace("14 dni", "21 dni") + tekst[koniec:]
    return tekst.encode("utf-8")


class FalszywyKlient:
    """Odpowiada kolejnymi odpowiedziami z listy (str albo wyjątek) i zapamiętuje zapytania."""

    def __init__(self, *odpowiedzi):
        self.odpowiedzi = list(odpowiedzi)
        self.zapytania: list = []

    async def czat_json(self, wiadomosci):
        self.zapytania.append(wiadomosci)
        odp = self.odpowiedzi.pop(0)
        if isinstance(odp, Exception):
            raise odp
        return odp


def propozycja_etapu_10(ocena: dict) -> str:
    etap = next(e for e in ocena["algorytm_oceny_krokowej"] if e["etap_id"] == "ETAP_10")
    po = json.loads(json.dumps(etap).replace("14 dni", "21 dni"))
    return json.dumps(
        {
            "elementy": [
                {
                    "klucz": "algorytm_oceny_krokowej/ETAP_10",
                    "wymaga_zmiany": True,
                    "uzasadnienie": "Art. 13 ust. 1 UDIP wydłuża termin do 21 dni.",
                    "przepisy": ["Art. 13 ust. 1 UDIP"],
                    "po": po,
                }
            ]
        },
        ensure_ascii=False,
    )


@pytest.fixture
def srodowisko(tmp_path, monkeypatch):
    """Kopia bazy i folderu dokumentów w katalogu tymczasowym – testy nie zmieniają plików w repozytorium."""
    dokumenty = tmp_path / "dokumenty"
    dokumenty.mkdir()
    shutil.copy(U.katalog_dokumentow / PLIK_UDIP, dokumenty / PLIK_UDIP)
    shutil.copy(U.katalog_dokumentow / "Ustawy.txt", dokumenty / "Ustawy.txt")
    plik_oceny = tmp_path / "ocena.json"
    shutil.copy(U.plik_oceny, plik_oceny)
    u = replace(U, plik_oceny=plik_oceny, katalog_dokumentow=dokumenty, groq_api_key="test")
    app.dependency_overrides[pobierz_ustawienia] = lambda: u
    monkeypatch.setattr(analiza_aktu, "PRZERWA_PRZY_LIMICIE_S", 0)
    yield TestClient(app), u
    app.dependency_overrides.clear()


def wgraj(klient, falszywy, dane: bytes, nazwa_pliku="UDIP_nowelizacja.txt", zastepuje=PLIK_UDIP, **pola):
    app.dependency_overrides[pobierz_klienta] = lambda: falszywy
    formularz = {"zastepuje": zastepuje, "obowiazuje_od": DZIS.isoformat(), "publikator": "Dz. U. z 2026 r. poz. 1", **pola}
    odp = klient.post("/api/baza-wiedzy/analizy", data=formularz, files={"plik": (nazwa_pliku, dane)})
    assert odp.status_code == 202, odp.text
    return klient.get(f"/api/baza-wiedzy/analizy/{odp.json()['id']}").json()  # zadanie w tle już się wykonało


def zatwierdz_wszystko(klient, analiza, autor="AK"):
    decyzje = [{"id": z["id"], "zatwierdz": True} for z in analiza["zmiany"]]
    return klient.post(f"/api/baza-wiedzy/analizy/{analiza['id']}/zastosuj", json={"decyzje": decyzje, "autor": autor})


# ---------------------------------------------------------------- porównanie i dobór elementów


def test_porownanie_wykrywa_tylko_zmieniony_artykul(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / PLIK_UDIP).write_bytes(udip(False))
    (tmp_path / "b" / PLIK_UDIP).write_bytes(udip(True))
    roznice = analiza_aktu.porownaj(_indeksuj_dokument(tmp_path / "a" / PLIK_UDIP), _indeksuj_dokument(tmp_path / "b" / PLIK_UDIP))
    assert [(r.etykieta, r.rodzaj) for r in roznice] == [("Art. 13 UDIP", "zmieniony")]
    assert "21 dni" in roznice[0].po and "14 dni" in roznice[0].przed


def test_elementy_bazy_mozna_odczytac_i_podmienic():
    ocena = json.loads(U.plik_oceny.read_text(encoding="utf-8"))
    wszystkie = baza_wiedzy.elementy(ocena)
    assert len({e.klucz for e in wszystkie}) == len(wszystkie)
    for el in wszystkie:
        baza_wiedzy.ustaw_element(ocena, el.klucz, el.wartosc)  # podmiana na to samo nie psuje bazy
    assert ocena == json.loads(U.plik_oceny.read_text(encoding="utf-8"))


def test_walidacja_nowej_wartosci():
    przed = {"etap_id": "ETAP_10", "nazwa": "x", "zalozenia": ["a"]}
    with pytest.raises(baza_wiedzy.BladBazyWiedzy, match="brakuje pól"):
        baza_wiedzy.sprawdz_nowa_wartosc(przed, {"etap_id": "ETAP_10", "nazwa": "y"}, "k")
    with pytest.raises(baza_wiedzy.BladBazyWiedzy, match="identyfikatora"):
        baza_wiedzy.sprawdz_nowa_wartosc(przed, {**przed, "etap_id": "ETAP_99"}, "k")
    with pytest.raises(baza_wiedzy.BladBazyWiedzy, match="typ"):
        baza_wiedzy.sprawdz_nowa_wartosc(przed, {**przed, "zalozenia": "a"}, "k")
    baza_wiedzy.sprawdz_nowa_wartosc(przed, {**przed, "nazwa": "y", "nowe_pole": 1}, "k")


# ---------------------------------------------------------------- pełny przepływ przez API


def test_nowelizacja_propozycja_zapis_i_wycofanie(srodowisko):
    klient, u = srodowisko
    ocena = json.loads(u.plik_oceny.read_text(encoding="utf-8"))
    falszywy = FalszywyKlient(propozycja_etapu_10(ocena))
    analiza = wgraj(klient, falszywy, udip(True))

    assert analiza["status"] == "gotowa", analiza
    assert [r["etykieta"] for r in analiza["roznice"]] == ["Art. 13 UDIP"]
    klucze = [z["klucz"] for z in analiza["zmiany"]]
    assert klucze == ["metadane/akty_prawne_i_zrodla/UDIP", "algorytm_oceny_krokowej/ETAP_10"]
    # do modelu trafia tylko zmieniony przepis i element, który się na niego powołuje
    tresc = falszywy.zapytania[0][1]["content"]
    assert "21 dni" in tresc and "ETAP_10" in tresc and "ETAP_05" not in tresc

    odp = zatwierdz_wszystko(klient, analiza)
    assert odp.status_code == 200, odp.text
    wersja = odp.json()
    assert wersja["id"] == "v1" and wersja["akt_kod"] == "UDIP"

    nowa = json.loads(u.plik_oceny.read_text(encoding="utf-8"))
    etap = next(e for e in nowa["algorytm_oceny_krokowej"] if e["etap_id"] == "ETAP_10")
    assert "21 dni" in json.dumps(etap, ensure_ascii=False)
    assert next(a for a in nowa["metadane"]["akty_prawne_i_zrodla"] if a["skrot"] == "UDIP")["publikator"] == "Dz. U. z 2026 r. poz. 1"
    assert (u.katalog_dokumentow / PLIK_UDIP).read_bytes() == udip(True)  # wyszukiwarka przepisów widzi nowy tekst

    stan = klient.get("/api/baza-wiedzy").json()
    assert [(w["id"], w["status"]) for w in stan["wersje"]] == [("v1", "obowiazuje"), ("v0", "archiwalna")]

    # wycofanie przywraca poprzednią bazę i poprzedni tekst ustawy
    odp = klient.post("/api/baza-wiedzy/wersje/v1/wycofaj", json={"autor": "MW"})
    assert odp.status_code == 200 and odp.json()["wycofana"]["kto"] == "MW"
    przywrocona = json.loads(u.plik_oceny.read_text(encoding="utf-8"))
    assert przywrocona["algorytm_oceny_krokowej"] == ocena["algorytm_oceny_krokowej"]
    assert (u.katalog_dokumentow / PLIK_UDIP).read_bytes() == udip(False)
    assert klient.post("/api/baza-wiedzy/wersje/v0/wycofaj", json={"autor": "MW"}).status_code == 422


def test_odrzucone_zmiany_nie_trafiaja_do_bazy(srodowisko):
    klient, u = srodowisko
    ocena = json.loads(u.plik_oceny.read_text(encoding="utf-8"))
    analiza = wgraj(klient, FalszywyKlient(propozycja_etapu_10(ocena)), udip(True))
    decyzje = [{"id": z["id"], "zatwierdz": z["zrodlo"] == "metadane"} for z in analiza["zmiany"]]
    bez_decyzji = klient.post(f"/api/baza-wiedzy/analizy/{analiza['id']}/zastosuj", json={"decyzje": decyzje[:1], "autor": "AK"})
    assert bez_decyzji.status_code == 422
    odp = klient.post(f"/api/baza-wiedzy/analizy/{analiza['id']}/zastosuj", json={"decyzje": decyzje, "autor": "AK"})
    assert odp.status_code == 200
    nowa = json.loads(u.plik_oceny.read_text(encoding="utf-8"))
    assert nowa["algorytm_oceny_krokowej"] == ocena["algorytm_oceny_krokowej"]
    # ponowny zapis tej samej analizy jest zablokowany
    assert klient.post(f"/api/baza-wiedzy/analizy/{analiza['id']}/zastosuj", json={"decyzje": decyzje, "autor": "AK"}).status_code == 409


def test_poprawka_urzednika_zamiast_propozycji(srodowisko):
    klient, u = srodowisko
    ocena = json.loads(u.plik_oceny.read_text(encoding="utf-8"))
    analiza = wgraj(klient, FalszywyKlient(propozycja_etapu_10(ocena)), udip(True))
    zmiana = next(z for z in analiza["zmiany"] if z["zrodlo"] == "model")
    poprawka = {**zmiana["po"], "nazwa": "Termin – poprawione ręcznie"}
    zla = {k: v for k, v in zmiana["po"].items() if k != "zalozenia"}
    decyzje = [{"id": z["id"], "zatwierdz": True, "po": zla if z["id"] == zmiana["id"] else None} for z in analiza["zmiany"]]
    odp = klient.post(f"/api/baza-wiedzy/analizy/{analiza['id']}/zastosuj", json={"decyzje": decyzje, "autor": "AK"})
    assert odp.status_code == 422 and "brakuje pól" in odp.json()["detail"]
    decyzje = [{"id": z["id"], "zatwierdz": True, "po": poprawka if z["id"] == zmiana["id"] else None} for z in analiza["zmiany"]]
    assert klient.post(f"/api/baza-wiedzy/analizy/{analiza['id']}/zastosuj", json={"decyzje": decyzje, "autor": "AK"}).status_code == 200
    nowa = json.loads(u.plik_oceny.read_text(encoding="utf-8"))
    assert next(e for e in nowa["algorytm_oceny_krokowej"] if e["etap_id"] == "ETAP_10")["nazwa"] == "Termin – poprawione ręcznie"


def test_akt_zaplanowany_obowiazuje_od_daty_wejscia_w_zycie(srodowisko):
    klient, u = srodowisko
    ocena = json.loads(u.plik_oceny.read_text(encoding="utf-8"))
    jutro = DZIS + timedelta(days=30)
    analiza = wgraj(klient, FalszywyKlient(propozycja_etapu_10(ocena)), udip(True), obowiazuje_od=jutro.isoformat())
    assert zatwierdz_wszystko(klient, analiza).status_code == 200

    # dziś nic się nie zmienia – ani baza, ani tekst ustawy
    assert json.loads(u.plik_oceny.read_text(encoding="utf-8"))["algorytm_oceny_krokowej"] == ocena["algorytm_oceny_krokowej"]
    assert (u.katalog_dokumentow / PLIK_UDIP).read_bytes() == udip(False)
    stan = klient.get("/api/baza-wiedzy").json()
    assert stan["wersje"][0]["status"] == "zaplanowana"

    # wniosek, który wpłynie po wejściu w życie, jest oceniany według nowej wersji
    sciezka, wersja = baza_wiedzy.sciezka_oceny_na_dzien(u.plik_oceny, jutro)
    assert wersja == "v1" and "21 dni" in sciezka.read_text(encoding="utf-8")
    assert baza_wiedzy.sciezka_oceny_na_dzien(u.plik_oceny, DZIS)[1] == "v0"

    # w dniu wejścia w życie synchronizacja podmienia bazę i tekst ustawy
    baza_wiedzy.synchronizuj(u.plik_oceny, u.katalog_dokumentow, dzis=jutro)
    assert "21 dni" in json.dumps(json.loads(u.plik_oceny.read_text(encoding="utf-8"))["algorytm_oceny_krokowej"], ensure_ascii=False)
    assert (u.katalog_dokumentow / PLIK_UDIP).read_bytes() == udip(True)


def test_akt_niezwiazany_z_dip_nie_zmienia_bazy(srodowisko):
    klient, u = srodowisko
    przed = u.plik_oceny.read_bytes()
    falszywy = FalszywyKlient(json.dumps({"dotyczy": False, "uzasadnienie": "Ustawa o ruchu drogowym."}))
    tekst = "USTAWA z dnia 20 czerwca 1997 r. Prawo o ruchu drogowym\nArt. 1. 1. Ustawa określa zasady ruchu na drogach publicznych.".encode()
    analiza = wgraj(klient, falszywy, tekst, nazwa_pliku="prawo_o_ruchu_drogowym.txt", zastepuje="", nazwa="Prawo o ruchu drogowym", skrot="PRD")
    assert analiza["status"] == "nie_dotyczy" and "ruchu drogowym" in analiza["komunikat"]
    assert zatwierdz_wszystko(klient, analiza).status_code == 409
    assert u.plik_oceny.read_bytes() == przed


def test_nowy_akt_dodaje_zrodlo_i_plik(srodowisko):
    klient, u = srodowisko
    falszywy = FalszywyKlient(json.dumps({"dotyczy": True, "uzasadnienie": "Dotyczy ponownego wykorzystywania informacji."}))
    tekst = "USTAWA o otwartych danych\nArt. 1. Ustawa określa zasady udostępniania danych.\nArt. 2. 1. Dane udostępnia się bezpłatnie.".encode()
    analiza = wgraj(klient, falszywy, tekst, nazwa_pliku="Otwarte dane.txt", zastepuje="", nazwa="Ustawa o otwartych danych", skrot="UOD")
    assert analiza["status"] == "gotowa" and analiza["akt"]["nowy"]
    assert [z["klucz"] for z in analiza["zmiany"]] == ["metadane/akty_prawne_i_zrodla/UOD"]
    assert zatwierdz_wszystko(klient, analiza).status_code == 200
    assert (u.katalog_dokumentow / "Otwarte dane.txt").exists()
    zrodla = json.loads(u.plik_oceny.read_text(encoding="utf-8"))["metadane"]["akty_prawne_i_zrodla"]
    assert any(a["skrot"] == "UOD" for a in zrodla)
    # wycofanie usuwa dodany akt z folderu dokumentów
    klient.post("/api/baza-wiedzy/wersje/v1/wycofaj", json={"autor": "AK"})
    assert not (u.katalog_dokumentow / "Otwarte dane.txt").exists()


def test_limit_zapytan_groq_jest_przeczekiwany(srodowisko):
    klient, u = srodowisko
    ocena = json.loads(u.plik_oceny.read_text(encoding="utf-8"))
    falszywy = FalszywyKlient(BladLLM("limit", 429), propozycja_etapu_10(ocena))
    analiza = wgraj(klient, falszywy, udip(True))
    assert analiza["status"] == "gotowa" and len(falszywy.zapytania) == 2


def test_blad_modelu_konczy_analize_komunikatem(srodowisko):
    klient, _ = srodowisko
    analiza = wgraj(klient, FalszywyKlient(BladLLM("Groq odrzucił klucz API (401).", 502)), udip(True))
    assert analiza["status"] == "blad" and "401" in analiza["komunikat"]


def test_baza_zmieniona_w_trakcie_wymaga_ponownej_analizy(srodowisko):
    klient, u = srodowisko
    ocena = json.loads(u.plik_oceny.read_text(encoding="utf-8"))
    pierwsza = wgraj(klient, FalszywyKlient(propozycja_etapu_10(ocena)), udip(True))
    druga = wgraj(klient, FalszywyKlient(propozycja_etapu_10(ocena)), udip(True))
    assert zatwierdz_wszystko(klient, pierwsza).status_code == 200
    odp = zatwierdz_wszystko(klient, druga)
    assert odp.status_code == 409 and "ponownie" in odp.json()["detail"]


def test_wniosek_oceniany_wedlug_wersji_z_dnia_wplywu(srodowisko):
    klient, u = srodowisko
    ocena = json.loads(u.plik_oceny.read_text(encoding="utf-8"))
    analiza = wgraj(klient, FalszywyKlient(propozycja_etapu_10(ocena)), udip(True))
    assert zatwierdz_wszystko(klient, analiza).status_code == 200
    # wersja v1 obowiązuje od dziś – wniosek sprzed wejścia w życie oceniamy według v0
    wczoraj = (DZIS - timedelta(days=1)).isoformat()
    model = json.dumps({"werdykt": "MOZNA_UDOSTEPNIC", "uzasadnienie": "x", "projekt_odpowiedzi": "Pismo"})
    falszywy = FalszywyKlient(model, model)
    app.dependency_overrides[pobierz_klienta] = lambda: falszywy
    tresc = "Wnoszę o udostępnienie informacji o terminie załatwienia wniosków o informację publiczną w 2026 r."
    stara = klient.post("/api/propozycja-odpowiedzi", json={"tresc": tresc, "data_wplywu": wczoraj}).json()
    nowa = klient.post("/api/propozycja-odpowiedzi", json={"tresc": tresc, "data_wplywu": DZIS.isoformat()}).json()
    assert "wersji v0" in " ".join(stara["ostrzezenia"])
    assert not any("wersji" in o for o in nowa["ostrzezenia"])
