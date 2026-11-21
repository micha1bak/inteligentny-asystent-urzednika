import asyncio
import json
import re
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from inteligentny_asystent_urzednika.app import app, pobierz_klienta
from inteligentny_asystent_urzednika.config import wczytaj_ustawienia
from inteligentny_asystent_urzednika.groq_klient import BladLLM, KlientGroq
from inteligentny_asystent_urzednika.wzor.pismo import POLA_KODU, DanePisma, numer_sprawy, zloz_pismo
from inteligentny_asystent_urzednika.propozycja import ZAPAS_TOKENOW, Wniosek, szacuj_tokeny, zbuduj_wiadomosci, zweryfikuj
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
    "wzor": "udostepnienie_punkt_po_punkcie",
    "forma": "Pan",
    "adresat": ["jan@example.com"],
    "pola": {
        "zakres_wniosku": "liczby psów i kotów przyjętych przez schronisko w 2026 r. oraz kosztu opieki",
        "odpowiedzi": ["[[do uzupełnienia: liczba psów i kotów]]", "[[do uzupełnienia: koszt opieki]]"],
        "wymyslone_pole": "nie powinno trafić do pisma",
    },
    "zalaczniki": [],
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
        # każde «pole» w treści jest zdefiniowane albo uzupełniane przez kod
        uzyte = set(re.findall(r"«([a-z_]+)»", wz["tresc"]))
        assert uzyte <= set(wz.get("pola", {})) | POLA_KODU, wz["id"]
    assert WIEDZA.wzory["naglowek"] == "URZĄD MIASTA BYDGOSZCZY\nBiuro Komunikacji Społecznej"
    assert "Jezuicka 1" in WIEDZA.wzory["stopka"]
    assert WIEDZA.wzory["podpis"].startswith("Łączę wyrazy szacunku")


def test_wzory_dobierane_do_sprawy():
    # sprawa jak 543 (schronisko) -> wzory udostępnienia, najpierw punkt po punkcie / w treści
    schronisko = _wzory_w_kontekscie("Ile psów i kotów przyjęło schronisko w 2026 r. i jaki był koszt opieki nad bezdomnymi zwierzętami?")
    assert schronisko[0].startswith(("udostepnienie", "odpowiedz_po_kwerendzie"))
    # sprawa jak 17 (umowa ze spółką, UMB nie jest dysponentem) -> pismo informacyjne
    umowa = _wzory_w_kontekscie("Proszę o pełną dokumentację realizacji umowy nr 102/TT/2019 ze spółką Jakotako, aneksy i faktury.")
    assert umowa[0] in {"nieposiadanie_wskazanie_dysponenta", "brak_danych"}


