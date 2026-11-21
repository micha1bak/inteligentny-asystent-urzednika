"""Konfiguracja z zmiennych środowiskowych (plik .env w katalogu głównym repozytorium)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

KATALOG_GLOWNY = Path(__file__).resolve().parents[2]

load_dotenv(KATALOG_GLOWNY / ".env")


@dataclass(frozen=True)
class Ustawienia:
    groq_api_key: str | None
    groq_model: str
    groq_url: str
    groq_timeout_s: float
    # Limit tokenów na minutę planu Groq (darmowy plan: 8000) – zapytanie jest do niego przycinane.
    groq_limit_tpm: int
    # Maksymalna długość odpowiedzi modelu (liczy się do limitu TPM).
    groq_max_tokens: int
    # "wybrany" – streszczenie algorytmu + fragmenty dopasowane do wniosku (mieści się w darmowym planie);
    # "pelny" – cały model oceny prawnej i całe archiwum (~23 tys. tokenów, wymaga wyższego planu)
    kontekst_prawny: str
    plik_oceny: Path
    plik_werdyktow: Path
    plik_wzorow: Path
    katalog_dokumentow: Path
    dozwolone_originy: list[str]


def _tryb_kontekstu(wartosc: str) -> str:
    wartosc = wartosc.strip().lower()
    # "skrocony" – nazwa z poprzedniej wersji, oznacza teraz tryb "wybrany"
    return "pelny" if wartosc == "pelny" else "wybrany"


def wczytaj_ustawienia() -> Ustawienia:
    return Ustawienia(
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        groq_url=os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions"),
        groq_timeout_s=float(os.getenv("GROQ_TIMEOUT_S", "90")),
        groq_limit_tpm=int(os.getenv("GROQ_LIMIT_TPM", "8000")),
        groq_max_tokens=int(os.getenv("GROQ_MAX_TOKENS", "2000")),
        kontekst_prawny=_tryb_kontekstu(os.getenv("KONTEKST_PRAWNY", "wybrany")),
        plik_oceny=Path(os.getenv("PLIK_OCENY", KATALOG_GLOWNY / "ocena_prawna_wniosku_dip_kompletny.json")),
        plik_werdyktow=Path(os.getenv("PLIK_WERDYKTOW", KATALOG_GLOWNY / "werdykty_wniosek_odpowiedz_dip.json")),
        plik_wzorow=Path(os.getenv("PLIK_WZOROW", KATALOG_GLOWNY / "wzory_pism.json")),
        katalog_dokumentow=Path(os.getenv("KATALOG_DOKUMENTOW", KATALOG_GLOWNY / "Dokumenty i podstawy prawne")),
        dozwolone_originy=os.getenv(
            "DOZWOLONE_ORIGINY", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(","),
    )
