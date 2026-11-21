import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from inteligentny_asystent_urzednika.app import app, pobierz_klienta
from inteligentny_asystent_urzednika.config import wczytaj_ustawienia
from inteligentny_asystent_urzednika.groq_klient import BladLLM, KlientGroq
from inteligentny_asystent_urzednika.propozycja import ZAPAS_TOKENOW, Wniosek, szacuj_tokeny, ujednolic_pismo, zbuduj_wiadomosci, zweryfikuj
from inteligentny_asystent_urzednika.wiedza import wczytaj_wiedze

U = wczytaj_ustawienia()
WIEDZA = wczytaj_wiedze(U.plik_oceny, U.plik_werdyktow, U.plik_wzorow)
WNIOSEK = Wniosek(
    tresc="Wnoszę o udostępnienie informacji, ile psów i kotów przyjęło schronisko w 2026 r. "
    "oraz jaki był koszt opieki. Jan Testowy, jan@example.com",
    numer="BKS.IV.1431.700.2026",
    data_wplywu="2026-11-20",
)

ODPOWIEDZ_MODELU = {
    "werdykt": "MOZNA_UDOSTEPNIC",
    "uzasadnienie": "Informacja o wydatkach publicznych i realizacji zadania.",
    "podstawy_prawne": ["Art. 6 ust. 1 pkt 5 UDIP", "Art. 13 ust. 1 UDIP"],
    "komorka_merytoryczna": "Wydział Zieleni i Gospodarki Komunalnej",
    "podobne_sprawy": [
        {"sygnatura": "BKS.IV.1431.543.2026", "dlaczego": "opieka nad bezdomnymi zwierzętami"},
        {"sygnatura": "BKS.IV.1431.999.2026", "dlaczego": "wymyślona"},
    ],
    "dane_do_anonimizacji": ["imię i nazwisko wnioskodawcy", "adres e-mail"],
    "do_weryfikacji": ["liczby z wydziału"],
    "projekt_odpowiedzi": "Bydgoszcz, [[data]]\n…\nZ poważaniem\n[[podpis]]",
}


class FałszywyKlient:
    def __init__(self, odpowiedz: str):
        self.odpowiedz = odpowiedz
        self.wiadomosci: list | None = None

    async def czat_json(self, wiadomosci):
        self.wiadomosci = wiadomosci
        return self.odpowiedz


def test_pelny_kontekst_zawiera_model_prawny_i_wszystkie_sprawy():
    wiadomosci, _ = zbuduj_wiadomosci(WNIOSEK, WIEDZA, "pelny")
    tresc = wiadomosci[1]["content"]
    for etap in (f"ETAP_{i:02d}" for i in range(1, 13)):
        assert etap in tresc
    for sygnatura in WIEDZA.sygnatury:
        assert sygnatura in tresc
    assert "MOZNA_Z_ANONIMIZACJA" in tresc
    assert WNIOSEK.tresc in tresc
    assert wiadomosci[0]["role"] == "system"


def test_wybrany_kontekst_miesci_sie_w_darmowym_planie():
    budzet = 8000 - 2000 - ZAPAS_TOKENOW
    wiadomosci, ostrzezenia = zbuduj_wiadomosci(WNIOSEK, WIEDZA, "wybrany", budzet)
    tresc = wiadomosci[1]["content"]
    assert szacuj_tokeny(wiadomosci) <= budzet
    assert not ostrzezenia
    for etap in (f"ETAP_{i:02d}" for i in range(1, 13)):
        assert etap in tresc  # wszystkie etapy oceny zawsze są w kontekście
    assert "MOZNA_Z_ANONIMIZACJA" in tresc
    assert "BKS.IV.1431.543.2026" in tresc  # najbardziej podobna sprawa (schronisko)
    assert WNIOSEK.tresc in tresc


def test_wybrany_kontekst_skraca_bardzo_dlugi_wniosek():
    dlugi = Wniosek(tresc="Proszę o udostępnienie dokumentów dotyczących inwestycji. " * 400)
    budzet = 8000 - 2000 - ZAPAS_TOKENOW
    wiadomosci, ostrzezenia = zbuduj_wiadomosci(dlugi, WIEDZA, "wybrany", budzet)
    assert szacuj_tokeny(wiadomosci) <= budzet + 50
    assert ostrzezenia and "znaków" in ostrzezenia[0]


