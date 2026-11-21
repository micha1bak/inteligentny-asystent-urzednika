"""Filtr pisma odręcznego + konwersja dokumentów na TXT.

1. Model qwen/qwen3.8-27b (Groq) klasyfikuje każdą stronę: ODRĘCZNE / DRUKOWANE.
2. Jeśli którakolwiek strona jest odręczna, dokument jest odfiltrowany:
   zwracana jest informacja, że użytkownik musi sam ocenić dokument.
3. Dokumenty drukowane są konwertowane na TXT: tekst z warstwy tekstowej PDF,
   a dla stron bez niej (skan druku) – odczyt modelem.
4. Pliki DOCX to dokumenty tekstowe z definicji – tekst jest wyciągany bezpośrednio,
   bez modelu (nic nie jest wysyłane do API).

Klucz: GROQ_API_KEY w zmiennych środowiskowych albo w pliku .env.

Użycie (jeden plik na raz):
    python -m inteligentny_asystent_urzednika.konwersja.ocr_llm PLIK [-o PLIK.txt]
(obsługiwane: .pdf, .docx, .png, .jpg, .jpeg, .tif, .tiff)

Wynik: plik konwersja/pliki_txt/<nazwa>.txt (albo w miejscu podanym w -o),
a jego ścieżka jest wypisywana na stdout. Kody wyjścia:
    0 – skonwertowano, 3 – pismo odręczne (brak TXT, komunikat na stdout), 1 – błąd.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from xml.etree import ElementTree
from dataclasses import dataclass
from pathlib import Path

# Model wizyjny OCR – domyślnie Groq; docelowo lokalny serwer zgodny z API OpenAI (np. Ollama: OCR_URL=
# http://localhost:11434/v1/chat/completions, OCR_MODEL=qwen2.5vl:7b) – wtedy skany nie opuszczają urzędu.
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
URL = os.getenv("OCR_URL", GROQ_URL)
MODEL = os.getenv("OCR_MODEL", "qwen/qwen3.8-27b")
DPI = 200
KOD_ODRECZNY = 3  # kod wyjścia, gdy dokument jest odręczny
PROBY = 6  # ponowienia przy limicie zapytań (HTTP 429) i błędach serwera
MIN_ZNAKOW_WARSTWY = 40  # mniej znaków w warstwie tekstowej = strona to skan
KATALOG_TXT = Path(__file__).parent / "pliki_txt"  # domyślne miejsce plików .txt
ROZSZERZENIA = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

PROMPT_KLASYFIKACJA = (
    "Oceń, czy główna treść pisma na obrazie jest napisana odręcznie, czy wydrukowana "
    "(komputer, maszyna do pisania). Nie bierz pod uwagę podpisów, parafek, pieczątek, "
    "naklejek z kodem kreskowym ani odręcznych dopisków urzędu (np. numer wpływu, dekretacja). "
    "Odpowiedz jednym słowem: ODRĘCZNE albo DRUKOWANE."
)
PROMPT_ODCZYT = (
    "Przepisz dokładnie cały tekst pisma z obrazu, po polsku, bez poprawiania i bez komentarzy. "
    "Każdy akapit w osobnej linii. Nieczytelne słowo zastąp znacznikiem [nieczytelne]. "
    "Pomiń pieczątki wpływu, naklejki z kodem kreskowym i numery kancelaryjne urzędu. "
    "Zwróć wyłącznie przepisany tekst."
)
KOMUNIKAT_ODRECZNE = "Dokument zawiera pismo odręczne – użytkownik musi samodzielnie ocenić dokument."


@dataclass
class Wynik:
    plik: Path
    odreczny: bool
    strony_odreczne: list[int]
    txt: Path | None = None

    @property
    def komunikat(self) -> str:
        if self.odreczny:
            strony = ", ".join(map(str, self.strony_odreczne))
            return f"{KOMUNIKAT_ODRECZNE} (strony: {strony})"
        return str(self.txt)


# ---------------------------------------------------------------- API
def model_dostepny() -> bool:
    """Czy jest model OCR: klucz do Groq albo lokalny serwer (OCR_URL inny niż Groq)."""
    try:
        return bool(_klucz())
    except RuntimeError:
        return False


def _klucz() -> str:
    if klucz := os.environ.get("OCR_API_KEY") or os.environ.get("GROQ_API_KEY"):
        return klucz
    if URL != GROQ_URL:
        return "lokalny"  # lokalny serwer (np. Ollama) nie wymaga klucza
    env = Path(".env")
    if env.exists():
        for linia in env.read_text(encoding="utf-8").splitlines():
            if linia.startswith("GROQ_API_KEY="):
                return linia.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError("Brak GROQ_API_KEY (zmienna środowiskowa lub .env)")


def _zapytaj(obraz, prompt: str, max_tokens: int = 4096) -> str:
    """Wysyła obraz strony (PIL.Image) z poleceniem do modelu i zwraca odpowiedź."""
    buf = io.BytesIO()
    obraz.convert("L").save(buf, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    tresc = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]}],
    }
    zad = urllib.request.Request(URL, data=json.dumps(tresc).encode(), headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_klucz()}",
        "User-Agent": "inteligentny-asystent-urzednika/0.1",  # Cloudflare blokuje domyślny UA urllib
    })
    for proba in range(PROBY):
        try:
            with urllib.request.urlopen(zad, timeout=180) as odp:
                tekst = json.load(odp)["choices"][0]["message"]["content"] or ""
            return re.sub(r"<think>.*?</think>", "", tekst, flags=re.S).strip()
        except urllib.error.HTTPError as e:
            # 429 = limit zapytań Groq; czekamy tyle, ile podaje serwer
            if e.code not in (429, 500, 502, 503) or proba == PROBY - 1:
                raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from e
            time.sleep(float(e.headers.get("retry-after") or 2 ** (proba + 2)))
    raise AssertionError("nieosiągalne")


def czy_odreczne(obraz) -> bool:
    odp = _zapytaj(obraz, PROMPT_KLASYFIKACJA, max_tokens=20).upper()
    if "ODR" in odp:
        return True
    if "DRUK" in odp:
        return False
    raise RuntimeError(f"Nieoczekiwana odpowiedź klasyfikatora: {odp!r}")


# ---------------------------------------------------------------- strony
def _strony(plik: Path):
    """Zwraca listę (obraz strony, tekst z warstwy tekstowej lub '')."""
    if plik.suffix.lower() == ".pdf":
        import pdfplumber

        with pdfplumber.open(plik) as doc:
            return [(p.to_image(resolution=DPI).original, p.extract_text() or "") for p in doc.pages]
    from PIL import Image

    return [(Image.open(plik), "")]


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def tekst_docx(plik: Path) -> str:
    """Tekst z DOCX: akapity (także w tabelach) w kolejności dokumentu, puste pominięte."""
    with zipfile.ZipFile(plik) as z:
        korzen = ElementTree.fromstring(z.read("word/document.xml"))
    akapity = []
    for p in korzen.iter(f"{_W}p"):
        czesci = []
        for el in p.iter():
            if el.tag == f"{_W}t":
                czesci.append(el.text or "")
            elif el.tag == f"{_W}tab":
                czesci.append("\t")
            elif el.tag in (f"{_W}br", f"{_W}cr"):
                czesci.append("\n")
        if tekst := "".join(czesci).replace("\xa0", " ").strip():
            akapity.append(tekst)
    return "\n".join(akapity)


def _zapisz(cel: Path, tekst: str) -> Path:
    cel.parent.mkdir(parents=True, exist_ok=True)
    cel.write_text(tekst.strip() + "\n", encoding="utf-8")
    return cel


@dataclass
class Konwersja:
    """Wynik konwersji w pamięci (bez zapisu pliku) – używany przez API backendu."""

    tekst: str
    odreczny: bool
    strony_odreczne: list[int]
    stron: int
    # numery stron bez warstwy tekstowej, przepisane przez model (skany druku)
    strony_z_modelu: list[int]

    @property
    def komunikat(self) -> str | None:
        if not self.odreczny:
            return None
        return f"{KOMUNIKAT_ODRECZNE} (strony: {', '.join(map(str, self.strony_odreczne))})"


def sprawdz_format(plik: Path) -> None:
    if plik.suffix.lower() not in ROZSZERZENIA:
        raise ValueError(f"Nieobsługiwany format: {plik.suffix or 'brak rozszerzenia'} (obsługiwane: {', '.join(sorted(ROZSZERZENIA))})")


class BrakModeluOCR(RuntimeError):
    """Skan wymaga modelu OCR, a żaden nie jest skonfigurowany."""


def konwertuj(plik: Path) -> Konwersja:
    """Konwertuje jeden plik na tekst. Dokument z pismem odręcznym zwraca pusty tekst i `odreczny=True`."""
    sprawdz_format(plik)
    if plik.suffix.lower() == ".docx":
        return Konwersja(tekst_docx(plik).strip(), False, [], 1, [])

    strony = _strony(plik)
    if not model_dostepny():
        # tryb bez modelu: odczyt warstwy tekstowej PDF; skan (strona bez tekstu) wymaga modelu OCR
        bez_tekstu = [i for i, (_, w) in enumerate(strony, 1) if len(re.sub(r"\s", "", w)) < MIN_ZNAKOW_WARSTWY]
        if bez_tekstu:
            raise BrakModeluOCR(
                "Plik jest skanem (strony bez tekstu: " + ", ".join(map(str, bez_tekstu)) + ") – odczyt wymaga modelu "
                "OCR (lokalnego: OCR_URL, albo GROQ_API_KEY). Wgraj plik Word lub PDF z tekstem."
            )
        return Konwersja("\n\n".join(w.strip() for _, w in strony).strip(), False, [], len(strony), [])

    odreczne = [i for i, (obraz, _) in enumerate(strony, 1) if czy_odreczne(obraz)]
    if odreczne:
        return Konwersja("", True, odreczne, len(strony), [])

    teksty, z_modelu = [], []
    for i, (obraz, warstwa) in enumerate(strony, 1):
        if len(re.sub(r"\s", "", warstwa)) >= MIN_ZNAKOW_WARSTWY:
            teksty.append(warstwa.strip())
        else:
            teksty.append(_zapytaj(obraz, PROMPT_ODCZYT))
            z_modelu.append(i)
    return Konwersja("\n\n".join(teksty).strip(), False, [], len(strony), z_modelu)


def przetworz(plik: Path, cel: Path | None = None) -> Wynik:
    """Przetwarza jeden plik. TXT trafia do `cel` (domyślnie KATALOG_TXT/<nazwa>.txt)."""
    k = konwertuj(plik)
    if k.odreczny:
        return Wynik(plik, True, k.strony_odreczne)
    return Wynik(plik, False, [], _zapisz(cel or KATALOG_TXT / f"{plik.stem}.txt", k.tekst))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plik", type=Path, help="jeden plik wejściowy")
    ap.add_argument("-o", "--wyjscie", type=Path, help="plik .txt (domyślnie konwersja/pliki_txt/<nazwa>.txt)")
    args = ap.parse_args(argv)

    if not args.plik.is_file():
        powod = "to katalog, podaj jeden plik" if args.plik.is_dir() else "nie ma takiego pliku"
        print(f"BŁĄD: {powod}: {args.plik}", file=sys.stderr)
        return 1
    try:
        wynik = przetworz(args.plik, args.wyjscie)
    except Exception as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    if wynik.odreczny:
        print(wynik.komunikat)
        return KOD_ODRECZNY
    print(wynik.txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