def test_weryfikacja_wzoru():
    p = zweryfikuj(json.dumps({**ODPOWIEDZ_MODELU, "wzor": "udostepnienie_w_tresci"}), WIEDZA)
    assert p.wzor_nazwa == "Udostępnienie informacji w treści pisma"

    # nieznany wzór przy zwykłym werdykcie -> uniwersalny wzór z zachowaniem punktów, daty wniosku i podstaw prawnych
    p = zweryfikuj(json.dumps({**ODPOWIEDZ_MODELU, "wzor": "wymyslony"}), WIEDZA, "m", WNIOSEK)
    assert p.wzor == "odpowiedz_uniwersalna" and p.wzor_nazwa == "Uniwersalny wzór odpowiedzi"
    assert any("nieznany wzór" in o for o in p.ostrzezenia)
    assert "brak pasującego wzoru" not in p.projekt_odpowiedzi
    assert "z dnia 20 listopada 2026 r." in p.projekt_odpowiedzi
    assert "liczby psów i kotów" in p.projekt_odpowiedzi
    assert "Ad 1" in p.projekt_odpowiedzi and "Ad 2" in p.projekt_odpowiedzi
    assert "art. 6 ust. 1 pkt 5 oraz art. 13 ust. 1 ustawy z dnia 6 września 2001 r. o dostępie do informacji publicznej" in p.projekt_odpowiedzi

    # pusty wzór przy decyzji odmownej -> kompletna decyzja administracyjna (art. 107 KPA + art. 16 UDIP + SKO)
    p_decyzja = zweryfikuj(
        json.dumps({
            **ODPOWIEDZ_MODELU,
            "werdykt": "NIE_MOZNA_DECYZJA_ODMOWNA",
            "podstawy_prawne": ["Art. 5 ust. 2 UDIP", "Art. 16 ust. 1 UDIP", "§ 11 ust. 9 Zarządzenia Nr 535/2024"],
            "wzor": "",
            "pola": {},
        }),
        WIEDZA,
        "m",
        WNIOSEK,
    )
    assert p_decyzja.wzor == "decyzja_administracyjna"
    assert p_decyzja.pismo["tytul"] == ["DECYZJA"]
    assert "brak pasującego wzoru" not in p_decyzja.projekt_odpowiedzi
    assert "w zw. z art. 5 ust. 2 ustawy z dnia 6 września 2001 r. o dostępie do informacji publicznej" in p_decyzja.projekt_odpowiedzi
    assert "Zarządzenia Nr 535/2024" not in p_decyzja.projekt_odpowiedzi
    assert "orzekam:" in p_decyzja.projekt_odpowiedzi
    assert "UZASADNIENIE" in p_decyzja.projekt_odpowiedzi
    assert "POUCZENIE" in p_decyzja.projekt_odpowiedzi
    assert "Samorządowego Kolegium Odwoławczego w Bydgoszczy" in p_decyzja.projekt_odpowiedzi
    assert "art. 127a" in p_decyzja.projekt_odpowiedzi
    assert "art. 16 ust. 2 pkt 2" in p_decyzja.projekt_odpowiedzi
    assert "z up. Prezydenta Miasta Bydgoszczy" in p_decyzja.projekt_odpowiedzi
    assert any("radcy prawnego" in d for d in p_decyzja.do_weryfikacji)

    # pusty wzór przy decyzji o umorzeniu
    p_umorz = zweryfikuj(
        json.dumps({**ODPOWIEDZ_MODELU, "werdykt": "NIE_MOZNA_UMORZENIE_DECYZJA", "wzor": "", "pola": {}}),
        WIEDZA,
        "m",
        WNIOSEK,
    )
    assert p_umorz.wzor == "decyzja_administracyjna"
    assert "umorzyć postępowanie" in p_umorz.projekt_odpowiedzi

    pismo_none, _ = zloz_pismo(
        None,
        WIEDZA.wzory,
        DanePisma(pola={"zakres_wniosku": "testu", "stanowisko_glowne": "Treść odpowiedzi."}),
    )
    assert "brak pasującego wzoru" not in pismo_none.tekst and "Treść odpowiedzi." in pismo_none.tekst


