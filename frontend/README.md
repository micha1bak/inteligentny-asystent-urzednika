# Frontend – Asystent urzędnika (React + Vite + TypeScript)

Prototyp interfejsu z dwiema funkcjami: **dodawanie wniosku z pliku PDF** i **kalendarz wniosków z oznaczeniem pilnych**.
Działa bez backendu – dane trzyma w `localStorage` przeglądarki, PDF czyta lokalnie (pdf.js).

```powershell
npm install
npm run dev      # http://localhost:5173
npm test         # terminy + odczyt przykładowych wniosków PDF z repo
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

**Ograniczenie:** skany PDF bez warstwy tekstowej (2 z 3 przykładowych wniosków PDF w repo) nie są odczytywane –
aplikacja to sygnalizuje, a dane wpisuje się ręcznie. Do rozwiązania przez OCR (np. tesseract.js lokalnie albo w backendzie).
