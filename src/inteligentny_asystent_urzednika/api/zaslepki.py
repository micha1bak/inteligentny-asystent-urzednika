"""Zaślepki endpointów z etapów 2–4.

Zwracają przykładowe dane w docelowym formacie, żeby UI mógł powstawać równolegle z backendem.
Każdą zaślepkę zastępuje właściciel odpowiedniego issue (numer w opisie endpointu).
"""

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel

from ..wydzialy import wczytaj_wydzialy

router = APIRouter(prefix="/api", tags=["zaślepki (etapy 2–4)"])


class PodobnaSprawa(BaseModel):
    wniosek_numer: str
    temat: str
    podobienstwo: float
    fragment_odpowiedzi: str


class SugestiaWydzialu(BaseModel):
    symbol: str
    nazwa: str
    pewnosc: float
    uzasadnienie: str


class FragmentDoAnonimizacji(BaseModel):
    poczatek: int
    koniec: int
    tekst: str
    typ: str  # imie_nazwisko, pesel, telefon, email, adres, ...
    stan: str = "propozycja"  # propozycja (szary) / zaakceptowany (czarny) / odrzucony


class ProjektPisma(BaseModel):
    tresc: str
    zrodla: list[str]
    do_anonimizacji: list[FragmentDoAnonimizacji]


class TekstWejsciowy(BaseModel):
    tekst: str


@router.post("/wnioski/{wniosek_id}/dokumenty")
async def wgraj_dokument(wniosek_id: int, plik: UploadFile, rodzaj: str = "wniosek"):
    """[2.1 #5] Wgranie PDF/DOCX do sprawy. Zaślepka: nie zapisuje pliku."""
    return {"wniosek_id": wniosek_id, "nazwa_pliku": plik.filename, "rodzaj": rodzaj, "tekst": "(zaślepka)"}


@router.get("/wnioski/{wniosek_id}/podobne", response_model=list[PodobnaSprawa])
def podobne_sprawy(wniosek_id: int):
    """[3.2 #7] Podobne wnioski z ostatniego roku."""
    return [
        PodobnaSprawa(
            wniosek_numer="BKS.1431.87.2025",
            temat="Koszt remontu ul. Gdańskiej",
            podobienstwo=0.82,
            fragment_odpowiedzi="Całkowity koszt inwestycji wyniósł ...",
        )
    ]


@router.get("/wnioski/{wniosek_id}/wydzialy", response_model=list[SugestiaWydzialu])
def sugerowane_wydzialy(wniosek_id: int):
    """[3.4 #8] Proponowane wydziały do przygotowania odpowiedzi."""
    wydzialy = {w["symbol"]: w for w in wczytaj_wydzialy()}
    return [
        SugestiaWydzialu(symbol="WIM", nazwa=wydzialy["WIM"]["nazwa"], pewnosc=0.9,
                         uzasadnienie="Wniosek dotyczy kosztów inwestycji drogowej."),
        SugestiaWydzialu(symbol="WZB", nazwa=wydzialy["WZB"]["nazwa"], pewnosc=0.4,
                         uzasadnienie="Dane o wydatkach budżetowych."),
    ]


@router.post("/wnioski/{wniosek_id}/projekt-pisma", response_model=ProjektPisma)
def projekt_pisma(wniosek_id: int):
    """[4.1 #10] Projekt odpowiedzi na podstawie odpowiedzi wydziałów."""
    tresc = (
        "Bydgoszcz, dnia ...\n\nPan Jan Kowalski\n\n"
        "W odpowiedzi na wniosek o udostępnienie informacji publicznej ... informuję, że ..."
    )
    return ProjektPisma(
        tresc=tresc,
        zrodla=["Odpowiedź WIM z dnia ..."],
        do_anonimizacji=[FragmentDoAnonimizacji(poczatek=23, koniec=37, tekst="Jan Kowalski", typ="imie_nazwisko")],
    )


@router.post("/anonimizacja/propozycje", response_model=list[FragmentDoAnonimizacji])
def propozycje_anonimizacji(dane: TekstWejsciowy):
    """[2.2 #11, 3.5 #12] Fragmenty tekstu proponowane do ukrycia."""
    return []
