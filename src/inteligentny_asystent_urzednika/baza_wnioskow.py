"""Baza SQLite dla wniosków o dostęp do informacji publicznej i ich metadanych."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal

from pydantic import BaseModel, Field

StatusWniosku = Literal[
    "brak_dzialan",
    "zapytania_wyslane",
    "kwerenda",
    "odpowiedz_przygotowana",
    "odpowiedz_wyslana",
]

_WZOR_NUMERU = re.compile(r"^BKS\.IV\.1431\.(\d+)\.(\d{4})$")
_WZOR_DATY = r"^\d{4}-\d{2}-\d{2}$"


class BladBazy(Exception):
    def __init__(self, status: int, komunikat: str):
        super().__init__(komunikat)
        self.status = status
        self.komunikat = komunikat


class WniosekWejscie(BaseModel):
    id: str | None = None
    numer: str | None = Field(default=None, max_length=120)
    data_wplywu: str = Field(..., pattern=_WZOR_DATY)
    temat: str = Field(..., min_length=1, max_length=500)
    wnioskodawca: str = Field(default="", max_length=300)
    kontakt: str | None = Field(default=None, max_length=300)
    inicjaly: str = Field(default="", max_length=16)
    tresc: str = Field(default="", max_length=100_000)
    status: StatusWniosku = "brak_dzialan"
    dni_kwerendy: int | None = Field(default=None, ge=0, le=62)
    data_odpowiedzi: str | None = Field(default=None, pattern=_WZOR_DATY)
    nazwa_pliku: str | None = Field(default=None, max_length=300)


class ZatwierdzonaOdpowiedz(BaseModel):
    werdykt: str = ""
    uzasadnienie: str = ""
    podstawy_prawne: list[str] = []
    komorka_merytoryczna: str = ""
    wzor: str = ""
    wzor_nazwa: str = ""
    tresc: str = Field(min_length=1, max_length=100_000)
    pismo: dict | None = None
    autor: str = ""
    zatwierdzono: str = ""


class ZatwierdzenieOdpowiedziWejscie(BaseModel):
    werdykt: str = Field(default="", max_length=60)
    uzasadnienie: str = Field(default="", max_length=10_000)
    podstawy_prawne: list[str] = []
    komorka_merytoryczna: str = Field(default="", max_length=200)
    wzor: str = Field(default="", max_length=120)
    wzor_nazwa: str = Field(default="", max_length=200)
    tresc: str = Field(min_length=1, max_length=100_000)
    pismo: dict | None = None
    autor: str = Field(default="", max_length=40)


class OdpowiedzWydzialu(BaseModel):
    """Odpowiedź komórki merytorycznej wgrana przez urzędnika (treść odczytana z pliku PDF/Word)."""

    id: str
    wydzial: str
    nazwa_pliku: str = ""
    tresc: str
    dodano: str


class OdpowiedzWydzialuWejscie(BaseModel):
    wydzial: str = Field(min_length=2, max_length=200)
    nazwa_pliku: str = Field(default="", max_length=255)
    tresc: str = Field(min_length=1, max_length=100_000)


class WniosekZapisany(BaseModel):
    id: str
    numer: str
    data_wplywu: str
    temat: str
    wnioskodawca: str
    kontakt: str | None = None
    inicjaly: str
    tresc: str
    status: StatusWniosku
    dni_kwerendy: int | None = None
    data_odpowiedzi: str | None = None
    nazwa_pliku: str | None = None
    zatwierdzona_odpowiedz: ZatwierdzonaOdpowiedz | None = None
    odpowiedzi_wydzialow: list[OdpowiedzWydzialu] = []
    utworzono: str
    zaktualizowano: str


class WniosekWsad(BaseModel):
    wnioski: list[WniosekWejscie]


_SCHEMAT = """
CREATE TABLE IF NOT EXISTS wnioski (
    id TEXT PRIMARY KEY,
    numer TEXT UNIQUE NOT NULL,
    data_wplywu TEXT NOT NULL,
    temat TEXT NOT NULL,
    wnioskodawca TEXT NOT NULL DEFAULT '',
    kontakt TEXT,
    inicjaly TEXT NOT NULL DEFAULT '',
    tresc TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'brak_dzialan',
    dni_kwerendy INTEGER,
    data_odpowiedzi TEXT,
    nazwa_pliku TEXT,
    odpowiedz_tresc TEXT,
    odpowiedz_werdykt TEXT,
    odpowiedz_zatwierdzono TEXT,
    odpowiedz_json TEXT,
    odpowiedzi_wydzialow TEXT,
    utworzono TEXT NOT NULL,
    zaktualizowano TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wnioski_data_wplywu ON wnioski(data_wplywu);
"""

_NOWE_KOLUMNY = (
    ("odpowiedz_tresc", "TEXT"),
    ("odpowiedz_werdykt", "TEXT"),
    ("odpowiedz_zatwierdzono", "TEXT"),
    ("odpowiedz_json", "TEXT"),
    ("odpowiedzi_wydzialow", "TEXT"),
)


def _teraz_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _migruj(conn: sqlite3.Connection) -> None:
    istniejace = {w["name"] for w in conn.execute("PRAGMA table_info(wnioski)")}
    for nazwa, typ in _NOWE_KOLUMNY:
        if nazwa not in istniejace:
            conn.execute(f"ALTER TABLE wnioski ADD COLUMN {nazwa} {typ}")


@contextmanager
def _polaczenie(sciezka: Path) -> Iterator[sqlite3.Connection]:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sciezka, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMAT)
        _migruj(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _parsuj_odpowiedz(wiersz: sqlite3.Row) -> ZatwierdzonaOdpowiedz | None:
    surowy = wiersz["odpowiedz_json"]
    if not surowy:
        return None
    try:
        return ZatwierdzonaOdpowiedz.model_validate(json.loads(surowy))
    except Exception:
        return None


def _parsuj_odpowiedzi_wydzialow(wiersz: sqlite3.Row) -> list[OdpowiedzWydzialu]:
    surowy = wiersz["odpowiedzi_wydzialow"] if "odpowiedzi_wydzialow" in wiersz.keys() else None
    if not surowy:
        return []
    try:
        return [OdpowiedzWydzialu.model_validate(o) for o in json.loads(surowy)]
    except Exception:
        return []


def _wiersz_na_model(wiersz: sqlite3.Row) -> WniosekZapisany:
    return WniosekZapisany(
        id=wiersz["id"],
        numer=wiersz["numer"],
        data_wplywu=wiersz["data_wplywu"],
        temat=wiersz["temat"],
        wnioskodawca=wiersz["wnioskodawca"],
        kontakt=wiersz["kontakt"],
        inicjaly=wiersz["inicjaly"],
        tresc=wiersz["tresc"],
        status=wiersz["status"],
        dni_kwerendy=wiersz["dni_kwerendy"],
        data_odpowiedzi=wiersz["data_odpowiedzi"],
        nazwa_pliku=wiersz["nazwa_pliku"],
        zatwierdzona_odpowiedz=_parsuj_odpowiedz(wiersz),
        odpowiedzi_wydzialow=_parsuj_odpowiedzi_wydzialow(wiersz),
        utworzono=wiersz["utworzono"],
        zaktualizowano=wiersz["zaktualizowano"],
    )


def _nastepny_numer(conn: sqlite3.Connection, rok: str) -> str:
    maks = 0
    for wiersz in conn.execute("SELECT numer FROM wnioski"):
        m = _WZOR_NUMERU.match(wiersz["numer"])
        if m and m.group(2) == rok:
            maks = max(maks, int(m.group(1)))
    return f"BKS.IV.1431.{maks + 1}.{rok}"


def _oczyszczone(dane: WniosekWejscie) -> dict:
    kontakt = dane.kontakt.strip() if dane.kontakt else None
    nazwa_pliku = dane.nazwa_pliku.strip() if dane.nazwa_pliku else None
    data_odpowiedzi = dane.data_odpowiedzi or None
    dni_kwerendy = dane.dni_kwerendy if dane.status == "kwerenda" and dane.dni_kwerendy else None
    return {
        "data_wplywu": dane.data_wplywu,
        "temat": dane.temat.strip(),
        "wnioskodawca": dane.wnioskodawca.strip(),
        "kontakt": kontakt or None,
        "inicjaly": dane.inicjaly.strip().upper(),
        "tresc": dane.tresc,
        "status": dane.status,
        "dni_kwerendy": dni_kwerendy,
        "data_odpowiedzi": data_odpowiedzi if dane.status == "odpowiedz_wyslana" else None,
        "nazwa_pliku": nazwa_pliku or None,
    }


def _wstaw(conn: sqlite3.Connection, dane: WniosekWejscie, teraz: str) -> WniosekZapisany:
    id_wniosku = (dane.id or "").strip() or str(uuid.uuid4())
    numer = (dane.numer or "").strip() or _nastepny_numer(conn, dane.data_wplywu[:4])
    pola = _oczyszczone(dane)
    try:
        conn.execute(
            """
            INSERT INTO wnioski (
                id, numer, data_wplywu, temat, wnioskodawca, kontakt, inicjaly,
                tresc, status, dni_kwerendy, data_odpowiedzi, nazwa_pliku, utworzono, zaktualizowano
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id_wniosku,
                numer,
                pola["data_wplywu"],
                pola["temat"],
                pola["wnioskodawca"],
                pola["kontakt"],
                pola["inicjaly"],
                pola["tresc"],
                pola["status"],
                pola["dni_kwerendy"],
                pola["data_odpowiedzi"],
                pola["nazwa_pliku"],
                teraz,
                teraz,
            ),
        )
    except sqlite3.IntegrityError as e:
        raise BladBazy(409, f"Wniosek o numerze {numer} już istnieje w bazie.") from e
    wiersz = conn.execute("SELECT * FROM wnioski WHERE id = ?", (id_wniosku,)).fetchone()
    assert wiersz is not None
    return _wiersz_na_model(wiersz)


