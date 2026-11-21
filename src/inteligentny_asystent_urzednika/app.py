"""API backendu: propozycja odpowiedzi na wniosek UDIP przez Groq."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Query, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import analiza_aktu, anonimizacja, archiwum, baza_wiedzy, baza_wnioskow
from .analiza_aktu import ROZSZERZENIA_AKTU, Analiza
from .archiwum import BladArchiwum, Sprawa, SprawaZArchiwum, ZmianaSprawy
from .baza_wiedzy import BladBazyWiedzy, Wersja, WersjaZeStatusem
from .baza_wnioskow import (
    BladBazy,
    OdpowiedzWydzialuWejscie,
    WniosekWejscie,
    WniosekWsad,
    WniosekZapisany,
    ZatwierdzenieOdpowiedziWejscie,
)
from .config import KATALOG_GLOWNY, Ustawienia, wczytaj_ustawienia
from .groq_klient import BladLLM, KlientGroq, KlientLLM
from .konwersja import ocr_llm
from .podobne import WynikPodobnych, ZapytanieOPodobne, znajdz as znajdz_podobne
from .wzor import eksport
from .propozycja import ZAPAS_TOKENOW, Propozycja, Wniosek, szacuj_tokeny, zaproponuj_odpowiedz, zbuduj_wiadomosci
from .propozycja_archiwum import PropozycjaWpisu, ZapytanieOWpis, zaproponuj_wpis
from .przepisy import (
    DokumentPrawnyInfo,
    IndeksPrzepisow,
    WynikWyszukiwaniaPrzepisow,
    szukaj_przepisow,
    wczytaj_indeks_przepisow,
)
from .wiedza import JEDNOSTKI_UMB, Wiedza, wczytaj_wiedze
from .wydzialy import (
    PropozycjaWydzialu,
    Wiadomosc,
    WniosekDoWydzialu,
    ZapytanieOWiadomosc,
    jednostka_po_nazwie,
    propozycja_bez_modelu,
    zaproponuj_wydzial,
    zloz_wiadomosc,
)


MAKS_ROZMIAR_PLIKU = 20 * 1024 * 1024  # 20 MB


class Archiwum(BaseModel):
    sprawy: list[SprawaZArchiwum]
    werdykty: dict[str, str]
    jednostki: list[str]


class AktWBazie(BaseModel):
    kod: str
    nazwa: str
    plik: str


class StanBazyWiedzy(BaseModel):
    wersje: list[WersjaZeStatusem]
    akty: list[AktWBazie]


class DecyzjaZmiany(BaseModel):
    id: str
    zatwierdz: bool
    po: object | None = None  # wartość poprawiona przez urzędnika (zamiast propozycji modelu)


class ZatwierdzenieAnalizy(BaseModel):
    decyzje: list[DecyzjaZmiany]
    autor: str = Field(min_length=1, max_length=40)


class Autor(BaseModel):
    autor: str = Field(min_length=1, max_length=40)


class WynikZatwierdzenia(BaseModel):
    wniosek: WniosekZapisany
    zaktualizowano_werdykty: bool
    werdykt_nowy_wpis: bool = False
    komunikat_werdykty: str | None = None


class EksportPisma(BaseModel):
    pismo: dict
    nazwa: str = Field(default="odpowiedz", max_length=120)


class EksportDokumentu(BaseModel):
    tekst: str = Field(max_length=500_000)
    ukryte: list[str] = Field(default=[], max_length=2000)
    nazwa: str = Field(default="dokument_zanonimizowany", max_length=120)


class ZapytanieOAnonimizacje(BaseModel):
    tekst: str = Field(max_length=200_000)
    dodatkowe: list[str] = Field(default=[], max_length=200)


class WynikKonwersji(BaseModel):
    tekst: str
    # "tekst" – cały tekst z warstwy tekstowej / DOCX; "model" – co najmniej jedna strona przepisana przez model
    zrodlo: str
    odreczny: bool
    strony_odreczne: list[int]
    stron: int
    strony_z_modelu: list[int]
    komunikat: str | None = None


def pobierz_ustawienia() -> Ustawienia:
    return wczytaj_ustawienia()


def pobierz_wiedze(u: Ustawienia = Depends(pobierz_ustawienia)) -> Wiedza:
    # główny plik bazy = wersja obowiązująca dziś (zaplanowana wersja mogła właśnie wejść w życie)
    baza_wiedzy.synchronizuj_jesli_trzeba(u.plik_oceny, u.katalog_dokumentow)
    return wczytaj_wiedze(u.plik_oceny, u.plik_werdyktow, u.plik_wzorow)


def budzet_tokenow(u: Ustawienia) -> int:
    return u.groq_limit_tpm - u.groq_max_tokens - ZAPAS_TOKENOW


def liczba_zmian(n: int) -> str:
    if n == 1:
        return "1 zmiana"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} zmiany"
    return f"{n} zmian"


PROBNY_WNIOSEK ="Wnoszę o udostępnienie informacji o kosztach remontu ulicy Gdańskiej w 2026 r. oraz o nazwie wykonawcy."


def walidator_bazy(u: Ustawienia):
    """Sprawdza bazę przed zapisem nowej wersji: struktura czytelna dla `wiedza.py`, a zapytanie w trybie
    „wybrany” mieści się w limicie GROQ_LIMIT_TPM."""

    def sprawdz(ocena: dict) -> None:
        try:
            wiedza = Wiedza(
                ocena=ocena,
                werdykty=json.loads(u.plik_werdyktow.read_text(encoding="utf-8")),
                wzory=json.loads(u.plik_wzorow.read_text(encoding="utf-8")),
            )
            wiadomosci, _ = zbuduj_wiadomosci(Wniosek(tresc=PROBNY_WNIOSEK), wiedza, "wybrany", budzet_tokenow(u))
            baza_wiedzy.elementy(ocena)
        except (KeyError, TypeError, AttributeError, IndexError) as e:
            raise BladBazyWiedzy(f"Po zmianie baza wiedzy ma niepoprawną strukturę ({e.__class__.__name__}: {e}).") from e
        if szacuj_tokeny(wiadomosci) > budzet_tokenow(u):
            raise BladBazyWiedzy("Po zmianie zapytanie do modelu nie mieści się w limicie GROQ_LIMIT_TPM – skróć zmienione elementy.")

    return sprawdz


def pobierz_indeks_przepisow(u: Ustawienia = Depends(pobierz_ustawienia)) -> IndeksPrzepisow:
    return wczytaj_indeks_przepisow(u.katalog_dokumentow)


def pobierz_klienta(u: Ustawienia = Depends(pobierz_ustawienia)) -> KlientLLM:
    if not u.groq_api_key:
        raise HTTPException(503, "Brak klucza GROQ_API_KEY w pliku .env – backend nie może połączyć się z modelem.")
    return KlientGroq(u.groq_api_key, u.groq_model, u.groq_url, u.groq_timeout_s, u.groq_max_tokens)


def utworz_aplikacje() -> FastAPI:
    app = FastAPI(title="Asystent urzędnika – API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=wczytaj_ustawienia().dozwolone_originy,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/zdrowie")
    def zdrowie(
        u: Ustawienia = Depends(pobierz_ustawienia),
        wiedza: Wiedza = Depends(pobierz_wiedze),
        indeks: IndeksPrzepisow = Depends(pobierz_indeks_przepisow),
    ) -> dict:
        return {
            "status": "ok",
            "llm_skonfigurowany": bool(u.groq_api_key),
            "model": u.groq_model,
            "kontekst_prawny": u.kontekst_prawny,
            "limit_tpm": u.groq_limit_tpm,
            "spraw_w_archiwum": len(wiedza.sygnatury),
            "werdyktow": len(wiedza.slownik_werdyktow),
            "dokumentow_prawnych": len(indeks.dokumenty),
            "wnioskow_w_bazie": baza_wnioskow.liczba(u.plik_bazy),
        }

    # ------------------------------------------------------------ baza wniosków (SQLite)

    @app.get("/api/wnioski", response_model=list[WniosekZapisany])
    def wnioski_lista(u: Ustawienia = Depends(pobierz_ustawienia)) -> list[WniosekZapisany]:
        return baza_wnioskow.lista(u.plik_bazy)

    @app.get("/api/wnioski/{id_wniosku}", response_model=WniosekZapisany)
    def wnioski_pobierz(id_wniosku: str, u: Ustawienia = Depends(pobierz_ustawienia)) -> WniosekZapisany:
        try:
            return baza_wnioskow.pobierz(u.plik_bazy, id_wniosku)
        except BladBazy as e:
            raise HTTPException(e.status, e.komunikat) from e

    @app.post("/api/wnioski", response_model=WniosekZapisany, status_code=201)
    def wnioski_dodaj(dane: WniosekWejscie, u: Ustawienia = Depends(pobierz_ustawienia)) -> WniosekZapisany:
        try:
            return baza_wnioskow.dodaj(u.plik_bazy, dane)
        except BladBazy as e:
            raise HTTPException(e.status, e.komunikat) from e

    @app.post("/api/wnioski/wsadowo", response_model=list[WniosekZapisany], status_code=201)
    def wnioski_dodaj_wsadowo(wsad: WniosekWsad, u: Ustawienia = Depends(pobierz_ustawienia)) -> list[WniosekZapisany]:
        try:
            return baza_wnioskow.dodaj_wsadowo(u.plik_bazy, wsad.wnioski)
        except BladBazy as e:
            raise HTTPException(e.status, e.komunikat) from e

    @app.post("/api/wnioski/zastap", response_model=list[WniosekZapisany])
    def wnioski_zastap(wsad: WniosekWsad, u: Ustawienia = Depends(pobierz_ustawienia)) -> list[WniosekZapisany]:
        try:
            return baza_wnioskow.zastap_wszystkie(u.plik_bazy, wsad.wnioski)
        except BladBazy as e:
            raise HTTPException(e.status, e.komunikat) from e

    @app.put("/api/wnioski/{id_wniosku}", response_model=WniosekZapisany)
    def wnioski_zmien(
        id_wniosku: str, dane: WniosekWejscie, u: Ustawienia = Depends(pobierz_ustawienia)
    ) -> WniosekZapisany:
        try:
            return baza_wnioskow.zmien(u.plik_bazy, id_wniosku, dane)
        except BladBazy as e:
            raise HTTPException(e.status, e.komunikat) from e

    @app.post("/api/wnioski/{id_wniosku}/odpowiedzi-wydzialow", response_model=WniosekZapisany, status_code=201)
    def wnioski_dodaj_odpowiedz_wydzialu(
        id_wniosku: str, dane: OdpowiedzWydzialuWejscie, u: Ustawienia = Depends(pobierz_ustawienia)
    ) -> WniosekZapisany:
        """Odpowiedź komórki merytorycznej (treść z wgranego pliku) – podstawa projektu pisma."""
        try:
            return baza_wnioskow.dodaj_odpowiedz_wydzialu(u.plik_bazy, id_wniosku, dane)
        except BladBazy as e:
            raise HTTPException(e.status, e.komunikat) from e

    @app.delete("/api/wnioski/{id_wniosku}/odpowiedzi-wydzialow/{id_odpowiedzi}", response_model=WniosekZapisany)
    def wnioski_usun_odpowiedz_wydzialu(
        id_wniosku: str, id_odpowiedzi: str, u: Ustawienia = Depends(pobierz_ustawienia)
    ) -> WniosekZapisany:
        try:
            return baza_wnioskow.usun_odpowiedz_wydzialu(u.plik_bazy, id_wniosku, id_odpowiedzi)
        except BladBazy as e:
            raise HTTPException(e.status, e.komunikat) from e

    @app.post("/api/wnioski/{id_wniosku}/zatwierdz-odpowiedz", response_model=WynikZatwierdzenia)
    def wnioski_zatwierdz_odpowiedz(
        id_wniosku: str,
        dane: ZatwierdzenieOdpowiedziWejscie,
        u: Ustawienia = Depends(pobierz_ustawienia),
        wiedza: Wiedza = Depends(pobierz_wiedze),
    ) -> WynikZatwierdzenia:
        try:
            wniosek = baza_wnioskow.zatwierdz_odpowiedz(u.plik_bazy, id_wniosku, dane)
        except BladBazy as e:
            raise HTTPException(e.status, e.komunikat) from e

        zaktualizowano = False
        nowy_wpis = False
        komunikat: str | None = None

        if dane.werdykt.strip() in wiedza.slownik_werdyktow:
            opis_wniosku = anonimizacja.zanonimizuj(wniosek.temat).strip()
            if len(opis_wniosku) < 10:
                fragment = anonimizacja.zanonimizuj(wniosek.tresc).strip()
                opis_wniosku = f"{opis_wniosku}: {fragment}".strip(": ")[:2800]
            if len(opis_wniosku) < 10:
                opis_wniosku = f"Wniosek {wniosek.numer} o udostępnienie informacji publicznej"

            opis_odpowiedzi = anonimizacja.zanonimizuj(dane.uzasadnienie.strip() or dane.tresc.strip())[:4800]
            if len(opis_odpowiedzi) < 10:
                opis_odpowiedzi = anonimizacja.zanonimizuj(dane.tresc.strip())[:4800]
            if len(opis_odpowiedzi) < 10:
                opis_odpowiedzi = "Udzielono odpowiedzi na wniosek o dostęp do informacji publicznej."

            autor = (wniosek.zatwierdzona_odpowiedz.autor if wniosek.zatwierdzona_odpowiedz else "") or "UMB"
            sprawa = Sprawa(
                sygnatura=wniosek.numer,
                data_odpowiedzi=wniosek.data_odpowiedzi or date.today().isoformat(),
                komorka_merytoryczna=anonimizacja.zanonimizuj(dane.komorka_merytoryczna)[:200],
                wniosek_o_co=opis_wniosku[:3000],
                jaka_odpowiedz=opis_odpowiedzi[:5000],
                werdykt=dane.werdykt.strip(),
                forma_zalatwienia=anonimizacja.zanonimizuj(dane.wzor_nazwa or "Pismo urzędowe")[:1000],
                etap_i_podstawa=anonimizacja.zanonimizuj(", ".join(dane.podstawy_prawne))[:1000],
            )
            try:
                _, nowy_wpis = archiwum.zapisz_lub_aktualizuj(
                    u.plik_werdyktow,
                    ZmianaSprawy(sprawa=sprawa, autor=autor),
                    wiedza.slownik_werdyktow,
                )
                zaktualizowano = True
            except BladArchiwum as e:
                komunikat = e.komunikat
        else:
            komunikat = "Odpowiedź zapisana w bazie; werdykt spoza słownika nie został dodany do pliku werdyktów."

        return WynikZatwierdzenia(
            wniosek=wniosek,
            zaktualizowano_werdykty=zaktualizowano,
            werdykt_nowy_wpis=nowy_wpis,
            komunikat_werdykty=komunikat,
        )

    @app.delete("/api/wnioski/{id_wniosku}", status_code=204)
    def wnioski_usun(id_wniosku: str, u: Ustawienia = Depends(pobierz_ustawienia)) -> Response:
        try:
            baza_wnioskow.usun(u.plik_bazy, id_wniosku)
        except BladBazy as e:
            raise HTTPException(e.status, e.komunikat) from e
        return Response(status_code=204)

    @app.get("/api/przepisy/dokumenty", response_model=list[DokumentPrawnyInfo])
    def dokumenty_prawne(
        indeks: IndeksPrzepisow = Depends(pobierz_indeks_przepisow),
    ) -> list[DokumentPrawnyInfo]:
        """Lista lokalnie zaindeksowanych plików z folderu „Dokumenty i podstawy prawne” (bez modelu AI)."""
        return indeks.informacje_o_dokumentach()

    @app.get("/api/przepisy/szukaj", response_model=WynikWyszukiwaniaPrzepisow)
    def przepisy_szukaj(
        q: str = Query(..., min_length=1, max_length=300, description="Odwołanie do przepisu lub fraza"),
        akt: str | None = Query(default=None, max_length=60, description="Opcjonalny filtr aktu (np. UDIP, KPA)"),
        limit: int = Query(default=8, ge=1, le=20),
        indeks: IndeksPrzepisow = Depends(pobierz_indeks_przepisow),
    ) -> WynikWyszukiwaniaPrzepisow:
        """Deterministyczne wyszukiwanie ustępów, artykułów i paragrafów w folderze dokumentów (bez AI)."""
        return szukaj_przepisow(indeks, q, akt=akt, limit=limit)

    @app.post("/api/podobne", response_model=WynikPodobnych)
    def podobne(
        z: ZapytanieOPodobne, u: Ustawienia = Depends(pobierz_ustawienia), wiedza: Wiedza = Depends(pobierz_wiedze)
    ) -> WynikPodobnych:
        """Podobne sprawy z archiwum odpowiedzi i podobne wnioski z ostatniego roku (bez AI)."""
        try:
            wnioski = baza_wnioskow.lista(u.plik_bazy)
        except BladBazy:
            wnioski = []
        return znajdz_podobne(z, wiedza.sprawy, wnioski)

    @app.get("/api/jednostki")
    def jednostki() -> list[dict]:
        """Wydziały i biura UMB (nazwy i symbole z BIP, zakres spraw) – do wyboru jednostki przez urzędnika."""
        return JEDNOSTKI_UMB

    @app.post("/api/wydzial/propozycja", response_model=PropozycjaWydzialu)
    async def wydzial_propozycja(
        wniosek: WniosekDoWydzialu,
        u: Ustawienia = Depends(pobierz_ustawienia),
        wiedza: Wiedza = Depends(pobierz_wiedze),
    ) -> PropozycjaWydzialu:
        """Wskazanie ścieżki: ranking jednostek UMB właściwych dla wniosku (z AI, a bez klucza – archiwum i zakresy)."""
        if not u.groq_api_key:
            return propozycja_bez_modelu(wiedza, wniosek.tresc)
        klient = KlientGroq(u.groq_api_key, u.groq_model, u.groq_url, u.groq_timeout_s, u.groq_max_tokens)
        try:
            return await zaproponuj_wydzial(wniosek, wiedza, klient, u.groq_model)
        except BladLLM as e:
            p = propozycja_bez_modelu(wiedza, wniosek.tresc)
            p.ostrzezenia.insert(0, f"Model AI niedostępny ({e.komunikat[:120]}).")
            return p

    @app.post("/api/wydzial/wiadomosc", response_model=Wiadomosc)
    def wydzial_wiadomosc(z: ZapytanieOWiadomosc) -> Wiadomosc:
        """Prośba do wydziału o projekt odpowiedzi – składana przez kod; urzędnik wysyła ją sam (brak automatycznej wysyłki)."""
        j = jednostka_po_nazwie(z.jednostka)
        if not j:
            raise HTTPException(422, f"Nieznana jednostka UMB: {z.jednostka}")
        try:
            termin = date.fromisoformat(z.termin) if z.termin else None
        except ValueError as e:
            raise HTTPException(422, "Termin musi mieć format RRRR-MM-DD.") from e
        return zloz_wiadomosc(j["nazwa"], z.numer, z.data_wplywu, termin)

    @app.post("/api/propozycja-odpowiedzi", response_model=Propozycja)
    async def propozycja_odpowiedzi(
        wniosek: Wniosek,
        u: Ustawienia = Depends(pobierz_ustawienia),
        wiedza: Wiedza = Depends(pobierz_wiedze),
        klient: KlientLLM = Depends(pobierz_klienta),
    ) -> Propozycja:
        # wniosek oceniamy według bazy wiedzy obowiązującej w dniu wpływu
        uwagi: list[str] = []
        try:
            dzien = date.fromisoformat(wniosek.data_wplywu) if wniosek.data_wplywu else date.today()
        except ValueError:
            dzien = date.today()
        sciezka, wersja = baza_wiedzy.sciezka_oceny_na_dzien(u.plik_oceny, dzien)
        _, wersja_dzis = baza_wiedzy.sciezka_oceny_na_dzien(u.plik_oceny, date.today())
        if wersja != wersja_dzis:
            wiedza = wczytaj_wiedze(sciezka, u.plik_werdyktow, u.plik_wzorow)
            uwagi.append(f"Wniosek oceniono według bazy wiedzy w wersji {wersja}, obowiązującej w dniu wpływu ({dzien.isoformat()}).")
        try:
            propozycja = await zaproponuj_odpowiedz(wniosek, wiedza, klient, u.groq_model, u.kontekst_prawny, budzet_tokenow(u))
        except BladLLM as e:
            raise HTTPException(e.status, e.komunikat) from e
        propozycja.ostrzezenia = uwagi + propozycja.ostrzezenia
        return propozycja

    # ------------------------------------------------------------ baza wiedzy: nowe akty prawne i wersje

    @app.get("/api/baza-wiedzy", response_model=StanBazyWiedzy)
    def baza_wiedzy_stan(
        u: Ustawienia = Depends(pobierz_ustawienia),
        indeks: IndeksPrzepisow = Depends(pobierz_indeks_przepisow),
    ) -> StanBazyWiedzy:
        baza_wiedzy.synchronizuj_jesli_trzeba(u.plik_oceny, u.katalog_dokumentow)
        indeks = wczytaj_indeks_przepisow(u.katalog_dokumentow)  # po synchronizacji pliki aktów mogły się zmienić
        return StanBazyWiedzy(
            wersje=baza_wiedzy.lista_wersji(u.plik_oceny),
            akty=[
                AktWBazie(kod=d.akt, nazwa=d.nazwa, plik=d.plik)
                for d in indeks.dokumenty
                if any(j.rodzaj in ("art", "par") for j in d.jednostki)
            ],
        )

    @app.post("/api/baza-wiedzy/analizy", response_model=Analiza, status_code=202)
    async def baza_wiedzy_analiza(
        tla: BackgroundTasks,
        plik: UploadFile,
        obowiazuje_od: date = Form(...),
        zastepuje: str = Form("", max_length=300),
        nazwa: str = Form("", max_length=300),
        skrot: str = Form("", max_length=40),
        publikator: str = Form("", max_length=300),
        u: Ustawienia = Depends(pobierz_ustawienia),
        indeks: IndeksPrzepisow = Depends(pobierz_indeks_przepisow),
        klient: KlientLLM = Depends(pobierz_klienta),
    ) -> Analiza:
        """Wgranie aktu: `zastepuje` = plik aktu w folderze dokumentów, którego to nowa wersja (pusty = nowy akt)."""
        nazwa_pliku = Path(plik.filename or "").name
        if Path(nazwa_pliku).suffix.lower() not in ROZSZERZENIA_AKTU:
            raise HTTPException(415, f"Nieobsługiwany format aktu (obsługiwane: {', '.join(sorted(ROZSZERZENIA_AKTU))}).")
        dane = await plik.read(MAKS_ROZMIAR_PLIKU + 1)
        if len(dane) > MAKS_ROZMIAR_PLIKU:
            raise HTTPException(413, "Plik jest za duży (maks. 20 MB).")
        poprzedni = next((d for d in indeks.dokumenty if d.plik == zastepuje), None) if zastepuje else None
        if zastepuje and not poprzedni:
            raise HTTPException(422, f"Nie ma w folderze dokumentów aktu {zastepuje}.")
        if not poprzedni and (not nazwa.strip() or not skrot.strip()):
            raise HTTPException(422, "Dla nowego aktu podaj jego pełną nazwę i skrót.")
        akt = analiza_aktu.dane_aktu_z_formularza(nazwa_pliku, poprzedni, nazwa, skrot, publikator, obowiazuje_od)
        zadanie = analiza_aktu.utworz(akt, dane, Path(nazwa_pliku).suffix.lower(), poprzedni.plik if poprzedni else None)
        tla.add_task(analiza_aktu.analizuj, zadanie, u.plik_oceny, indeks, klient, budzet_tokenow(u))
        return zadanie.analiza

    @app.get("/api/baza-wiedzy/analizy/{id_analizy}", response_model=Analiza)
    def baza_wiedzy_analiza_stan(id_analizy: str) -> Analiza:
        zadanie = analiza_aktu.pobierz(id_analizy)
        if not zadanie:
            raise HTTPException(404, "Nie ma takiej analizy (mogła wygasnąć po restarcie backendu) – wgraj akt ponownie.")
        return zadanie.analiza

    @app.post("/api/baza-wiedzy/analizy/{id_analizy}/zastosuj", response_model=Wersja)
    def baza_wiedzy_zastosuj(
        id_analizy: str, zatwierdzenie: ZatwierdzenieAnalizy, u: Ustawienia = Depends(pobierz_ustawienia)
    ) -> Wersja:
        zadanie = analiza_aktu.pobierz(id_analizy)
        if not zadanie:
            raise HTTPException(404, "Nie ma takiej analizy – wgraj akt ponownie.")
        a = zadanie.analiza
        with zadanie.blokada:
            if a.status != "gotowa":
                powod = {
                    "w_toku": "analiza jeszcze trwa",
                    "zapisana": "analiza została już zapisana",
                    "nie_dotyczy": "akt nie dotyczy dostępu do informacji publicznej",
                    "blad": "analiza zakończyła się błędem",
                }[a.status]
                raise HTTPException(409, f"Nie można zapisać: {powod}.")
            decyzje = {d.id: d for d in zatwierdzenie.decyzje}
            if any(z.id not in decyzje for z in a.zmiany):
                raise HTTPException(422, "Zatwierdź albo odrzuć każdą proponowaną zmianę.")
            zmiany = [
                (z.klucz, z.opis, decyzje[z.id].po if decyzje[z.id].po is not None else z.po)
                for z in a.zmiany
                if decyzje[z.id].zatwierdz
            ]
            opis = f"{a.akt.skrot}: " + ("nowy akt" if a.akt.nowy else f"nowa wersja aktu ({liczba_zmian(len(zmiany))} w bazie)")
            try:
                wersja = baza_wiedzy.zapisz_wersje(
                    u.plik_oceny,
                    u.katalog_dokumentow,
                    a.baza_wersja,
                    zmiany,
                    zatwierdzenie.autor,
                    opis,
                    date.fromisoformat(a.akt.obowiazuje_od),
                    analiza_aktu.jako_nowy_akt(zadanie),
                    walidator_bazy(u),
                )
            except BladBazyWiedzy as e:
                raise HTTPException(e.status, e.komunikat) from e
            a.status, a.zapisana_wersja = "zapisana", wersja.id
            return wersja

    @app.post("/api/baza-wiedzy/wersje/{id_wersji}/wycofaj", response_model=Wersja)
    def baza_wiedzy_wycofaj(id_wersji: str, autor: Autor, u: Ustawienia = Depends(pobierz_ustawienia)) -> Wersja:
        try:
            return baza_wiedzy.wycofaj(u.plik_oceny, u.katalog_dokumentow, id_wersji, autor.autor)
        except BladBazyWiedzy as e:
            raise HTTPException(e.status, e.komunikat) from e

    # ------------------------------------------------------------ archiwum spraw

    @app.get("/api/archiwum", response_model=Archiwum)
    def archiwum_lista(u: Ustawienia = Depends(pobierz_ustawienia), wiedza: Wiedza = Depends(pobierz_wiedze)) -> Archiwum:
        return Archiwum(
            sprawy=archiwum.lista(u.plik_werdyktow),
            werdykty=wiedza.slownik_werdyktow,
            jednostki=[j["nazwa"] for j in JEDNOSTKI_UMB],
        )

    @app.post("/api/archiwum", response_model=SprawaZArchiwum, status_code=201)
    def archiwum_dodaj(
        zmiana: ZmianaSprawy, u: Ustawienia = Depends(pobierz_ustawienia), wiedza: Wiedza = Depends(pobierz_wiedze)
    ) -> SprawaZArchiwum:
        try:
            return archiwum.dodaj(u.plik_werdyktow, zmiana, wiedza.slownik_werdyktow)
        except BladArchiwum as e:
            raise HTTPException(e.status, e.komunikat) from e

    @app.put("/api/archiwum/{sygnatura}", response_model=SprawaZArchiwum)
    def archiwum_zmien(
        sygnatura: str,
        zmiana: ZmianaSprawy,
        u: Ustawienia = Depends(pobierz_ustawienia),
        wiedza: Wiedza = Depends(pobierz_wiedze),
    ) -> SprawaZArchiwum:
        try:
            return archiwum.zmien(u.plik_werdyktow, sygnatura, zmiana, wiedza.slownik_werdyktow)
        except BladArchiwum as e:
            raise HTTPException(e.status, e.komunikat) from e

    @app.delete("/api/archiwum/{sygnatura}", status_code=204)
    def archiwum_usun(sygnatura: str, u: Ustawienia = Depends(pobierz_ustawienia)) -> Response:
        try:
            archiwum.usun(u.plik_werdyktow, sygnatura)
        except BladArchiwum as e:
            raise HTTPException(e.status, e.komunikat) from e
        return Response(status_code=204)

    @app.post("/api/archiwum/propozycja", response_model=PropozycjaWpisu)
    async def archiwum_propozycja(
        zapytanie: ZapytanieOWpis,
        u: Ustawienia = Depends(pobierz_ustawienia),
        wiedza: Wiedza = Depends(pobierz_wiedze),
        klient: KlientLLM = Depends(pobierz_klienta),
    ) -> PropozycjaWpisu:
        try:
            return await zaproponuj_wpis(zapytanie, wiedza, klient, u.groq_model)
        except BladLLM as e:
            raise HTTPException(e.status, e.komunikat) from e

    # ------------------------------------------------------------ anonimizacja (lokalnie, bez modelu AI)
    @app.post("/api/anonimizacja/sugestie")
    def anonimizacja_sugestie(z: ZapytanieOAnonimizacje) -> list[dict]:
        """Fragmenty proponowane do anonimizacji (dane osobowe) – urzędnik je akceptuje lub odrzuca."""
        return [f.jako_slownik() for f in anonimizacja.sugestie(z.tekst, z.dodatkowe)]

    # ------------------------------------------------------------ eksport pisma (DOCX / TXT) z anonimizacją
    def _naglowek_pliku(nazwa: str, rozszerzenie: str) -> str:
        """Content-Disposition: nazwa ASCII (polskie litery zamienione) + pełna nazwa UTF-8 (RFC 5987)."""
        from urllib.parse import quote

        polskie = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
        ascii_ = "".join(z if (z.isascii() and z.isalnum()) or z in "._-" else "_" for z in nazwa.translate(polskie))
        ascii_ = ascii_.strip("._") or "odpowiedz"
        return f'attachment; filename="{ascii_}.{rozszerzenie}"; filename*=UTF-8\'\'{quote(nazwa)}.{rozszerzenie}'

    @app.post("/api/pismo/docx")
    def pismo_docx(e: EksportPisma) -> Response:
        """Pismo w formacie DOCX (układ BKS); fragmenty ukryte przez urzędnika są zastąpione znakami █."""
        return Response(
            eksport.pismo_do_docx(e.pismo),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": _naglowek_pliku(e.nazwa, "docx")},
        )

    @app.post("/api/dokument/docx")
    def dokument_docx(e: EksportDokumentu) -> Response:
        """Dowolny dokument po anonimizacji (DOCX) – ukryte fragmenty zastąpione znakami █."""
        return Response(
            eksport.dokument_do_docx(e.tekst, e.ukryte),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": _naglowek_pliku(e.nazwa, "docx")},
        )

    @app.post("/api/dokument/txt")
    def dokument_txt(e: EksportDokumentu) -> Response:
        return Response(
            eksport.anonimizuj(e.tekst, e.ukryte),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": _naglowek_pliku(e.nazwa, "txt")},
        )

    @app.post("/api/pismo/txt")
    def pismo_txt(e: EksportPisma) -> Response:
        """Pismo jako zwykły tekst (UTF-8), po anonimizacji."""
        return Response(
            eksport.pismo_do_tekstu(e.pismo),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": _naglowek_pliku(e.nazwa, "txt")},
        )

    @app.post("/api/konwersja", response_model=WynikKonwersji)
    async def konwersja(plik: UploadFile, u: Ustawienia = Depends(pobierz_ustawienia)) -> WynikKonwersji:
        """Odczyt wniosku (PDF/DOCX/obraz) modułem `konwersja`: filtr pisma odręcznego + tekst.

        Plik trafia do katalogu tymczasowego i jest usuwany po konwersji – nic nie zostaje na dysku.
        """
        nazwa = Path(plik.filename or "").name
        try:
            ocr_llm.sprawdz_format(Path(nazwa))
        except ValueError as e:
            raise HTTPException(415, str(e)) from e
        dane = await plik.read(MAKS_ROZMIAR_PLIKU + 1)
        if len(dane) > MAKS_ROZMIAR_PLIKU:
            raise HTTPException(413, "Plik jest za duży (maks. 20 MB).")

        with tempfile.TemporaryDirectory() as katalog:
            sciezka = Path(katalog) / f"wniosek{Path(nazwa).suffix.lower()}"
            sciezka.write_bytes(dane)
            try:
                k = await run_in_threadpool(ocr_llm.konwertuj, sciezka)
            except ocr_llm.BrakModeluOCR as e:
                raise HTTPException(503, str(e)) from e
            except RuntimeError as e:
                raise HTTPException(502, f"Błąd odczytu przez model: {e}") from e
            except Exception as e:
                raise HTTPException(422, f"Nie udało się odczytać pliku: {e}") from e
        return WynikKonwersji(
            tekst=k.tekst,
            zrodlo="model" if k.strony_z_modelu else "tekst",
            odreczny=k.odreczny,
            strony_odreczne=k.strony_odreczne,
            stron=k.stron,
            strony_z_modelu=k.strony_z_modelu,
            komunikat=k.komunikat,
        )

    # zbudowany frontend (npm --prefix frontend run build) pod tym samym adresem co API – jedno polecenie do
    # uruchomienia w urzędzie; trasy /api/* zarejestrowane wyżej mają pierwszeństwo
    dist = Path(os.getenv("FRONTEND_DIST", str(KATALOG_GLOWNY / "frontend" / "dist")))
    if (dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")

    return app


app = utworz_aplikacje()
