"""Wersjonowana baza wiedzy prawnej (ocena_prawna_wniosku_dip_kompletny.json) i pliki aktów prawnych.

Każda zatwierdzona aktualizacja tworzy nową wersję: pełną kopię bazy (`wersje_bazy_wiedzy/ocena_vN.json`)
z datą, od której obowiązuje. Wniosek jest oceniany według wersji obowiązującej w dniu wpływu.
Główny plik bazy i pliki aktów w folderze „Dokumenty i podstawy prawne” zawsze odpowiadają wersji
obowiązującej dziś (synchronizacja po każdej zmianie i przy odczycie). Wycofanie wersji przywraca poprzednią.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

KATALOG_WERSJI = "wersje_bazy_wiedzy"
PLIK_MANIFESTU = "manifest.json"

# Kod aktu z modułu `przepisy` → skrót aktu w metadanych bazy wiedzy.
SKROT_W_BAZIE = {"UDIP": "UDIP", "KPA": "KPA", "ZARZADZENIE_535_2024": "Zarzadzenie_535_2024"}

_blokada = threading.RLock()


class BladBazyWiedzy(Exception):
    def __init__(self, komunikat: str, status: int = 422):
        super().__init__(komunikat)
        self.komunikat = komunikat
        self.status = status


class Wycofanie(BaseModel):
    kiedy: str
    kto: str


class OpisZmiany(BaseModel):
    klucz: str
    opis: str


class Wersja(BaseModel):
    id: str
    utworzono: str
    autor: str
    opis: str
    obowiazuje_od: str | None = None  # None = od zawsze (wersja początkowa)
    plik_bazy: str
    akt_kod: str | None = None
    akt_nazwa: str | None = None
    plik_aktu: str | None = None  # kopia wgranego aktu w katalogu wersji
    nazwa_w_dokumentach: str | None = None  # pod jaką nazwą akt leży w folderze dokumentów
    zastapiony_plik: str | None = None  # kopia pliku, który akt zastąpił (do przywrócenia)
    nazwa_oryginalu: str | None = None  # nazwa zastąpionego pliku w folderze dokumentów
    zmiany: list[OpisZmiany] = []
    wycofana: Wycofanie | None = None


class WersjaZeStatusem(Wersja):
    status: str  # obowiazuje | zaplanowana | archiwalna | wycofana


# ---------------------------------------------------------------- elementy bazy


@dataclass(frozen=True)
class Element:
    """Fragment bazy wiedzy, który model może zaproponować do zmiany (zawsze w całości)."""

    klucz: str
    opis: str
    wartosc: Any


_LISTY_Z_ID = [
    ("algorytm_oceny_krokowej", None, "etap_id", "Etap oceny"),
    ("matryca_oceny_informacji", None, "id", "Matryca oceny"),
    ("katalog_danych_podlegajacych_anonimizacji", "pozycje", "id", "Katalog anonimizacji"),
    ("przepisy_kpa_stosowane_w_postepowaniu_dip", "kluczowe_instytucje_kpa", "instytucja", "Instytucja KPA"),
]


def _lista(ocena: dict, sekcja: str, podsekcja: str | None) -> list:
    wezel = ocena.get(sekcja, {})
    return wezel.get(podsekcja, []) if podsekcja else wezel


def elementy(ocena: dict) -> list[Element]:
    wynik: list[Element] = []
    for sekcja, podsekcja, pole_id, nazwa in _LISTY_Z_ID:
        for el in _lista(ocena, sekcja, podsekcja):
            ident = el.get(pole_id)
            klucz = "/".join(p for p in (sekcja, podsekcja, ident) if p)
            opis = f"{nazwa} {ident}" + (f" – {el['nazwa']}" if el.get("nazwa") else "")
            wynik.append(Element(klucz, opis, el))
    katalog = ocena.get("katalog_danych_podlegajacych_anonimizacji", {})
    if "zasada_ogolna" in katalog:
        wynik.append(
            Element(
                "katalog_danych_podlegajacych_anonimizacji/zasady",
                "Katalog anonimizacji – zasada ogólna i wyjątki",
                {k: katalog[k] for k in ("zasada_ogolna", "wyjatki_ustawowe_art_5_ust_2") if k in katalog},
            )
        )
    if "procedura_wewnetrzna_urzedu_miasta_bydgoszczy" in ocena:
        wynik.append(
            Element(
                "procedura_wewnetrzna_urzedu_miasta_bydgoszczy",
                "Procedura wewnętrzna UMB",
                ocena["procedura_wewnetrzna_urzedu_miasta_bydgoszczy"],
            )
        )
    kpa = ocena.get("przepisy_kpa_stosowane_w_postepowaniu_dip", {})
    if "zakres_stosowania" in kpa:
        wynik.append(
            Element(
                "przepisy_kpa_stosowane_w_postepowaniu_dip/zakres_stosowania",
                "Zakres stosowania KPA w postępowaniu DIP",
                kpa["zakres_stosowania"],
            )
        )
    for a in ocena.get("metadane", {}).get("akty_prawne_i_zrodla", []):
        wynik.append(Element(f"metadane/akty_prawne_i_zrodla/{a['skrot']}", f"Źródło prawa {a['skrot']}", a))
    return wynik


def element(ocena: dict, klucz: str) -> Element | None:
    return next((e for e in elementy(ocena) if e.klucz == klucz), None)


def ustaw_element(ocena: dict, klucz: str, wartosc: Any) -> None:
    """Podmienia element (albo dodaje nowe źródło prawa w metadanych)."""
    if klucz.startswith("metadane/akty_prawne_i_zrodla/"):
        skrot = klucz.rsplit("/", 1)[1]
        akty = ocena["metadane"].setdefault("akty_prawne_i_zrodla", [])
        for i, a in enumerate(akty):
            if a.get("skrot") == skrot:
                akty[i] = wartosc
                return
        akty.append(wartosc)
        return
    if klucz == "katalog_danych_podlegajacych_anonimizacji/zasady":
        ocena["katalog_danych_podlegajacych_anonimizacji"].update(wartosc)
        return
    if klucz == "procedura_wewnetrzna_urzedu_miasta_bydgoszczy":
        ocena[klucz] = wartosc
        return
    if klucz == "przepisy_kpa_stosowane_w_postepowaniu_dip/zakres_stosowania":
        ocena["przepisy_kpa_stosowane_w_postepowaniu_dip"]["zakres_stosowania"] = wartosc
        return
    for sekcja, podsekcja, pole_id, _ in _LISTY_Z_ID:
        prefiks = "/".join(p for p in (sekcja, podsekcja) if p) + "/"
        if klucz.startswith(prefiks):
            ident = klucz[len(prefiks) :]
            lista = _lista(ocena, sekcja, podsekcja)
            for i, el in enumerate(lista):
                if el.get(pole_id) == ident:
                    lista[i] = wartosc
                    return
    raise BladBazyWiedzy(f"Nie ma w bazie wiedzy elementu {klucz}.")


def sprawdz_nowa_wartosc(przed: Any, po: Any, klucz: str) -> None:
    """Nowa wartość musi mieć ten sam typ i nie może gubić pól (ochrona struktury bazy przed błędem modelu)."""
    if przed is None:
        if not isinstance(po, dict):
            raise BladBazyWiedzy(f"{klucz}: nowy element musi być obiektem JSON.")
        return
    if type(po) is not type(przed):
        raise BladBazyWiedzy(f"{klucz}: zmieniony element musi mieć ten sam typ co obecny ({type(przed).__name__}).")
    if isinstance(przed, dict):
        brak = [k for k in przed if k not in po]
        if brak:
            raise BladBazyWiedzy(f"{klucz}: w nowej wersji brakuje pól: {', '.join(brak)}.")
        for k in przed:
            if przed[k] is not None and po[k] is not None and type(po[k]) is not type(przed[k]):
                raise BladBazyWiedzy(f"{klucz}: pole „{k}” musi mieć typ {type(przed[k]).__name__}.")
        for pole_id in ("etap_id", "id", "instytucja", "skrot"):
            if pole_id in przed and po.get(pole_id) != przed[pole_id]:
                raise BladBazyWiedzy(f"{klucz}: nie można zmienić identyfikatora „{pole_id}”.")


# ---------------------------------------------------------------- pliki i manifest


def katalog_wersji(plik_oceny: Path) -> Path:
    return plik_oceny.parent / KATALOG_WERSJI


def _zapisz_atomowo(cel: Path, dane: bytes) -> None:
    cel.parent.mkdir(parents=True, exist_ok=True)
    fd, tymczasowy = tempfile.mkstemp(dir=cel.parent, prefix=f".{cel.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(dane)
        os.replace(tymczasowy, cel)
    except BaseException:
        Path(tymczasowy).unlink(missing_ok=True)
        raise


def _json_bajty(dane: Any) -> bytes:
    return (json.dumps(dane, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _wczytaj_manifest(plik_oceny: Path) -> list[Wersja]:
    plik = katalog_wersji(plik_oceny) / PLIK_MANIFESTU
    if not plik.exists():
        return []
    return [Wersja.model_validate(w) for w in json.loads(plik.read_text(encoding="utf-8"))["wersje"]]


def _zapisz_manifest(plik_oceny: Path, wersje: list[Wersja]) -> None:
    dane = {"opis": "Wersje bazy wiedzy prawnej – zarządzane przez aplikację", "wersje": [w.model_dump() for w in wersje]}
    _zapisz_atomowo(katalog_wersji(plik_oceny) / PLIK_MANIFESTU, _json_bajty(dane))


def _zapewnij_wersje_poczatkowa(plik_oceny: Path) -> list[Wersja]:
    wersje = _wczytaj_manifest(plik_oceny)
    if wersje:
        return wersje
    ocena = json.loads(plik_oceny.read_text(encoding="utf-8"))
    ocena.setdefault("metadane", {})["wersja_bazy"] = "v0"
    _zapisz_atomowo(katalog_wersji(plik_oceny) / "ocena_v0.json", _json_bajty(ocena))
    v0 = Wersja(
        id="v0",
        utworzono=datetime.now().isoformat(timespec="seconds"),
        autor="system",
        opis="Wersja początkowa bazy wiedzy",
        plik_bazy="ocena_v0.json",
    )
    _zapisz_manifest(plik_oceny, [v0])
    return [v0]


def _aktywne(wersje: list[Wersja]) -> list[Wersja]:
    return [w for w in wersje if not w.wycofana]


def _wersja_na_dzien(wersje: list[Wersja], dzien: date) -> Wersja | None:
    kandydaci = [w for w in _aktywne(wersje) if w.obowiazuje_od is None or w.obowiazuje_od <= dzien.isoformat()]
    return max(kandydaci, key=lambda w: (w.obowiazuje_od or "", w.utworzono, _nr(w.id)), default=None)


def _nr(id_wersji: str) -> int:
    return int(id_wersji[1:]) if re.fullmatch(r"v\d+", id_wersji) else -1


def najnowsza(wersje: list[Wersja]) -> Wersja | None:
    """Ostatnio utworzona aktywna wersja (także zaplanowana) – podstawa kolejnej aktualizacji."""
    return max(_aktywne(wersje), key=lambda w: _nr(w.id), default=None)


def sciezka_oceny_na_dzien(plik_oceny: Path, dzien: date) -> tuple[Path, str | None]:
    """Plik bazy obowiązującej danego dnia i id wersji (bez wersjonowania: główny plik, None)."""
    wersje = _wczytaj_manifest(plik_oceny)
    w = _wersja_na_dzien(wersje, dzien) if wersje else None
    if not w:
        return plik_oceny, None
    return katalog_wersji(plik_oceny) / w.plik_bazy, w.id


def wczytaj_najnowsza(plik_oceny: Path) -> tuple[dict, str]:
    """Najnowsza aktywna wersja bazy (podstawa analizy nowego aktu) i jej id."""
    with _blokada:
        wersje = _zapewnij_wersje_poczatkowa(plik_oceny)
        w = najnowsza(wersje)
        assert w is not None  # v0 nie da się wycofać
        return json.loads((katalog_wersji(plik_oceny) / w.plik_bazy).read_text(encoding="utf-8")), w.id


def lista_wersji(plik_oceny: Path, dzis: date | None = None) -> list[WersjaZeStatusem]:
    dzis = dzis or date.today()
    wersje = _wczytaj_manifest(plik_oceny)
    obowiazujaca = _wersja_na_dzien(wersje, dzis)
    wynik = []
    for w in sorted(wersje, key=lambda x: _nr(x.id), reverse=True):
        if w.wycofana:
            status = "wycofana"
        elif obowiazujaca and w.id == obowiazujaca.id:
            status = "obowiazuje"
        elif w.obowiazuje_od and w.obowiazuje_od > dzis.isoformat():
            status = "zaplanowana"
        else:
            status = "archiwalna"
        wynik.append(WersjaZeStatusem(**w.model_dump(), status=status))
    return wynik


# ---------------------------------------------------------------- zapis nowej wersji


@dataclass
class NowyAkt:
    kod: str
    nazwa: str
    nazwa_pliku: str  # pod jaką nazwą zapisać akt w folderze dokumentów
    dane: bytes
    rozszerzenie: str
    zastepuje_plik: str | None = None  # obecny plik tego aktu w folderze dokumentów (może mieć inne rozszerzenie)


def zapisz_wersje(
    plik_oceny: Path,
    katalog_dokumentow: Path,
    baza_wersja: str,
    zmiany: list[tuple[str, str, Any]],  # (klucz, opis, nowa wartość)
    autor: str,
    opis: str,
    obowiazuje_od: date,
    akt: NowyAkt | None,
    walidacja: Any = None,  # funkcja(ocena) – rzuca BladBazyWiedzy, gdy baza po zmianie jest niepoprawna
) -> Wersja:
    with _blokada:
        wersje = _zapewnij_wersje_poczatkowa(plik_oceny)
        podstawa = najnowsza(wersje)
        assert podstawa is not None
        if podstawa.id != baza_wersja:
            raise BladBazyWiedzy(
                f"Baza wiedzy zmieniła się od czasu analizy (teraz {podstawa.id}, analiza na {baza_wersja}). "
                "Przeanalizuj akt ponownie.",
                409,
            )
        katalog = katalog_wersji(plik_oceny)
        ocena = json.loads((katalog / podstawa.plik_bazy).read_text(encoding="utf-8"))
        nowa_ocena = copy.deepcopy(ocena)
        for klucz, _, wartosc in zmiany:
            przed = element(nowa_ocena, klucz)
            sprawdz_nowa_wartosc(przed.wartosc if przed else None, wartosc, klucz)
            ustaw_element(nowa_ocena, klucz, wartosc)

        id_wersji = f"v{max(_nr(w.id) for w in wersje) + 1}"
        nowa_ocena["metadane"]["wersja_bazy"] = id_wersji
        if walidacja:
            walidacja(nowa_ocena)

        wersja = Wersja(
            id=id_wersji,
            utworzono=datetime.now().isoformat(timespec="seconds"),
            autor=autor.strip(),
            opis=opis,
            obowiazuje_od=obowiazuje_od.isoformat(),
            plik_bazy=f"ocena_{id_wersji}.json",
            zmiany=[OpisZmiany(klucz=k, opis=o) for k, o, _ in zmiany],
        )
        if akt:
            wersja.akt_kod, wersja.akt_nazwa = akt.kod, akt.nazwa
            wersja.plik_aktu = f"akt_{id_wersji}{akt.rozszerzenie}"
            wersja.nazwa_w_dokumentach = akt.nazwa_pliku
            _zapisz_atomowo(katalog / wersja.plik_aktu, akt.dane)
            # pierwsza zmiana tego aktu: zachowujemy oryginał, żeby dało się go przywrócić
            if not any(w.akt_kod == akt.kod for w in wersje) and akt.zastepuje_plik:
                oryginal = katalog_dokumentow / akt.zastepuje_plik
                if oryginal.exists():
                    wersja.nazwa_oryginalu = akt.zastepuje_plik
                    wersja.zastapiony_plik = f"oryginal_{id_wersji}_{akt.zastepuje_plik}"
                    shutil.copy2(oryginal, katalog / wersja.zastapiony_plik)
        _zapisz_atomowo(katalog / wersja.plik_bazy, _json_bajty(nowa_ocena))
        _zapisz_manifest(plik_oceny, [*wersje, wersja])
        synchronizuj(plik_oceny, katalog_dokumentow)
        return wersja


def wycofaj(plik_oceny: Path, katalog_dokumentow: Path, id_wersji: str, autor: str) -> Wersja:
    with _blokada:
        wersje = _wczytaj_manifest(plik_oceny)
        w = next((x for x in wersje if x.id == id_wersji), None)
        if not w:
            raise BladBazyWiedzy(f"Nie ma wersji {id_wersji}.", 404)
        if w.id == "v0":
            raise BladBazyWiedzy("Wersji początkowej nie można wycofać.")
        if w.wycofana:
            raise BladBazyWiedzy(f"Wersja {id_wersji} jest już wycofana.")
        w.wycofana = Wycofanie(kiedy=datetime.now().isoformat(timespec="seconds"), kto=autor.strip())
        _zapisz_manifest(plik_oceny, wersje)
        synchronizuj(plik_oceny, katalog_dokumentow)
        return w


def synchronizuj(plik_oceny: Path, katalog_dokumentow: Path, dzis: date | None = None) -> None:
    """Główny plik bazy i pliki aktów w folderze dokumentów = wersja obowiązująca dziś."""
    dzis = dzis or date.today()
    with _blokada:
        wersje = _wczytaj_manifest(plik_oceny)
        if not wersje:
            return
        katalog = katalog_wersji(plik_oceny)
        obowiazujaca = _wersja_na_dzien(wersje, dzis)
        if obowiazujaca:
            _zapisz_jesli_inny(plik_oceny, (katalog / obowiazujaca.plik_bazy).read_bytes())

        for kod in {w.akt_kod for w in wersje if w.akt_kod}:
            dotyczace = [w for w in wersje if w.akt_kod == kod]
            pierwsza = min(dotyczace, key=lambda w: _nr(w.id))
            w_mocy = [
                w for w in _aktywne(dotyczace) if w.obowiazuje_od is None or w.obowiazuje_od <= dzis.isoformat()
            ]
            cel: Path | None = None
            if w_mocy:
                aktualna = max(w_mocy, key=lambda w: (w.obowiazuje_od or "", _nr(w.id)))
                cel = katalog_dokumentow / (aktualna.nazwa_w_dokumentach or "")
                _zapisz_jesli_inny(cel, (katalog / (aktualna.plik_aktu or "")).read_bytes())
            elif pierwsza.zastapiony_plik and pierwsza.nazwa_oryginalu:
                cel = katalog_dokumentow / pierwsza.nazwa_oryginalu
                _zapisz_jesli_inny(cel, (katalog / pierwsza.zastapiony_plik).read_bytes())
            # inne pliki tego aktu (np. stary PDF po wgraniu DOCX albo akt dodany od zera i wycofany) usuwamy,
            # żeby wyszukiwarka przepisów nie widziała dwóch wersji
            nazwy = {w.nazwa_w_dokumentach for w in dotyczace} | {pierwsza.nazwa_oryginalu}
            for nazwa in nazwy - {None, cel.name if cel else None}:
                (katalog_dokumentow / nazwa).unlink(missing_ok=True)


def _zapisz_jesli_inny(cel: Path, dane: bytes) -> None:
    # bez zbędnego zapisu: zmiana czasu modyfikacji unieważnia indeks przepisów i cache bazy
    if cel.exists() and cel.read_bytes() == dane:
        return
    _zapisz_atomowo(cel, dane)


_OSTATNIA_SYNCHRONIZACJA: dict[Path, tuple[int, str]] = {}


def synchronizuj_jesli_trzeba(plik_oceny: Path, katalog_dokumentow: Path) -> None:
    """Synchronizacja przy odczycie – tylko po zmianie manifestu albo dnia (wersja zaplanowana mogła wejść w życie)."""
    manifest = katalog_wersji(plik_oceny) / PLIK_MANIFESTU
    if not manifest.exists():
        return
    klucz = (manifest.stat().st_mtime_ns, date.today().isoformat())
    if _OSTATNIA_SYNCHRONIZACJA.get(plik_oceny) == klucz:
        return
    synchronizuj(plik_oceny, katalog_dokumentow)
    _OSTATNIA_SYNCHRONIZACJA[plik_oceny] = klucz
