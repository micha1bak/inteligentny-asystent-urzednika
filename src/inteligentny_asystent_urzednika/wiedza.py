"""Baza wiedzy przekazywana do modelu: model oceny prawnej, archiwum spraw z werdyktami i wzory pism UMB."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .archiwum import POLA_SPRAWY
from .podobienstwo import najpodobniejsze
from .wzor.pismo import ID_WZORU_DECYZJI, ID_WZORU_UNIWERSALNEGO, WZOR_DECYZJI, WZOR_UNIWERSALNY

# Wydziały i biura Urzędu Miasta Bydgoszczy (nazwy z BIP: /artykuly/198/wydzialy, /artykuly/1158/biura).
JEDNOSTKI_UMB: list[dict] = json.loads(
    (Path(__file__).parent / "zasoby" / "wydzialy.json").read_text(encoding="utf-8")
)["jednostki"]

# Wzory dobierane, gdy werdykty podobnych spraw nic nie podpowiadają.
WZORY_DOMYSLNE = ["udostepnienie_w_tresci", "nieposiadanie_wskazanie_dysponenta", "brak_danych", ID_WZORU_UNIWERSALNEGO]


@dataclass(frozen=True)
class Wybor:
    """Ile materiału dołączyć w trybie „wybrany” – zmniejszane, dopóki zapytanie nie zmieści się w limicie."""

    matryca: int = 3
    sprawy: int = 3
    wzory: int = 2
    anonimizacja: bool = True
    dlugosc_rozstrzygniecia: int = 220


# Kolejne, coraz oszczędniejsze warianty kontekstu.
STOPNIE_WYBORU = [
    Wybor(),
    Wybor(anonimizacja=False),
    Wybor(matryca=2, sprawy=2, anonimizacja=False),
    Wybor(matryca=2, sprawy=2, wzory=1, anonimizacja=False, dlugosc_rozstrzygniecia=120),
    Wybor(matryca=1, sprawy=1, wzory=1, anonimizacja=False, dlugosc_rozstrzygniecia=120),
    Wybor(matryca=1, sprawy=1, wzory=1, anonimizacja=False, dlugosc_rozstrzygniecia=0),
]


@dataclass(frozen=True)
class Wiedza:
    ocena: dict
    werdykty: dict
    wzory: dict

    @property
    def slownik_werdyktow(self) -> dict[str, str]:
        return self.ocena["metadane"]["slownik_werdyktow"]

    @property
    def sprawy(self) -> list[dict]:
        """Aktualne sprawy z archiwum, bez pól technicznych (historia zmian, znacznik nieaktualności)."""
        return [
            {k: s[k] for k in POLA_SPRAWY if k in s} for s in self.werdykty["sprawy"] if not s.get("nieaktualna")
        ]

    @property
    def sygnatury(self) -> set[str]:
        return {s["sygnatura"] for s in self.sprawy}

    @property
    def id_wzorow(self) -> set[str]:
        return {w["id"] for w in self.wzory["wzory"]}

    def wzor(self, id_wzoru: str) -> dict | None:
        return next((w for w in self.wzory["wzory"] if w["id"] == id_wzoru), None)

    def wzor_uniwersalny(self) -> dict:
        return self.wzor(ID_WZORU_UNIWERSALNEGO) or WZOR_UNIWERSALNY

    def wzor_decyzji(self) -> dict:
        return self.wzor(ID_WZORU_DECYZJI) or WZOR_DECYZJI

    # --- tryb „pelny”: wszystko (ok. 25 tys. tokenów – wymaga planu Groq z wyższym limitem) ---

    def kontekst_pelny(self) -> str:
        return (
            f"MODEL OCENY PRAWNEJ:\n{_zwarty(self.ocena)}\n\n"
            f"JEDNOSTKI UMB:\n{_zwarty([j['nazwa'] for j in JEDNOSTKI_UMB])}\n\n"
            f"ARCHIWUM SPRAW:\n{_zwarty(self.sprawy)}\n\n"
            f"WZORY PISM UMB:\n{_zwarty(self._wzory_do_kontekstu(self.wzory['wzory']))}"
        )

    # --- tryb „wybrany”: streszczenie algorytmu + fragmenty dopasowane do treści wniosku ---

    def kontekst_wybrany(self, tresc_wniosku: str, wybor: Wybor = Wybor()) -> str:
        ocena = self.ocena
        etapy = []
        for e in ocena["algorytm_oceny_krokowej"]:
            etap = {"id": e["etap_id"], "nazwa": e["nazwa"], "podstawa": e.get("podstawa_prawna", [])}
            rozstrzygniecie = (e.get("werdykt") or {}).get("rozstrzygniecie", "")
            if wybor.dlugosc_rozstrzygniecia and rozstrzygniecie:
                etap["rozstrzygniecie"] = _skroc(rozstrzygniecie, wybor.dlugosc_rozstrzygniecia)
            etapy.append(etap)

        matryca = ocena["matryca_oceny_informacji"]
        dopasowana = najpodobniejsze(
            tresc_wniosku, matryca, [f"{m['informacja']} {m['zalozenia']}" for m in matryca], wybor.matryca
        )
        podobne = self.podobne_sprawy(tresc_wniosku, 3)

        model = {
            "akty_prawne": [
                {"skrot": a["skrot"], "nazwa": a["pelna_nazwa"], "publikator": a["publikator"]}
                for a in ocena["metadane"]["akty_prawne_i_zrodla"][:3]
            ],
            "slownik_werdyktow": self.slownik_werdyktow,
            "etapy_oceny": etapy,
            "matryca_dopasowana_do_wniosku": dopasowana,
            "jednostki_umb": [j["nazwa"] for j in JEDNOSTKI_UMB],
        }
        if wybor.anonimizacja:
            model["katalog_anonimizacji"] = [
                p["informacja"] for p in ocena["katalog_danych_podlegajacych_anonimizacji"]["pozycje"]
            ]
        pola = ("sygnatura", "komorka_merytoryczna", "wniosek_o_co", "jaka_odpowiedz", "werdykt", "etap_i_podstawa")
        archiwum = [{k: s[k] for k in pola if k in s} for s in podobne[: wybor.sprawy]]
        wzory = self.wybierz_wzory(tresc_wniosku, podobne, wybor.wzory)
        return (
            f"MODEL OCENY PRAWNEJ (wybrane fragmenty):\n{_zwarty(model)}\n\n"
            f"ARCHIWUM SPRAW (najbardziej podobne):\n{_zwarty(archiwum)}\n\n"
            f"WZORY PISM UMB (dobrane do sprawy):\n{_zwarty(self._wzory_do_kontekstu(wzory))}"
        )

    def podobne_sprawy(self, tresc_wniosku: str, limit: int) -> list[dict]:
        sprawy = self.sprawy
        return najpodobniejsze(
            tresc_wniosku, sprawy, [f"{s['wniosek_o_co']} {s['komorka_merytoryczna']}" for s in sprawy], limit
        )

    def wybierz_wzory(self, tresc_wniosku: str, podobne: list[dict], limit: int) -> list[dict]:
        """Wzory pasujące do werdyktów najbardziej podobnych spraw, w kolejności podobieństwa sprawy,
        a w obrębie tego samego werdyktu – według dopasowania opisu wzoru („kiedy”) do treści wniosku."""
        wszystkie = self.wzory["wzory"]
        wg_opisu = najpodobniejsze(tresc_wniosku, wszystkie, [f"{w['nazwa']} {w['kiedy']}" for w in wszystkie], len(wszystkie))
        ranga_opisu = {w["id"]: i for i, w in enumerate(wg_opisu)}

        punkty: dict[str, float] = {}
        for pozycja, sprawa in enumerate(podobne):
            for w in wszystkie:
                if w["id"] in (ID_WZORU_UNIWERSALNEGO, ID_WZORU_DECYZJI):
                    continue
                if sprawa.get("werdykt") in w["werdykty"]:
                    punkty[w["id"]] = punkty.get(w["id"], 0) + (len(podobne) - pozycja)
        wybrane = sorted(punkty, key=lambda i: (-punkty[i], ranga_opisu.get(i, 99)))
        tresc_mala = tresc_wniosku.lower()
        if any(s in tresc_mala for s in ("sąsiad", "pesel", "prywatn", "tajemnic", "odmow", "umorze", "podatnik", "zaległości")):
            wybrane.insert(1 if wybrane else 0, ID_WZORU_DECYZJI)
        for domyslny in WZORY_DOMYSLNE:
            if domyslny not in wybrane:
                wybrane.append(domyslny)
        return [w for i in wybrane[:limit] if (w := self.wzor(i))]

    def _wzory_do_kontekstu(self, wzory: list[dict]) -> dict:
        # Modelowi wystarczą: id, kiedy, treść (żeby fragmenty pasowały do zdania) i opis pól.
        # Nagłówek, podpis i stopkę wstawia kod (wzor/pismo.py). Uwagi tylko przy najlepiej dopasowanym wzorze.
        return {
            "zasady_wypelniania": self.wzory["zasady_wypelniania"],
            "wzory": [
                {
                    "id": w["id"],
                    "kiedy": w["kiedy"],
                    "tresc": w["tresc"],
                    "pola": {
                        k: (f"[{p['typ']}] " if p.get("typ", "tekst") != "tekst" else "")
                        + ("(opcjonalne) " if p.get("opcjonalne") else "")
                        + p["opis"]
                        for k, p in w.get("pola", {}).items()
                    },
                    **({"zalaczniki": True} if w.get("zalaczniki") else {}),
                    **({"uwagi": w["uwagi"]} if i == 0 and w.get("uwagi") else {}),
                }
                for i, w in enumerate(wzory)
            ],
        }


def _skroc(tekst: str, dlugosc: int) -> str:
    return tekst if len(tekst) <= dlugosc else tekst[:dlugosc].rsplit(" ", 1)[0] + "…"


def _zwarty(dane: object) -> str:
    return json.dumps(dane, ensure_ascii=False, separators=(",", ":"))


def wczytaj_wiedze(plik_oceny: Path, plik_werdyktow: Path, plik_wzorow: Path) -> Wiedza:
    """Wczytuje bazę wiedzy; ponownie tylko po zmianie któregoś z plików (np. edycji archiwum z aplikacji)."""
    znaczniki = tuple(p.stat().st_mtime_ns for p in (plik_oceny, plik_werdyktow, plik_wzorow))
    return _wczytaj_wiedze(plik_oceny, plik_werdyktow, plik_wzorow, znaczniki)


@lru_cache(maxsize=8)
def _wczytaj_wiedze(plik_oceny: Path, plik_werdyktow: Path, plik_wzorow: Path, _znaczniki: tuple) -> Wiedza:
    return Wiedza(
        ocena=json.loads(plik_oceny.read_text(encoding="utf-8")),
        werdykty=json.loads(plik_werdyktow.read_text(encoding="utf-8")),
        wzory=json.loads(plik_wzorow.read_text(encoding="utf-8")),
    )
