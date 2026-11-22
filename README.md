# Inteligentny asystent urzędnika

Wsparcie obsługi wniosków o dostęp do informacji publicznej w Urzędzie Miasta Bydgoszczy (Hacknation 2026).

- `frontend/` – React: kalendarz wniosków z oznaczeniem pilnych, dodawanie wniosku z PDF/DOCX, propozycja odpowiedzi AI.
- `src/inteligentny_asystent_urzednika/` – backend FastAPI: odczyt plików wniosków (`konwersja/`) i propozycja odpowiedzi przez Groq.
- `ocena_prawna_wniosku_dip_kompletny.json` – model oceny prawnej.
- `werdykty_wniosek_odpowiedz_dip.json` – archiwum spraw z odpowiedziami i werdyktami.
- `wzory_pism.json` – wzory pism Biura Komunikacji Społecznej, opracowane na podstawie pism z `Przykładowe wnioski i odpowiedzi/`.

## Zgodność z wymaganiami zadania UMB

| Wymaganie / krok instrukcji | Jak jest zrealizowane |
|---|---|
| Wgrywanie plików PDF / Word | „Dodaj wniosek” (wiele plików naraz); Word i PDF z warstwą tekstową odczytywane lokalnie, bez modelu; skany, zdjęcia i wykrywanie pisma odręcznego – model wizyjny `qwen/qwen3.8-27b` na Groq (docelowo model lokalny) |
| Kalendarz wniosków | tabela + widok miesiąca, sortowanie wg daty wpływu rosnąco, Lp., nr, temat, inicjały, data wpływu, termin (z dniami wolnymi), data odpowiedzi, podświetlenie: po terminie, termin dziś, termin w następny dzień roboczy |
| Statusy na każdym kroku | Nierozpatrzone → wysłane do wydziału → kwerenda + dni → odpowiedź przygotowana → Rozpatrzone |
| Podobne wnioski z ostatniego roku / przeszukiwanie archiwum | karta „Podobne sprawy i wnioski” po wgraniu i w szczegółach sprawy (TF-IDF, lokalnie), z wydziałami, do których przekazano podobne sprawy |
| Wskazywanie ścieżki – wydziały z BIP | karta „Zapytanie do wydziału”:  propozycje jednostek z uzasadnieniem, wybór urzędnika, treść prośby wg Zarządzenia 535/2024 |
| Odpowiedzi z wydziałów → projekt pisma | karta „Odpowiedzi z wydziałów” (wgranie PDF/Word), model opiera na nich pola pisma; pismo składa kod ze wzorów BKS |
| Anonimizacja (szare → czarne po akceptacji) | w podglądzie pisma (tryb anonimizacji) i na stronie „Anonimizacja dokumentu”; wykrywanie lokalne (imiona i nazwiska, adresy, PESEL, NIP, dowód, telefon, e-mail, konto); ukryte dane nie trafiają do pliku |
| Odpowiedź w pliku DOC / TXT | „Pobierz DOCX / TXT” w podglądzie pisma (układ BKS), druk / PDF |
| Brak automatycznej wysyłki, brak integracji | program niczego nie wysyła – urzędnik kopiuje prośbę / odpowiedź i oznacza status |
| „Uczenie się” na danych urzędu | Baza wiedzy (wgrane ustawy), Archiwum odpowiedzi |
| Docelowo zamknięty model bez internetu | `LLM_URL` / `OCR_URL` – lokalny serwer zgodny z API OpenAI (np. Ollama); bez modelu nie działają tylko: ocena prawna i projekt pisma, odczyt skanów, propozycja wpisu do archiwum i analiza zmian w bazie wiedzy |

### Tryb lokalny (docelowo w urzędzie, bez internetu)

Na Hacknation używany jest Groq (otwarte modele w chmurze, tylko dane testowe): `openai/gpt-oss-120b` do oceny
prawnej i propozycji odpowiedzi (`LLM_MODEL` / `GROQ_MODEL`) oraz `qwen/qwen3.8-27b` do odczytu skanów (`OCR_MODEL`).

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

