# Inteligentny asystent urzędnika

Narzędzie dla urzędników Urzędu Miasta Bydgoszczy obsługujących wnioski o dostęp do informacji publicznej (UDIP):
kalendarz wniosków z terminami, wyszukiwanie podobnych spraw w archiwum, podpowiadanie wydziałów,
generowanie projektu odpowiedzi i anonimizacja danych osobowych. Projekt na Hacknation.

Zadania zespołu: [issues](https://github.com/micha1bak/inteligentny-asystent-urzednika/issues) i [etapy](https://github.com/micha1bak/inteligentny-asystent-urzednika/milestones).

## Uruchomienie

Wymagany [uv](https://docs.astral.sh/uv/) (sam pobierze Pythona 3.15).

```powershell
uv sync
uv run inteligentny-asystent-urzednika dane-testowe   # 10 wniosków testowych, archiwum, odpowiedzi wydziałów
uv run inteligentny-asystent-urzednika start --reload
```

- interfejs: http://127.0.0.1:8000
- dokumentacja API (Swagger): http://127.0.0.1:8000/docs

Testy: `uv run pytest`

## Stos

| Warstwa | Technologia |
|---|---|
| Backend / API | FastAPI |
| Baza danych | SQLite przez SQLModel (plik `dane/asystent.db`, poza repo) |
| Interfejs | statyczne HTML/JS serwowane przez FastAPI (`src/.../static/`) |
| Model językowy | Ollama + Bielik lokalnie (docelowo) albo gpt-oss-120b w chmurze Groq (tylko na hackathonie) |

## Struktura

```
src/inteligentny_asystent_urzednika/
  app.py            aplikacja FastAPI
  config.py         ustawienia (zmienne ASYSTENT_*, plik .env – patrz .env.example)
  models.py         model danych: Wniosek, Dokument, statusy                     [1.2]
  terminy.py        terminy UDIP: 14 dni + kwerenda, przesunięcie z dni wolnych
  llm.py            jedyny punkt kontaktu z modelami (generuj / osadz)            [1.3]
  wydzialy.py       lista wydziałów i biur UMB (zasoby/wydzialy.json)
  dane_testowe.py   wczytywanie dane_testowe/ do bazy                             [1.4]
  api/wnioski.py    kalendarz wniosków: lista, dodawanie, zmiana statusu
  api/zaslepki.py   zaślepki endpointów z etapów 2–4 (przykładowe dane dla UI)
  parsowanie/       PDF i DOCX                                    osoba 1  [2.1]
  wyszukiwanie/     baza wiedzy, podobne sprawy                   osoba 1  [3.1–3.2]
  pisma/            metadane, wydziały, projekt pisma             osoba 1  [3.3, 3.4, 4.1]
  anonimizacja/     dane osobowe, ukrywanie, eksport              osoba 2  [2.2, 3.5, 4.2]
  static/           interfejs                                     osoba 3  [2.3+]
dane_testowe/       fikcyjne wnioski, archiwum, odpowiedzi wydziałów, wniosek z danymi osobowymi
tests/
```

## Zasady

- **Model danych** (`models.py`) to wspólny kontrakt – zmiany uzgadniamy w zespole.
- **Modele językowe** wołamy wyłącznie przez `llm.generuj()` i `llm.osadz()`. Dzięki temu przejście na
  model lokalny to zmiana jednej zmiennej (`ASYSTENT_LLM_BACKEND=lokalny`), bez zmian w kodzie.
- **Dane rzeczywiste nigdy nie trafiają do chmury.** Backend `groq` wolno używać tylko z danymi testowymi.
  Klucz Groq trzymamy w `.env` jako `AI_API_KEY` (plik jest poza repo).
- Aplikacja **niczego nie wysyła** – ani do wydziałów, ani na zewnątrz. Ostateczną decyzję podejmuje urzędnik.
- Zaślepki w `api/zaslepki.py` zastępuje właściciel issue podanego w opisie endpointu.

## Terminy

Termin odpowiedzi = data wpływu + 14 dni (art. 13 ust. 1 UDIP) + dni kwerendy (przedłużenie, art. 13 ust. 2),
przesunięty na najbliższy dzień roboczy, jeśli wypada w sobotę, niedzielę lub święto (art. 57 § 4 KPA).
Wniosek jest **pilny**, gdy termin minął, jest dziś albo w najbliższy dzień roboczy, a odpowiedź nie została wysłana.
