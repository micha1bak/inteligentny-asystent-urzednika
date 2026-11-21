"""Lista wydziałów i biur Urzędu Miasta Bydgoszczy (źródło: BIP UMB)."""

import json
from functools import cache
from importlib.resources import files


@cache
def wczytaj_wydzialy() -> list[dict]:
    """Wydziały i biura: symbol, nazwa, rodzaj, zakres (roboczy opis do podpowiadania wydziału)."""
    return json.loads(files(__package__).joinpath("zasoby/wydzialy.json").read_text(encoding="utf-8"))["jednostki"]