def test_ai_formuuje_gotowy_mail_z_podstaw_prawnych():
    from inteligentny_asystent_urzednika.propozycja import zaproponuj_odpowiedz

    # 1) Model od razu zwraca treść maila w tresc_pisma dla dopasowanych podstaw prawnych
    odp_z_tekstem = {
        **ODPOWIEDZ_MODELU,
        "werdykt": "NIE_MOZNA_PISMO_INFORMACYJNE",
        "podstawy_prawne": ["Art. 10 ust. 1 UDIP"],
        "wzor": "odpowiedz_ai",
        "pola": {},
        "tresc_pisma": [
            "W odpowiedzi na Pana wniosek informuję, że na podstawie art. 10 ust. 1 UDIP wnioskowane dane są opublikowane w BIP.",
            "Dokumenty są dostępne pod adresem [[do uzupełnienia: link do BIP]].",
        ],
    }
    p = zweryfikuj(json.dumps(odp_z_tekstem), WIEDZA, "m", WNIOSEK)
    assert p.wzor == "odpowiedz_ai"
    assert "AI na podstawie podstaw prawnych" in p.wzor_nazwa
    assert "art. 10 ust. 1 UDIP" in p.projekt_odpowiedzi
    assert p.projekt_odpowiedzi.startswith("URZĄD MIASTA BYDGOSZCZY")
    assert "Szanowny Panie," in p.projekt_odpowiedzi

    # 2) Gdy pierwsze wywołanie Groq nie zwróciło tresc_pisma, ale są podstawy prawne i brak szczegółowego wzoru,
    #    zaproponuj_odpowiedz() wywołuje Groq po gotowy mail w oparciu o podstawy prawne
    class DwuetapowyKlient:
        def __init__(self, odpowiedzi):
            self.odpowiedzi = list(odpowiedzi)
            self.wywolania = 0

        async def czat_json(self, wiadomosci):
            self.wywolania += 1
            wynik = self.odpowiedzi.pop(0)
            if isinstance(wynik, Exception):
                raise wynik
            return wynik

    klient = DwuetapowyKlient([
        json.dumps({**ODPOWIEDZ_MODELU, "wzor": "", "pola": {}, "podstawy_prawne": ["Art. 1 ust. 2 UDIP"]}),
        json.dumps({"tytul_pisma": [], "tresc_pisma": ["Informuję, że na mocy art. 1 ust. 2 UDIP obowiązuje odrębny tryb."]}),
    ])
    p2 = asyncio.run(zaproponuj_odpowiedz(WNIOSEK, WIEDZA, klient, "test-model"))
    assert klient.wywolania == 2
    assert p2.wzor == "odpowiedz_ai"
    assert "odrębny tryb" in p2.projekt_odpowiedzi

    # 3) Gdy brak podstaw prawnych – bez drugiego wywołania Groq, działa uniwersalny wzorzec
    klient_bez_podstaw = DwuetapowyKlient([
        json.dumps({**ODPOWIEDZ_MODELU, "wzor": "", "pola": {}, "podstawy_prawne": []}),
    ])
    p3 = asyncio.run(zaproponuj_odpowiedz(WNIOSEK, WIEDZA, klient_bez_podstaw, "test-model"))
    assert klient_bez_podstaw.wywolania == 1
    assert p3.wzor == "odpowiedz_uniwersalna"
    assert "brak pasującego wzoru" not in p3.projekt_odpowiedzi

    # 4) Gdy drugie wywołanie Groq zwróci błąd (np. limit TPM 429) – bezpieczny fallback na wzorzec
    klient_limit = DwuetapowyKlient([
        json.dumps({**ODPOWIEDZ_MODELU, "wzor": "", "pola": {}, "podstawy_prawne": ["Art. 5 ust. 2 UDIP"]}),
        BladLLM("limit", 429),
    ])
    p4 = asyncio.run(zaproponuj_odpowiedz(WNIOSEK, WIEDZA, klient_limit, "test-model"))
    assert p4.wzor == "odpowiedz_uniwersalna"
    assert "art. 5 ust. 2 ustawy" in p4.projekt_odpowiedzi


def test_pismo_skladane_przez_kod_ze_wzoru():
    p = zweryfikuj(json.dumps(ODPOWIEDZ_MODELU), WIEDZA, "m", WNIOSEK)
    linie = p.projekt_odpowiedzi.splitlines()
    assert linie[:2] == ["URZĄD MIASTA BYDGOSZCZY", "Biuro Komunikacji Społecznej"]
    assert re.fullmatch(r"Bydgoszcz, dnia \d{1,2} [a-zźśęó]+ \d{4} r\.", linie[2])
    assert linie[3] == "BKS.IV.1431.700.2026" and linie[4] == "jan@example.com"
    # struktura do podglądu A4
    assert p.pismo["znak"] == "BKS.IV.1431.700.2026" and p.pismo["adresat"] == ["jan@example.com"]
    assert [b["typ"] for b in p.pismo["tresc"]] == ["akapit", "ad", "akapit", "ad", "akapit"]
    assert p.pismo["zakonczenie"] == "Łączę wyrazy szacunku," and p.pismo["podpis"][0] == "Biuro Komunikacji Społecznej"
    # stałe sformułowania wzoru + pola modelu + komórka z oceny
    assert linie[5].startswith("W odpowiedzi na wystosowany przez Pana wniosek o udostępnienie informacji publicznej w zakresie liczby psów")
    assert "tj. Wydział Zieleni i Gospodarki Komunalnej Urzędu Miasta Bydgoszczy informuję, co następuje." in linie[5]
    assert linie[6:10] == ["Ad 1", "[[do uzupełnienia: liczba psów i kotów]]", "Ad 2", "[[do uzupełnienia: koszt opieki]]"]
    assert "wymyslone_pole" not in p.pola_wzoru and "nie powinno" not in p.projekt_odpowiedzi
    assert p.projekt_odpowiedzi.endswith(WIEDZA.wzory["podpis"] + "\n\n" + WIEDZA.wzory["stopka"])


