# Inteligentny asystent urzędnika

Wsparcie obsługi wniosków o dostęp do informacji publicznej w Urzędzie Miasta Bydgoszczy (Hacknation).

- `frontend/` – React: kalendarz wniosków z oznaczeniem pilnych, dodawanie wniosku z PDF/DOCX/skanu, propozycja odpowiedzi AI. Szczegóły w [frontend/README.md](frontend/README.md).
- `src/inteligentny_asystent_urzednika/` – backend FastAPI: odczyt plików wniosków (`konwersja/`) i propozycja odpowiedzi przez Groq.
- `ocena_prawna_wniosku_dip_kompletny.json` – model oceny prawnej (UDIP, KPA, Zarządzenie 535/2024, katalog anonimizacji).
- `werdykty_wniosek_odpowiedz_dip.json` – archiwum spraw z odpowiedziami i werdyktami.
- `wzory_pism.json` – wzory pism Biura Komunikacji Społecznej (nagłówek, podpis, zasady stylu i 8 wzorów: udostępnienie
  w treści / w załączniku / punkt po punkcie, UMB nie jest dysponentem, brak danych, wezwanie do doprecyzowania,
  przedłużenie terminu, szkielet decyzji odmownej) opracowane na podstawie pism z `Przykładowe wnioski i odpowiedzi/`.
  Można je poprawiać bez zmian w kodzie.

## Uruchomienie