def test_podobne_sprawy_sa_dobierane_do_tresci():
    wiadomosci, _ = zbuduj_wiadomosci(
        Wniosek(tresc="Ile uczniów uczy się w szkołach podstawowych w Bydgoszczy i ilu jest obcokrajowców?"), WIEDZA
    )
    assert "BKS.IV.1431.307.2025" in wiadomosci[1]["content"]


def test_weryfikacja_odsiewa_halucynacje():
    p = zweryfikuj("```json\n" + json.dumps(ODPOWIEDZ_MODELU) + "\n```", WIEDZA, "test-model")
    assert [s.sygnatura for s in p.podobne_sprawy] == ["BKS.IV.1431.543.2026"]
    assert any("999" in o for o in p.ostrzezenia)
    assert p.werdykt_opis.startswith("Informacja podlega udostępnieniu")


def test_weryfikacja_nieznany_werdykt():
    p = zweryfikuj(json.dumps({**ODPOWIEDZ_MODELU, "werdykt": "COS_INNEGO"}), WIEDZA)
    assert p.werdykt_opis == ""
    assert any("nieznany werdykt" in o for o in p.ostrzezenia)


def test_weryfikacja_zly_json():
    with pytest.raises(BladLLM):
        zweryfikuj("to nie jest json", WIEDZA)


@pytest.fixture
def klient_api():
    falszywy = FałszywyKlient(json.dumps(ODPOWIEDZ_MODELU))
    app.dependency_overrides[pobierz_klienta] = lambda: falszywy
    yield TestClient(app), falszywy
    app.dependency_overrides.clear()


def test_endpoint_zwraca_propozycje(klient_api):
    klient, falszywy = klient_api
    odp = klient.post("/api/propozycja-odpowiedzi", json=WNIOSEK.model_dump())
    assert odp.status_code == 200, odp.text
    dane = odp.json()
    assert dane["werdykt"] == "MOZNA_UDOSTEPNIC"
    assert len(dane["podobne_sprawy"]) == 1
    assert "ETAP_01" in falszywy.wiadomosci[1]["content"]


def test_endpoint_waliduje_wejscie(klient_api):
    klient, _ = klient_api
    assert klient.post("/api/propozycja-odpowiedzi", json={"tresc": "za krótko"}).status_code == 422


def test_zdrowie():
    dane = TestClient(app).get("/api/zdrowie").json()
    assert dane["status"] == "ok" and dane["spraw_w_archiwum"] == 8 and dane["werdyktow"] == 7


def _groq(handler) -> KlientGroq:
    return KlientGroq("klucz-testowy", "model-testowy", "https://groq.test/v1/chat/completions", 5, transport=httpx.MockTransport(handler))


def test_klient_groq_wysyla_poprawne_zapytanie():
    zapytania = []

    def handler(req: httpx.Request):
        zapytania.append(req)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{\"ok\": true}"}}]})

    wynik = asyncio.run(_groq(handler).czat_json([{"role": "user", "content": "x"}]))
    assert wynik == '{"ok": true}'
    cialo = json.loads(zapytania[0].content)
    assert cialo["model"] == "model-testowy"
    assert cialo["response_format"] == {"type": "json_object"}
    assert zapytania[0].headers["authorization"] == "Bearer klucz-testowy"
    assert cialo["max_completion_tokens"] == 2000


def test_klient_groq_ucieta_odpowiedz():
    odp = {"choices": [{"message": {"content": "{\"werdykt\": \"MO"}, "finish_reason": "length"}]}
    with pytest.raises(BladLLM) as e:
        asyncio.run(_groq(lambda req: httpx.Response(200, json=odp)).czat_json([]))
    assert "GROQ_MAX_TOKENS" in e.value.komunikat


@pytest.mark.parametrize(
    ("status", "tekst", "fragment"),
    [
        (401, '{"error":{"message":"Invalid API Key"}}', "klucz API"),
        (413, '{"error":{"message":"Request too large"}}', "KONTEKST_PRAWNY=wybrany"),
        (429, '{"error":{"message":"Rate limit reached for tokens per minute"}}', "Odczekaj minutę"),
        (500, '{"error":{"message":"boom"}}', "boom"),
    ],
)
def test_klient_groq_bledy(status, tekst, fragment):
    with pytest.raises(BladLLM) as e:
        asyncio.run(_groq(lambda req: httpx.Response(status, text=tekst)).czat_json([]))
    assert fragment in e.value.komunikat