def test_brakujace_pole_oznaczone_do_uzupelnienia():
    odp = {**ODPOWIEDZ_MODELU, "wzor": "udostepnienie_w_tresci", "forma": "Pani", "pola": {"zakres_wniosku": "liczby mieszkańców"}}
    p = zweryfikuj(json.dumps(odp), WIEDZA, "m", WNIOSEK)
    assert "Szanowna Pani,\nw odpowiedzi na wystosowany przez Panią wniosek" in p.projekt_odpowiedzi
    assert "informuję, że [[do uzupełnienia: udostępniana informacja]]." in p.projekt_odpowiedzi
    assert any(w.startswith("Uzupełnij w piśmie: udostępniana informacja") for w in p.do_weryfikacji)


def test_pismo_opcjonalne_linie_zalaczniki_i_kropki():
    wzor = WIEDZA.wzor("wezwanie_do_doprecyzowania")
    dane = DanePisma(pola={"zakres_wniosku": "budynku", "niejasnosc": "dokumentacji", "co_wskazac": "o jakie akta chodzi."},
                     forma="Pan", znak_sprawy="BKS.IV.1431.509.2026", komorka_merytoryczna="Wydział Administracji Budowlanej")
    pismo, braki = zloz_pismo(wzor, WIEDZA.wzory, dane)
    tekst = pismo.tekst
    assert pismo.tytul == ["WEZWANIE DO DOPRECYZOWANIA", "ZAKRESU OTRZYMANEGO WNIOSKU"] and pismo.tresc[0].typ == "zwrot"
    assert not braki and "WEZWANIE DO DOPRECYZOWANIA" in tekst
    assert "o jakie akta chodzi.\n" in tekst and "chodzi.." not in tekst
    assert "nowy termin" not in tekst  # opcjonalna linia pominięta bez wartości
    dane.pola["nowy_termin"] = "18 września br."
    assert "wskazując dzień 18 września br." in zloz_pismo(wzor, WIEDZA.wzory, dane)[0].tekst

    zal = DanePisma(pola={"zakres_wniosku": "x", "odpowiedzi": ["a"]}, zalaczniki=["Informacja_293", "Uchwała"], forma="Państwo")
    pismo, _ = zloz_pismo(WIEDZA.wzor("udostepnienie_punkt_po_punkcie"), WIEDZA.wzory, zal)
    assert "Załączniki:\n1. Informacja_293\n2. Uchwała" in pismo.tekst
    assert pismo.adresat == []  # brak adresu we wniosku -> brak linii adresata (jak w oryginałach)
    pismo, _ = zloz_pismo(WIEDZA.wzor("udostepnienie_w_zalaczniku"), WIEDZA.wzory, DanePisma(pola={"zakres_wniosku": "x"}, znak_sprawy="BKS.IV.1431.307.2025"))
    assert "Załącznik: Informacja_307" in pismo.tekst and "[[Pana / Panią / Państwa]]" in pismo.tekst
    pismo, _ = zloz_pismo(WIEDZA.wzor("odpowiedz_po_kwerendzie"), WIEDZA.wzory, DanePisma(forma="Pani"))
    assert pismo.tresc[0].tekst.startswith("w nawiązaniu")  # oryginał 543 nie ma zwrotu


def test_numer_sprawy():
    assert numer_sprawy("BKS.IV.1431.307.2025") == "307" and numer_sprawy("") == ""


