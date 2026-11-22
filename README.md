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

## Zgodność z wymaganiami zadania UMB

| Wymaganie / krok instrukcji | Jak jest zrealizowane |
|---|---|
| Wgrywanie plików PDF / Word | „Dodaj wniosek” (wiele plików naraz), odczyt Word i PDF lokalnie; skany i pismo odręczne – model wizyjny |
| Kalendarz wniosków | tabela + widok miesiąca, sortowanie wg daty wpływu rosnąco, Lp., nr, temat, inicjały, data wpływu, termin (z dniami wolnymi), data odpowiedzi, wybór roku; podświetlenie: po terminie, termin dziś, termin w następny dzień roboczy |
| Statusy na każdym kroku | brak działań → zapytania do wydziałów (po oznaczeniu wysłania prośby) → kwerenda + dni → odpowiedź przygotowana (po zatwierdzeniu pisma) → odpowiedź wysłana + data |
| Podobne wnioski z ostatniego roku / przeszukiwanie archiwum | karta „Podobne sprawy i wnioski” po wgraniu i w szczegółach sprawy (TF-IDF, lokalnie) |
| Wskazywanie ścieżki – wydziały z BIP | karta „Zapytanie do wydziału”: 3 propozycje jednostek z uzasadnieniem, wybór urzędnika, treść prośby wg Zarządzenia 535/2024 |
| Odpowiedzi z wydziałów → projekt pisma | karta „Odpowiedzi z wydziałów” (wgranie PDF/Word), model opiera na nich pola pisma; pismo składa kod ze wzorów BKS |
| Anonimizacja (szare → czarne po akceptacji) | w podglądzie pisma (tryb anonimizacji) i na stronie „Anonimizacja dokumentu”; wykrywanie lokalne (imiona i nazwiska, adresy, PESEL, NIP, dowód, telefon, e-mail, konto); ukryte dane nie trafiają do pliku |
| Odpowiedź w pliku DOC / TXT | „Pobierz DOCX / TXT” w podglądzie pisma (układ BKS), druk / PDF |
| Brak automatycznej wysyłki, brak integracji | program niczego nie wysyła – urzędnik kopiuje prośbę / odpowiedź i oznacza status |
| „Uczenie się” na danych urzędu | Baza wiedzy (wgranie ustaw i aktualizacji – wersje), Archiwum odpowiedzi (dodawanie spraw z dokumentów) |
| Docelowo zamknięty model bez internetu | `LLM_URL` / `OCR_URL` – lokalny serwer zgodny z API OpenAI (np. Ollama); bez modelu działają wszystkie funkcje poza oceną prawną i odczytem skanów |

### Tryb lokalny (docelowo w urzędzie, bez internetu)

Na Hacknation używany jest Groq (otwarte modele w chmurze, tylko dane testowe). Docelowo:

```env
LLM_URL=http://<serwer-umb>:11434/v1/chat/completions      # Ollama lub vLLM w sieci urzędu
LLM_MODEL=SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M        # polski model (alternatywy: qwen3:14b, gpt-oss:20b)
OCR_URL=http://<serwer-umb>:11434/v1/chat/completions
OCR_MODEL=qwen2.5vl:7b                                       # model wizyjny: skany i pismo odręczne
```

Lokalny serwer nie wymaga klucza. Dane (SQLite `wnioski.db`, archiwum i baza wiedzy w JSON) są przechowywane lokalnie.
Bez żadnego modelu działają: kalendarz, podobne sprawy, propozycja wydziałów (archiwum + zakresy jednostek),
anonimizacja, eksport DOCX/TXT, odczyt Word i PDF z warstwą tekstową.

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

### Wdrożenie w urzędzie (jeden proces)

```powershell
npm --prefix frontend install
npm --prefix frontend run build          # jednorazowo – frontend trafia do frontend/dist
$env:BACKEND_RELOAD="0"; uv run inteligentny-asystent-urzednika
```

Aplikacja (frontend i API) jest wtedy dostępna pod http://127.0.0.1:8000 – bez serwera deweloperskiego Vite.
Dane zostają na komputerze/serwerze urzędu: `wnioski.db` (SQLite), archiwum i baza wiedzy (JSON), dokumenty prawne.

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
| POST | `/api/podobne` | `{tresc, pomin_id?, data_odniesienia?}` → podobne sprawy z archiwum i wnioski z ostatniego roku (bez AI) |
| GET | `/api/jednostki` | wydziały i biura UMB (nazwy z BIP, zakres spraw) |
| POST | `/api/wydzial/propozycja` | `{tresc, numer?, data_wplywu?}` → do 3 właściwych jednostek z uzasadnieniem (AI; bez klucza – archiwum + zakresy) |
| POST | `/api/wydzial/wiadomosc` | `{jednostka, numer?, data_wplywu?, termin?}` → treść prośby do wydziału (do skopiowania – program nic nie wysyła) |
| POST | `/api/wnioski/{id}/odpowiedzi-wydzialow` | `{wydzial, nazwa_pliku, tresc}` → odpowiedź wydziału zapisana przy wniosku (podstawa projektu pisma) |
| DELETE | `/api/wnioski/{id}/odpowiedzi-wydzialow/{id_odp}` | usunięcie odpowiedzi wydziału |
| POST | `/api/anonimizacja/sugestie` | `{tekst, dodatkowe?}` → fragmenty z danymi osobowymi do ukrycia (lokalnie, bez AI) |
| POST | `/api/pismo/docx`, `/api/pismo/txt` | `{pismo, nazwa}` → plik odpowiedzi; fragmenty ukryte przez urzędnika zastąpione znakami █ |
| POST | `/api/dokument/docx`, `/api/dokument/txt` | `{tekst, ukryte, nazwa}` → dowolny dokument po anonimizacji |

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
