# Inteligentny asystent urzędnika

Wsparcie obsługi wniosków o dostęp do informacji publicznej w Urzędzie Miasta Bydgoszczy (Hacknation).

- `frontend/` – React: kalendarz wniosków z oznaczeniem pilnych, dodawanie wniosku z PDF (z OCR skanów), propozycja odpowiedzi AI. Szczegóły w [frontend/README.md](frontend/README.md).
- `src/inteligentny_asystent_urzednika/` – backend FastAPI: propozycja odpowiedzi przez Groq.
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
| POST | `/api/propozycja-odpowiedzi` | `{tresc, temat?, numer?, data_wplywu?, wnioskodawca?}` → propozycja |

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

**Uwaga:** treść wniosku jest wysyłana do zewnętrznego dostawcy (Groq) – na hackathonie tylko dane testowe.
Docelowo ten sam interfejs `KlientLLM` (`groq_klient.py`) można podpiąć pod model lokalny (np. Ollama/vLLM z API zgodnym z OpenAI – wystarczy zmienić `GROQ_URL` i `GROQ_MODEL`).

## Testy

```powershell
uv run pytest
```
```powershell
npm --prefix frontend test
```
