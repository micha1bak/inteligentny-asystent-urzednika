# Frontend – Asystent urzędnika (React + Vite + TypeScript)

Samodzielny prototyp interfejsu: działa bez backendu, dane trzyma w `localStorage` przeglądarki.

```powershell
npm install
npm run dev      # http://localhost:5173
npm test         # testy terminów, anonimizacji i parsowania przykładowych wniosków
npm run build
```

## Widoki
- **Kalendarz wniosków** (`/`) – tabela od najstarszych, wybór roku, filtry, widok miesiąca; podświetlenie: po terminie / termin dziś / termin jutro.
- **Nowy wniosek** (`/nowy`) – wgranie PDF/DOCX/TXT (odczyt w przeglądarce), automatyczne wypełnienie pól do zatwierdzenia, podpowiedź wydziałów i podobnych spraw.
- **Sprawa** (`/sprawa/:id`) – statusy (brak działań → zapytania → kwerenda z liczbą dni → przygotowana → wysłana), odpowiedzi wydziałów, projekt pisma, anonimizacja (szare = propozycja, czarne = zaakceptowane, ręczne zaznaczanie), eksport DOCX/TXT, ocena prawna wg `ocena_prawna_wniosku_dip_kompletny.json`.
- **Baza wiedzy** (`/baza`) – archiwum (z `werdykty_wniosek_odpowiedz_dip.json` + dodane ręcznie), akty prawne, katalog anonimizacji.

## Co jest tymczasowe (do zastąpienia przez backend)
| Moduł | Teraz | Docelowo |
|---|---|---|
| `src/magazyn.tsx` | `localStorage` | API backendu (te same operacje) |
| `src/lib/podobienstwo.ts` | TF-IDF na rdzeniach słów | embeddingi z lokalnego modelu |
| `src/lib/anonimizacja.ts` | reguły (PESEL z sumą kontrolną, dowód, telefon, e-mail, IBAN, adresy, imię+nazwisko) | reguły + lokalny model NER |
| `src/lib/pismo.ts` | szablon z odpowiedzi wydziałów | redakcja przez lokalny LLM |
| `src/lib/parsowanie.ts` | pdf.js / mammoth w przeglądarce | + OCR skanów po stronie serwera |

Terminy (`src/lib/terminy.ts`): 14 dni od dnia po wpływie (art. 13 ust. 1 UDIP), kwerenda do 2 miesięcy (art. 13 ust. 2), przesunięcie z soboty i dni ustawowo wolnych na najbliższy dzień roboczy (art. 57 § 4 KPA).