def lista(sciezka: Path) -> list[WniosekZapisany]:
    with _polaczenie(sciezka) as conn:
        wiersze = conn.execute("SELECT * FROM wnioski ORDER BY data_wplywu ASC, numer ASC").fetchall()
        return [_wiersz_na_model(w) for w in wiersze]


def liczba(sciezka: Path) -> int:
    with _polaczenie(sciezka) as conn:
        wiersz = conn.execute("SELECT COUNT(*) AS n FROM wnioski").fetchone()
        return int(wiersz["n"]) if wiersz else 0


def pobierz(sciezka: Path, id_wniosku: str) -> WniosekZapisany:
    with _polaczenie(sciezka) as conn:
        wiersz = conn.execute("SELECT * FROM wnioski WHERE id = ?", (id_wniosku,)).fetchone()
        if wiersz is None:
            raise BladBazy(404, "Nie znaleziono wniosku.")
        return _wiersz_na_model(wiersz)


def dodaj(sciezka: Path, dane: WniosekWejscie) -> WniosekZapisany:
    teraz = _teraz_iso()
    with _polaczenie(sciezka) as conn:
        return _wstaw(conn, dane, teraz)


def dodaj_wsadowo(sciezka: Path, pozycje: list[WniosekWejscie]) -> list[WniosekZapisany]:
    teraz = _teraz_iso()
    with _polaczenie(sciezka) as conn:
        return [_wstaw(conn, p, teraz) for p in pozycje]