def test_kontekst_zawiera_liste_jednostek_umb():
    wiadomosci, _ = zbuduj_wiadomosci(WNIOSEK, WIEDZA)
    assert "Wydział Administracji Budowlanej" in wiadomosci[1]["content"]
    assert "Biuro Rady Miasta" in wiadomosci[1]["content"]


def _wzory_w_kontekscie(tresc: str) -> list[str]:
    wiadomosci, _ = zbuduj_wiadomosci(Wniosek(tresc=tresc), WIEDZA, "wybrany", 8000 - 2000 - ZAPAS_TOKENOW)
    blok = wiadomosci[1]["content"].split("WZORY PISM UMB (dobrane do sprawy):\n", 1)[1].split("\n\nNOWY WNIOSEK", 1)[0]
    return [w["id"] for w in json.loads(blok)["wzory"]]


def test_plik_wzorow_jest_kompletny():
    werdykty_we_wzorach = {w for wz in WIEDZA.wzory["wzory"] for w in wz["werdykty"]}
    assert werdykty_we_wzorach <= set(WIEDZA.slownik_werdyktow)
    for wz in WIEDZA.wzory["wzory"]:
        assert wz["tresc"] and wz["kiedy"] and wz["nazwa"]
    assert "Jezuicka 1" in WIEDZA.wzory["naglowek"]
    assert WIEDZA.wzory["podpis"].startswith("Łączę wyrazy szacunku")


def test_wzory_dobierane_do_sprawy():
    # sprawa jak 543 (schronisko) -> wzory udostępnienia, najpierw punkt po punkcie / w treści
    schronisko = _wzory_w_kontekscie("Ile psów i kotów przyjęło schronisko w 2026 r. i jaki był koszt opieki nad bezdomnymi zwierzętami?")
    assert schronisko[0].startswith("udostepnienie")
    # sprawa jak 17 (umowa ze spółką, UMB nie jest dysponentem) -> pismo informacyjne
    umowa = _wzory_w_kontekscie("Proszę o pełną dokumentację realizacji umowy nr 102/TT/2019 ze spółką Jakotako, aneksy i faktury.")
    assert umowa[0] in {"nieposiadanie_wskazanie_dysponenta", "brak_danych"}


def test_kontekst_wybrany_z_wzorami_miesci_sie_w_limicie():
    budzet = 8000 - 2000 - ZAPAS_TOKENOW
    wiadomosci, ostrzezenia = zbuduj_wiadomosci(WNIOSEK, WIEDZA, "wybrany", budzet)
    assert szacuj_tokeny(wiadomosci) <= budzet and not ostrzezenia
    assert "Łączę wyrazy szacunku" in wiadomosci[1]["content"]


def test_weryfikacja_wzoru():
    p = zweryfikuj(json.dumps({**ODPOWIEDZ_MODELU, "wzor": "udostepnienie_w_tresci"}), WIEDZA)
    assert p.wzor_nazwa == "Udostępnienie informacji w treści pisma"
    p = zweryfikuj(json.dumps({**ODPOWIEDZ_MODELU, "wzor": "wymyslony"}), WIEDZA)
    assert p.wzor == "" and p.wzor_nazwa == ""


def test_ujednolicenie_naglowka_i_podpisu():
    pismo = (
        "URZĄD MIASTA BYDGOSZCZY\nBiuro Komunikacji Spoleczne\n85-102 Bydgoszcz\ntel. x\ne-mail: bks@um.bydgoszcz.pl\n"
        "Bydgoszcz, dnia [[data]] r.\nTreść.\nŁączę wyrazy szacunku,\nBiuro Komunikacji Spojalnej\nUrząd Miasta"
    )
    wynik = ujednolic_pismo(pismo, WIEDZA.wzory)
    assert wynik.startswith(WIEDZA.wzory["naglowek"])
    assert wynik.endswith(WIEDZA.wzory["podpis"])
    assert "Spojalnej" not in wynik and "Treść." in wynik


def test_ujednolicenie_dodaje_brakujacy_naglowek():
    wynik = ujednolic_pismo("Bydgoszcz, dnia [[data]] r.\nTreść.", WIEDZA.wzory)
    assert wynik.startswith("URZĄD MIASTA BYDGOSZCZY")
