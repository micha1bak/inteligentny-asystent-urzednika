"""API backendu: propozycja odpowiedzi na wniosek UDIP przez Groq."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import archiwum
from .archiwum import BladArchiwum, SprawaZArchiwum, ZmianaSprawy
from .config import Ustawienia, wczytaj_ustawienia
from .groq_klient import BladLLM, KlientGroq, KlientLLM
from .konwersja import ocr_llm
from .propozycja import ZAPAS_TOKENOW, Propozycja, Wniosek, zaproponuj_odpowiedz
from .propozycja_archiwum import PropozycjaWpisu, ZapytanieOWpis, zaproponuj_wpis
from .wiedza import JEDNOSTKI_UMB, Wiedza, wczytaj_wiedze


MAKS_ROZMIAR_PLIKU = 20 * 1024 * 1024  # 20 MB


class Archiwum(BaseModel):
    sprawy: list[SprawaZArchiwum]
    werdykty: dict[str, str]
    jednostki: list[str]


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
    return wczytaj_wiedze(u.plik_oceny, u.plik_werdyktow, u.plik_wzorow)


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
    def zdrowie(u: Ustawienia = Depends(pobierz_ustawienia), wiedza: Wiedza = Depends(pobierz_wiedze)) -> dict:
        return {
            "status": "ok",
            "llm_skonfigurowany": bool(u.groq_api_key),
            "model": u.groq_model,
            "kontekst_prawny": u.kontekst_prawny,
            "limit_tpm": u.groq_limit_tpm,
            "spraw_w_archiwum": len(wiedza.sygnatury),
            "werdyktow": len(wiedza.slownik_werdyktow),
        }

    @app.post("/api/propozycja-odpowiedzi", response_model=Propozycja)
    async def propozycja_odpowiedzi(
        wniosek: Wniosek,
        u: Ustawienia = Depends(pobierz_ustawienia),
        wiedza: Wiedza = Depends(pobierz_wiedze),
        klient: KlientLLM = Depends(pobierz_klienta),
    ) -> Propozycja:
        try:
            budzet = u.groq_limit_tpm - u.groq_max_tokens - ZAPAS_TOKENOW
            return await zaproponuj_odpowiedz(wniosek, wiedza, klient, u.groq_model, u.kontekst_prawny, budzet)
        except BladLLM as e:
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
        if Path(nazwa).suffix.lower() != ".docx" and not u.groq_api_key:
            raise HTTPException(503, "Brak klucza GROQ_API_KEY w pliku .env – odczyt PDF i skanów wymaga modelu.")

        with tempfile.TemporaryDirectory() as katalog:
            sciezka = Path(katalog) / f"wniosek{Path(nazwa).suffix.lower()}"
            sciezka.write_bytes(dane)
            try:
                k = await run_in_threadpool(ocr_llm.konwertuj, sciezka)
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

    return app


app = utworz_aplikacje()