def test_kontekst_wybrany_z_wzorami_miesci_sie_w_limicie():
    budzet = 8000 - 2000 - ZAPAS_TOKENOW
    wiadomosci, ostrzezenia = zbuduj_wiadomosci(WNIOSEK, WIEDZA, "wybrany", budzet)
    assert szacuj_tokeny(wiadomosci) <= budzet and not ostrzezenia
    tresc = wiadomosci[1]["content"]
    assert "zasady_wypelniania" in tresc and "«zakres_wniosku»" in tresc
    assert "Łączę wyrazy szacunku" not in tresc  # podpis wstawia kod, nie model


# ---------------------------------------------------------------- konwersja plików (/api/konwersja)
from pathlib import Path

from inteligentny_asystent_urzednika.konwersja import ocr_llm

PRZYKLADY = Path(__file__).resolve().parents[1] / "Przykładowe wnioski i odpowiedzi"


def _wyslij(nazwa: str, dane: bytes | None = None):
    dane = dane if dane is not None else (PRZYKLADY / nazwa).read_bytes()
    return TestClient(app).post("/api/konwersja", files={"plik": (nazwa, dane)})


@pytest.fixture
def bez_modelu(monkeypatch):
    """Zastępuje zapytania do modelu: wszystkie strony drukowane, skan „przepisany”."""
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(ocr_llm, "czy_odreczne", lambda obraz: False)
    monkeypatch.setattr(ocr_llm, "_zapytaj", lambda obraz, prompt, max_tokens=4096: "TEKST ZE SKANU")


def test_konwersja_docx_bez_modelu(monkeypatch):
    monkeypatch.setattr(ocr_llm, "_zapytaj", lambda *a, **k: pytest.fail("DOCX nie może trafiać do modelu"))
    dane = _wyslij("Wniosek - BKS.IV.1431.15.2026.docx").json()
    assert dane["zrodlo"] == "tekst" and not dane["odreczny"]
    assert len(dane["tekst"]) > 50


@pytest.mark.parametrize("nazwa", sorted(p.name for p in PRZYKLADY.glob("Wniosek*.pdf")))
def test_konwersja_pdf(bez_modelu, nazwa):
    dane = _wyslij(nazwa).json()
    assert not dane["odreczny"] and dane["stron"] >= 1
    assert dane["tekst"]
    if dane["zrodlo"] == "model":
        assert "TEKST ZE SKANU" in dane["tekst"] and dane["strony_z_modelu"]


