"""Składanie pisma BKS ze wzoru (wzory_pism.json) i pól podanych przez model.

Kod odpowiada za cały układ pisma: nagłówek, datę, znak sprawy, adresata, tytuł, zwrot,
stałe sformułowania wzoru, numerację „Ad 1, Ad 2 …”, załączniki, podpis i stopkę.
Model podaje wyłącznie wartości pól wybranego wzoru (fragmenty wstawiane w «pole»).

Wynikiem jest `Pismo` – struktura (z typami bloków treści), z której frontend rysuje
stronę A4 w układzie oryginalnych pism BKS, oraz jego wersja tekstowa (`Pismo.tekst`).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date

MIESIACE = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
            "sierpnia", "września", "października", "listopada", "grudnia")

# forma -> (zwrot, „przez …”)
FORMY = {
    "pan": ("Szanowny Panie,", "Pana"),
    "pani": ("Szanowna Pani,", "Panią"),
    "państwo": ("Szanowni Państwo,", "Państwa"),
    "panstwo": ("Szanowni Państwo,", "Państwa"),
}
FORMA_NIEZNANA = ("[[do uzupełnienia: Szanowny Panie / Szanowna Pani / Szanowni Państwo]],", "[[Pana / Panią / Państwa]]")
POLA_KODU = {"przez_kogo", "komorka_merytoryczna", "numer_sprawy", "z_dnia", "data_wniosku", "wnioskodawca"}
ID_WZORU_UNIWERSALNEGO = "odpowiedz_uniwersalna"
ID_WZORU_DECYZJI = "decyzja_administracyjna"
_NAGLOWKI_SEKCJI = {"orzekam:", "UZASADNIENIE", "POUCZENIE"}

WZOR_UNIWERSALNY: dict = {
    "id": ID_WZORU_UNIWERSALNEGO,
    "nazwa": "Uniwersalny wzór odpowiedzi",
    "zwrot": True,
    "zalaczniki": True,
    "tresc": (
        "w odpowiedzi na wystosowany przez «przez_kogo» wniosek«z_dnia» o udostępnienie informacji publicznej "
        "w zakresie «zakres_wniosku», po przeprowadzeniu analizy sprawy we współpracy z komórką merytoryczną, "
        "tj. «komorka_merytoryczna» Urzędu Miasta Bydgoszczy, uprzejmie informuję, co następuje.\n"
        "«stanowisko_glowne»\n"
        "?punkty_odpowiedzi «punkty_odpowiedzi»\n"
        "?wyjasnienie «wyjasnienie»\n"
        "?podstawa_prawna Niniejszej odpowiedzi udzielam na podstawie «podstawa_prawna».\n"
        "?informacje_dodatkowe «informacje_dodatkowe»"
    ),
    "pola": {
        "zakres_wniosku": {"opis": "czego dotyczy wniosek", "typ": "tekst"},
        "stanowisko_glowne": {"opis": "stanowisko urzędu i główna treść odpowiedzi", "typ": "tekst"},
        "punkty_odpowiedzi": {"opis": "odpowiedzi punkt po punkcie", "typ": "punkty", "opcjonalne": True},
        "wyjasnienie": {"opis": "uzasadnienie faktyczne i prawne", "typ": "tekst", "opcjonalne": True},
        "podstawa_prawna": {"opis": "podstawa prawna rozstrzygnięcia", "typ": "tekst", "opcjonalne": True},
        "informacje_dodatkowe": {"opis": "dodatkowe informacje lub pouczenie", "typ": "tekst", "opcjonalne": True},
    },
}

WZOR_DECYZJI: dict = {
    "id": ID_WZORU_DECYZJI,
    "nazwa": "Decyzja administracyjna (odmowa udostępnienia / umorzenie postępowania)",
    "tytul": "DECYZJA",
    "zwrot": False,
    "podpis": "z up. Prezydenta Miasta Bydgoszczy\n[[do uzupełnienia: imię, nazwisko i stanowisko osoby upoważnionej]]",
    "tresc": (
        "Na podstawie art. 104 i art. 107 ustawy z dnia 14 czerwca 1960 r. – Kodeks postępowania administracyjnego "
        "(t.j. Dz. U. z 2025 r. poz. 1691) oraz art. 16 ust. 1 ustawy z dnia 6 września 2001 r. o dostępie do informacji "
        "publicznej (t.j. Dz. U. z 2022 r. poz. 902, z 2025 r. poz. 1844) w zw. z «podstawa_szczegolowa», "
        "po rozpatrzeniu wniosku«z_dnia» złożonego przez «wnioskodawca» o udostępnienie informacji publicznej "
        "w zakresie «zakres_wniosku»,\n"
        "orzekam:\n"
        "«sentencja»\n"
        "UZASADNIENIE\n"
        "W dniu «data_wniosku» do Urzędu Miasta Bydgoszczy wpłynął wniosek o udostępnienie informacji publicznej "
        "dotyczącej «zakres_wniosku».\n"
        "Po przeprowadzeniu analizy sprawy we współpracy z komórką merytoryczną, tj. «komorka_merytoryczna» "
        "Urzędu Miasta Bydgoszczy, organ ustalił następujący stan faktyczny i prawny.\n"
        "«uzasadnienie_faktyczne_i_prawne»\n"
        "?osoby_stanowisko Stosownie do art. 16 ust. 2 pkt 2 ustawy o dostępie do informacji publicznej wskazuję, "
        "że stanowisko w toku postępowania zajęli: «osoby_stanowisko».\n"
        "?chronione_podmioty Oznaczenie podmiotów, ze względu na których dobra wydano niniejszą decyzję: «chronione_podmioty».\n"
        "Mając na uwadze powyższe, należało orzec jak w sentencji.\n"
        "POUCZENIE\n"
        "Od niniejszej decyzji służy stronie odwołanie do Samorządowego Kolegium Odwoławczego w Bydgoszczy "
        "za pośrednictwem Prezydenta Miasta Bydgoszczy w terminie 14 dni od dnia jej doręczenia "
        "(art. 127 § 1 i 2 oraz art. 129 § 1 i 2 KPA).\n"
        "Przed upływem terminu do wniesienia odwołania strona może zrzec się prawa do wniesienia odwołania wobec "
        "organu administracji publicznej, który wydał decyzję (art. 127a § 1 KPA). Z dniem doręczenia organowi "
        "oświadczenia o zrzeczeniu się prawa do wniesienia odwołania przez ostatnią ze stron postępowania decyzja "
        "staje się ostateczna i prawomocna (art. 127a § 2 KPA)."
    ),
    "pola": {
        "podstawa_szczegolowa": {"opis": "szczegółowe przepisy materialne", "typ": "tekst"},
        "zakres_wniosku": {"opis": "czego dotyczy wniosek", "typ": "tekst"},
        "sentencja": {"opis": "rozstrzygnięcie decyzji", "typ": "tekst"},
        "uzasadnienie_faktyczne_i_prawne": {"opis": "uzasadnienie faktyczne i prawne", "typ": "tekst"},
        "osoby_stanowisko": {"opis": "osoby zajmujące stanowisko w toku postępowania", "typ": "tekst", "opcjonalne": True},
        "chronione_podmioty": {"opis": "podmioty, ze względu na których dobra wydano decyzję", "typ": "tekst", "opcjonalne": True},
    },
}

_POLE = re.compile(r"«([a-z_]+)»")
_OPCJONALNA = re.compile(r"^\?([a-z_]+) (.*)$")


def do_uzupelnienia(opis: str) -> str:
    return f"[[do uzupełnienia: {opis}]]"


@dataclass
class DanePisma:
    """Dane z odpowiedzi modelu i z wniosku potrzebne do złożenia pisma."""

    pola: dict[str, str | list[str]] = field(default_factory=dict)
    forma: str = ""
    adresat: list[str] = field(default_factory=list)
    zalaczniki: list[str] = field(default_factory=list)
    komorka_merytoryczna: str = ""
    znak_sprawy: str = ""
    data: date | None = None
    data_wniosku: str = ""
    wnioskodawca: str = ""


@dataclass
class Blok:
    """Element treści pisma. typ: zwrot | akapit | ad (nagłówek „Ad n”) | linia (bez justowania)."""

    typ: str
    tekst: str


@dataclass
class Pismo:
    naglowek: list[str]
    data: str
    znak: str
    adresat: list[str]
    tytul: list[str]
    tresc: list[Blok]
    zakonczenie: str
    podpis: list[str]
    stopka: list[str]

    @property
    def tekst(self) -> str:
        linie = [*self.naglowek, self.data, self.znak, *self.adresat, *self.tytul, *(b.tekst for b in self.tresc),
                 self.zakonczenie, *self.podpis]
        return "\n".join([*linie, "", *self.stopka] if self.stopka else linie)

    def jako_slownik(self) -> dict:
        return asdict(self)


def data_slownie(d: date) -> str:
    return f"{d.day} {MIESIACE[d.month - 1]} {d.year}"


def numer_sprawy(znak: str) -> str:
    """BKS.IV.1431.307.2025 -> 307 (numer kolejny ze znaku sprawy)."""
    m = re.search(r"\.(\d+)\.\d{4}$", znak.strip())
    return m.group(1) if m else ""


def _czysc(wartosc: str) -> str:
    """Wartość pola: bez znaczników «» i zbędnych spacji."""
    return re.sub(r"\s+", " ", str(wartosc).replace("«", "").replace("»", "")).strip()


def _linie(wartosc: str | list[str]) -> list[str]:
    elementy = wartosc if isinstance(wartosc, list) else str(wartosc).splitlines()
    return [c for e in elementy if (c := _czysc(e))]


def _formatuj_date_wniosku(surowa: str) -> str:
    surowa = surowa.strip()
    if not surowa:
        return ""
    try:
        return f"{data_slownie(date.fromisoformat(surowa))} r."
    except ValueError:
        return surowa


def zloz_tresc(wzor: dict, dane: DanePisma) -> tuple[list[Blok], list[str]]:
    """Wypełnia treść wzoru. Zwraca (bloki treści, opisy brakujących pól)."""
    definicje: dict[str, dict] = wzor.get("pola", {})
    zwrot, przez_kogo = FORMY.get(dane.forma.strip().lower(), FORMA_NIEZNANA)
    data_wn_tekst = _formatuj_date_wniosku(dane.data_wniosku)
    wartosci: dict[str, str | list[str]] = {
        "przez_kogo": przez_kogo,
        "komorka_merytoryczna": _czysc(dane.komorka_merytoryczna) or do_uzupelnienia("komórka merytoryczna"),
        "numer_sprawy": numer_sprawy(dane.znak_sprawy) or do_uzupelnienia("numer sprawy"),
        "z_dnia": f" z dnia {data_wn_tekst}" if data_wn_tekst else "",
        "data_wniosku": data_wn_tekst or do_uzupelnienia("data wpływu wniosku"),
        "wnioskodawca": _czysc(dane.wnioskodawca) or "Wnioskodawcę",
    }
    braki: list[str] = []
    for nazwa, definicja in definicje.items():
        surowa = dane.pola.get(nazwa)
        if definicja.get("typ") in ("punkty", "linie"):
            wartosc: str | list[str] = _linie(surowa) if surowa else []
        else:
            wartosc = _czysc(" ".join(surowa) if isinstance(surowa, list) else surowa or "")
        if not wartosc and not definicja.get("opcjonalne"):
            opis = definicja["opis"].split(" – ")[0]
            braki.append(opis)
            wartosc = do_uzupelnienia(opis)
        wartosci[nazwa] = wartosc

    def wstaw(linia: str) -> list[Blok]:
        """Wstawia wartości pól w linię wzoru; pole listowe zajmujące całą linię rozwija na wiele bloków."""
        if (m := _POLE.fullmatch(linia.strip())) and isinstance(wartosci.get(m.group(1)), list):
            nazwa = m.group(1)
            if definicje.get(nazwa, {}).get("typ") == "punkty":
                return [b for i, e in enumerate(wartosci[nazwa], 1) for b in (Blok("ad", f"Ad {i}"), Blok("akapit", e))]
            return [Blok("linia", e) for e in wartosci[nazwa]]

        def zamien(m: re.Match) -> str:
            w = wartosci.get(m.group(1), do_uzupelnienia(m.group(1)))
            w = "; ".join(w) if isinstance(w, list) else w
            # „…, że 5697 osób.” + „.” ze wzoru -> jedna kropka
            if linia[m.end() : m.end() + 1] in (".", ",") and w.endswith((".", ",", ";")):
                w = w[:-1]
            return w

        tekst = _POLE.sub(zamien, linia)
        if tekst.strip() in _NAGLOWKI_SEKCJI:
            return [Blok("ad", tekst.strip())]
        return [Blok("linia" if tekst.startswith("Załącznik") else "akapit", tekst)]

    bloki: list[Blok] = [Blok("zwrot", zwrot)] if wzor.get("zwrot") else []
    for linia in wzor["tresc"].splitlines():
        if m := _OPCJONALNA.match(linia):
            if not wartosci.get(m.group(1)):
                continue
            linia = m.group(2)
        bloki += wstaw(linia)

    if wzor.get("zalaczniki") and (zal := _linie(dane.zalaczniki)):
        if len(zal) == 1:
            bloki.append(Blok("linia", f"Załącznik: {zal[0]}"))
        else:
            bloki += [Blok("linia", "Załączniki:"), *(Blok("linia", f"{i}. {z}") for i, z in enumerate(zal, 1))]
    return bloki, braki


_NAGLOWKI_DO_POMINIECIA = (
    "urząd miasta bydgoszczy",
    "biuro komunikacji społecznej",
    "łączę wyrazy szacunku",
    "z poważaniem",
    "85-102 bydgoszcz",
)


def zloz_pismo_z_tekstu(
    akapity: list[str],
    wzory: dict,
    dane: DanePisma,
    *,
    tytul: list[str] | None = None,
    zwrot: bool = True,
    podpis_wlasny: str | None = None,
) -> Pismo:
    """Składa kompletne pismo A4 z akapitów sformułowanych przez AI, dodając nagłówek, zwrot, podpis i stopkę BKS."""
    zwrot_tekst, _ = FORMY.get(dane.forma.strip().lower(), FORMA_NIEZNANA)
    oczyszczone = [
        linia
        for a in akapity
        for surowa in (a.splitlines() if isinstance(a, str) else [str(a)])
        if (linia := _czysc(surowa)) and not any(linia.lower().startswith(p) for p in _NAGLOWKI_DO_POMINIECIA)
    ]

    bloki: list[Blok] = []
    ma_zwrot = bool(oczyszczone and oczyszczone[0].lower().startswith(("szanown", "dzień dobry", "witam")))
    if zwrot and not ma_zwrot:
        bloki.append(Blok("zwrot", zwrot_tekst))

    for i, linia in enumerate(oczyszczone):
        if i == 0 and ma_zwrot:
            bloki.append(Blok("zwrot", linia))
        elif linia in _NAGLOWKI_SEKCJI or re.fullmatch(r"Ad\.?\s*\d+\.?", linia):
            bloki.append(Blok("ad", linia))
        elif linia.startswith("Załącznik"):
            bloki.append(Blok("linia", linia))
        else:
            bloki.append(Blok("akapit", linia))

    if zal := _linie(dane.zalaczniki):
        if not any(b.tekst.startswith("Załącznik") for b in bloki):
            if len(zal) == 1:
                bloki.append(Blok("linia", f"Załącznik: {zal[0]}"))
            else:
                bloki += [Blok("linia", "Załączniki:"), *(Blok("linia", f"{i}. {z}") for i, z in enumerate(zal, 1))]

    podpis_tekst = podpis_wlasny or wzory["podpis"]
    zakonczenie, *podpis = podpis_tekst.splitlines()
    return Pismo(
        naglowek=wzory["naglowek"].splitlines(),
        data=f"Bydgoszcz, dnia {data_slownie(dane.data or date.today())} r.",
        znak=dane.znak_sprawy.strip() or do_uzupelnienia("znak sprawy"),
        adresat=_linie(dane.adresat),
        tytul=_linie(tytul) if tytul else [],
        tresc=bloki,
        zakonczenie=zakonczenie,
        podpis=podpis,
        stopka=wzory.get("stopka", "").splitlines(),
    )


def zloz_pismo(wzor: dict | None, wzory: dict, dane: DanePisma) -> tuple[Pismo, list[str]]:
    """Całe pismo: nagłówek, data, znak sprawy, adresat, [tytuł], treść, zakończenie, podpis, stopka."""
    uzyty_wzor = wzor if wzor is not None else WZOR_UNIWERSALNY
    tresc, braki = zloz_tresc(uzyty_wzor, dane)
    podpis_tekst = uzyty_wzor.get("podpis") or wzory["podpis"]
    zakonczenie, *podpis = podpis_tekst.splitlines()
    pismo = Pismo(
        naglowek=wzory["naglowek"].splitlines(),
        data=f"Bydgoszcz, dnia {data_slownie(dane.data or date.today())} r.",
        znak=dane.znak_sprawy.strip() or do_uzupelnienia("znak sprawy"),
        adresat=_linie(dane.adresat),
        tytul=uzyty_wzor.get("tytul", "").splitlines(),
        tresc=tresc,
        zakonczenie=zakonczenie,
        podpis=podpis,
        stopka=wzory.get("stopka", "").splitlines(),
    )
    return pismo, braki
