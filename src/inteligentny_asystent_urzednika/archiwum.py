"""Archiwum spraw (werdykty_wniosek_odpowiedz_dip.json): dodawanie, edycja, oznaczanie jako nieaktualne, usuwanie.

Archiwum jest źródłem podobnych spraw i werdyktów dla modelu oraz przykładów przydziału wniosków do wydziałów:
`wydzialy` to symbole jednostek UMB, do których przekazano wniosek (pusta lista – nie przekazano, np. UMB nie posiada
informacji), a `podmiot_poza_umb` – wskazany dysponent spoza Urzędu. Każda zmiana z aplikacji trafia do pliku JSON
(zapis atomowy) razem z historią: kto, kiedy, co zmienił. Plik nadal można edytować ręcznie.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from .anonimizacja import wykryj

# Pola sprawy przekazywane modelowi (bez pól technicznych archiwum).
POLA_SPRAWY = (
    "sygnatura",
    "data_odpowiedzi",
    "komorka_merytoryczna",
    "wydzialy",
    "podmiot_poza_umb",
    "wniosek_o_co",
    "jaka_odpowiedz",
    "werdykt",
    "forma_zalatwienia",
    "etap_i_podstawa",
)
POLA_TECHNICZNE = ("nieaktualna", "historia")
# Wartość pola, gdy brak go w starszym wpisie (porównanie w historii zmian).
_DOMYSLNE: dict[str, object] = {"wydzialy": []}

_blokada = threading.Lock()


class BladArchiwum(Exception):
    def __init__(self, komunikat: str, status: int = 422):
        super().__init__(komunikat)
        self.komunikat = komunikat
        self.status = status


class Sprawa(BaseModel):
    sygnatura: str = Field(min_length=3, max_length=60)
    data_odpowiedzi: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    komorka_merytoryczna: str = Field(default="", max_length=200)
    wydzialy: list[str] = Field(default=[], max_length=10, description="Symbole jednostek UMB, do których przekazano wniosek")
    podmiot_poza_umb: str = Field(default="", max_length=300, description="Właściwy dysponent spoza UMB, jeśli wskazano")
    wniosek_o_co: str = Field(min_length=10, max_length=3000)
    jaka_odpowiedz: str = Field(min_length=10, max_length=5000)
    werdykt: str = Field(min_length=1, max_length=60)
    forma_zalatwienia: str = Field(default="", max_length=1000)
    etap_i_podstawa: str = Field(default="", max_length=1000)
    nieaktualna: bool = False

    @field_validator(
        "sygnatura", "komorka_merytoryczna", "podmiot_poza_umb", "wniosek_o_co", "jaka_odpowiedz", "forma_zalatwienia",
        "etap_i_podstawa",
    )
    @classmethod
    def _przytnij(cls, v: str) -> str:
        return v.strip()

    @field_validator("wydzialy")
    @classmethod
    def _symbole(cls, v: list[str]) -> list[str]:
        """Symbol albo pełna nazwa jednostki -> symbol; bez powtórzeń. Nieznane zostają (odrzuca je `sprawdz`)."""
        wynik: list[str] = []
        for pozycja in v:
            symbol = symbol_jednostki(pozycja) or pozycja.strip()
            if symbol and symbol not in wynik:
                wynik.append(symbol)
        return wynik


class ZmianaSprawy(BaseModel):
    sprawa: Sprawa
    autor: str = Field(min_length=1, max_length=40, description="Inicjały lub nazwisko urzędnika")


class WpisHistorii(BaseModel):
    kiedy: str
    kto: str
    zmiana: str
    pola: dict[str, dict[str, object]] = {}


class SprawaZArchiwum(Sprawa):
    historia: list[WpisHistorii] = []


def symbol_jednostki(tekst: str) -> str | None:
    """Symbol jednostki UMB dla symbolu lub dokładnej nazwy (wielkość liter bez znaczenia)."""
    from .wiedza import JEDNOSTKI_UMB  # import lokalny: wiedza importuje ten moduł

    t = " ".join(tekst.split()).lower()
    for j in JEDNOSTKI_UMB:
        if t in (j["symbol"].lower(), " ".join(j["nazwa"].split()).lower()):
            return j["symbol"]
    return None


# ---------------------------------------------------------------- plik


def wczytaj(plik: Path) -> dict:
    return json.loads(plik.read_text(encoding="utf-8"))


def _zapisz(plik: Path, dane: dict) -> None:
    dane["metadane"]["liczba_spraw"] = len(dane["sprawy"])
    tresc = json.dumps(dane, ensure_ascii=False, indent=2) + "\n"
    fd, tymczasowy = tempfile.mkstemp(dir=plik.parent, prefix=f".{plik.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(tresc)
        os.replace(tymczasowy, plik)
    except BaseException:
        Path(tymczasowy).unlink(missing_ok=True)
        raise


def lista(plik: Path) -> list[SprawaZArchiwum]:
    return [SprawaZArchiwum.model_validate(s) for s in wczytaj(plik)["sprawy"]]


# ---------------------------------------------------------------- walidacja


def sprawdz(sprawa: Sprawa, slownik_werdyktow: dict[str, str]) -> None:
    if sprawa.werdykt not in slownik_werdyktow:
        raise BladArchiwum(f"Nieznany werdykt „{sprawa.werdykt}” – wybierz werdykt ze słownika.")
    if nieznane := [w for w in sprawa.wydzialy if not symbol_jednostki(w)]:
        raise BladArchiwum(f"Nieznane jednostki UMB: {', '.join(nieznane)} – wybierz wydziały z listy.")
    dane_osobowe = wykryj(" \n ".join(str(getattr(sprawa, p)) for p in POLA_SPRAWY))
    if dane_osobowe:
        lista_ = "; ".join(f"{rodzaj}: {fragment}" for rodzaj, fragment in dane_osobowe)
        raise BladArchiwum(f"Wpis zawiera dane osobowe – zanonimizuj je przed zapisem ({lista_}).")


def _wpis(kto: str, zmiana: str, pola: dict | None = None) -> dict:
    return {"kiedy": datetime.now().isoformat(timespec="seconds"), "kto": kto.strip(), "zmiana": zmiana, "pola": pola or {}}


def _zmienione_pola(stara: dict, nowa: dict) -> dict:
    return {
        p: {"przed": stara.get(p, _DOMYSLNE.get(p, "")), "po": nowa.get(p, _DOMYSLNE.get(p, ""))}
        for p in POLA_SPRAWY
        if stara.get(p, _DOMYSLNE.get(p, "")) != nowa.get(p, _DOMYSLNE.get(p, ""))
    }


def _jako_slownik(sprawa: Sprawa) -> dict:
    d = sprawa.model_dump()
    if not d["nieaktualna"]:
        d.pop("nieaktualna")
    return d


# ---------------------------------------------------------------- operacje


def dodaj(plik: Path, zmiana: ZmianaSprawy, slownik_werdyktow: dict[str, str]) -> SprawaZArchiwum:
    sprawa = zmiana.sprawa
    sprawdz(sprawa, slownik_werdyktow)
    with _blokada:
        dane = wczytaj(plik)
        if any(s["sygnatura"] == sprawa.sygnatura for s in dane["sprawy"]):
            raise BladArchiwum(
                f"Sprawa {sprawa.sygnatura} jest już w archiwum – zmień istniejący wpis zamiast dodawać nowy.", 409
            )
        nowa = {**_jako_slownik(sprawa), "historia": [_wpis(zmiana.autor, "dodano")]}
        dane["sprawy"].append(nowa)
        _zapisz(plik, dane)
    return SprawaZArchiwum.model_validate(nowa)


def zmien(plik: Path, sygnatura: str, zmiana: ZmianaSprawy, slownik_werdyktow: dict[str, str]) -> SprawaZArchiwum:
    sprawa = zmiana.sprawa
    if sprawa.sygnatura != sygnatura:
        raise BladArchiwum("Sygnatury sprawy nie można zmienić – usuń wpis i dodaj go ponownie.")
    sprawdz(sprawa, slownik_werdyktow)
    with _blokada:
        dane = wczytaj(plik)
        i = _indeks(dane, sygnatura)
        stara = dane["sprawy"][i]
        nowa = _jako_slownik(sprawa)
        pola = _zmienione_pola(stara, nowa)
        byla_nieaktualna, jest_nieaktualna = bool(stara.get("nieaktualna")), sprawa.nieaktualna
        historia = list(stara.get("historia", []))
        if pola:
            historia.append(_wpis(zmiana.autor, "edytowano", pola))
        if byla_nieaktualna != jest_nieaktualna:
            historia.append(
                _wpis(zmiana.autor, "oznaczono jako nieaktualną" if jest_nieaktualna else "przywrócono jako aktualną")
            )
        nowa["historia"] = historia
        dane["sprawy"][i] = nowa
        if historia != stara.get("historia", []):
            _zapisz(plik, dane)
    return SprawaZArchiwum.model_validate(nowa)


def zapisz_lub_aktualizuj(
    plik: Path, zmiana: ZmianaSprawy, slownik_werdyktow: dict[str, str]
) -> tuple[SprawaZArchiwum, bool]:
    """Dodaje nową sprawę lub aktualizuje istniejącą po sygnaturze (z historią zmian). Zwraca (sprawa, czy_nowa)."""
    sprawa = zmiana.sprawa
    sprawdz(sprawa, slownik_werdyktow)
    with _blokada:
        dane = wczytaj(plik)
        istniejacy = next((i for i, s in enumerate(dane["sprawy"]) if s["sygnatura"] == sprawa.sygnatura), None)
        if istniejacy is None:
            nowa = {**_jako_slownik(sprawa), "historia": [_wpis(zmiana.autor, "dodano (zatwierdzona odpowiedź)")]}
            dane["sprawy"].append(nowa)
            _zapisz(plik, dane)
            return SprawaZArchiwum.model_validate(nowa), True

        stara = dane["sprawy"][istniejacy]
        nowa = _jako_slownik(sprawa)
        pola = _zmienione_pola(stara, nowa)
        historia = list(stara.get("historia", []))
        if pola:
            historia.append(_wpis(zmiana.autor, "zaktualizowano (zatwierdzona odpowiedź)", pola))
        if bool(stara.get("nieaktualna")) and not sprawa.nieaktualna:
            historia.append(_wpis(zmiana.autor, "przywrócono jako aktualną"))
        nowa["historia"] = historia
        dane["sprawy"][istniejacy] = nowa
        if historia != stara.get("historia", []):
            _zapisz(plik, dane)
        return SprawaZArchiwum.model_validate(nowa), False


def przywroc(plik: Path, wzorzec: Path) -> int:
    """Zastępuje archiwum jego stanem początkowym (`wzorzec`). Zwraca liczbę spraw po przywróceniu."""
    try:
        dane = wczytaj(wzorzec)
        for s in dane["sprawy"]:
            SprawaZArchiwum.model_validate(s)
    except FileNotFoundError as e:
        raise BladArchiwum(f"Brak pliku z początkowym stanem archiwum ({wzorzec.name}).", 500) from e
    except (ValueError, KeyError, TypeError) as e:
        raise BladArchiwum(f"Plik z początkowym stanem archiwum ({wzorzec.name}) jest uszkodzony.", 500) from e
    with _blokada:
        _zapisz(plik, dane)
    return len(dane["sprawy"])


def usun(plik: Path, sygnatura: str) -> None:
    with _blokada:
        dane = wczytaj(plik)
        del dane["sprawy"][_indeks(dane, sygnatura)]
        _zapisz(plik, dane)


def _indeks(dane: dict, sygnatura: str) -> int:
    for i, s in enumerate(dane["sprawy"]):
        if s["sygnatura"] == sygnatura:
            return i
    raise BladArchiwum(f"Nie ma w archiwum sprawy {sygnatura}.", 404)
