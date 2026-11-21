"""Wczytywanie danych testowych z katalogu dane_testowe/ do bazy."""

import json
from datetime import date, timedelta
from pathlib import Path

from sqlmodel import Session, delete, func, select

from .config import KATALOG_PROJEKTU
from .db import silnik, utworz_tabele
from .models import Dokument, RodzajDokumentu, StatusWniosku, Wniosek
from .terminy import czy_dzien_roboczy, dni_do_terminu, termin_odpowiedzi

KATALOG = KATALOG_PROJEKTU / "dane_testowe"


def data_wplywu_dla(termin_za_dni: int, dni_kwerendy: int = 0, dzis: date | None = None) -> date:
    """Najpóźniejsza data wpływu (dzień roboczy, jeśli się da), przy której termin wypada za `termin_za_dni` dni."""
    dzis = dzis or date.today()
    kandydaci = [dzis - timedelta(days=d) for d in range(0, 120)]

    def odleglosc(wplyw: date) -> tuple[int, bool]:
        dni = dni_do_terminu(termin_odpowiedzi(wplyw, dni_kwerendy), dzis)
        return abs(dni - termin_za_dni), not czy_dzien_roboczy(wplyw)

    return min(kandydaci, key=odleglosc)


def _json(nazwa: str) -> dict:
    return json.loads((KATALOG / nazwa).read_text(encoding="utf-8"))


def wczytaj(wyczysc: bool = False, dzis: date | None = None) -> str:
    utworz_tabele()
    with Session(silnik()) as s:
        if wyczysc:
            s.exec(delete(Dokument))
            s.exec(delete(Wniosek))
            s.commit()

        istniejace = set(s.exec(select(Wniosek.numer)).all())
        nowe = [
            (data_wplywu_dla(w["termin_za_dni"], w.get("dni_kwerendy", 0), dzis), w)
            for w in _json("wnioski.json")["wnioski"] if w["numer"] not in istniejace
        ]
        lp_w_roku: dict[int, int] = {}
        dodane = 0
        for wplyw, dane in sorted(nowe, key=lambda p: (p[0], p[1]["numer"])):
            kwerenda = dane.get("dni_kwerendy", 0)
            if wplyw.year not in lp_w_roku:
                lp_w_roku[wplyw.year] = s.exec(select(func.max(Wniosek.lp)).where(Wniosek.rok == wplyw.year)).one() or 0
            lp_w_roku[wplyw.year] += 1
            wniosek = Wniosek(
                numer=dane["numer"], temat=dane["temat"], data_wplywu=wplyw, rok=wplyw.year,
                lp=lp_w_roku[wplyw.year], inicjaly=dane.get("inicjaly"), dni_kwerendy=kwerenda,
                status=StatusWniosku(dane.get("status", "brak_dzialan")), wydzialy=dane.get("wydzialy"),
            )
            s.add(wniosek)
            s.flush()
            s.add(Dokument(wniosek_id=wniosek.id, rodzaj=RodzajDokumentu.WNIOSEK,
                           nazwa_pliku=f"{dane['numer']}.txt", tekst=dane["tresc"]))
            dodane += 1
        s.commit()

        id_po_numerze = {w.numer: w.id for w in s.exec(select(Wniosek)).all()}
        odp = 0
        for o in _json("odpowiedzi_wydzialow.json")["odpowiedzi"]:
            wid = id_po_numerze.get(o["numer_wniosku"])
            nazwa = f"odpowiedz_{o['wydzial']}_{o['numer_wniosku']}.txt"
            if wid and not s.exec(select(Dokument).where(Dokument.nazwa_pliku == nazwa)).first():
                s.add(Dokument(wniosek_id=wid, rodzaj=RodzajDokumentu.ODPOWIEDZ_WYDZIALU,
                               nazwa_pliku=nazwa, tekst=o["tresc"], wydzial=o["wydzial"]))
                odp += 1

        arch = 0
        for sprawa in _json("archiwum.json")["sprawy"]:
            nazwa = f"{sprawa['numer']}.txt"
            if not s.exec(select(Dokument).where(Dokument.nazwa_pliku == nazwa)).first():
                tekst = f"Temat: {sprawa['temat']}\n\nWniosek:\n{sprawa['wniosek']}\n\nOdpowiedź:\n{sprawa['odpowiedz']}"
                s.add(Dokument(rodzaj=RodzajDokumentu.ARCHIWUM, nazwa_pliku=nazwa, tekst=tekst, wydzial=sprawa["wydzial"]))
                arch += 1
        s.commit()

    return f"Dodano: {dodane} wniosków, {odp} odpowiedzi wydziałów, {arch} spraw archiwalnych."


def sciezka_wniosku_z_danymi_osobowymi() -> Path:
    return KATALOG / "wniosek_z_danymi_osobowymi.txt"
