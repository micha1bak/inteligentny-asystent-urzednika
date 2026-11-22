"""Podobne sprawy z archiwum i podobne wnioski z ostatniego roku (krok 3 instrukcji UMB) – lokalnie, bez AI.

Podobieństwo: pokrycie wag TF-IDF na rdzeniach słów (`podobienstwo.py`) – działa offline i skaluje się do setek
dokumentów. Ta sama sprawa daje zwykle 50–80%, sprawa o podobnym temacie 20–40%.
"""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field

from .baza_wnioskow import WniosekZapisany
from .podobienstwo import z_wynikiem
from .wiedza import JEDNOSTKI_UMB

_NAZWY = {j["symbol"]: j["nazwa"] for j in JEDNOSTKI_UMB}

PROG = 0.20  # poniżej tej miary dokument uznajemy za niepodobny


class ZapytanieOPodobne(BaseModel):
    tresc: str = Field(min_length=10, max_length=30_000)
    pomin_id: str | None = None
    data_odniesienia: str | None = Field(default=None, description="YYYY-MM-DD; domyślnie dziś")
    limit: int = Field(default=5, ge=1, le=20)


class PodobnaSprawaArchiwum(BaseModel):
    sygnatura: str
    wniosek_o_co: str
    jaka_odpowiedz: str
    werdykt: str
    komorka_merytoryczna: str
    wydzialy: list[dict[str, str]] = Field(default=[], description="Jednostki UMB, do których przekazano wniosek")
    podmiot_poza_umb: str = ""
    podobienstwo: float


class PodobnyWniosek(BaseModel):
    id: str
    numer: str
    data_wplywu: str
    temat: str
    status: str
    podobienstwo: float


class WynikPodobnych(BaseModel):
    sprawy: list[PodobnaSprawaArchiwum]
    wnioski: list[PodobnyWniosek]


def tekst_sprawy(s: dict) -> str:
    """Tekst sprawy z archiwum do wyszukiwania: o co wniosek, odpowiedź, komórka i wydziały, dysponent spoza UMB."""
    wydzialy = " ".join(_NAZWY.get(w, w) for w in s.get("wydzialy", []))
    return " ".join(
        [s.get("wniosek_o_co", ""), s.get("jaka_odpowiedz", ""), s.get("komorka_merytoryczna", ""), wydzialy,
         s.get("podmiot_poza_umb", "")]
    )


def znajdz(z: ZapytanieOPodobne, sprawy: list[dict], wnioski: list[WniosekZapisany]) -> WynikPodobnych:
    try:
        odniesienie = date.fromisoformat(z.data_odniesienia) if z.data_odniesienia else date.today()
    except ValueError:
        odniesienie = date.today()
    od = (odniesienie - timedelta(days=365)).isoformat()

    teksty = [tekst_sprawy(s) for s in sprawy]
    wyniki_spraw = [
        PodobnaSprawaArchiwum(
            sygnatura=s["sygnatura"], wniosek_o_co=s.get("wniosek_o_co", ""), jaka_odpowiedz=s.get("jaka_odpowiedz", ""),
            werdykt=s.get("werdykt", ""), komorka_merytoryczna=s.get("komorka_merytoryczna", ""),
            wydzialy=[{"symbol": w_, "nazwa": _NAZWY.get(w_, w_)} for w_ in s.get("wydzialy", [])],
            podmiot_poza_umb=s.get("podmiot_poza_umb", ""), podobienstwo=round(w, 3),
        )
        for w, s in z_wynikiem(z.tresc, sprawy, teksty, z.limit)
        if w >= PROG
    ]

    z_roku = [w for w in wnioski if w.id != z.pomin_id and od <= w.data_wplywu <= odniesienie.isoformat()]
    wyniki_wnioskow = [
        PodobnyWniosek(id=w.id, numer=w.numer, data_wplywu=w.data_wplywu, temat=w.temat, status=w.status,
                       podobienstwo=round(wynik, 3))
        for wynik, w in z_wynikiem(z.tresc, z_roku, [f"{w.temat} {w.tresc}" for w in z_roku], z.limit)
        if wynik >= PROG
    ]
    return WynikPodobnych(sprawy=wyniki_spraw, wnioski=wyniki_wnioskow)
