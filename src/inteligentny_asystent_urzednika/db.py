"""Połączenie z bazą danych (domyślnie lokalny plik SQLite)."""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import ustawienia

_silnik = None


def silnik():
    global _silnik
    if _silnik is None:
        ustawienia.katalog_danych.mkdir(parents=True, exist_ok=True)
        _silnik = create_engine(ustawienia.url_bazy, connect_args={"check_same_thread": False})
    return _silnik


def ustaw_silnik(nowy) -> None:
    """Podmiana silnika (testy)."""
    global _silnik
    _silnik = nowy


def utworz_tabele() -> None:
    from . import models  # noqa: F401 – rejestracja tabel

    SQLModel.metadata.create_all(silnik())


def sesja() -> Iterator[Session]:
    with Session(silnik()) as s:
        yield s
