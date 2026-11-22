# Przypadki testowe – obsługa wniosku od wpływu do odpowiedzi

Każdy folder to jedna sprawa: wniosek (dane NIEzanonimizowane, fikcyjne) → oczekiwany wydział → oczekiwana prośba do wydziału → odpowiedź wydziału (DOCX) → oczekiwane pismo do wnioskodawcy.

Pliki `3_…` i `5_…` są składane funkcjami aplikacji (`wydzialy.zloz_wiadomosc`, `wzor.pismo.zloz_pismo`), więc szablon (nagłówek, przepisy, podpis, stopka) musi zgadzać się 1:1. Wartości pól wzoru są wzorcem – model może je sformułować inaczej, ale fakty (liczby, daty, numery, jednostka) muszą być te same.

Wszystkie osoby, adresy, telefony, e-maile, firmy i liczby są zmyślone. Regeneracja: `uv run python "Przypadki testowe/_generator.py"`.

| ID | Sprawa | Wydział | Wzór pisma | Werdykt |
|---|---|---|---|---|
| TC01 | Liczba deklaracji odpadowych i zadeklarowanych mieszkańców | WGO | udostepnienie_w_tresci | MOZNA_UDOSTEPNIC |
| TC02 | Zestawienie przedszkoli miejskich – dzieci, oddziały, wolne miejsca | WE | udostepnienie_w_zalaczniku | MOZNA_UDOSTEPNIC |
| TC03 | Budowa ronda Fordońska / Wyszogrodzka – wykonawca, koszty, terminy, kary | WIM | udostepnienie_punkt_po_punkcie | MOZNA_UDOSTEPNIC |
| TC04 | Przyczyny zamknięcia działalności gospodarczych w 2025 r. | WSO | brak_danych | NIE_MOZNA_PISMO_INFORMACYJNE |
| TC05 | Samochody służbowe Urzędu Miasta – liczba, wykaz, koszt paliwa | WOA | udostepnienie_punkt_po_punkcie | MOZNA_UDOSTEPNIC |
| TC06 | Zezwolenie na usunięcie dębów przy ul. Leśnej 14 | WOŚ | udostepnienie_w_tresci | MOZNA_Z_ANONIMIZACJA |
| TC07 | Punktualność kursów linii autobusowej nr 69 | — (Zarząd Dróg Miejskich i Komunikacji Publicznej w Bydgoszczy) | nieposiadanie_wskazanie_dysponenta | NIE_MOZNA_PISMO_INFORMACYJNE |
| TC08 | Wniosek o „wszystkie dokumenty w mojej sprawie” – niejasny | — (odesłanie) | pismo z akapitów (zloz_pismo_z_tekstu) | MOZNA_WARUNKOWO |
| TC09 | Spór sąsiedzki – prośba o poradę i dane sąsiada | — (odesłanie) | pismo z akapitów (zloz_pismo_z_tekstu) | NIE_MOZNA_PISMO_INFORMACYJNE |