def test_konwersja_odrzuca_pismo_odreczne(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(ocr_llm, "czy_odreczne", lambda obraz: True)
    dane = _wyslij("Wniosek - BKS.IV.1431.16.2026.pdf").json()
    assert dane["odreczny"] and dane["tekst"] == "" and dane["strony_odreczne"]
    assert "odręczne" in dane["komunikat"]


def test_konwersja_nieobslugiwany_format():
    assert _wyslij("wniosek.txt", b"abc").status_code == 415


def test_konwersja_bez_modelu_offline(monkeypatch):
    """Tryb bez modelu (offline): PDF z warstwą tekstową czytany lokalnie, skan – czytelny komunikat 503."""
    monkeypatch.setattr(ocr_llm, "model_dostepny", lambda: False)
    monkeypatch.setattr(ocr_llm, "_zapytaj", lambda *a, **k: pytest.fail("bez modelu nie wolno wołać OCR"))
    tekstowy = _wyslij("Wniosek - BKS.IV.1431.590.2026.pdf")
    assert tekstowy.status_code == 200 and "Astoria" in tekstowy.json()["tekst"]
    skan = _wyslij("Wniosek - BKS.IV.1431.16.2026.pdf")
    assert skan.status_code == 503 and "OCR" in skan.json()["detail"]


def test_odpowiedzi_wydzialow_trafiaja_do_modelu_i_mieszcza_sie_w_limicie():
    from inteligentny_asystent_urzednika.propozycja import OdpowiedzWydzialuDoPisma

    budzet = 8000 - 2000 - ZAPAS_TOKENOW
    w = Wniosek(
        tresc=WNIOSEK.tresc, numer=WNIOSEK.numer,
        odpowiedzi_wydzialow=[
            OdpowiedzWydzialuDoPisma(wydzial="Wydział Zieleni i Gospodarki Komunalnej",
                                     tresc="W 2026 r. schronisko przyjęło 894 psy i 607 kotów. " * 60),
            OdpowiedzWydzialuDoPisma(wydzial="Wydział Księgowości", tresc="Koszt opieki: 3 143 761,14 zł."),
        ],
    )
    wiadomosci, _ = zbuduj_wiadomosci(w, WIEDZA, "wybrany", budzet)
    tresc = wiadomosci[1]["content"]
    assert "ODPOWIEDZI WYDZIAŁÓW" in tresc and "3 143 761,14 zł" in tresc and "894 psy" in tresc
    assert 'wydzial="Wydział Zieleni i Gospodarki Komunalnej"' in tresc
    assert szacuj_tokeny(wiadomosci) <= budzet + 50
    assert "ODPOWIEDZI WYDZIAŁÓW" in wiadomosci[0]["content"]  # reguła w poleceniu systemowym
    assert "ODPOWIEDZI WYDZIAŁÓW" not in zbuduj_wiadomosci(WNIOSEK, WIEDZA, "wybrany", budzet)[0][1]["content"]


def test_podobne_sprawy_i_wnioski_z_ostatniego_roku():
    from inteligentny_asystent_urzednika.baza_wnioskow import WniosekZapisany
    from inteligentny_asystent_urzednika.podobne import ZapytanieOPodobne, znajdz

    def w(id_, data, temat):
        return WniosekZapisany(id=id_, numer=f"N{id_}", data_wplywu=data, temat=temat, wnioskodawca="", inicjaly="",
                               tresc=temat, status="brak_dzialan", utworzono="", zaktualizowano="")

    wnioski = [w("1", "2026-05-01", "Koszt opieki nad bezdomnymi psami i kotami w schronisku"),
               w("2", "2024-01-10", "Koszt opieki nad bezdomnymi psami w schronisku"),  # starszy niż rok
               w("3", "2026-06-01", "Wycinka drzew przy ul. Fordońskiej")]
    z = ZapytanieOPodobne(tresc="Ile psów i kotów przyjęło schronisko i jaki był koszt opieki nad zwierzętami?",
                          data_odniesienia="2026-11-21", pomin_id="9")
    wynik = znajdz(z, WIEDZA.sprawy, wnioski)
    assert wynik.sprawy[0].sygnatura == "BKS.IV.1431.543.2026" and 0 < wynik.sprawy[0].podobienstwo <= 1
    assert [x.id for x in wynik.wnioski] == ["1"]  # z ostatniego roku i podobny; „3” niepodobny, „2” za stary
    assert znajdz(ZapytanieOPodobne(tresc=z.tresc, pomin_id="1", data_odniesienia="2026-11-21"), [], wnioski).wnioski == []


def test_endpoint_podobnych():
    odp = TestClient(app).post("/api/podobne", json={"tresc": "Liczba uczniów w szkołach podstawowych i obcokrajowców"})
    assert odp.status_code == 200 and odp.json()["sprawy"][0]["sygnatura"] == "BKS.IV.1431.307.2025"


def test_konfiguracja_lokalnego_modelu(monkeypatch):
    from inteligentny_asystent_urzednika.config import wczytaj_ustawienia

    for z in ("LLM_API_KEY", "GROQ_API_KEY", "LLM_URL", "GROQ_URL", "LLM_MODEL"):
        monkeypatch.delenv(z, raising=False)
    assert wczytaj_ustawienia().groq_api_key is None  # Groq bez klucza – brak modelu
    monkeypatch.setenv("LLM_URL", "http://localhost:11434/v1/chat/completions")
    monkeypatch.setenv("LLM_MODEL", "bielik-11b")
    u = wczytaj_ustawienia()
    assert u.groq_url.startswith("http://localhost") and u.groq_model == "bielik-11b" and u.groq_api_key == "lokalny"
