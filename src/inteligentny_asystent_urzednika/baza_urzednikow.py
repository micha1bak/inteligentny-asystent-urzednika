"""Baza SQLite urzędników (unikalny id_u, powiązane inicjały Os. i zahaszowane hasło) oraz sesji logowania."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from pydantic import BaseModel, Field

_ITERACJE = 120_000
_PREFIKS_HASHA = "pbkdf2_sha256"
_WZOR_ID_U = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,31}$")

# Domyślni urzędnicy: unikalny ciąg znaków i liczb (id_u) powiązany ze skrótem Os. (AK, MW, PB) z wniosków testowych.
DOMYSLNI_URZEDNICY: tuple[tuple[str, str, str], ...] = (
    ("UMB-001", "AK", "haslo123"),
    ("UMB-002", "MW", "haslo123"),
    ("UMB-003", "PB", "haslo123"),
)


class BladLogowania(Exception):
    def __init__(self, status: int, komunikat: str):
        super().__init__(komunikat)
        self.status = status
        self.komunikat = komunikat


class LogowanieWejscie(BaseModel):
    id_u: str = Field(..., min_length=3, max_length=32, description="Unikalny identyfikator urzędnika (litery i cyfry)")
    haslo: str = Field(..., min_length=4, max_length=128)


class RejestracjaWejscie(LogowanieWejscie):
    inicjaly: str = Field(..., min_length=2, max_length=6, description="Inicjały urzędnika powiązane z kolumną Os.")


class SesjaOdpowiedz(BaseModel):
    id_u: str
    inicjaly: str
    token: str


class StanSesji(BaseModel):
    zalogowany: bool
    id_u: str | None = None
    inicjaly: str | None = None


_SCHEMAT = """
CREATE TABLE IF NOT EXISTS urzednicy (
    id_u TEXT PRIMARY KEY,
    inicjaly TEXT NOT NULL,
    haslo TEXT NOT NULL,
    utworzono TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sesje (
    token TEXT PRIMARY KEY,
    id_u TEXT NOT NULL,
    utworzono TEXT NOT NULL,
    FOREIGN KEY (id_u) REFERENCES urzednicy(id_u) ON DELETE CASCADE
);
"""


def _teraz_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalizuj_id(id_u: str) -> str:
    oczyszczone = id_u.strip().upper()
    if not _WZOR_ID_U.match(oczyszczone):
        raise BladLogowania(
            422,
            "Identyfikator urzędnika musi mieć 3–32 znaki (litery A–Z, cyfry 0–9, „-” lub „_”).",
        )
    return oczyszczone


def _normalizuj_inicjaly(inicjaly: str) -> str:
    oczyszczone = inicjaly.strip().upper()
    if len(oczyszczone) < 2 or len(oczyszczone) > 6:
        raise BladLogowania(422, "Inicjały (Os.) muszą mieć od 2 do 6 znaków.")
    return oczyszczone


def zahaszuj_haslo(haslo: str) -> str:
    sol = secrets.token_hex(16)
    skrot = hashlib.pbkdf2_hmac("sha256", haslo.encode("utf-8"), bytes.fromhex(sol), _ITERACJE).hex()
    return f"{_PREFIKS_HASHA}${_ITERACJE}${sol}${skrot}"


def sprawdz_haslo(haslo: str, zapisane: str) -> bool:
    czesci = zapisane.split("$")
    if len(czesci) != 4 or czesci[0] != _PREFIKS_HASHA:
        return False
    try:
        iteracje = int(czesci[1])
        sol = bytes.fromhex(czesci[2])
    except ValueError:
        return False
    obliczone = hashlib.pbkdf2_hmac("sha256", haslo.encode("utf-8"), sol, iteracje).hex()
    return hmac.compare_digest(obliczone, czesci[3])


def _migruj(conn: sqlite3.Connection) -> None:
    kolumny = {w["name"] for w in conn.execute("PRAGMA table_info(urzednicy)")}
    if "inicjaly" not in kolumny:
        conn.execute("ALTER TABLE urzednicy ADD COLUMN inicjaly TEXT NOT NULL DEFAULT ''")


def _zasiej_domyslnych(conn: sqlite3.Connection) -> None:
    liczba = conn.execute("SELECT COUNT(*) AS n FROM urzednicy").fetchone()["n"]
    if liczba > 0:
        return
    teraz = _teraz_iso()
    for id_u, inicjaly, haslo in DOMYSLNI_URZEDNICY:
        conn.execute(
            "INSERT INTO urzednicy (id_u, inicjaly, haslo, utworzono) VALUES (?, ?, ?, ?)",
            (id_u, inicjaly, zahaszuj_haslo(haslo), teraz),
        )


@contextmanager
def _polaczenie(sciezka: Path) -> Iterator[sqlite3.Connection]:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sciezka, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMAT)
        _migruj(conn)
        _zasiej_domyslnych(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lista_urzednikow(sciezka: Path) -> list[dict[str, str]]:
    with _polaczenie(sciezka) as conn:
        return [
            {"id_u": w["id_u"], "inicjaly": w["inicjaly"]}
            for w in conn.execute("SELECT id_u, inicjaly FROM urzednicy ORDER BY id_u ASC")
        ]


def zarejestruj(sciezka: Path, dane: RejestracjaWejscie) -> SesjaOdpowiedz:
    id_u = _normalizuj_id(dane.id_u)
    inicjaly = _normalizuj_inicjaly(dane.inicjaly)
    teraz = _teraz_iso()
    token = secrets.token_urlsafe(32)
    with _polaczenie(sciezka) as conn:
        try:
            conn.execute(
                "INSERT INTO urzednicy (id_u, inicjaly, haslo, utworzono) VALUES (?, ?, ?, ?)",
                (id_u, inicjaly, zahaszuj_haslo(dane.haslo), teraz),
            )
        except sqlite3.IntegrityError as e:
            raise BladLogowania(409, f"Urzędnik o identyfikatorze {id_u} już istnieje.") from e
        conn.execute(
            "INSERT INTO sesje (token, id_u, utworzono) VALUES (?, ?, ?)",
            (token, id_u, teraz),
        )
    return SesjaOdpowiedz(id_u=id_u, inicjaly=inicjaly, token=token)


def zaloguj(sciezka: Path, dane: LogowanieWejscie) -> SesjaOdpowiedz:
    id_u = _normalizuj_id(dane.id_u)
    with _polaczenie(sciezka) as conn:
        wiersz = conn.execute("SELECT id_u, inicjaly, haslo FROM urzednicy WHERE id_u = ?", (id_u,)).fetchone()
        if wiersz is None or not sprawdz_haslo(dane.haslo, wiersz["haslo"]):
            raise BladLogowania(401, "Niepoprawny identyfikator urzędnika lub hasło.")
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO sesje (token, id_u, utworzono) VALUES (?, ?, ?)",
            (token, wiersz["id_u"], _teraz_iso()),
        )
        return SesjaOdpowiedz(id_u=wiersz["id_u"], inicjaly=wiersz["inicjaly"], token=token)


def sprawdz_sesje(sciezka: Path, token: str | None) -> tuple[str, str] | None:
    if not token:
        return None
    with _polaczenie(sciezka) as conn:
        wiersz = conn.execute(
            """
            SELECT u.id_u, u.inicjaly
            FROM sesje s
            JOIN urzednicy u ON u.id_u = s.id_u
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
        return (wiersz["id_u"], wiersz["inicjaly"]) if wiersz else None


def wyloguj(sciezka: Path, token: str | None) -> None:
    if not token:
        return
    with _polaczenie(sciezka) as conn:
        conn.execute("DELETE FROM sesje WHERE token = ?", (token,))
