"""Kalendarz wniosków: lista, dodawanie, zmiana danych i statusu."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from ..db import sesja
from ..models import StatusWniosku, Wniosek, WniosekNowy, WniosekWidok, WniosekZmiana

router = APIRouter(prefix="/api/wnioski", tags=["wnioski"])


@router.get("", response_model=list[WniosekWidok])
def lista_wnioskow(rok: int | None = None, s: Session = Depends(sesja)):
    """Wnioski z danego roku (domyślnie bieżącego), od najstarszego do najnowszego."""
    rok = rok or date.today().year
    wnioski = s.exec(
        select(Wniosek).where(Wniosek.rok == rok).order_by(Wniosek.data_wplywu, Wniosek.lp)
    ).all()
    return [WniosekWidok.z_wniosku(w) for w in wnioski]


@router.get("/lata", response_model=list[int])
def lata(s: Session = Depends(sesja)):
    """Lata, w których są wnioski (do przełącznika roku)."""
    lata = s.exec(select(Wniosek.rok).distinct().order_by(Wniosek.rok.desc())).all()
    return lata or [date.today().year]


@router.post("", response_model=WniosekWidok, status_code=201)
def dodaj_wniosek(dane: WniosekNowy, s: Session = Depends(sesja)):
    rok = dane.data_wplywu.year
    ostatnie_lp = s.exec(select(func.max(Wniosek.lp)).where(Wniosek.rok == rok)).one()
    wniosek = Wniosek(**dane.model_dump(), rok=rok, lp=(ostatnie_lp or 0) + 1)
    s.add(wniosek)
    s.commit()
    s.refresh(wniosek)
    return WniosekWidok.z_wniosku(wniosek)


def _pobierz(s: Session, wniosek_id: int) -> Wniosek:
    wniosek = s.get(Wniosek, wniosek_id)
    if not wniosek:
        raise HTTPException(404, "Nie ma takiego wniosku")
    return wniosek


@router.get("/{wniosek_id}", response_model=WniosekWidok)
def pobierz_wniosek(wniosek_id: int, s: Session = Depends(sesja)):
    return WniosekWidok.z_wniosku(_pobierz(s, wniosek_id))


@router.patch("/{wniosek_id}", response_model=WniosekWidok)
def zmien_wniosek(wniosek_id: int, zmiana: WniosekZmiana, s: Session = Depends(sesja)):
    wniosek = _pobierz(s, wniosek_id)
    pola = zmiana.model_dump(exclude_unset=True)
    for pole, wartosc in pola.items():
        setattr(wniosek, pole, wartosc)
    if pola.get("status") == StatusWniosku.ODPOWIEDZ_WYSLANA and not wniosek.data_odpowiedzi:
        wniosek.data_odpowiedzi = date.today()
    if pola.get("dni_kwerendy") and "status" not in pola and wniosek.status == StatusWniosku.BRAK_DZIALAN:
        wniosek.status = StatusWniosku.KWERENDA
    s.add(wniosek)
    s.commit()
    s.refresh(wniosek)
    return WniosekWidok.z_wniosku(wniosek)


@router.delete("/{wniosek_id}", status_code=204)
def usun_wniosek(wniosek_id: int, s: Session = Depends(sesja)):
    s.delete(_pobierz(s, wniosek_id))
    s.commit()