1. Klucz Groq: skopiuj `.envexample` do `.env` i wpisz `GROQ_API_KEY`.
2. Backend (http://127.0.0.1:8000):
   ```powershell
   uv run inteligentny-asystent-urzednika
   ```
3. Frontend (http://localhost:5173, `/api` przekierowane na backend):
   ```powershell
   npm --prefix frontend install
   npm --prefix frontend run dev
   ```

## API

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/api/zdrowie` | stan backendu: czy jest klucz, model, liczba spraw i werdyktów |
| POST | `/api/konwersja` | plik wniosku (multipart, pole `plik`: PDF, DOCX, PNG/JPG/TIFF, maks. 20 MB) → `{tekst, zrodlo, odreczny, strony_odreczne, stron, strony_z_modelu, komunikat}` |
| POST | `/api/propozycja-odpowiedzi` | `{tresc, temat?, numer?, data_wplywu?, wnioskodawca?}` → propozycja |
| GET | `/api/archiwum` | sprawy z archiwum (z historią zmian), słownik werdyktów i lista jednostek UMB |
| POST | `/api/archiwum` | `{sprawa, autor}` → dodanie sprawy (409 – sygnatura już jest, 422 – nieznany werdykt lub dane osobowe) |
| PUT | `/api/archiwum/{sygnatura}` | `{sprawa, autor}` → edycja, także `nieaktualna: true/false` |
| DELETE | `/api/archiwum/{sygnatura}` | usunięcie sprawy |
| POST | `/api/archiwum/propozycja` | `{wniosek, odpowiedz, sygnatura?}` (treść dokumentów) → zanonimizowana propozycja wpisu od modelu |
| GET | `/api/baza-wiedzy` | wersje bazy wiedzy (ze statusem) i akty prawne z folderu dokumentów |
| POST | `/api/baza-wiedzy/analizy` | multipart: `plik` (PDF/DOCX/TXT), `zastepuje`, `nazwa`, `skrot`, `publikator`, `obowiazuje_od` → analiza w tle |
| GET | `/api/baza-wiedzy/analizy/{id}` | postęp i wynik analizy: zmienione przepisy i proponowane zmiany bazy |
| POST | `/api/baza-wiedzy/analizy/{id}/zastosuj` | `{decyzje: [{id, zatwierdz, po?}], autor}` → nowa wersja bazy |
| POST | `/api/baza-wiedzy/wersje/{id}/wycofaj` | `{autor}` → wycofanie wersji (powrót do poprzedniej) |

`/api/konwersja` używa modułu `konwersja/ocr_llm.py` (ten sam co w CLI `python -m inteligentny_asystent_urzednika.konwersja.ocr_llm`):
DOCX jest czytany lokalnie bez modelu; każda strona PDF/obrazu jest najpierw klasyfikowana przez model wizyjny Groq
(pismo odręczne → tekst nie jest odczytywany, urzędnik ocenia dokument sam), a strony bez warstwy tekstowej (skany druku)
są przepisywane przez model. Plik jest zapisywany tylko w katalogu tymczasowym na czas konwersji.

Do modelu trafia instrukcja systemowa, wiedza z `ocena_prawna_wniosku_dip_kompletny.json` i `werdykty_wniosek_odpowiedz_dip.json`
oraz treść wniosku (oznaczona jako dane, nie polecenia). Tryb wiedzy (`KONTEKST_PRAWNY`):

- **`wybrany`** (domyślny, ok. 4 tys. tokenów – mieści się w darmowym planie Groq: 8000 tokenów/min): akty prawne,
  słownik werdyktów, wszystkie 12 etapów oceny (nazwa, podstawy prawne, rozstrzygnięcie), 3 pozycje matrycy i 3 sprawy
  z archiwum najbardziej podobne do wniosku, lista jednostek UMB, katalog anonimizacji oraz 2 wzory pism dobrane
  według werdyktów podobnych spraw. Gdy zapytanie nie mieści się w `GROQ_LIMIT_TPM`,
  backend stopniowo zmniejsza kontekst, a w ostateczności skraca bardzo długi wniosek (z ostrzeżeniem),
- **`pelny`**: cały model oceny i całe archiwum (ok. 23 tys. tokenów – tylko przy płatnym planie).

Darmowy plan mieści ok. jedno zapytanie na minutę – przy kolejnym w tej samej minucie pojawi się prośba o odczekanie. Odpowiedź (tryb JSON) zawiera: werdykt ze słownika, uzasadnienie,
podstawy prawne, komórkę merytoryczną, podobne sprawy, dane do anonimizacji, listę rzeczy do sprawdzenia i projekt pisma.

Backend weryfikuje wynik: werdykt musi być w słowniku, a podobne sprawy – w archiwum (inne są odrzucane z ostrzeżeniem);
nagłówek i podpis BKS w projekcie pisma są wstawiane dosłownie z `wzory_pism.json`.
Brakujące fakty model oznacza w piśmie jako `[[do uzupełnienia: …]]`.

Konfiguracja (`.env`, opis w `.envexample`): `GROQ_MODEL` (domyślnie `openai/gpt-oss-120b`), `KONTEKST_PRAWNY=wybrany|pelny`,
`GROQ_LIMIT_TPM` (domyślnie 8000), `GROQ_MAX_TOKENS` (domyślnie 2000), `GROQ_TIMEOUT_S`.

### Archiwum odpowiedzi

Urzędnik zarządza archiwum spraw w aplikacji (zakładka **Archiwum odpowiedzi**): wyszukuje, edytuje, oznacza sprawy jako
nieaktualne (model ich wtedy nie używa) i usuwa. Nową sprawę dodaje ręcznie albo z pary dokumentów: wniosek + wysłana
odpowiedź. Model proponuje wtedy wpis, a urzędnik go poprawia i zatwierdza. Przy wniosku ze statusem „Odpowiedź wysłana” w kalendarzu
jest link „Dodaj do archiwum”, który przenosi treść wniosku, sygnaturę i datę odpowiedzi.

- zmiany są zapisywane w `werdykty_wniosek_odpowiedz_dip.json` (zapis atomowy) razem z historią: kto, kiedy,
  które pola (przed → po); plik nadal można edytować ręcznie, a backend wczytuje go ponownie po każdej zmianie,
- przed zapisem backend sprawdza werdykt (musi być w słowniku) i blokuje dane osobowe o jednoznacznym formacie
  (e-mail, telefon, PESEL, numer konta – `anonimizacja.py`); w propozycji modelu są one maskowane automatycznie,
  a imiona i nazwiska model zastępuje opisem roli – urzędnik sprawdza wpis przed zatwierdzeniem,
- pola techniczne (`historia`, `nieaktualna`) nie trafiają do modelu.

### Aktualizacja bazy wiedzy po zmianie przepisów

Zakładka **Baza wiedzy**: urzędnik wgrywa nową wersję aktu (np. tekst jednolity UDIP, KPA, nowe zarządzenie) albo nowy akt.
Aplikacja:

1. porównuje nową wersję z obecną (folder `Dokumenty i podstawy prawne/`) artykuł po artykule – bez modelu,
2. wybiera elementy bazy (`ocena_prawna_wniosku_dip_kompletny.json`: etapy algorytmu, matryca, katalog anonimizacji,
   instytucje KPA, procedura UMB), które powołują się na zmienione przepisy,
3. wysyła do modelu tylko te elementy i zmienione przepisy (paczkami w limicie `GROQ_LIMIT_TPM`; przy limicie zapytań
   na minutę czeka i ponawia) – model proponuje nowe brzmienie elementów,
4. pokazuje „było → będzie” dla każdej zmiany; urzędnik zatwierdza, odrzuca albo poprawia (JSON) każdą z nich.

Analiza działa w tle, a interfejs pokazuje jej postęp. Wyniki są trzymane w pamięci backendu, więc znikają po restarcie.
Akt niezwiązany z dostępem do informacji publicznej jest odrzucany, a baza zostaje bez zmian. Nowy akt bez poprzedniej
wersji jest dodawany do źródeł i do wyszukiwarki przepisów, ale algorytmu oceny nie zmienia automatycznie.

Każdy zapis tworzy wersję w `wersje_bazy_wiedzy/` (pełna kopia bazy, wgrany akt, manifest: kto, kiedy, co, od kiedy obowiązuje).
Wersja z przyszłą datą wejścia w życie czeka. Wniosek jest oceniany według wersji obowiązującej w dniu wpływu,
a główny plik bazy i tekst aktu w folderze dokumentów są podmieniane w dniu wejścia w życie. Wycofanie wersji przywraca
poprzednią bazę i poprzedni tekst aktu. Przed zapisem backend sprawdza strukturę bazy i to, czy zapytanie w trybie
`wybrany` mieści się w limicie tokenów. Gdy istnieje katalog `wersje_bazy_wiedzy/`, ręczne zmiany głównego pliku bazy
zostaną nadpisane przy synchronizacji, więc zmieniaj bazę przez aplikację.

**Uwaga:** treść wniosku jest wysyłana do zewnętrznego dostawcy (Groq) – na hackathonie tylko dane testowe.
Docelowo ten sam interfejs `KlientLLM` (`groq_klient.py`) można podpiąć pod model lokalny (np. Ollama/vLLM z API zgodnym z OpenAI – wystarczy zmienić `GROQ_URL` i `GROQ_MODEL`).

## Testy

```powershell
uv run pytest
```
```powershell
npm --prefix frontend test
```
