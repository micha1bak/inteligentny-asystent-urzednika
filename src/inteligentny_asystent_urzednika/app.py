"""API backendu: propozycja odpowiedzi na wniosek UDIP przez Groq."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import Ustawienia, wczytaj_ustawienia
from .groq_klient import BladLLM, KlientGroq, KlientLLM
from .konwersja import ocr_llm
from .propozycja import ZAPAS_TOKENOW, Propozycja, Wniosek, zaproponuj_odpowiedz
from .przepisy import (
    DokumentPrawnyInfo,
    IndeksPrzepisow,
    WynikWyszukiwaniaPrzepisow,
    szukaj_przepisow,
    wczytaj_indeks_przepisow,
)
from .wiedza import Wiedza, wczytaj_wiedze


MAKS_ROZMIAR_PLIKU = 20 * 1024 * 1024  # 20 MB


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
        allow_methods=["GET", "POST"],
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
        }

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
