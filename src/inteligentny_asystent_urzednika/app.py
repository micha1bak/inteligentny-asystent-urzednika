"""API backendu: propozycja odpowiedzi na wniosek UDIP przez Groq."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import Ustawienia, wczytaj_ustawienia
from .groq_klient import BladLLM, KlientGroq, KlientLLM
from .propozycja import ZAPAS_TOKENOW, Propozycja, Wniosek, zaproponuj_odpowiedz
from .wiedza import Wiedza, wczytaj_wiedze


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
        allow_methods=["GET", "POST"],
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

    return app


app = utworz_aplikacje()