def zmien(sciezka: Path, id_wniosku: str, dane: WniosekWejscie) -> WniosekZapisany:
    teraz = _teraz_iso()
    with _polaczenie(sciezka) as conn:
        istniejacy = conn.execute("SELECT * FROM wnioski WHERE id = ?", (id_wniosku,)).fetchone()
        if istniejacy is None:
            raise BladBazy(404, "Nie znaleziono wniosku.")
        numer = (dane.numer or "").strip() or istniejacy["numer"]
        pola = _oczyszczone(dane)
        try:
            conn.execute(
                """
                UPDATE wnioski
                SET numer = ?, data_wplywu = ?, temat = ?, wnioskodawca = ?, kontakt = ?,
                    inicjaly = ?, tresc = ?, status = ?, dni_kwerendy = ?, data_odpowiedzi = ?,
                    nazwa_pliku = ?, zaktualizowano = ?
                WHERE id = ?
                """,
                (
                    numer,
                    pola["data_wplywu"],
                    pola["temat"],
                    pola["wnioskodawca"],
                    pola["kontakt"],
                    pola["inicjaly"],
                    pola["tresc"],
                    pola["status"],
                    pola["dni_kwerendy"],
                    pola["data_odpowiedzi"],
                    pola["nazwa_pliku"],
                    teraz,
                    id_wniosku,
                ),
            )
        except sqlite3.IntegrityError as e:
            raise BladBazy(409, f"Wniosek o numerze {numer} już istnieje w bazie.") from e
        wiersz = conn.execute("SELECT * FROM wnioski WHERE id = ?", (id_wniosku,)).fetchone()
        assert wiersz is not None
        return _wiersz_na_model(wiersz)


