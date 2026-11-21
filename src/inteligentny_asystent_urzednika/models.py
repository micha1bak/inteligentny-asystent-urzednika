"""Model danych: wnioski UDIP i dokumenty (wspólny kontrakt backendu i UI)."""

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from .terminy import czy_pilny, dni_do_terminu, termin_odpowiedzi


class StatusWniosku(StrEnum):
    BRAK_DZIALAN = "brak_dzialan"
    ZAPYTANIA_WYSLANE = "zapytania_wyslane"
    KWERENDA = "kwerenda"
    ODPOWIEDZ_PRZYGOTOWANA = "odpowiedz_przygotowana"
    ODPOWIEDZ_WYSLANA = "odpowiedz_wyslana"


class RodzajDokumentu(StrEnum):
    WNIOSEK = "wniosek"
    ODPOWIEDZ_WYDZIALU = "odpowiedz_wydzialu"
    PROJEKT_PISMA = "projekt_pisma"
    USTAWA = "ustawa"
    ZARZADZENIE = "zarzadzenie"
    ARCHIWUM = "archiwum"


# --- Wniosek ---------------------------------------------------------------

class WniosekBaza(SQLModel):
    numer: str = Field(index=True, description="Numer wniosku nadany w urzędzie, np. BKS.1431.12.2026")
    temat: str = Field(description="Krótki opis tematu wniosku")
    data_wplywu: date
    inicjaly: str | None = Field(default=None, max_length=5, description="Inicjały osoby obsługującej")
    dni_kwerendy: int = Field(default=0, ge=0, description="Dodatkowe dni na odpowiedź (przedłużenie)")
    status: StatusWniosku = StatusWniosku.BRAK_DZIALAN
    data_odpowiedzi: date | None = None
    wydzialy: str | None = Field(default=None, description="Symbole wydziałów, do których wysłano zapytania, np. 'WE,WIM'")


class Wniosek(WniosekBaza, table=True):
    id: int | None = Field(default=None, primary_key=True)
    rok: int = Field(index=True)
    lp: int = Field(description="Liczba porządkowa w danym roku")
    utworzono: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WniosekNowy(WniosekBaza):
    pass


class WniosekZmiana(SQLModel):
    numer: str | None = None
    temat: str | None = None
    data_wplywu: date | None = None
    inicjaly: str | None = None
    dni_kwerendy: int | None = Field(default=None, ge=0)
    status: StatusWniosku | None = None
    data_odpowiedzi: date | None = None
    wydzialy: str | None = None


class WniosekWidok(WniosekBaza):
    """Wniosek z polami wyliczanymi, zwracany przez API."""

    id: int
    rok: int
    lp: int
    termin_odpowiedzi: date
    dni_do_terminu: int
    pilny: bool = Field(
        description="Termin minął, jest dziś lub w najbliższy dzień roboczy, a odpowiedź nie została wysłana"
    )

    @classmethod
    def z_wniosku(cls, w: Wniosek, dzis: date | None = None) -> "WniosekWidok":
        termin = termin_odpowiedzi(w.data_wplywu, w.dni_kwerendy)
        return cls(
            **w.model_dump(exclude={"utworzono"}),
            termin_odpowiedzi=termin,
            dni_do_terminu=dni_do_terminu(termin, dzis),
            pilny=czy_pilny(termin, dzis) and w.status != StatusWniosku.ODPOWIEDZ_WYSLANA,
        )


# --- Dokument --------------------------------------------------------------

class Dokument(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    wniosek_id: int | None = Field(default=None, foreign_key="wniosek.id", index=True)
    rodzaj: RodzajDokumentu = Field(index=True)
    nazwa_pliku: str
    sciezka: str | None = Field(default=None, description="Ścieżka pliku w katalogu danych")
    tekst: str = Field(default="", description="Tekst wyciągnięty z pliku")
    wydzial: str | None = Field(default=None, description="Symbol wydziału (dla odpowiedzi wydziałów)")
    dodano: datetime = Field(default_factory=lambda: datetime.now(UTC))