## API

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/api/zdrowie` | stan backendu: czy jest klucz, model, tryb kontekstu, limit TPM, liczba spraw, werdyktów, dokumentów prawnych i wniosków w bazie |
| POST | `/api/logowanie` | logowanie urzędnika (`urzednicy.db`) → sesja w ciasteczku |
| POST | `/api/urzednicy` | rejestracja urzędnika → sesja |
| GET | `/api/sesja` | czy urzędnik jest zalogowany (id, inicjały) |
| POST | `/api/wyloguj` | zakończenie sesji |
| GET | `/api/wnioski`, `/api/wnioski/{id}` | wnioski z kalendarza (SQLite `wnioski.db`) |
| POST | `/api/wnioski` | dodanie wniosku |
| POST | `/api/wnioski/wsadowo` | dodanie wielu wniosków naraz |
| POST | `/api/wnioski/zastap` | zastąpienie wszystkich wniosków (dane testowe) |
| PUT | `/api/wnioski/{id}` | edycja wniosku (m.in. zmiana statusu) |
| DELETE | `/api/wnioski/{id}` | usunięcie wniosku |
| POST | `/api/wnioski/{id}/zatwierdz-odpowiedz` | zatwierdzenie odpowiedzi; przy werdykcie ze słownika sprawa (zanonimizowana) trafia do archiwum |
| GET | `/api/przepisy/dokumenty` | akty prawne zaindeksowane z folderu dokumentów |
| GET | `/api/przepisy/szukaj` | `?q=…&akt=…&limit=…` → wyszukiwanie artykułów, ustępów i paragrafów (bez AI) |
| POST | `/api/konwersja` | plik wniosku (multipart, pole `plik`: PDF, DOCX, PNG/JPG/TIFF, maks. 20 MB) → `{tekst, zrodlo, odreczny, strony_odreczne, stron, strony_z_modelu, komunikat}` |
| POST | `/api/propozycja-odpowiedzi` | `{tresc, temat?, numer?, data_wplywu?, wnioskodawca?}` → propozycja |
| GET | `/api/archiwum` | sprawy z archiwum (z historią zmian), słownik werdyktów i lista jednostek UMB |
| POST | `/api/archiwum` | `{sprawa, autor}` → dodanie sprawy (409 – sygnatura już jest, 422 – nieznany werdykt lub dane osobowe) |
| PUT | `/api/archiwum/{sygnatura}` | `{sprawa, autor}` → edycja, także `nieaktualna: true/false` |
| DELETE | `/api/archiwum/{sygnatura}` | usunięcie sprawy |
| POST | `/api/archiwum/przywroc` | przywraca początkowy stan archiwum z `archiwum_poczatkowe.json` → `{liczba_spraw}` |
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

Do modelu trafia instrukcja systemowa, wiedza z `ocena_prawna_wniosku_dip_kompletny.json` i `werdykty_wniosek_odpowiedz_dip.json`
oraz treść wniosku.
Darmowy plan mieści ok. jedno zapytanie na minutę – przy kolejnym w tej samej minucie pojawi się prośba o odczekanie. Odpowiedź (tryb JSON) zawiera: werdykt ze słownika, uzasadnienie,
podstawy prawne, komórkę merytoryczną, podobne sprawy, dane do anonimizacji, listę rzeczy do sprawdzenia i projekt pisma.

### Archiwum odpowiedzi

Zakładka **Archiwum odpowiedzi**: urzędnik wyszukuje, edytuje, usuwa sprawy i oznacza je jako nieaktualne (model ich
wtedy nie używa). Nową sprawę dodaje ręcznie albo z pary wniosek + odpowiedź – model proponuje wpis, urzędnik go
zatwierdza. Przy wniosku „Rozpatrzone” w kalendarzu jest link „Dodaj do archiwum”.

- `wydzialy` – jednostki UMB, do których przekazano wniosek (przykłady dla propozycji wydziału); `podmiot_poza_umb` –
  dysponent spoza Urzędu,
- 9 prawdziwych i 100 fikcyjnych spraw (`skrypty/archiwum_przykladowe.py`); „Przywróć dane testowe” przywraca stan
  z `archiwum_poczatkowe.json`,
- podobieństwo (TF-IDF, 0–100%): ta sama sprawa zwykle 50–80%, od 45% – „bardzo podobna”,
- zapis atomowy do `werdykty_wniosek_odpowiedz_dip.json` z historią zmian (kto, kiedy, przed → po),
- backend sprawdza werdykt i blokuje dane osobowe (e-mail, telefon, PESEL, konto); pola `historia` i `nieaktualna`
  nie trafiają do modelu.

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
Docelowo ten sam interfejs `KlientLLM` (`groq_klient.py`) można podpiąć pod model lokalny (np. Ollama/vLLM z API zgodnym z OpenAI – wystarczy ustawić `LLM_URL` i `LLM_MODEL`, a dla skanów `OCR_URL` i `OCR_MODEL`; dawne nazwy `GROQ_URL` / `GROQ_MODEL` też działają).

## Testy

```powershell
uv run pytest
```
```powershell
npm --prefix frontend test
```