def zatwierdz_odpowiedz(
    sciezka: Path, id_wniosku: str, dane: ZatwierdzenieOdpowiedziWejscie
) -> WniosekZapisany:
    teraz = _teraz_iso()
    with _polaczenie(sciezka) as conn:
        istniejacy = conn.execute("SELECT * FROM wnioski WHERE id = ?", (id_wniosku,)).fetchone()
        if istniejacy is None:
            raise BladBazy(404, "Nie znaleziono wniosku.")

        autor = dane.autor.strip().upper() or istniejacy["inicjaly"] or "UMB"
        zapisana = ZatwierdzonaOdpowiedz(
            werdykt=dane.werdykt.strip(),
            uzasadnienie=dane.uzasadnienie.strip(),
            podstawy_prawne=[p.strip() for p in dane.podstawy_prawne if p.strip()],
            komorka_merytoryczna=dane.komorka_merytoryczna.strip(),
            wzor=dane.wzor.strip(),
            wzor_nazwa=dane.wzor_nazwa.strip(),
            tresc=dane.tresc.strip(),
            pismo=dane.pismo,
            autor=autor,
            zatwierdzono=teraz,
        )
        nowy_status = (
            istniejacy["status"]
            if istniejacy["status"] == "odpowiedz_wyslana"
            else "odpowiedz_przygotowana"
        )
        conn.execute(
            """
            UPDATE wnioski
            SET status = ?, odpowiedz_tresc = ?, odpowiedz_werdykt = ?,
                odpowiedz_zatwierdzono = ?, odpowiedz_json = ?, zaktualizowano = ?
            WHERE id = ?
            """,
            (
                nowy_status,
                zapisana.tresc,
                zapisana.werdykt,
                teraz,
                zapisana.model_dump_json(),
                teraz,
                id_wniosku,
            ),
        )
        wiersz = conn.execute("SELECT * FROM wnioski WHERE id = ?", (id_wniosku,)).fetchone()
        assert wiersz is not None
        return _wiersz_na_model(wiersz)


def usun(sciezka: Path, id_wniosku: str) -> None:
    with _polaczenie(sciezka) as conn:
        kursor = conn.execute("DELETE FROM wnioski WHERE id = ?", (id_wniosku,))
        if kursor.rowcount == 0:
            raise BladBazy(404, "Nie znaleziono wniosku.")


def zastap_wszystkie(sciezka: Path, pozycje: list[WniosekWejscie]) -> list[WniosekZapisany]:
    teraz = _teraz_iso()
    with _polaczenie(sciezka) as conn:
        conn.execute("DELETE FROM wnioski")
        return [_wstaw(conn, p, teraz) for p in pozycje]


# ---------------------------------------------------------------- odpowiedzi wydziałów (krok 6 instrukcji UMB)
def _zapisz_odpowiedzi(conn: sqlite3.Connection, id_wniosku: str, odpowiedzi: list[OdpowiedzWydzialu]) -> None:
    conn.execute(
        "UPDATE wnioski SET odpowiedzi_wydzialow = ?, zaktualizowano = ? WHERE id = ?",
        (json.dumps([o.model_dump() for o in odpowiedzi], ensure_ascii=False), _teraz_iso(), id_wniosku),
    )


def dodaj_odpowiedz_wydzialu(sciezka: Path, id_wniosku: str, dane: OdpowiedzWydzialuWejscie) -> WniosekZapisany:
    with _polaczenie(sciezka) as conn:
        wiersz = conn.execute("SELECT * FROM wnioski WHERE id = ?", (id_wniosku,)).fetchone()
        if wiersz is None:
            raise BladBazy(404, "Nie znaleziono wniosku.")
        odpowiedzi = _parsuj_odpowiedzi_wydzialow(wiersz)
        odpowiedzi.append(OdpowiedzWydzialu(
            id=uuid.uuid4().hex[:12], wydzial=dane.wydzial.strip(), nazwa_pliku=dane.nazwa_pliku.strip(),
            tresc=dane.tresc.strip(), dodano=_teraz_iso(),
        ))
        _zapisz_odpowiedzi(conn, id_wniosku, odpowiedzi)
        return _wiersz_na_model(conn.execute("SELECT * FROM wnioski WHERE id = ?", (id_wniosku,)).fetchone())


def usun_odpowiedz_wydzialu(sciezka: Path, id_wniosku: str, id_odpowiedzi: str) -> WniosekZapisany:
    with _polaczenie(sciezka) as conn:
        wiersz = conn.execute("SELECT * FROM wnioski WHERE id = ?", (id_wniosku,)).fetchone()
        if wiersz is None:
            raise BladBazy(404, "Nie znaleziono wniosku.")
        odpowiedzi = [o for o in _parsuj_odpowiedzi_wydzialow(wiersz) if o.id != id_odpowiedzi]
        _zapisz_odpowiedzi(conn, id_wniosku, odpowiedzi)
        return _wiersz_na_model(conn.execute("SELECT * FROM wnioski WHERE id = ?", (id_wniosku,)).fetchone())
