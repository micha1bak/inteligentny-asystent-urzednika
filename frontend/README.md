# Frontend – Asystent urzędnika (React + Vite + TypeScript)

Prototyp interfejsu z dwiema funkcjami: **dodawanie wniosku z pliku PDF** i **kalendarz wniosków z oznaczeniem pilnych**.
Działa bez backendu – dane trzyma w `localStorage` przeglądarki, PDF czyta lokalnie (pdf.js).

```powershell
npm install
npm run dev      # http://localhost:5173
npm test         # terminy, odczyt PDF i OCR skanów z repo (~1 min)
npm run build
```

## Kalendarz wniosków (`/`)
- tabela od najstarszych: Lp., nr wniosku, data wpływu, temat, inicjały, termin, pozostało dni, status, data odpowiedzi,
- podświetlenie: **po terminie** (czerwony), **termin dziś** (pomarańczowy), **termin jutro** (żółty),
- liczniki pilnych, filtr „tylko pilne”, wybór roku, widok miesiąca z wnioskami w dniu terminu,
- 10 wniosków testowych z datami liczonymi od dziś („Przywróć dane testowe”).

Termin (`src/lib/terminy.ts`): 14 dni od dnia po wpływie (art. 13 ust. 1 UDIP), kwerenda do 2 miesięcy (art. 13 ust. 2),
przesunięcie z soboty i dni ustawowo wolnych na najbliższy dzień roboczy (art. 57 § 4 KPA).

## Dodaj wniosek (`/nowy`)
- wgranie PDF (przeciągnij lub kliknij), odczyt tekstu w przeglądarce,
- automatyczne wypełnienie tematu, wnioskodawcy i e-maila; kolejny numer BKS.IV.1431.N.rok; podgląd terminu,
- urzędnik sprawdza i zatwierdza – wniosek trafia do kalendarza ze statusem „Brak działań”.

## OCR skanów (`src/lib/ocr.ts`)
Gdy PDF nie ma warstwy tekstowej (skan), strony (maks. 5) są renderowane w ~216 DPI i rozpoznawane przez
**tesseract.js** z polskim modelem (`pol`, wariant `best_int`, silnik LSTM). Wszystko działa w przeglądarce i **offline**:
worker, rdzeń WebAssembly i model są kopiowane z `node_modules` do `public/ocr/` skryptem `scripts/kopiuj-ocr.mjs`
(uruchamia się sam przy `npm install`, `npm run dev` i `npm run build`; katalog jest w `.gitignore`, ok. 23 MB).

- czas: ok. 5–7 s na stronę (pierwsze uruchomienie dodatkowo ładuje model),
- pewność OCR jest pokazywana urzędnikowi; poniżej 60% (pismo odręczne, zły skan) pola **nie** są wypełniane automatycznie,
- przykłady z repo: wydruk BKS.IV.1431.543 – pewność 88%, temat odczytany poprawnie; odręczny BKS.IV.1431.16 – 25%, odrzucony
  (Tesseract nie rozpoznaje pisma odręcznego).

Test `src/lib/ocr.test.ts` uruchamia OCR na skanach z repo (ok. 45 s).
